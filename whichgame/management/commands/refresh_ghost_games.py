import requests
import os
import json
import time
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db.models import Q
from decouple import config
from whichgame.models import Game

class Command(BaseCommand):
    help = 'REFRESH : Met à jour les métadonnées (Notes, Dates, Temps) des jeux fantômes'

    def handle(self, *args, **options):
        # --- 1. AUTHENTIFICATION (Identique à ton script d'import) ---
        token_file = os.path.join(settings.BASE_DIR, 'twitch_token.json')
        access_token = None
        client_id = config('IGDB_CLIENT_ID')
        client_secret = config('IGDB_CLIENT_SECRET')

        # Lecture du token existant
        if os.path.exists(token_file):
            try:
                with open(token_file, 'r') as f:
                    data = json.load(f)
                    if data.get('expires_at') > time.time() + 60: 
                        access_token = data.get('access_token')
            except: # noqa: E722
                pass

        # Régénération si nécessaire
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

        # --- 2. CIBLAGE DES JEUX FANTÔMES ---
        current_year = datetime.now().year
        
        # On cible : Jeux de (Année - 1) à aujourd'hui/futur
        # QUI ont (< 5 votes OU pas de temps de jeu)
        ghosts = Game.objects.filter(
            Q(release_year__gte=current_year - 1) & 
            (Q(total_rating_count__lt=5) | Q(playtime_main=0) | Q(total_rating_count__isnull=True))
        ).exclude(igdb_id__isnull=True)

        count = ghosts.count()
        if count == 0:
            self.stdout.write(self.style.SUCCESS("✅ Aucun jeu fantôme à mettre à jour."))
            return

        self.stdout.write(f"👻 {count} jeux fantômes détectés. Traitement par paquets de 50...")

        # --- 3. TRAITEMENT PAR BATCH (50 IDs par requête) ---
        batch_size = 50
        ghost_list = list(ghosts)
        updated_total = 0

        for i in range(0, count, batch_size):
            batch = ghost_list[i:i + batch_size]
            
            # Création de la liste d'IDs : "12,455,900"
            ids_string = ",".join([str(g.igdb_id) for g in batch])
            
            # A. Récupération INFOS GÉNÉRALES
            fields = "fields total_rating, total_rating_count, first_release_date, release_dates.y;"
            body = f"{fields} where id = ({ids_string}); limit 50;"
            
            try:
                # Appel API IGDB Games
                resp = requests.post("https://api.igdb.com/v4/games", headers=headers, data=body)
                
                if resp.status_code == 429:
                    self.stdout.write(self.style.WARNING("⏳ Rate Limit. Pause de 2s..."))
                    time.sleep(2)
                    continue
                
                api_data = resp.json()
                data_map = {item['id']: item for item in api_data}

                # B. Récupération TEMPS DE JEU (HLTB)
                # On fait une requête séparée pour les temps de jeu de ce batch
                times_map = {}
                try:
                    body_times = f"fields game_id, normally, hastily, completely; where game_id = ({ids_string}); limit 50;"
                    resp_time = requests.post("https://api.igdb.com/v4/game_time_to_beats", headers=headers, data=body_times)
                    for t in resp_time.json():
                        # On prend 'normally' en priorité, sinon les autres
                        sec = t.get('normally') or t.get('hastily') or t.get('completely') or 0
                        if sec > 0:
                            times_map[t['game_id']] = max(1, round(sec / 3600))
                except: # noqa: E722
                    pass

                # C. MISE À JOUR LOCALE
                batch_updates = 0
                for game in batch:
                    # Infos de base
                    if game.igdb_id in data_map:
                        info = data_map[game.igdb_id]
                        has_changed = False

                        # 1. Notes
                        new_count = info.get('total_rating_count', 0)
                        new_rating = info.get('total_rating')
                        
                        if new_count > (game.total_rating_count or 0):
                            game.total_rating_count = new_count
                            game.rating = new_rating
                            has_changed = True
                            self.stdout.write(f"   📈 {game.title}: {game.total_rating_count} -> {new_count} votes")

                        # 2. Date
                        if 'first_release_date' in info:
                             r_date = datetime.fromtimestamp(info['first_release_date']).date()
                             if game.first_release_date != r_date:
                                 game.first_release_date = r_date
                                 has_changed = True
                        
                        # 3. Temps de jeu
                        if game.igdb_id in times_map:
                            new_time = times_map[game.igdb_id]
                            if new_time > 0 and new_time != game.playtime_main:
                                game.playtime_main = new_time
                                has_changed = True
                                self.stdout.write(f"   ⏱️ {game.title}: {new_time}h")

                        if has_changed:
                            game.save(update_fields=['total_rating_count', 'rating', 'first_release_date', 'playtime_main'])
                            batch_updates += 1

                updated_total += batch_updates
                time.sleep(0.3) # Politesse API

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Erreur batch: {e}"))

        self.stdout.write(self.style.SUCCESS(f"🎉 Terminé ! {updated_total} jeux mis à jour sur {count} fantômes vérifiés."))