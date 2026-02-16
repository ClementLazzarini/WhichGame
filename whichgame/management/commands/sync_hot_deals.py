import requests
import re
import time
from django.core.management.base import BaseCommand
from django.db.models import Q
from whichgame.models import Game

class Command(BaseCommand):
    help = 'Télécharge les promos multi-stores (Steam, Epic, GOG...) sans effacer les prix de base'

    def clean(self, name):
        """ Nettoie le titre pour faciliter la correspondance """
        return re.sub(r'[^a-z0-9]', '', str(name).lower())

    def handle(self, *args, **options):
        self.stdout.write("🌍 1. Téléchargement des meilleures promos Multi-Stores...")
        
        live_deals = {}
        # On peut monter à 50 pages (soit les 3000 meilleures promos du web)
        pages_to_fetch = 50 
        
        session = requests.Session()

        for page in range(pages_to_fetch):
            # 💡 J'AI ENLEVÉ storeID=1 -> Ça cherche partout (Epic, GOG, Steam...)
            url = f"https://www.cheapshark.com/api/1.0/deals?sortBy=Deal Rating&pageSize=60&page={page}"
            
            try:
                res = session.get(url, timeout=10)
                
                # Si on se prend un 429, on le signale clairement
                if res.status_code == 429:
                    self.stdout.write(self.style.ERROR("\n🛑 Ton IP est encore bannie ! Attends la fin du chrono."))
                    return

                if res.status_code != 200:
                    self.stdout.write(self.style.WARNING(f"⚠️ Erreur API page {page} (Code {res.status_code})"))
                    break
                
                deals = res.json()
                if not deals:
                    break 
                
                for deal in deals:
                    clean_title = self.clean(deal['title'])
                    price = float(deal['salePrice'])
                    
                    if clean_title not in live_deals or price < live_deals[clean_title]:
                        live_deals[clean_title] = price
                
                self.stdout.write(f"   📥 Page {page+1}/{pages_to_fetch} aspirée...")
                time.sleep(0.5) 
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Erreur requête : {e}"))
                break
                
        session.close()

        total_deals = len(live_deals)
        self.stdout.write(self.style.SUCCESS(f"✅ {total_deals} deals récupérés en mémoire !"))
        self.stdout.write("🧠 2. Croisement avec la base de données locale...")

        pc_platforms = ['PC (Microsoft Windows)', 'Mac', 'Linux', 'PC']
        query = Q()
        for plat in pc_platforms:
            query |= Q(platforms__icontains=plat)
            
        local_games = Game.objects.filter(query)
        match_count = 0

        for game in local_games:
            clean_local_title = self.clean(game.title)
            
            # Si le jeu est en promo en ce moment sur un des stores
            if clean_local_title in live_deals:
                new_price = live_deals[clean_local_title]
                
                # On met à jour le prix
                game.price_current = new_price
                game.save(update_fields=['price_current'])
                match_count += 1
                
            # 💡 NOTE IMPORTANTE : Il n'y a plus de "else" !
            # Si le jeu n'est pas en promo, on ne touche à rien, il garde son prix précédent.

        self.stdout.write(self.style.SUCCESS(
            f"🎉 Terminé ! \n"
            f"   🔥 {match_count} jeux mis à jour avec le prix promo du jour !"
        ))