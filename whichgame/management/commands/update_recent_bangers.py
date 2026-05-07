import time
import requests
import re
from django.db.models import Q
from django.core.management.base import BaseCommand
from whichgame.models import Game
from howlongtobeatpy import HowLongToBeat

class Command(BaseCommand):
    help = 'Met à jour le prix et le temps de jeu des 20 derniers gros jeux incomplets.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🚀 Début de la complétion des gros jeux..."))

        recent_incomplete_games = Game.objects.filter(
            total_rating_count__gte=5
        ).filter(
            Q(price_current=0) | Q(price_current__isnull=True) | Q(playtime_main=0) | Q(playtime_main__isnull=True)
        ).order_by('-first_release_date')[:20]

        if not recent_incomplete_games.exists():
            self.stdout.write(self.style.SUCCESS("✨ Tous les gros jeux récents ont déjà leur prix et temps de jeu !"))
            return
        
        hltb_tool = HowLongToBeat()
        updated_count = 0

        for game in recent_incomplete_games:
            self.stdout.write(f"🔄 Traitement de : {game.title}...")
            needs_save = False

            # --- VÉRIFICATION ET MISE À JOUR DU PRIX (CheapShark) ---
            if game.price_current == 0 or game.price_current is None:
                try:
                    cs_url = f"https://www.cheapshark.com/api/1.0/games?title={game.title}&limit=1"
                    cs_response = requests.get(cs_url, timeout=5)
                    if cs_response.status_code == 200:
                        cs_data = cs_response.json()
                        if cs_data:
                            cheapest_price = float(cs_data[0].get('cheapest', 0))
                            if cheapest_price > 0:
                                game.price_current = cheapest_price
                                needs_save = True
                                self.stdout.write(f"   💰 Prix trouvé : {cheapest_price}€")
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"   ❌ Erreur prix : {e}"))
                
                time.sleep(1)

            # --- VÉRIFICATION ET MISE À JOUR DU TEMPS DE JEU (HLTB) ---
            if game.playtime_main == 0 or game.playtime_main is None:
                try:
                    nouveau_temps = self._fetch_playtime(hltb_tool, game.title) 
                    if nouveau_temps > 0:
                        game.playtime_main = nouveau_temps
                        needs_save = True
                        self.stdout.write(f"   ⏱️ Temps de jeu trouvé : {nouveau_temps}h")
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"   ❌ Erreur temps de jeu : {e}"))
                

                time.sleep(1.6)

            # --- SAUVEGARDE ---
            if needs_save:
                game.save()
                updated_count += 1
                self.stdout.write(self.style.SUCCESS(f"   ✅ {game.title} mis à jour en base !"))
            else:
                self.stdout.write(self.style.WARNING(f"   ⚠️ Aucune nouvelle info trouvée pour {game.title} aujourd'hui."))

        self.stdout.write(self.style.SUCCESS(f"🏁 Terminé ! {updated_count} jeux complétés sur cette session."))


    def _clean_title(self, title):
        """Removes special characters to improve search matching."""
        return re.sub(r'[^\w\s]', '', title)
        
    def _short_title(self, title):
        """Removes subtitles after a colon or dash."""
        return re.split(r'[:\-]', title)[0].strip()

    def _fetch_playtime(self, hltb_tool, title):
        """
        Cherche le jeu sur HLTB. Si l'histoire principale n'est pas dispo 
        (ex: sandbox, multijoueur), tente de récupérer les autres temps.
        """
        try:
            results = hltb_tool.search(title)
            
            if not results:
                clean_title = self._clean_title(title)
                if clean_title != title:
                    results = hltb_tool.search(clean_title)
                    
            if not results:
                short_title = self._short_title(title)
                if short_title != title:
                    results = hltb_tool.search(short_title)

            if results:
                best_match = max(results, key=lambda x: x.similarity)

                time_to_beat = best_match.main_story
                
                if not time_to_beat or float(time_to_beat) == 0:
                    time_to_beat = best_match.main_extra
                    
                if not time_to_beat or float(time_to_beat) == 0:
                    time_to_beat = best_match.completionist
                
                if time_to_beat and float(time_to_beat) > 0:
                    return int(round(float(time_to_beat)))
                else:
                    self.stdout.write(self.style.WARNING(f"   ⏳ {title} trouvé sur HLTB."))
                    
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ❌ Erreur HLTB pour '{title}': {e}"))
            
        return 0