import requests
import os
import json
import time
from django.core.management.base import BaseCommand
from django.conf import settings
from decouple import config
from whichgame.models import Game

class Command(BaseCommand):
    help = 'LAYER 1 : Import IGDB avec filtres qualité (Main, Remake, Remaster) + Gestion Token Intelligent'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=200,
            help='Nombre de jeux à importer (défaut: 200)'
        )

    def handle(self, *args, **options):
        # 1. Gestion de l'Offset via fichier texte (SSOT)
        state_file = os.path.join(settings.BASE_DIR, 'igdb_import.state')
        offset = 0
        limit = options['limit']
        
        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                try:
                    offset = int(f.read().strip())
                except ValueError:
                    offset = 0
        
        self.stdout.write(f"🚀 Démarrage Import IGDB (Offset : {offset} | Limit : {limit})")

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
                        self.stdout.write("🔑 Token Twitch existant récupéré (Cache).")
            except Exception:
                self.stdout.write("⚠️ Erreur lecture cache token, renouvellement...")

        if not access_token:
            self.stdout.write("🔄 Demande d'un nouveau Token Twitch...")
            try:
                auth = requests.post("https://id.twitch.tv/oauth2/token", params={
                    'client_id': client_id, 
                    'client_secret': client_secret, 
                    'grant_type': 'client_credentials'
                }).json()
                
                if 'access_token' not in auth:
                    self.stdout.write(self.style.ERROR(f"❌ Erreur Auth Twitch : {auth}"))
                    return
                
                access_token = auth['access_token']
                expires_in = auth['expires_in']
                
                with open(token_file, 'w') as f:
                    json.dump({
                        'access_token': access_token,
                        'expires_at': time.time() + expires_in
                    }, f)
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Erreur connexion Auth: {e}"))
                return

        headers = {'Client-ID': client_id, 'Authorization': f'Bearer {access_token}'}

        # 3. Requête IGDB (Avec Vidéos et Screenshots)
        body_games = f"fields name, slug, rating, cover.url, platforms.name, genres.name, release_dates.y, game_type, videos.video_id, screenshots.url; where game_type = (0, 8, 9) & cover != null; sort total_rating_count desc; limit {limit}; offset {offset};"
        
        try:
            response = requests.post("https://api.igdb.com/v4/games", headers=headers, data=body_games)
            
            if response.status_code != 200:
                self.stdout.write(self.style.ERROR(f"🔴 ERREUR IGDB ({response.status_code}): {response.text}"))
                return 

            games_data = response.json()

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Erreur Technique API: {e}"))
            return

        if not games_data:
            self.stdout.write(self.style.WARNING("⚠️ Fin de liste (liste vide). Reset de l'offset à 0."))
            with open(state_file, 'w') as f: 
                f.write("0")
            return

        # 4. Récupération Temps (HLTB via IGDB)
        game_ids = [g['id'] for g in games_data]
        ids_string = ",".join(map(str, game_ids))
        
        body_times = f"fields game_id, hastily, normally, completely; where game_id = ({ids_string}); limit 500;"
        
        try:
            response_time = requests.post("https://api.igdb.com/v4/game_time_to_beats", headers=headers, data=body_times)
            times_data = response_time.json()
        except Exception:
            self.stdout.write(self.style.WARNING("⚠️ Impossible de récupérer les temps (API Time Out ou erreur), import continué sans temps."))
            times_data = [] 
        
        times_map = {}
        if isinstance(times_data, list):
            for t in times_data:
                # Priorité : Rush > Normal > Complet
                seconds = t.get('hastily') or t.get('normally') or t.get('completely') or 0
                if seconds > 0:
                    hours = round(seconds / 3600)
                    if hours == 0: 
                        hours = 1 
                    times_map[t['game_id']] = hours

        # 5. Sauvegarde
        count = 0
        for data in games_data:
            if 'name' not in data: 
                continue
            
            cover_url = ""
            if 'cover' in data and 'url' in data['cover']:
                cover_url = data['cover']['url'].replace('t_thumb', 't_cover_big')
                if cover_url.startswith('//'): 
                    cover_url = f"https:{cover_url}"

            vid_id = None
            if 'videos' in data and data['videos']:
                for v in data['videos']:
                    if 'video_id' in v:
                        vid_id = v['video_id']
                        break 

            screens_list = []
            if 'screenshots' in data:
                for sc in data['screenshots'][:3]: 
                    if 'url' in sc:
                        url = sc['url'].replace('t_thumb', 't_1080p')
                        if url.startswith('//'): 
                            url = f"https:{url}"
                        screens_list.append(url)

            platform_names = [p['name'] for p in data.get('platforms', [])]
            
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
                        'playtime_main': times_map.get(data['id'], 0),
                        'game_type': data.get('game_type', 0),
                        'release_year': min([d['y'] for d in data.get('release_dates', []) if 'y' in d], default=None),
                        'video_id': vid_id,
                        'screenshots': screens_list
                    }
                )
                count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Erreur sauvegarde {data['name']}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"✅ {count} jeux importés/mis à jour."))

        # 6. Mise à jour offset
        new_offset = offset + limit
        with open(state_file, 'w') as f:
            f.write(str(new_offset))
        self.stdout.write(f"💾 Prochain démarrage prévu à l'offset : {new_offset}")