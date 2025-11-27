import requests
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from decouple import config
from whichgame.models import Game

class Command(BaseCommand):
    help = 'LAYER 1 : Import IGDB avec mémoire (State File)'

    def handle(self, *args, **options):
        # 1. Gestion de l'Offset via fichier texte
        state_file = os.path.join(settings.BASE_DIR, 'igdb_import.state')
        offset = 0
        limit = 50
        
        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                try:
                    offset = int(f.read().strip())
                except ValueError:
                    offset = 0

        self.stdout.write(f"🚀 Démarrage Import IGDB (Offset : {offset})")

        # 2. Auth IGDB
        client_id = config('IGDB_CLIENT_ID')
        client_secret = config('IGDB_CLIENT_SECRET')
        try:
            auth = requests.post("https://id.twitch.tv/oauth2/token", params={
                'client_id': client_id, 'client_secret': client_secret, 'grant_type': 'client_credentials'
            }).json()
            access_token = auth['access_token']
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Erreur Auth: {e}"))
            return

        headers = {'Client-ID': client_id, 'Authorization': f'Bearer {access_token}'}

        # 3. Récupération Jeux
        body_games = f"fields name, slug, rating, cover.url, platforms.name, genres.name, release_dates.y; sort rating_count desc; limit {limit}; offset {offset};"
        games_data = requests.post("https://api.igdb.com/v4/games", headers=headers, data=body_games).json()

        if not games_data or 'status' in games_data:
            self.stdout.write(self.style.WARNING("⚠️ Fin de liste ou erreur. Reset de l'offset à 0."))
            # On remet à 0 pour la prochaine fois
            with open(state_file, 'w') as f: 
                f.write("0")
            return

        # 4. Récupération Temps (IGDB)
        game_ids = [g['id'] for g in games_data]
        ids_string = ",".join(map(str, game_ids))
        
        body_times = f"fields game_id, hastily, normally, completely; where game_id = ({ids_string}); limit 500;"
        times_data = requests.post("https://api.igdb.com/v4/game_time_to_beats", headers=headers, data=body_times).json()
        
        times_map = {}
        if isinstance(times_data, list):
            for t in times_data:
                # Logique cascade
                seconds = t.get('hastily') or t.get('normally') or t.get('completely') or 0
                if seconds > 0:
                    times_map[t['game_id']] = round(seconds / 3600) or 1

        # 5. Sauvegarde BDD
        count = 0
        for data in games_data:
            if 'name' not in data: 
                continue
            
            cover_url = ""
            if 'cover' in data and 'url' in data['cover']:
                cover_url = data['cover']['url'].replace('t_thumb', 't_cover_big')
                if cover_url.startswith('//'): 
                    cover_url = f"https:{cover_url}"

            platform_names = [p['name'] for p in data.get('platforms', [])]
            
            Game.objects.update_or_create(
                igdb_id=data['id'],
                defaults={
                    'title': data['name'],
                    'slug': data['slug'],
                    'rating': data.get('rating'),
                    'cover_url': cover_url,
                    'platforms': platform_names,
                    'genres': [g['name'] for g in data.get('genres', [])],
                    'playtime_main': times_map.get(data['id'], 0),
                    'release_year': min([d['y'] for d in data.get('release_dates', []) if 'y' in d], default=None)
                }
            )
            count += 1

        self.stdout.write(self.style.SUCCESS(f"✅ {count} jeux traités."))

        # 6. Mise à jour de l'offset pour le prochain tour
        new_offset = offset + limit
        with open(state_file, 'w') as f:
            f.write(str(new_offset))
        self.stdout.write(f"💾 Prochain démarrage prévu à l'offset : {new_offset}")