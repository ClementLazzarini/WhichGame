import requests
import re
from django.core.management.base import BaseCommand
from decouple import config
from whichgame.models import Game
from difflib import SequenceMatcher

class Command(BaseCommand):
    help = 'Import V10 : Temps en Cascade + Prix au plus court'

    def add_arguments(self, parser):
        parser.add_argument('--offset', type=int, default=0)
        parser.add_argument('--limit', type=int, default=50)

    def handle(self, *args, **options):
        offset = options['offset']
        limit = options['limit']
        
        # 1. AUTH IGDB
        client_id = config('IGDB_CLIENT_ID')
        client_secret = config('IGDB_CLIENT_SECRET')
        
        try:
            auth = requests.post("https://id.twitch.tv/oauth2/token", params={
                'client_id': client_id, 'client_secret': client_secret, 'grant_type': 'client_credentials'
            }).json()
            access_token = auth['access_token']
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Erreur Auth : {e}"))
            return

        headers = {'Client-ID': client_id, 'Authorization': f'Bearer {access_token}'}

        # ---------------------------------------------------------
        # ÉTAPE 1 : Récupérer les JEUX
        # ---------------------------------------------------------
        url_games = "https://api.igdb.com/v4/games"
        body_games = f"""
            fields name, slug, rating, cover.url, platforms.name, genres.name, release_dates.y; 
            sort rating_count desc; 
            limit {limit}; 
            offset {offset};
        """
        
        self.stdout.write(f"📡 Récupération des jeux (Offset {offset})...")
        response_games = requests.post(url_games, headers=headers, data=body_games)
        games_data = response_games.json()

        if not games_data or 'status' in games_data: 
            self.stdout.write(self.style.ERROR(f"❌ Erreur Jeux: {games_data}"))
            return

        game_ids = [g['id'] for g in games_data]
        ids_string = ",".join(map(str, game_ids))

        # ---------------------------------------------------------
        # ÉTAPE 2 : Récupérer les TEMPS (AVEC CASCADE)
        # ---------------------------------------------------------
        url_times = "https://api.igdb.com/v4/game_time_to_beats"
        
        # On demande les 3 types de temps
        body_times = f"""
            fields game_id, hastily, normally, completely; 
            where game_id = ({ids_string});
            limit 500; 
        """
        
        self.stdout.write(f"⏱️  Récupération des temps de jeu...")
        response_times = requests.post(url_times, headers=headers, data=body_times)
        times_data = response_times.json()

        times_map = {}
        if isinstance(times_data, list):
            for t in times_data:
                gid = t['game_id']
                seconds = 0
                
                # --- LOGIQUE DE CASCADE (Priorité : Rapide > Normal > Complet) ---
                if t.get('hastily', 0) > 0:
                    seconds = t['hastily']
                elif t.get('normally', 0) > 0:
                    seconds = t['normally']
                elif t.get('completely', 0) > 0:
                    seconds = t['completely']
                
                if seconds > 0:
                    hours = round(seconds / 3600)
                    # Si c'est un jeu très court (ex: 10 min), on met au moins 1h pour l'affichage
                    if hours == 0 and seconds > 0:
                        hours = 1
                    
                    times_map[gid] = hours

        # ---------------------------------------------------------
        # ÉTAPE 3 : Fusion
        # ---------------------------------------------------------
        self.stdout.write(f"📦 Traitement de {len(games_data)} jeux...")

        for data in games_data:
            if 'name' not in data: continue 
            game_name = data['name']
            game_id = data['id']
            
            # --- PLATEFORMES ---
            platforms = [p['name'] for p in data.get('platforms', [])]
            is_pc = any(x in ['PC (Microsoft Windows)', 'Mac', 'Linux'] for x in platforms)

            # --- PRIX (CheapShark) ---
            price = None
            if is_pc:
                price = self.get_best_price(game_name)

            # --- ANNÉE ---
            release_year = None
            if 'release_dates' in data:
                years = [d['y'] for d in data['release_dates'] if 'y' in d]
                if years: release_year = min(years)

            # --- TEMPS DE JEU ---
            playtime_hours = times_map.get(game_id, 0)

            # --- IMAGE ---
            cover_url = ""
            if 'cover' in data and 'url' in data['cover']:
                cover_url = data['cover']['url'].replace('t_thumb', 't_cover_big')
                if cover_url.startswith('//'): cover_url = f"https:{cover_url}"

            # --- SAUVEGARDE ---
            try:
                game, created = Game.objects.update_or_create(
                    igdb_id=game_id,
                    defaults={
                        'title': game_name,
                        'slug': data['slug'],
                        'rating': data.get('rating'),
                        'cover_url': cover_url,
                        'platforms': platforms,
                        'genres': [g['name'] for g in data.get('genres', [])],
                        'price_current': price,
                        'playtime_main': playtime_hours,
                        'release_year': release_year
                    }
                )
                
                p_str = f"{price}€" if price is not None else "-"
                t_str = f"{playtime_hours}h" if playtime_hours > 0 else "-"
                icon = "✨" if created else "🆗"
                
                self.stdout.write(f"{icon} {game.title[:25]:<25} | {p_str:<6} | {t_str}")

            except Exception as e:
                self.stdout.write(f"Err BDD: {e}")

    def clean(self, name):
        """Ne garde que chiffres et lettres minuscules"""
        return re.sub(r'[^a-z0-9]', '', name.lower())

    def get_best_price(self, game_name):
        try:
            url = f"https://www.cheapshark.com/api/1.0/games?title={game_name}&limit=10"
            res = requests.get(url, timeout=3).json()
            if not res: return None

            clean_game = self.clean(game_name)
            candidates = []
            
            for r in res:
                clean_shark = self.clean(r['external'])
                # Match Exact OU Inclusion
                if clean_game == clean_shark or clean_game in clean_shark:
                    candidates.append(r)
            
            if candidates:
                # REVERT : On prend le nom le plus court (ex: Mass Effect 2 > Mass Effect 2 Digital Edition)
                best_match = min(candidates, key=lambda x: len(x['external']))
                return float(best_match['cheapest'])
            
            return None
        except: return None