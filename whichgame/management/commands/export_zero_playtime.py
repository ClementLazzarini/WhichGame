import csv
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from whichgame.models import Game

class Command(BaseCommand):
    help = 'Exporte la liste des jeux ayant 0h de durée de vie dans un fichier CSV'

    def handle(self, *args, **options):
        # On récupère les jeux à 0h, triés par popularité décroissante
        # Comme ça, tu mets à jour les jeux les plus importants en premier !
        games = Game.objects.filter(playtime_main=0).order_by('-total_rating_count')
        count = games.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS("✅ Aucun jeu à 0h trouvé dans la base de données !"))
            return

        # Le fichier sera créé à la racine de ton projet
        filepath = os.path.join(settings.BASE_DIR, 'jeux_0h_a_verifier.csv')

        self.stdout.write(f"⏳ Création de l'export pour {count} jeux...")

        with open(filepath, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file, delimiter=';') # Le point-virgule est plus facile à ouvrir sur Excel FR
            
            # En-têtes des colonnes
            writer.writerow(['ID', 'Titre', 'Popularité (Votes)', 'Genres', 'Plateformes'])

            for game in games:
                # On transforme les listes de genres et plateformes en texte simple
                genres = ", ".join(game.genres) if game.genres else "Non spécifié"
                platforms = ", ".join(game.platforms) if game.platforms else "Non spécifié"
                
                writer.writerow([
                    game.id, 
                    game.title, 
                    game.total_rating_count, 
                    genres, 
                    platforms
                ])

        self.stdout.write(self.style.SUCCESS(f"✅ Fichier créé avec succès : {filepath}"))
        self.stdout.write(self.style.WARNING("💡 Astuce : Ouvre ce fichier avec Excel ou Google Sheets pour le lire facilement."))