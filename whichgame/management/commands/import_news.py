import requests
import os
import json
import time
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.conf import settings
from decouple import config
from whichgame.models import Game

class Command(BaseCommand):
    help = 'LAYER 2 : Import NOUVEAUTÉS (Seulement les jeux Hype ou Notés)'

    def handle(self, *args, **options):
        self.stdout.write("🔥 Démarrage Import NEWS Qualitatif...")

        # 1. AUTH IGDB
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
            except Exception: 
                return

        headers = {'Client-ID': client_id, 'Authorization': f'Bearer {access_token}'}

        # 2. REQUÊTE : Jeux sortis les 60 derniers jours
        # On ne limite pas à 20, on en prend 100 et on trie nous-même
        timestamp_now = int(time.time())
        timestamp_past = int((datetime.now() - timedelta(days=60)).timestamp())
        
        # On ajoute 'hypes' et les nouveaux champs du model
        fields = "fields name, slug, rating, total_rating_count, hypes, summary, cover.url, platforms.name, genres.name, themes.name, first_release_date, release_dates.y, game_type, videos.video_id, screenshots.url"
        
        # Filtre : Sortis récemment ET (Avoir une note OU de la Hype)
        # Note: IGDB ne permet pas facilement le OR dans le where sur des champs différents, 
        # donc on filtre large ici et on affine en Python.
        body = f"{fields}; where game_type = (0, 8, 9) & cover != null & first_release_date > {timestamp_past} & first_release_date <= {timestamp_now}; sort first_release_date desc; limit 100;"

        try:
            response = requests.post("https://api.igdb.com/v4/games", headers=headers, data=body)
            games_data = response.json()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erreur API: {e}"))
            return

        if not games_data:
            self.stdout.write(self.style.WARNING("⚠️ Aucun jeu récent trouvé."))
            return

        # 3. HLTB
        game_ids = [g['id'] for g in games_data]
        ids_string = ",".join(map(str, game_ids))
        times_map = {}
        try:
            body_t = f"fields game_id, hastily, normally, completely; where game_id = ({ids_string}); limit 500;"
            resp_t = requests.post("https://api.igdb.com/v4/game_time_to_beats", headers=headers, data=body_t)
            for t in resp_t.json():
                s = t.get('hastily') or t.get('normally') or t.get('completely') or 0
                if s > 0: 
                    times_map[t['game_id']] = max(1, round(s / 3600))
        except:  # noqa: E722
            pass

        # 4. SAUVEGARDE FILTRÉE
        count = 0
        ignored = 0
        
        for data in games_data:
            # --- LE GARDEN KEEPER (FILTRE INTELLIGENT) ---
            rating_count = data.get('total_rating_count', 0)
            hypes = data.get('hypes', 0)
            
            # CRITÈRE : Soit > 5 avis (Jeu validé), Soit > 5 Hypes (Jeu attendu)
            if rating_count < 5 and hypes < 5:
                ignored += 1
                # self.stdout.write(f"   🗑️ Ignoré (Trop obscur): {data['name']}")
                continue

            # --- Mapping ---
            r_date = None
            if 'first_release_date' in data:
                r_date = datetime.fromtimestamp(data['first_release_date']).date()

            cover_url = ""
            if 'cover' in data and 'url' in data['cover']:
                cover_url = data['cover']['url'].replace('t_thumb', 't_cover_big')
                if cover_url.startswith('//'): 
                    cover_url = f"https:{cover_url}"

            vid_id = None
            if 'videos' in data:
                vid_id = next((v['video_id'] for v in data['videos'] if 'video_id' in v), None)

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
                        'themes': [t['name'] for t in data.get('themes', [])],
                        'playtime_main': times_map.get(data['id'], 0),
                        'game_type': data.get('game_type', 0),
                        'release_year': min([d['y'] for d in data.get('release_dates', []) if 'y' in d], default=None),
                        'first_release_date': r_date,
                        'video_id': vid_id,
                        'screenshots': screens
                    }
                )
                count += 1
                self.stdout.write(f"   ✅ NEWS: {data['name']} (Hype: {hypes} | Avis: {rating_count})")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Erreur: {e}"))

        self.stdout.write(self.style.SUCCESS(f"🏁 Terminé. {count} nouveautés ajoutées. {ignored} poubelles évitées."))