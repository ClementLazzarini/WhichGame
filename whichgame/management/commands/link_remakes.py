from django.core.management.base import BaseCommand
from whichgame.models import Game
from django.db.models import Q

class Command(BaseCommand):
    help = 'LAYER 4 : Lie les jeux originaux à leur version la plus RÉCENTE (Remake/Remaster)'

    def handle(self, *args, **options):
        main_games = Game.objects.filter(game_type=0)
        
        count = 0
        self.stdout.write("🔗 Recherche de liaisons (Priorité au plus récent)...")

        for game in main_games:
            candidate = Game.objects.filter(
                Q(game_type=8) | Q(game_type=9),
                title__icontains=game.title
            ).exclude(pk=game.pk).order_by('-release_year').first()

            if candidate:
                if game.remake_slug != candidate.slug:
                    game.remake_slug = candidate.slug
                    game.save()
                    
                    type_name = "Remake" if candidate.game_type == 8 else "Remaster"
                    self.stdout.write(f"   ✨ Lié (Update) : {game.title} -> {candidate.title} ({type_name} - {candidate.release_year})")
                    count += 1
        
        self.stdout.write(self.style.SUCCESS(f"✅ Terminé. {count} liaisons mises à jour."))