import re
import time
import requests

from django.core.management.base import BaseCommand
from django.db.models import Q
from whichgame.models import Game

class Command(BaseCommand):
    help = 'Fetches multi-store deals (Steam, Epic, GOG, etc.) and updates local PC game prices.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🌍 1. Fetching best multi-store deals..."))
        
        # Step 1: Fetch live deals into memory
        live_deals = self._fetch_live_deals(pages_to_fetch=50)
        
        if not live_deals:
            self.stdout.write(self.style.WARNING("⚠️ No deals fetched or API limit reached. Aborting."))
            return
            
        self.stdout.write(self.style.SUCCESS(f"\n✅ {len(live_deals)} UNIQUE deals stored in memory!"))
        self.stdout.write("🧠 2. Cross-referencing with local database...\n")
        
        # Step 2: Update local database
        match_count = self._update_local_games(live_deals)
        
        self.stdout.write(self.style.SUCCESS(
            f"\n🎉 Finished! \n"
            f"   🔥 {match_count} games updated with today's promotional prices!"
        ))

    def _clean_title(self, title):
        """Removes special characters and spaces to facilitate strict string matching."""
        return re.sub(r'[^a-z0-9]', '', str(title).lower())

    def _fetch_live_deals(self, pages_to_fetch=50):
        """
        Iterates through CheapShark API pages to fetch current deals.
        Returns a dictionary mapping 'clean_title' -> lowest_price.
        """
        live_deals = {}
        
        with requests.Session() as session:
            for page in range(pages_to_fetch):
                url = f"https://www.cheapshark.com/api/1.0/deals?sortBy=Deal Rating&pageSize=60&pageNumber={page}"
                
                try:
                    response = session.get(url, timeout=10)
                    
                    if response.status_code == 429:
                        self.stdout.write(self.style.ERROR("\n🛑 IP rate-limited (HTTP 429)! Wait for the cooldown period."))
                        break

                    if response.status_code != 200:
                        self.stdout.write(self.style.WARNING(f"⚠️ API error on page {page} (Code {response.status_code})"))
                        break
                    
                    deals = response.json()
                    if not deals:
                        break # No more pages available
                    
                    for deal in deals:
                        clean_title = self._clean_title(deal.get('title', ''))
                        try:
                            price = float(deal.get('salePrice', 0))
                        except ValueError:
                            continue
                        
                        # Keep only the lowest price if duplicate games exist across stores
                        if clean_title not in live_deals or price < live_deals[clean_title]:
                            live_deals[clean_title] = price
                    
                    self.stdout.write(f"   📥 Page {page+1}/{pages_to_fetch} fetched...")
                    time.sleep(0.5) # Anti-ban delay
                    
                except requests.RequestException as e:
                    self.stdout.write(self.style.ERROR(f"Request error on page {page}: {e}"))
                    break
                    
        return live_deals

    def _update_local_games(self, live_deals):
        """
        Queries local PC games and updates their current price if a better live deal exists.
        Returns the number of games updated.
        """
        pc_platforms = ['PC (Microsoft Windows)', 'Mac', 'Linux', 'PC']
        query = Q()
        for plat in pc_platforms:
            query |= Q(platforms__icontains=plat)
            
        local_games = Game.objects.filter(query)
        match_count = 0

        for game in local_games:
            clean_local_title = self._clean_title(game.title)
            
            if clean_local_title in live_deals:
                new_price = live_deals[clean_local_title]
                old_price = game.price_current
                
                # Only update and hit the database if the price has actually changed
                if old_price != new_price:
                    game.price_current = new_price
                    game.save(update_fields=['price_current'])
                    match_count += 1
                    
                    old_display = f"{old_price}€" if old_price is not None else "None"
                    self.stdout.write(self.style.SUCCESS(f"   💸 UPDATE: {game.title[:40].ljust(40)} | {old_display} ➡️ {new_price}€"))

        return match_count