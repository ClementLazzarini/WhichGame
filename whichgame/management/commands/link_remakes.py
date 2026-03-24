from django.core.management.base import BaseCommand
from django.db.models import Q
from whichgame.models import Game

class Command(BaseCommand):
    help = 'Links original games to their most recent Remake or Remaster version.'

    def handle(self, *args, **options):
        # Fetch all original games (game_type 0)
        main_games = Game.objects.filter(game_type=0)
        
        update_count = 0
        self.stdout.write("🔗 Searching for remakes/remasters (Prioritizing the most recent release)...")

        for game in main_games:
            candidate = self._find_latest_remake(game)

            if candidate:
                # Update database only if the link doesn't already exist or has changed
                if game.remake_slug != candidate.slug:
                    game.remake_slug = candidate.slug
                    
                    # Optimize database write by targeting only the necessary field
                    game.save(update_fields=['remake_slug'])
                    
                    type_name = "Remake" if candidate.game_type == 8 else "Remaster"
                    self.stdout.write(self.style.SUCCESS(
                        f"   ✨ Linked: {game.title[:30].ljust(30)} -> {candidate.title[:30]} ({type_name} - {candidate.release_year})"
                    ))
                    update_count += 1
        
        self.stdout.write(self.style.SUCCESS(f"✅ Finished. {update_count} game links updated or created."))

    def _find_latest_remake(self, original_game):
        """
        Queries the database for a Remake (type 8) or Remaster (type 9)
        whose title contains the original game's title, returning the most recent one.
        """
        return Game.objects.filter(
            Q(game_type=8) | Q(game_type=9),
            title__icontains=original_game.title
        ).exclude(pk=original_game.pk).order_by('-release_year').first()