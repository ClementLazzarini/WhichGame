import requests
import os
import json
import time
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from decouple import config
from whichgame.models import Game

class Command(BaseCommand):
    help = 'LAYER 1 : Import IGDB Ultimate (Avec Thèmes & Dates)'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=500)

    def handle(self, *args, **options):
        # 1. SETUP (Offset, Token...) - Identique à avant
        state_file = os.path.join(settings.BASE_DIR, 'igdb_import.state')
        offset = 0
        limit = options['limit']
        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                try: 
                    offset = int(f.read().strip())
                except ValueError: 
                    offset = 0
        
        self.stdout.write(f"🚀 Démarrage Import (Offset : {offset})")

        # --- AUTHENTIFICATION TWITCH (Copier-Coller standard) ---
        token_file = os.path.join(settings.BASE_DIR, 'twitch_token.json')
        access_token = None
        client_id = config('IGDB_CLIENT_ID')
        client_secret = config('IGDB_CLIENT_SECRET')

        if os.path.exists(token_file):
            try:
                with open(token_file, 'r') as f:
                    data = json.load(f)
                    if data.get('expires_at') > time.time() + 60: 
                        access_token = data.get('access_token')
            except:  # noqa: E722
                pass

        if not access_token:
            try:
                auth = requests.post("https://id.twitch.tv/oauth2/token", params={
                    'client_id': client_id, 'client_secret': client_secret, 'grant_type': 'client_credentials'
                }).json()
                access_token = auth['access_token']
                with open(token_file, 'w') as f:
                    json.dump({'access_token': access_token, 'expires_at': time.time() + auth['expires_in']}, f)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Erreur Auth: {e}"))
                return

        headers = {'Client-ID': client_id, 'Authorization': f'Bearer {access_token}'}

        # 3. REQUÊTE IGDB (AJOUT: themes.name, first_release_date)
        fields = "fields name, slug, rating, total_rating_count, summary, cover.url, platforms.name, genres.name, themes.name, first_release_date, release_dates.y, game_type, videos.video_id, screenshots.url"
        filters = "where game_type = (0, 8, 9) & cover != null"
        body = f"{fields}; {filters}; sort total_rating_count desc; limit {limit}; offset {offset};"
        
        try:
            response = requests.post("https://api.igdb.com/v4/games", headers=headers, data=body)
            games_data = response.json()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ API Error: {e}"))
            return

        if not games_data:
            self.stdout.write(self.style.WARNING("⚠️ Fin de liste."))
            return

        # 4. HLTB (Temps) - Identique à avant
        game_ids = [g['id'] for g in games_data]
        ids_string = ",".join(map(str, game_ids))
        times_map = {}
        try:
            body_times = f"fields game_id, hastily, normally, completely; where game_id = ({ids_string}); limit 500;"
            resp_time = requests.post("https://api.igdb.com/v4/game_time_to_beats", headers=headers, data=body_times)
            for t in resp_time.json():
                sec = t.get('hastily') or t.get('normally') or t.get('completely') or 0
                if sec > 0: 
                    times_map[t['game_id']] = max(1, round(sec / 3600))
        except: # noqa: E722
            pass  

        # 5. SAUVEGARDE
        count = 0
        ignored = 0
        
        for data in games_data:
            # FILTRE ANTI-POUBELLE
            rating_count = data.get('total_rating_count', 0)
            if rating_count < 5:
                ignored += 1
                continue 

            # --- FILTRE ANTI WEB BROWSER  ---
            current_platform_names = [p['name'] for p in data.get('platforms', [])]
            
            if "Web Browser" in current_platform_names:
                ignored += 1
                continue

            # Traitement Date précise
            r_date = None
            if 'first_release_date' in data:
                # Convertir timestamp UNIX en Date Python
                r_date = datetime.fromtimestamp(data['first_release_date']).date()

            # Traitement Images (Big Cover)
            cover_url = ""
            if 'cover' in data and 'url' in data['cover']:
                cover_url = data['cover']['url'].replace('t_thumb', 't_cover_big')
                if cover_url.startswith('//'): 
                    cover_url = f"https:{cover_url}"

            # Traitement Vidéo
            vid_id = None
            if 'videos' in data:
                vid_id = next((v['video_id'] for v in data['videos'] if 'video_id' in v), None)

            # Traitement Screenshots
            screens = []
            if 'screenshots' in data:
                screens = [s['url'].replace('t_thumb', 't_1080p').replace('//', 'https://') for s in data['screenshots'][:3] if 'url' in s]

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
                        'platforms': [p['name'] for p in data.get('platforms', [])],
                        'genres': [g['name'] for g in data.get('genres', [])],
                        'themes': [t['name'] for t in data.get('themes', [])], # NOUVEAU
                        'playtime_main': times_map.get(data['id'], 0),
                        'game_type': data.get('game_type', 0),
                        'release_year': min([d['y'] for d in data.get('release_dates', []) if 'y' in d], default=None),
                        'first_release_date': r_date, # NOUVEAU
                        'video_id': vid_id,
                        'screenshots': screens
                    }
                )
                count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Err {data['name']}: {e}"))

        # MAJ Offset
        with open(state_file, 'w') as f: 
            f.write(str(offset + limit))
        self.stdout.write(self.style.SUCCESS(f"✅ {count} importés. 🗑️ {ignored} ignorés."))