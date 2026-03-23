import os
import re
import time
import requests

from django.core.management.base import BaseCommand
from django.conf import settings
from whichgame.models import Game

class Command(BaseCommand):
    help = 'Fetches and updates PC game prices via CheapShark API (Rate-limit safe).'

    def handle(self, *args, **options):
        state_file = os.path.join(settings.BASE_DIR, 'prices_update.state')
        limit = 50
        offset = self._get_offset(state_file)

        # 1. Fetch the next batch of games
        games_to_update = Game.objects.all().order_by('id')[offset:offset + limit]
        
        if not games_to_update:
            self.stdout.write(self.style.SUCCESS(f"✅ All prices are up to date (Offset {offset}). Waiting for new games..."))
            return

        self.stdout.write(f"💰 Updating prices for {len(games_to_update)} games (Offset: {offset})...")

        # 2. Process the batch using a persistent HTTP session
        success_batch = True
        
        with requests.Session() as session:
            for game in games_to_update:
                # Check if the game is available on computer platforms
                is_pc = any(platform in ['PC (Microsoft Windows)', 'PC', 'Mac', 'Linux'] for platform in game.platforms)
                
                if is_pc:
                    found_price, status_code = self._fetch_best_price(session, game.title)
                    
                    if status_code == 429:
                        self.stdout.write(self.style.ERROR(f"🛑 Rate limit exceeded (HTTP 429) on '{game.title}'. Pausing batch."))
                        success_batch = False
                        break
                    
                    if found_price is not None:
                        game.price_current = found_price # type: ignore
                        # Only update the specific field to avoid overwriting other concurrent changes
                        game.save(update_fields=['price_current'])
                        self.stdout.write(self.style.SUCCESS(f"   ✅ {game.title[:30]}: Updated -> {found_price}€"))
                    else:
                        self.stdout.write(self.style.WARNING(f"   ⚠️ {game.title[:30]}: Not found or no price available"))
                        
                    # Anti-ban sleep (CheapShark recommends keeping requests reasonable)
                    time.sleep(1.5)
                else:
                    self.stdout.write(f"   ⏩ {game.title[:30]}: Skipped (Console only)")

        # 3. Save state if the batch completed without hitting rate limits
        if success_batch:
            new_offset = offset + limit
            self._save_offset(state_file, new_offset)
            self.stdout.write(self.style.SUCCESS(f"💾 Batch complete. Next offset: {new_offset}"))
        else:
            self.stdout.write(self.style.WARNING(f"⚠️ Batch interrupted. Offset remains at {offset}."))

    def _get_offset(self, state_file):
        """Reads the current offset from the state file."""
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r') as f:
                    return int(f.read().strip())
            except ValueError:
                pass
        return 0

    def _save_offset(self, state_file, offset):
        """Saves the new offset to the state file."""
        with open(state_file, 'w') as f:
            f.write(str(offset))

    def _clean_title(self, title):
        """Removes special characters and spaces for better strict matching."""
        return re.sub(r'[^a-z0-9]', '', title.lower())

    def _fetch_best_price(self, session, game_name):
        """
        Fetches the best current price from CheapShark.
        Returns a tuple: (price_as_float_or_None, http_status_code)
        """
        url = "https://www.cheapshark.com/api/1.0/games"
        params = {'title': game_name, 'limit': 10}
        
        try:
            response = session.get(url, params=params, timeout=5)
            
            if response.status_code != 200:
                return None, response.status_code

            results = response.json()
            if not results:
                return None, 200

            clean_game = self._clean_title(game_name)
            candidates = []
            
            # Filter candidates to ensure strict matching
            for result in results:
                clean_shark = self._clean_title(result['external'])
                if clean_game == clean_shark or clean_game in clean_shark:
                    candidates.append(result)
            
            if candidates:
                # Select the match with the shortest title length (closest exact match)
                best_match = min(candidates, key=lambda x: len(x['external']))
                return float(best_match['cheapest']), 200
                
            return None, 200

        except requests.RequestException:
            # Treat network timeouts/errors gracefully without breaking the whole batch
            return None, 500