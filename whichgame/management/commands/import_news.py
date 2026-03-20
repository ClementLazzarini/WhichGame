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
    help = 'Fetches recent game releases from IGDB (Runs automatically on the 1st and 15th of each month).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Bypass the date restriction and run the script immediately.'
        )

    def handle(self, *args, **options):
        # 1. Schedule Check
        today = datetime.now().day
        if today not in [1, 15] and not options['force']:
            self.stdout.write(self.style.WARNING(f"Skipping execution: Today is the {today}th. Use --force to run manually."))
            return

        self.stdout.write(self.style.SUCCESS("Starting new releases import..."))

        # 2. Authentication
        access_token = self._get_twitch_access_token()
        if not access_token:
            self.stdout.write(self.style.ERROR("Failed to obtain Twitch access token. Aborting."))
            return

        headers = {
            'Client-ID': config('IGDB_CLIENT_ID'),
            'Authorization': f'Bearer {access_token}'
        }

        # 3. Fetch Recent Games (Last 60 Days)
        games_data = self._fetch_recent_games(headers)
        if not games_data:
            self.stdout.write(self.style.WARNING("No recent games found matching the criteria."))
            return

        # 4. Fetch Playtimes
        playtimes_map = self._fetch_playtimes(headers, games_data)

        # 5. Process and Save to Database
        self._process_and_save_games(games_data, playtimes_map)

    def _get_twitch_access_token(self):
        """Retrieves or generates a valid Twitch OAuth token."""
        token_file = os.path.join(settings.BASE_DIR, 'twitch_token.json')
        client_id = config('IGDB_CLIENT_ID')
        client_secret = config('IGDB_CLIENT_SECRET')

        # Check existing cached token
        if os.path.exists(token_file):
            try:
                with open(token_file, 'r') as f:
                    data = json.load(f)
                    if data.get('expires_at', 0) > time.time() + 60:
                        return data.get('access_token')
            except json.JSONDecodeError:
                pass # Invalid JSON, proceed to fetch a new one

        # Fetch new token from Twitch API
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
                # Cache the new token
                with open(token_file, 'w') as f:
                    json.dump({
                        'access_token': access_token,
                        'expires_at': time.time() + auth_data['expires_in']
                    }, f)
                return access_token
        except requests.RequestException as e:
            self.stdout.write(self.style.ERROR(f"Twitch Auth API Error: {e}"))
        
        return None

    def _fetch_recent_games(self, headers):
        """Fetches high-quality games released within the last 60 days."""
        timestamp_now = int(time.time())
        timestamp_past = int((datetime.now() - timedelta(days=60)).timestamp())
        
        fields = (
            "fields name, slug, rating, total_rating_count, hypes, summary, "
            "cover.url, platforms.name, genres.name, themes.name, "
            "first_release_date, release_dates.y, game_type, videos.video_id, screenshots.url"
        )
        
        query = (
            f"{fields}; "
            f"where game_type = (0, 8, 9) & cover != null & "
            f"first_release_date > {timestamp_past} & first_release_date <= {timestamp_now}; "
            f"sort first_release_date desc; limit 100;"
        )

        try:
            response = requests.post("https://api.igdb.com/v4/games", headers=headers, data=query)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            self.stdout.write(self.style.ERROR(f"IGDB Games API Error: {e}"))
            return []

    def _fetch_playtimes(self, headers, games_data):
        """Fetches playtime data for the retrieved games and caps it to prevent UI bugs."""
        game_ids = [str(g['id']) for g in games_data]
        ids_string = ",".join(game_ids)
        playtimes_map = {}
        
        query = f"fields game_id, hastily, normally, completely; where game_id = ({ids_string}); limit 500;"
        
        try:
            response = requests.post("https://api.igdb.com/v4/game_time_to_beats", headers=headers, data=query)
            response.raise_for_status()
            
            for time_data in response.json():
                seconds = time_data.get('hastily') or time_data.get('normally') or time_data.get('completely') or 0
                if seconds > 0:
                    hours = round(seconds / 3600)
                    # Cap at 500 hours to avoid extreme outlier data
                    playtimes_map[time_data['game_id']] = max(1, min(hours, 500)) 
        except requests.RequestException:
            pass # Silently fail playtimes, not critical for the main import
            
        return playtimes_map

    def _process_and_save_games(self, games_data, playtimes_map):
        """Formats the data, applies strict filters, and saves games to the database."""
        added_count = 0
        ignored_count = 0
        
        for data in games_data:
            # 1. Quality Filter (Requires minimal reviews or hype)
            rating_count = data.get('total_rating_count', 0)
            hypes = data.get('hypes', 0)
            
            if rating_count < 5 and hypes < 5:
                ignored_count += 1
                continue

            # 2. Platform Filter (Exclude Web Browser games)
            platform_names = [p['name'] for p in data.get('platforms', [])]
            if any("web browser" in p.lower() for p in platform_names):
                ignored_count += 1
                continue

            # 3. Data Formatting
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

            # 4. Database Save
            try:
                Game.objects.update_or_create(
                    igdb_id=data['id'],
                    defaults={
                        'title': data['name'],
                        'slug': data['slug'],
                        'rating': data.get('rating'),
                        'total_rating_count': rating_count,
                        'summary': data.get('summary', ''),
                        'cover_url': cover_url,
                        'platforms': platform_names,
                        'genres': [g['name'] for g in data.get('genres', [])],
                        'themes': [t['name'] for t in data.get('themes', [])],
                        'playtime_main': playtimes_map.get(data['id'], 0),
                        'game_type': data.get('game_type', 0),
                        'release_year': min([d['y'] for d in data.get('release_dates', []) if 'y' in d], default=None),
                        'first_release_date': release_date,
                        'video_id': video_id,
                        'screenshots': screenshots
                    }
                )
                added_count += 1
                self.stdout.write(self.style.SUCCESS(f"   [ADDED] {data['name']} (Hype: {hypes} | Reviews: {rating_count})"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"   [ERROR] Failed to save {data.get('name', 'Unknown')}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"Finished. Added: {added_count} | Ignored (Low Quality/Web): {ignored_count}"))