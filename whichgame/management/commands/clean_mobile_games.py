import time
from django.core.management.base import BaseCommand
from django.db.models import Q
from whichgame.models import Game

class Command(BaseCommand):
    help = 'Deletes games that are EXCLUSIVELY available on Mobile (Android/iOS) or Web Browser.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Shows what would be deleted without actually deleting anything.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        start_time = time.time()

        self.stdout.write("🕵️‍♂️ Analyzing Mobile & Web games...")
        
        # 1. Initial filtering of suspect games
        suspects = Game.objects.filter(
            Q(platforms__icontains="Android") | 
            Q(platforms__icontains="iOS") | 
            Q(platforms__icontains="Web browser") | 
            Q(platforms__icontains="Web Browser")
        )
        
        total_suspects = suspects.count()
        self.stdout.write(f"🔍 Found {total_suspects} games containing Mobile/Web platforms. Checking for exclusivity...")

        deleted_count = 0
        kept_count = 0

        # 2. Precise line-by-line analysis
        for game in suspects:
            if not game.platforms or not isinstance(game.platforms, list):
                continue

            if self._is_exclusively_trash(game.platforms):
                if dry_run:
                    self.stdout.write(self.style.WARNING(f"   [DRY-RUN] Would delete: {game.title} ({game.platforms})"))
                else:
                    game.delete()
                    self.stdout.write(f"   🗑️ Deleted: {game.title}")
                deleted_count += 1
            else:
                kept_count += 1

        # 3. Final Summary
        duration = round(time.time() - start_time, 2)
        
        if dry_run:
            self.stdout.write(self.style.SUCCESS(f"\n✅ Simulation completed in {duration}s"))
            self.stdout.write(f"   🗑️  Games that would be deleted: {deleted_count}")
            self.stdout.write(f"   🛡️  Multi-platform games kept: {kept_count}")
        else:
            self.stdout.write(self.style.SUCCESS(f"\n✅ Cleanup completed in {duration}s"))
            self.stdout.write(self.style.ERROR(f"   🗑️  Deleted games (100% Mobile/Web): {deleted_count}"))
            self.stdout.write(self.style.SUCCESS(f"   🛡️  Multi-platform games kept: {kept_count}"))

    def _is_exclusively_trash(self, platforms):
        """Returns True if the game is ONLY available on unwanted platforms."""
        # Lowercase everything to avoid case-sensitivity issues (e.g., "Web Browser" vs "Web browser")
        trash_platforms = {"android", "ios", "web browser"}
        current_platforms = {str(p).lower().strip() for p in platforms}
        
        # If removing trash platforms leaves nothing, it's exclusively trash
        remaining_platforms = current_platforms - trash_platforms
        return len(remaining_platforms) == 0