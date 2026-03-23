import os
import re
import time

from django.core.management.base import BaseCommand
from django.conf import settings
from whichgame.models import Game
from howlongtobeatpy import HowLongToBeat

class Command(BaseCommand):
    help = 'Fetches and updates game playtimes via HowLongToBeat (Rate-limit safe, max 10/run).'

    def handle(self, *args, **options):
        state_file = os.path.join(settings.BASE_DIR, 'hltb_update.state')
        limit = 10
        offset = self._get_offset(state_file)

        # 1. Fetch the next batch of games
        games_to_update = Game.objects.all().order_by('id')[offset:offset + limit]
        
        if not games_to_update:
            self.stdout.write(self.style.SUCCESS(f"✅ All playtimes are up to date (Offset {offset}). Waiting for new games..."))
            return

        self.stdout.write(f"⏱️ Updating playtimes for {len(games_to_update)} games (Offset: {offset})...")
        
        # Initialize the scraper tool once for the batch
        hltb_tool = HowLongToBeat()

        # 2. Process the batch
        for game in games_to_update:
            found_time = self._fetch_playtime(hltb_tool, game.title)

            if found_time > 0:
                game.playtime_main = found_time
                # Only update the specific field to optimize database write
                game.save(update_fields=['playtime_main'])
                self.stdout.write(self.style.SUCCESS(f"   ✅ {game.title[:30]}: Updated -> {found_time}h"))
            else:
                self.stdout.write(self.style.WARNING(f"   ⚠️ {game.title[:30]}: Not found on HLTB"))

            # Anti-ban sleep (HLTB is strictly monitored, keep at least 1.2s delay)
            time.sleep(1.2)

        # 3. Save state for the next cron execution
        new_offset = offset + limit
        self._save_offset(state_file, new_offset)
        self.stdout.write(self.style.SUCCESS(f"💾 Batch complete. Next offset: {new_offset}"))

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
        """Removes special characters to improve search matching."""
        return re.sub(r'[^\w\s]', '', title)
        
    def _short_title(self, title):
        """Removes subtitles after a colon or dash (e.g., 'The Witcher 3: Wild Hunt' -> 'The Witcher 3')."""
        return re.split(r'[:\-]', title)[0].strip()

    def _fetch_playtime(self, hltb_tool, title):
        """
        Attempts to find the game on HLTB and returns the main story playtime.
        Returns 0 if not found or if an error occurs.
        """
        try:
            # Strategy 1: Exact title search
            results = hltb_tool.search(title)
            
            # Strategy 2: Cleaned title search
            if not results:
                clean_title = self._clean_title(title)
                if clean_title != title:
                    results = hltb_tool.search(clean_title)
                    
            # Strategy 3: Shortened title search (drop subtitles)
            if not results:
                short_title = self._short_title(title)
                if short_title != title:
                    results = hltb_tool.search(short_title)

            if results:
                # Select the most relevant result based on the similarity score
                best_match = max(results, key=lambda x: x.similarity)
                
                # Parse the playtime safely (HLTB can return floats or None)
                if best_match.main_story:
                    return int(round(float(best_match.main_story)))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ❌ Error fetching '{title}': {e}"))
            
        return 0