import requests
import os
import re
import time
from django.core.management.base import BaseCommand
from django.conf import settings
from whichgame.models import Game

class Command(BaseCommand):
    help = 'LAYER 2 : Mise à jour PRIX (Sécurisé Anti-Ban)'

    def handle(self, *args, **options):
        state_file = os.path.join(settings.BASE_DIR, 'prices_update.state')
        offset = 0
        limit = 50 
        
        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                try: 
                    offset = int(f.read().strip())
                except ValueError: 
                    offset = 0

        games_to_update = Game.objects.all().order_by('id')[offset:offset+limit]
        
        if not games_to_update:
            self.stdout.write(self.style.SUCCESS(f"✅ Tout est à jour (Offset {offset}). En attente de nouveaux jeux..."))
            return

        self.stdout.write(f"💰 Mise à jour prix pour {len(games_to_update)} jeux (Offset {offset})...")

        # Variable de contrôle : Est-ce qu'on a tout fini sans erreur ?
        success_batch = True

        for game in games_to_update:
            # 1. Vérif si PC
            is_pc = any(x in ['PC (Microsoft Windows)', 'Mac', 'Linux'] for x in game.platforms)
            
            found_price = None 

            if is_pc:
                try:
                    # On appelle l'API
                    found_price, status_code = self.get_best_price(game.title)
                    
                    # GESTION DU BAN (429)
                    if status_code == 429:
                        self.stdout.write(self.style.ERROR("🛑 STOP ! Trop de requêtes (429). On arrête tout."))
                        success_batch = False
                        break # On sort de la boucle immédiatement
                    
                    if found_price is not None:
                        game.price_current = found_price
                        game.save()
                        self.stdout.write(f"   ✅ {game.title}: {found_price}€")
                    
                    # PAUSE OBLIGATOIRE ENTRE CHAQUE JEU (0.5 sec)
                    # 50 jeux prendront 25 secondes. C'est lent, mais sûr.
                    time.sleep(0.5) 

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"   ⚠️ Erreur sur {game.title}: {e}"))
            
            else:
                # Nettoyage si console
                if game.price_current is not None:
                    game.price_current = None
                    game.save()

        # SAUVEGARDE DE L'OFFSET
        # On ne met à jour l'offset QUE si le batch s'est terminé sans ban (success_batch = True)
        if success_batch:
            new_offset = offset + limit
            with open(state_file, 'w') as f:
                f.write(str(new_offset))
            self.stdout.write(self.style.SUCCESS(f"💾 Batch terminé. Prochain offset : {new_offset}"))
        else:
            self.stdout.write(self.style.WARNING(f"⚠️ Batch interrompu. L'offset reste à {offset} pour réessayer plus tard."))

    def clean(self, name):
        return re.sub(r'[^a-z0-9]', '', name.lower())

    def get_best_price(self, game_name):
        """ Retourne (prix, status_code) """
        try:
            url = f"https://www.cheapshark.com/api/1.0/games?title={game_name}&limit=10"
            res = requests.get(url, timeout=5)
            
            # Si Rate Limit, on renvoie le code d'erreur tout de suite
            if res.status_code == 429:
                return None, 429
                
            if res.status_code != 200:
                return None, res.status_code

            results = res.json()
            if not results: 
                return None, 200

            clean_game = self.clean(game_name)
            candidates = []
            
            for r in res:
                clean_shark = self.clean(r['external'])
                if clean_game == clean_shark or clean_game in clean_shark:
                    candidates.append(r)
            
            if candidates:
                best_match = min(candidates, key=lambda x: len(x['external']))
                return float(best_match['cheapest']), 200
            
            return None, 200
        except Exception: 
            return None, 500