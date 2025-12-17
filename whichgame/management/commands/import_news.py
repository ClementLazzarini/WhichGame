import requests
import os
import json
import time # Nécessaire pour le timestamp actuel
from django.core.management.base import BaseCommand
from django.conf import settings
from decouple import config
from whichgame.models import Game

class Command(BaseCommand):
    help = 'LAYER 2 : Import des NOUVEAUTÉS (Sorties passées uniquement + Temps de jeu)'

    def handle(self, *args, **options):
        self.stdout.write("🔥 Démarrage Import NEWS (Dernières sorties réelles)...")

        # 1. AUTH IGDB (Avec Cache Intelligent pour éviter le ban)
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
            except Exception: 
                pass

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

        # 2. REQUÊTE JEUX (Filtre anti-futur)
        current_timestamp = int(time.time()) # L'heure actuelle en secondes UNIX
        
        fields = "fields name, slug, rating, cover.url, platforms.name, genres.name, release_dates.y, game_type, videos.video_id, screenshots.url, first_release_date;"
        
        # AJOUT DU FILTRE : first_release_date <= current_timestamp
        # Cela exclut les jeux qui ne sont pas encore sortis
        body = f"{fields} where game_type = (0, 8, 9) & cover != null & first_release_date != null & first_release_date <= {current_timestamp}; sort first_release_date desc; limit 20;"

        try:
            response = requests.post("https://api.igdb.com/v4/games", headers=headers, data=body)
            games_data = response.json()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erreur API: {e}"))
            return

        if not games_data:
            self.stdout.write(self.style.WARNING("⚠️ Aucun jeu trouvé."))
            return

        # 3. RÉCUPÉRATION DES TEMPS DE JEU (HLTB)
        # On doit le faire aussi ici pour éviter le "Noneh"
        game_ids = [g['id'] for g in games_data]
        ids_string = ",".join(map(str, game_ids))
        
        body_times = f"fields game_id, hastily, normally, completely; where game_id = ({ids_string}); limit 100;"
        
        try:
            response_time = requests.post("https://api.igdb.com/v4/game_time_to_beats", headers=headers, data=body_times)
            times_data = response_time.json()
        except Exception:
            times_data = [] 
        
        times_map = {}
        if isinstance(times_data, list):
            for t in times_data:
                seconds = t.get('hastily') or t.get('normally') or t.get('completely') or 0
                if seconds > 0:
                    hours = round(seconds / 3600)
                    times_map[t['game_id']] = max(1, hours) # Min 1h

        # 4. SAUVEGARDE
        count = 0
        for data in games_data:
            if 'name' not in data: 
                continue
            
            # --- Traitement Images ---
            cover_url = ""
            if 'cover' in data and 'url' in data['cover']:
                cover_url = data['cover']['url'].replace('t_thumb', 't_cover_big')
                if cover_url.startswith('//'): 
                    cover_url = f"https:{cover_url}"
            
            # --- Traitement Vidéos ---
            vid_id = None
            if 'videos' in data and data['videos']:
                for v in data['videos']:
                    if 'video_id' in v:
                        vid_id = v['video_id']
                        break

            # --- Traitement Screenshots ---
            screens_list = []
            if 'screenshots' in data:
                for sc in data['screenshots'][:3]: 
                    if 'url' in sc:
                        url = sc['url'].replace('t_thumb', 't_1080p') 
                        if url.startswith('//'): 
                            url = f"https:{url}"
                        screens_list.append(url)

            platform_names = [p['name'] for p in data.get('platforms', [])]
            
            # --- Gestion du temps ---
            # Si on a trouvé un temps HLTB, on l'utilise.
            # Sinon, on met 0 (pour afficher "TBD" ou rien, plutôt que de planter).
            playtime = times_map.get(data['id'], 0)

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
                        'playtime_main': playtime,
                        'game_type': data.get('game_type', 0),
                        'release_year': min([d['y'] for d in data.get('release_dates', []) if 'y' in d], default=None),
                        'video_id': vid_id,
                        'screenshots': screens_list
                    }
                )
                count += 1
                self.stdout.write(f"   Updated/Created: {data['name']} ({playtime}h)")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Erreur save {data['name']}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"✅ Terminé : {count} jeux actualisés (News)."))