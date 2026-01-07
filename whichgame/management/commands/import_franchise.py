import requests
import os
import json
import time
from django.core.management.base import BaseCommand
from django.conf import settings
from decouple import config
from whichgame.models import Game

class Command(BaseCommand):
    help = 'Importe tous les jeux d\'une franchise spécifique (ex: "Mario", "Zelda")'

    def add_arguments(self, parser):
        parser.add_argument('query', type=str, help='Nom de la franchise ou du jeu à chercher')

    def handle(self, *args, **options):
        query = options['query']
        self.stdout.write(f"🔍 Recherche de la franchise : '{query}'...")

        # --- 1. AUTHENTIFICATION (Copier-Coller de ta logique existante) ---
        token_file = os.path.join(settings.BASE_DIR, 'twitch_token.json')
        access_token = None
        client_id = config('IGDB_CLIENT_ID')
        client_secret = config('IGDB_CLIENT_SECRET')

        # Lecture cache
        if os.path.exists(token_file):
            try:
                with open(token_file, 'r') as f:
                    data = json.load(f)
                    if data.get('expires_at') > time.time() + 60:
                        access_token = data.get('access_token')
            except Exception: 
                pass

        # Renouvellement si besoin
        if not access_token:
            try:
                auth = requests.post("https://id.twitch.tv/oauth2/token", params={
                    'client_id': client_id, 'client_secret': client_secret, 'grant_type': 'client_credentials'
                }).json()
                access_token = auth.get('access_token')
                if not access_token: 
                    return
                with open(token_file, 'w') as f:
                    json.dump({'access_token': access_token, 'expires_at': time.time() + auth['expires_in']}, f)
            except Exception: 
                return

        headers = {'Client-ID': client_id, 'Authorization': f'Bearer {access_token}'}

        # --- 2. RECHERCHE IGDB ---
        # Note l'utilisation de 'search' au lieu de 'where' pour le nom
        # On garde les filtres game_type pour éviter les DLCs obscurs
        body_games = f'''
            fields name, slug, rating, total_rating_count, cover.url, platforms.name, genres.name, release_dates.y, game_type, videos.video_id, screenshots.url;
            search "{query}";
            where game_type = (0, 8, 9) & cover != null & version_parent = null;
            limit 50;
        '''
        
        try:
            response = requests.post("https://api.igdb.com/v4/games", headers=headers, data=body_games)
            games_data = response.json()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erreur API: {e}"))
            return

        if not games_data:
            self.stdout.write(self.style.WARNING(f"Aucun jeu trouvé pour '{query}'."))
            return

        self.stdout.write(f"🎯 {len(games_data)} jeux trouvés. Récupération des temps de jeu...")

        # --- 3. HLTB (Temps de jeu) ---
        game_ids = [g['id'] for g in games_data]
        ids_string = ",".join(map(str, game_ids))
        
        body_times = f"fields game_id, hastily, normally, completely; where game_id = ({ids_string}); limit 100;"
        times_map = {}
        
        try:
            response_time = requests.post("https://api.igdb.com/v4/game_time_to_beats", headers=headers, data=body_times)
            times_data = response_time.json()
            if isinstance(times_data, list):
                for t in times_data:
                    seconds = t.get('hastily') or t.get('normally') or t.get('completely') or 0
                    if seconds > 0:
                        hours = round(seconds / 3600)
                        times_map[t['game_id']] = max(1, hours)
        except Exception:
            pass # On continue même si HLTB échoue

        # --- 4. SAUVEGARDE ---
        count = 0
        for data in games_data:
            if 'name' not in data: 
                continue

            # --- Filtre Anti-Poubelle Intégré (Optionnel mais recommandé) ---
            # Si le jeu a moins de 5 votes ET n'est pas tout récent (> 2023), on zappe
            # Tu peux commenter ces 3 lignes si tu veux TOUT importer
            rating_count = data.get('total_rating_count', 0)
            release_year = min([d['y'] for d in data.get('release_dates', []) if 'y' in d], default=0)
            if rating_count < 5 and release_year < 2023:
                 self.stdout.write(self.style.WARNING(f"   Skip (Trop peu populaire): {data['name']}"))
                 continue

            # Traitement Images
            cover_url = ""
            if 'cover' in data and 'url' in data['cover']:
                cover_url = data['cover']['url'].replace('t_thumb', 't_cover_big')
                if cover_url.startswith('//'): 
                    cover_url = f"https:{cover_url}"

            # Traitement Vidéos
            vid_id = None
            if 'videos' in data and data['videos']:
                for v in data['videos']:
                    if 'video_id' in v:
                        vid_id = v['video_id']
                        break

            # Traitement Screenshots
            screens_list = []
            if 'screenshots' in data:
                for sc in data['screenshots'][:3]: 
                    if 'url' in sc:
                        url = sc['url'].replace('t_thumb', 't_1080p')
                        if url.startswith('//'): 
                            url = f"https:{url}"
                        screens_list.append(url)

            # Sauvegarde DB
            try:
                Game.objects.update_or_create(
                    igdb_id=data['id'],
                    defaults={
                        'title': data['name'],
                        'slug': data['slug'],
                        'rating': data.get('rating'),
                        'cover_url': cover_url,
                        'platforms': [p['name'] for p in data.get('platforms', [])],
                        'genres': [g['name'] for g in data.get('genres', [])],
                        'playtime_main': times_map.get(data['id'], 0),
                        'game_type': data.get('game_type', 0),
                        'release_year': release_year if release_year > 0 else None,
                        'video_id': vid_id,
                        'screenshots': screens_list
                    }
                )
                count += 1
                self.stdout.write(f"   ✅ Importé: {data['name']}")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Erreur save {data['name']}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"✨ Terminé ! {count} jeux importés pour la franchise '{query}'."))