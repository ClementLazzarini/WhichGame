import os
import json
import time
import requests
from decouple import config

from django.core.management.base import BaseCommand
from django.conf import settings
from whichgame.models import Game

class Command(BaseCommand):
    help = 'Imports all games from a specific franchise or search query (e.g., "Mario", "Zelda").'

    def add_arguments(self, parser):
        parser.add_argument('query', type=str, help='Name of the franchise or game to search')

    def handle(self, *args, **options):
        query = options['query']
        self.stdout.write(f"🔍 Searching for franchise: '{query}'...")

        # 1. Authentication
        access_token = self._get_twitch_access_token()
        if not access_token:
            self.stdout.write(self.style.ERROR("❌ Failed to obtain Twitch access token. Aborting."))
            return

        headers = {
            'Client-ID': config('IGDB_CLIENT_ID'),
            'Authorization': f'Bearer {access_token}'
        }

        # 2. Search Games on IGDB
        games_data = self._search_franchise_games(headers, query)
        if not games_data:
            self.stdout.write(self.style.WARNING(f"⚠️ No games found for query '{query}'."))
            return

        # 3. Fetch Playtimes
        playtimes_map = self._fetch_playtimes(headers, games_data)

        # 4. Process and Save to Database
        self._process_and_save_games(games_data, playtimes_map, query)

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

    def _search_franchise_games(self, headers, query):
        """Searches IGDB for games matching the provided query."""
        fields = (
            "fields name, slug, rating, cover.url, platforms.name, genres.name, "
            "first_release_date, release_dates.y, game_type, videos.video_id, screenshots.url"
        )
        # Search syntax for IGDB
        igdb_query = f'search "{query}"; {fields}; where game_type = (0, 8, 9) & cover != null; limit 50;'

        try:
            response = requests.post("https://api.igdb.com/v4/games", headers=headers, data=igdb_query)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            self.stdout.write(self.style.ERROR(f"IGDB Search API Error: {e}"))
            return []

    def _fetch_playtimes(self, headers, games_data):
        """Fetches playtime data for the retrieved games."""
        game_ids = [str(g['id']) for g in games_data]
        if not game_ids:
            return {}

        ids_string = ",".join(game_ids)
        playtimes_map = {}
        
        query = f"fields game_id, hastily, normally, completely; where game_id = ({ids_string}); limit 500;"
        
        try:
            response = requests.post("https://api.igdb.com/v4/game_time_to_beats", headers=headers, data=query)
            response.raise_for_status()
            
            for time_data in response.json():
                seconds = time_data.get('hastily') or time_data.get('normally') or time_data.get('completely') or 0
                if seconds > 0:
                    playtimes_map[time_data['game_id']] = max(1, round(seconds / 3600))
        except requests.RequestException:
            pass
            
        return playtimes_map

    def _process_and_save_games(self, games_data, playtimes_map, query):
        """Formats the data, applies filters, and saves games to the database."""
        count = 0
        ignored = 0

        for data in games_data:
            # 1. Platform Filter (Exclude Web Browser games)
            platform_names = [p['name'] for p in data.get('platforms', [])]
            if any("web browser" in p.lower() for p in platform_names):
                ignored += 1
                continue

            # 2. Data Formatting
            release_year = min([d['y'] for d in data.get('release_dates', []) if 'y' in d], default=0)

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

            # 3. Database Save
            try:
                Game.objects.update_or_create(
                    igdb_id=data['id'],
                    defaults={
                        'title': data['name'],
                        'slug': data['slug'],
                        'rating': data.get('rating'),
                        'cover_url': cover_url,
                        'platforms': platform_names,
                        'genres': [g['name'] for g in data.get('genres', [])],
                        'playtime_main': playtimes_map.get(data['id'], 0),
                        'game_type': data.get('game_type', 0),
                        'release_year': release_year if release_year > 0 else None,
                        'video_id': video_id,
                        'screenshots': screenshots
                    }
                )
                count += 1
                self.stdout.write(self.style.SUCCESS(f"   ✅ Imported: {data['name']}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"   [ERROR] Failed to save {data.get('name', 'Unknown')}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"✨ Finished! {count} games imported for franchise '{query}' ({ignored} ignored)."))