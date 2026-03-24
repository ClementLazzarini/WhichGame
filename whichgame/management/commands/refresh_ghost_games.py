import os
import json
import time
import requests
from datetime import datetime, timedelta
from decouple import config

from django.core.management.base import BaseCommand
from django.conf import settings
from whichgame.models import Game

class Command(BaseCommand):
    help = 'Daily CRON: Updates missing ratings for existing games and imports highly hyped new releases.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("👻 Starting Ghost Games & Daily Bangers refresh..."))

        # 1. Authentication
        access_token = self._get_twitch_access_token()
        if not access_token:
            self.stdout.write(self.style.ERROR("Auth failed. Aborting."))
            return

        headers = {
            'Client-ID': config('IGDB_CLIENT_ID'),
            'Authorization': f'Bearer {access_token}'
        }

        # 2. Update existing "Ghost" games (Games currently hidden because reviews < 5)
        self.stdout.write("\n🔍 1. Updating existing Ghost games (Waiting for reviews)...")
        self._update_ghost_games(headers)

        # 3. Fetch and inject today's "Bangers" (Highly anticipated new releases)
        self.stdout.write("\n🔥 2. Fetching recent Bangers (High hype, newly released)...")
        self._fetch_daily_bangers(headers)

        self.stdout.write(self.style.SUCCESS("\n🎉 Daily refresh complete! Your catalog is perfectly up to date."))

    def _get_twitch_access_token(self):
        """Retrieves or generates a valid Twitch OAuth token."""
        token_file = os.path.join(settings.BASE_DIR, 'twitch_token.json')
        client_id = config('IGDB_CLIENT_ID')
        client_secret = config('IGDB_CLIENT_SECRET')

        if os.path.exists(token_file):
            try:
                with open(token_file, 'r') as f:
                    data = json.load(f)
                    if data.get('expires_at', 0) > time.time() + 60:
                        return data.get('access_token')
            except json.JSONDecodeError:
                pass 

        try:
            response = requests.post("https://id.twitch.tv/oauth2/token", params={
                'client_id': client_id,
                'client_secret': client_secret,
                'grant_type': 'client_credentials'
            })
            response.raise_for_status()
            auth_data = response.json()
            
            access_token = auth_data.get('access_token')
            if access_token:
                with open(token_file, 'w') as f:
                    json.dump({
                        'access_token': access_token,
                        'expires_at': time.time() + auth_data['expires_in']
                    }, f)
                return access_token
        except requests.RequestException:
            pass
        return None

    def _update_ghost_games(self, headers):
        """Finds games in DB with missing ratings and queries IGDB to update them."""
        # Get the 50 most recently added games that lack enough reviews
        ghosts = Game.objects.filter(total_rating_count__lt=5).order_by('-id')[:50]
        
        if not ghosts:
            self.stdout.write("   ✅ No ghost games found. Everything is rated!")
            return

        ghost_ids = [str(g.igdb_id) for g in ghosts if g.igdb_id]
        if not ghost_ids:
            return

        ids_string = ",".join(ghost_ids)
        query = f"fields name, rating, total_rating_count; where id = ({ids_string}); limit 50;"

        try:
            response = requests.post("https://api.igdb.com/v4/games", headers=headers, data=query)
            response.raise_for_status()
            updated_data = response.json()

            update_count = 0
            for data in updated_data:
                real_count = data.get('total_rating_count', 0)
                if real_count >= 5:
                    Game.objects.filter(igdb_id=data['id']).update(
                        rating=data.get('rating'),
                        total_rating_count=real_count
                    )
                    update_count += 1
                    self.stdout.write(self.style.SUCCESS(f"   📈 {data['name']} finally got its reviews ({real_count} ratings)!"))
            
            if update_count == 0:
                self.stdout.write("   ⏳ Ghost games checked, but still waiting for IGDB reviews.")

        except requests.RequestException as e:
            self.stdout.write(self.style.ERROR(f"   ❌ IGDB API Error: {e}"))

    def _fetch_daily_bangers(self, headers):
        """Fetches major games released in the last 7 days and forces them into the DB."""
        timestamp_now = int(time.time())
        timestamp_past = int((datetime.now() - timedelta(days=7)).timestamp())
        
        fields = (
            "fields name, slug, rating, total_rating_count, hypes, follows, summary, "
            "cover.url, platforms.name, genres.name, themes.name, "
            "first_release_date, release_dates.y, game_type, videos.video_id, screenshots.url"
        )
        
        # Filter: Only games released recently WITH high hype or follows (> 15)
        query = (
            f"{fields}; "
            f"where game_type = (0, 8, 9) & cover != null & "
            f"first_release_date > {timestamp_past} & first_release_date <= {timestamp_now} & "
            f"(hypes > 15 | follows > 15); "
            f"sort first_release_date desc; limit 20;"
        )

        try:
            response = requests.post("https://api.igdb.com/v4/games", headers=headers, data=query)
            response.raise_for_status()
            games_data = response.json()
        except requests.RequestException as e:
            self.stdout.write(self.style.ERROR(f"   ❌ IGDB API Error: {e}"))
            return

        if not games_data:
            self.stdout.write("   🤷 No major bangers released in the last 7 days.")
            return

        count = 0
        for data in games_data:
            # 💡 THE MAGIC TRICK: Artificial bypass for brand new hyped games
            real_count = data.get('total_rating_count', 0)
            real_rating = data.get('rating')
            
            if real_count < 5:
                # Inject temporary fake rating to bypass UI filters
                save_count = 5 
                save_rating = real_rating if real_rating else 80.0
                trick_applied = True
            else:
                save_count = real_count
                save_rating = real_rating
                trick_applied = False

            # Format data
            platform_names = [p['name'] for p in data.get('platforms', []) if "web browser" not in p['name'].lower()]
            if not platform_names:
                continue # Skip if it was only a web browser game

            release_date = None
            if 'first_release_date' in data:
                release_date = datetime.fromtimestamp(data['first_release_date']).date()

            cover_url = ""
            if 'cover' in data and 'url' in data['cover']:
                cover_url = data['cover']['url'].replace('t_thumb', 't_cover_big')
                if cover_url.startswith('//'): 
                    cover_url = f"https:{cover_url}"

            video_id = next((v['video_id'] for v in data.get('videos', []) if 'video_id' in v), None)
            screenshots = [
                s['url'].replace('t_thumb', 't_1080p').replace('//', 'https://') 
                for s in data.get('screenshots', [])[:3] if 'url' in s
            ]

            try:
                obj, created = Game.objects.update_or_create(
                    igdb_id=data['id'],
                    defaults={
                        'title': data['name'],
                        'slug': data['slug'],
                        'rating': save_rating,
                        'total_rating_count': save_count,
                        'summary': data.get('summary', ''),
                        'cover_url': cover_url,
                        'platforms': platform_names,
                        'genres': [g['name'] for g in data.get('genres', [])],
                        'themes': [t['name'] for t in data.get('themes', [])],
                        'game_type': data.get('game_type', 0),
                        'release_year': min([d['y'] for d in data.get('release_dates', []) if 'y' in d], default=None),
                        'first_release_date': release_date,
                        'video_id': video_id,
                        'screenshots': screenshots
                    }
                )
                
                if created:
                    count += 1
                    status = "💉 Artificially Boosted!" if trick_applied else "✅ Real Ratings!"
                    self.stdout.write(self.style.SUCCESS(f"   🎮 BANGER ADDED: {data['name']} -> {status}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"   ❌ DB Error on {data['name']}: {e}"))

        if count > 0:
            self.stdout.write(self.style.WARNING("   ⚠️ Note: Bangers added with 0h playtime. The HLTB cron will update them in the next cycle."))