import requests
import re
import time
from django.core.management.base import BaseCommand
from django.db.models import Q
from whichgame.models import Game

class Command(BaseCommand):
    help = 'Télécharge les promos multi-stores (Steam, Epic, GOG...) et affiche les MAJ'

    def clean(self, name):
        """ Nettoie le titre pour faciliter la correspondance """
        return re.sub(r'[^a-z0-9]', '', str(name).lower())

    def handle(self, *args, **options):
        self.stdout.write("🌍 1. Téléchargement des meilleures promos Multi-Stores...")
        
        live_deals = {}
        pages_to_fetch = 50 
        
        session = requests.Session()

        for page in range(pages_to_fetch):
            # 🐛 CORRECTION DU BUG ICI : pageNumber au lieu de page
            url = f"https://www.cheapshark.com/api/1.0/deals?sortBy=Deal Rating&pageSize=60&pageNumber={page}"
            
            try:
                res = session.get(url, timeout=10)
                
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
        self.stdout.write(self.style.SUCCESS(f"\n✅ {total_deals} deals UNIQUES récupérés en mémoire !"))
        self.stdout.write("🧠 2. Croisement avec la base de données locale...\n")

        pc_platforms = ['PC (Microsoft Windows)', 'Mac', 'Linux', 'PC']
        query = Q()
        for plat in pc_platforms:
            query |= Q(platforms__icontains=plat)
            
        local_games = Game.objects.filter(query)
        match_count = 0

        for game in local_games:
            clean_local_title = self.clean(game.title)
            
            if clean_local_title in live_deals:
                new_price = live_deals[clean_local_title]
                old_price = game.price_current
                
                # 💡 OPTIMISATION : On ne sauvegarde QUE si le prix a changé ou s'il était vide
                if old_price != new_price:
                    game.price_current = new_price
                    game.save(update_fields=['price_current'])
                    match_count += 1
                    
                    # AFFICHAGE DE LA MISE À JOUR
                    old_display = f"{old_price}€" if old_price is not None else "Aucun"
                    self.stdout.write(self.style.SUCCESS(f"   💸 MAJ : {game.title[:40].ljust(40)} | {old_display} ➡️ {new_price}€"))

        self.stdout.write(self.style.SUCCESS(
            f"\n🎉 Terminé ! \n"
            f"   🔥 {match_count} jeux mis à jour avec le prix promo du jour !"
        ))