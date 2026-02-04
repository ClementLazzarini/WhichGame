import time
from django.core.management.base import BaseCommand
from django.db.models import Q
from whichgame.models import Game

class Command(BaseCommand):
    help = 'Supprime les jeux qui sont EXCLUSIVEMENT sur Mobile (Android/iOS) ou Navigateur Web.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche seulement ce qui serait supprimé sans le faire.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        start_time = time.time()

        self.stdout.write("🕵️‍♂️  Analyse des jeux Mobile & Web en cours...")
        # 1. Filtrage initial des jeux suspects
        suspects = Game.objects.filter(
            Q(platforms__icontains="Android") | 
            Q(platforms__icontains="iOS") | 
            Q(platforms__icontains="Web Browser")
        )
        
        total_suspects = suspects.count()
        self.stdout.write(f"🔍 {total_suspects} jeux contiennent du Mobile/Web. Vérification s'ils sont exclusifs...")

        trash_platforms = {"Android", "iOS", "Web Browser"}
        
        deleted_count = 0
        kept_count = 0

        # 2. Analyse précise ligne par ligne
        for game in suspects:
            if not game.platforms or not isinstance(game.platforms, list):
                continue

            current_platforms = set(game.platforms)
            
            remaining_platforms = current_platforms - trash_platforms

            if len(remaining_platforms) == 0:
                if dry_run:
                    self.stdout.write(self.style.WARNING(f"   [DRY-RUN] Serait supprimé : {game.title} ({game.platforms})"))
                else:
                    game.delete()
                    self.stdout.write(f"   🗑️ Supprimé : {game.title}")
                
                deleted_count += 1
            else:
                kept_count += 1

        # 3. Résumé final
        duration = round(time.time() - start_time, 2)
        
        if dry_run:
            self.stdout.write(self.style.SUCCESS(f"\n✅ Simulation terminée en {duration}s"))
            self.stdout.write(f"   🗑️  Jeux qui seraient supprimés : {deleted_count}")
            self.stdout.write(f"   🛡️  Jeux multi-plateformes conservés : {kept_count}")
        else:
            self.stdout.write(self.style.SUCCESS(f"\n✅ Nettoyage terminé en {duration}s"))
            self.stdout.write(self.style.ERROR(f"   🗑️  Jeux supprimés (100% Mobile/Web) : {deleted_count}"))
            self.stdout.write(self.style.SUCCESS(f"   🛡️  Jeux conservés (Hybrides PC/Console) : {kept_count}"))