import time
import re
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from whichgame.models import Game
from howlongtobeatpy import HowLongToBeat

class Command(BaseCommand):
    help = 'LAYER 3 : Enrichissement des temps de jeu via HowLongToBeat (Production)'

    def handle(self, *args, **options):
        # 1. Gestion de l'état (Reprise sur erreur/arrêt)
        state_file = os.path.join(settings.BASE_DIR, 'hltb_update.state')
        offset = 0
        limit = 10  # On reste prudent avec le scraping (10 par 10)
        
        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                try: 
                    offset = int(f.read().strip())
                except ValueError: 
                    offset = 0

        # Récupération du lot de jeux
        games_to_update = Game.objects.all().order_by('id')[offset:offset+limit]
        
        # Si on arrive au bout de la BDD, on repart à 0
        if not games_to_update:
            self.stdout.write(self.style.SUCCESS(f"✅ Tout est à jour (Offset {offset}). En attente de nouveaux jeux..."))
            return

        self.stdout.write(f"⏱️  Traitement HLTB (Offset {offset} - {len(games_to_update)} jeux)...")
        hltb_tool = HowLongToBeat()

        for game in games_to_update:
            # OPTIMISATION : Si on a déjà un temps > 0 (via IGDB), on passe pour économiser l'API
            # Si tu veux privilégier la précision HLTB sur IGDB, commente ces 2 lignes :
            # if game.playtime_main and game.playtime_main > 0:
            #    self.stdout.write(f"   ⏩ {game.title[:20]}... : Déjà OK ({game.playtime_main}h)")
            #    continue 

            found_time = 0
            try:
                # Stratégie 1 : Recherche Nom Exact
                results = hltb_tool.search(game.title)
                
                # Stratégie 2 : Recherche Nom Nettoyé (si échec)
                if not results:
                    clean_title = re.sub(r'[^\w\s]', '', game.title)
                    if clean_title != game.title:
                        results = hltb_tool.search(clean_title)

                if results:
                    # On prend le résultat le plus pertinent
                    best = max(results, key=lambda x: x.similarity)
                    found_time = int(best.main_story)

                if found_time > 0:
                    game.playtime_main = found_time
                    game.save()
                    self.stdout.write(f"   ✅ {game.title[:20]}... : Mis à jour -> {found_time}h")
                else:
                    self.stdout.write(self.style.WARNING(f"   ⚠️ {game.title[:20]}... : Pas trouvé"))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"   ❌ Erreur sur {game.title}: {e}"))

            # PAUSE OBLIGATOIRE (Anti-Ban) - Ne pas descendre en dessous de 1.0s
            time.sleep(1.2)

        # 2. Sauvegarde du nouvel offset pour la prochaine exécution
        next_offset = offset + limit
        with open(state_file, 'w') as f:
            f.write(str(next_offset))
            
        self.stdout.write(self.style.SUCCESS(f"💾 Batch terminé. Prochain offset : {next_offset}"))