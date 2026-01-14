from django.core.management.base import BaseCommand
from whichgame.models import Game
from difflib import SequenceMatcher
import re

class Command(BaseCommand):
    help = 'Génère les recommandations basées sur score pondéré (Sémantique, Meta-data, Diversité)'

    def handle(self, *args, **options):
        # Filtre de base : Jeux avec au moins 5 votes
        games = list(Game.objects.filter(total_rating_count__gte=5))
        total = len(games)
        
        if total == 0:
            self.stdout.write(self.style.WARNING("Aucun jeu éligible trouvé."))
            return

        self.stdout.write(f"Traitement des recommandations pour {total} jeux...")

        STRICT_GENRES = {'Racing', 'Sport', 'Fighting', 'Puzzle', 'Strategy', 'Simulator'}
        
        STOPWORDS = {
            'the', 'a', 'an', 'and', 'or', 'of', 'to', 'in', 'on', 'at', 'with', 'by', 'from',
            'game', 'play', 'player', 'world', 'story', 'new', 'best', 'experience', 'character',
            'level', 'mode', 'edition', 'version', 'series', 'explore', 'fight', 'action', 'adventure',
            'gameplay', 'system', 'features', 'time', 'original', 'classic', 'set', 'take', 'control',
            'find', 'make', 'use', 'get', 'one', 'two', 'three', 'first', 'second', 'third'
        }

        count_updated = 0

        for index, game in enumerate(games):
            scores = []
            
            # Pré-calculs
            my_genres = set(game.genres)
            my_themes = set(game.themes)
            my_platforms = set(game.platforms)
            my_keywords = self.extract_keywords(game.summary, STOPWORDS)
            my_title_root = self.get_title_root(game.title)

            for candidate in games:
                if game.id == candidate.id:  # type: ignore
                    continue

                # 1. Filtre Strict (Genres cloisonnés)
                candidate_genres = set(candidate.genres)
                if not self.check_strict_genres(my_genres, candidate_genres, STRICT_GENRES):
                    continue

                # 2. Calcul du Score
                score = 0
                
                # Metadata (Genres & Thèmes)
                score += len(my_genres & candidate_genres) * 2
                score += len(my_themes & set(candidate.themes)) * 5

                # Sémantique (Mots-clés communs)
                candidate_keywords = self.extract_keywords(candidate.summary, STOPWORDS)
                score += len(my_keywords & candidate_keywords) * 3

                # Franchise et Titre
                candidate_title_root = self.get_title_root(candidate.title)
                is_same_franchise = (my_title_root and candidate_title_root and my_title_root == candidate_title_root)
                
                if is_same_franchise:
                    score += 25 
                else:
                    title_sim = SequenceMatcher(None, game.title.lower(), candidate.title.lower()).ratio()
                    if title_sim > 0.75: 
                        score += 10

                # Dates (Proximité temporelle)
                if game.release_year and candidate.release_year:
                    diff = abs(game.release_year - candidate.release_year)
                    if diff <= 3: 
                        score += 4
                    elif diff <= 7: 
                        score += 2

                # Plateforme
                if my_platforms & set(candidate.platforms):
                    score += 1

                # Qualité (Écart de note)
                if game.rating and candidate.rating:
                    if (game.rating - candidate.rating) > 20: 
                        score -= 15

                if score > 12:
                    scores.append({'game': candidate, 'score': score, 'root': candidate_title_root})

            # Tri par score décroissant
            scores.sort(key=lambda x: x['score'], reverse=True)

            # 3. Sélection avec Diversité (Max 2 de la même franchise)
            final_selection = []
            same_franchise_count = 0

            for item in scores:
                if len(final_selection) >= 3:
                    break
                
                candidate = item['game']
                cand_root = item['root']

                # Vérification franchise
                is_family = (cand_root == my_title_root)
                
                if is_family:
                    if same_franchise_count >= 2:
                        continue # On saute ce jeu car quota franchise atteint
                    same_franchise_count += 1
                
                final_selection.append(candidate)

            game.similar_games.set(final_selection)
            count_updated += 1

            if index % 100 == 0:
                self.stdout.write(f"   Processed {index}/{total}")

        self.stdout.write(self.style.SUCCESS(f"Terminé. {count_updated} jeux mis à jour."))

    def check_strict_genres(self, g1, g2, strict_list):
        for genre in strict_list:
            if (genre in g1) != (genre in g2):
                return False
        return True

    def extract_keywords(self, text, stopwords):
        if not text: 
            return set()
        text_clean = re.sub(r'[^\w\s]', '', text.lower())
        words = text_clean.split()
        return {w for w in words if len(w) > 3 and w not in stopwords}

    def get_title_root(self, title):
        if not title: 
            return ""
        t = title.lower()
        t = re.sub(r'\b(i|ii|iii|iv|v|vi|vii|viii|ix|x)\b', '', t) # Enlève chiffres romains isolés
        t = re.sub(r'[^\w\s]', '', t)
        for prefix in ['the ', 'a ', 'super ']:
            if t.startswith(prefix): 
                t = t[len(prefix):]
        words = t.split()
        if len(words) >= 2: 
            return " ".join(words[:2])
        if len(words) == 1: 
            return words[0]
        return t