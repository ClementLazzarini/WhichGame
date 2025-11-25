import requests
from django.core.management.base import BaseCommand
from decouple import config
from whichgame.models import Game
from howlongtobeatpy import HowLongToBeat

class Command(BaseCommand):
    help = 'Importe les jeux avec paramètres (offset/limit)'

    # 1. NOUVEAU : On définit les arguments acceptés
    def add_arguments(self, parser):
        parser.add_argument(
            '--offset',
            type=int,
            default=0,
            help='À partir de quel jeu commencer (par défaut 0)'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=50,
            help='Combien de jeux importer (par défaut 50)'
        )

    def handle(self, *args, **options):
        # 2. On récupère les valeurs passées en commande
        offset = options['offset']
        limit = options['limit']

        self.stdout.write(f"🚀 Démarrage : Import de {limit} jeux à partir du rang {offset}...")

        # --- AUTHENTIFICATION (Inchangé) ---
        client_id = config('IGDB_CLIENT_ID')
        client_secret = config('IGDB_CLIENT_SECRET')
        
        auth_req = requests.post("https://id.twitch.tv/oauth2/token", params={
            'client_id': client_id, 'client_secret': client_secret, 'grant_type': 'client_credentials'
        })
        access_token = auth_req.json()['access_token']

        # --- REQUÊTE IGDB DYNAMIQUE ---
        url = "https://api.igdb.com/v4/games"
        headers = {'Client-ID': client_id, 'Authorization': f'Bearer {access_token}'}
        
        # 3. Utilisation des variables limit et offset dans la requête (f-string)
        body = f"""
            fields name, slug, rating, cover.url, platforms.name, genres.name, release_dates.y; 
            sort rating_count desc; 
            limit {limit}; 
            offset {offset};
        """
        
        response = requests.post(url, headers=headers, data=body)
        games_data = response.json()
        
        if not games_data:
            self.stdout.write(self.style.WARNING("⚠️ Aucun jeu trouvé (fin de la liste ?)"))
            return

        self.stdout.write(f"📦 Traitement de {len(games_data)} jeux...")
        
        hltb_tool = HowLongToBeat()

        # --- BOUCLE DE TRAITEMENT (Identique à avant) ---
        for data in games_data:
            if 'name' not in data: continue 
            game_name = data['name']

            # Année
            release_year = None
            if 'release_dates' in data:
                years = [d['y'] for d in data['release_dates'] if 'y' in d]
                if years: release_year = min(years)

            # Prix
            price = self.get_cheapshark_price(game_name)
            
            # Temps (Avec petite sécurité erreur)
            playtime_hours = 0
            try:
                results = hltb_tool.search(game_name)
                if results:
                    best_match = max(results, key=lambda x: x.similarity)
                    playtime_hours = int(best_match.main_story)
            except: pass

            # Image
            cover_url = ""
            if 'cover' in data and 'url' in data['cover']:
                cover_url = data['cover']['url'].replace('t_thumb', 't_cover_big')
                if cover_url.startswith('//'): cover_url = f"https:{cover_url}"

            # Sauvegarde
            try:
                game, created = Game.objects.update_or_create(
                    igdb_id=data['id'],
                    defaults={
                        'title': game_name,
                        'slug': data['slug'],
                        'rating': data.get('rating'),
                        'cover_url': cover_url,
                        'platforms': [p['name'] for p in data.get('platforms', [])],
                        'genres': [g['name'] for g in data.get('genres', [])],
                        'price_current': price,
                        'playtime_main': playtime_hours,
                        'release_year': release_year
                    }
                )
                action = "✨" if created else "🔄"
                # Petit log plus compact
                self.stdout.write(f"{action} {game.title[:20]}... ({release_year})")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Err: {e}"))

        self.stdout.write(self.style.SUCCESS("🎉 Batch terminé !"))

    def get_cheapshark_price(self, game_name):
        try:
            url = f"https://www.cheapshark.com/api/1.0/games?title={game_name}&limit=1"
            res = requests.get(url, timeout=5)
            data = res.json()
            if data: return float(data[0]['cheapest'])
            return 0.00
        except: return 0.00