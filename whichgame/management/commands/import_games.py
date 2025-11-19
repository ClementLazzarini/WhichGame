import requests
from django.core.management.base import BaseCommand
from decouple import config
from whichgame.models import Game
from howlongtobeatpy import HowLongToBeat # NOUVEAU

class Command(BaseCommand):
    help = 'Importe les jeux depuis IGDB, enrichit avec CheapShark et HLTB'

    def handle(self, *args, **kwargs):
        self.stdout.write("🚀 Démarrage de l'importation COMPLÈTE...")

        # 1. --- AUTHENTIFICATION IGDB ---
        client_id = config('IGDB_CLIENT_ID')
        client_secret = config('IGDB_CLIENT_SECRET')
        
        auth_response = requests.post("https://id.twitch.tv/oauth2/token", params={
            'client_id': client_id,
            'client_secret': client_secret,
            'grant_type': 'client_credentials'
        })
        access_token = auth_response.json()['access_token']

        # 2. --- REQUÊTE IGDB (Top 10 pour tester) ---
        url = "https://api.igdb.com/v4/games"
        headers = {'Client-ID': client_id, 'Authorization': f'Bearer {access_token}'}
        
        # On demande les infos de base
        body = "fields name, slug, rating, cover.url, platforms.name, genres.name; sort rating_count desc; limit 10;"
        
        response = requests.post(url, headers=headers, data=body)
        games_data = response.json()
        
        self.stdout.write(f"📦 Traitement de {len(games_data)} jeux...")

        # Initialisation de l'outil HLTB
        hltb_tool = HowLongToBeat()

        # 3. --- BOUCLE UNIQUE DE TRAITEMENT ---
        for data in games_data:
            if 'name' not in data: continue # Sécurité

            game_name = data['name']

            # A. PRIX (CheapShark)
            price = self.get_cheapshark_price(game_name)
            
            # B. TEMPS DE JEU (HowLongToBeat) - NOUVEAU
            playtime_hours = 0
            try:
                # On cherche le jeu (ça peut prendre un peu de temps)
                results = hltb_tool.search(game_name)
                if results and len(results) > 0:
                    # On prend le meilleur résultat qui correspond au nom
                    best_match = max(results, key=lambda x: x.similarity)
                    playtime_hours = int(best_match.main_story) # On prend l'histoire principale
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"   ⚠️ Pas de temps trouvé pour {game_name} Erreur : {e}"))

            # C. IMAGE (Nettoyage)
            cover_url = ""
            if 'cover' in data and 'url' in data['cover']:
                cover_url = data['cover']['url'].replace('t_thumb', 't_cover_big')
                if cover_url.startswith('//'): cover_url = f"https:{cover_url}"

            # D. SAUVEGARDE BDD
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
                        'playtime_main': playtime_hours
                    }
                )
                
                status = "✨ Créé" if created else "🔄 Mis à jour"
                self.stdout.write(f"{status}: {game.title} | 💰 {price}€ | ⏱️ {playtime_hours}h")
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Erreur BDD : {e}"))

        self.stdout.write(self.style.SUCCESS("🎉 Import terminé ! Toutes les données sont là."))

    def get_cheapshark_price(self, game_name):
        """Interroge CheapShark pour trouver le prix le plus bas actuel"""
        try:
            url = f"https://www.cheapshark.com/api/1.0/games?title={game_name}&limit=1"
            res = requests.get(url)
            data = res.json()
            if data: return float(data[0]['cheapest'])
            return 0.00
        except: return 0.00