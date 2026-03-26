import re
from django.core.management.base import BaseCommand
from whichgame.models import Game

class Command(BaseCommand):
    help = 'Generates game recommendations based on a weighted score (Semantics, Metadata, Diversity).'

    def handle(self, *args, **options):
        # Base filter: Only process games with at least 5 reviews to ensure quality recommendations
        games = list(Game.objects.filter(total_rating_count__gte=5))
        total = len(games)
        
        if total == 0:
            self.stdout.write(self.style.WARNING("⚠️ No eligible games found for recommendations."))
            return

        self.stdout.write(f"🧠 Processing recommendations for {total} games...")

        strict_genres = {'Racing', 'Sport', 'Fighting', 'Puzzle', 'Strategy', 'Simulator'}
        stopwords = self._get_stopwords()

        count_updated = 0

        # Processing loop
        for index, game in enumerate(games, 1):
            candidates_scores = []
            game_keywords = self._extract_keywords(game.summary, stopwords)
            game_root = self._get_title_root(game.title)

            for candidate in games:
                if game.id == candidate.id: # type: ignore
                    continue

                # 1. Strict Genre Check (e.g., Don't recommend a Racing game for a RPG)
                if not self._check_strict_genres(game.genres, candidate.genres, strict_genres):
                    continue

                score = 0
                
                # 2. Keyword Intersection (Summary semantics)
                candidate_keywords = self._extract_keywords(candidate.summary, stopwords)
                shared_words = game_keywords.intersection(candidate_keywords)
                score += len(shared_words) * 2

                # 3. Metadata Intersection (Genres & Themes)
                shared_genres = set(game.genres).intersection(set(candidate.genres))
                score += len(shared_genres) * 5

                shared_themes = set(game.themes).intersection(set(candidate.themes))
                score += len(shared_themes) * 4

                # 4. Same Franchise / Title similarity penalty or boost
                candidate_root = self._get_title_root(candidate.title)
                if game_root and candidate_root and game_root == candidate_root:
                    score += 15 # Boost for being in the same franchise

                if score > 0:
                    candidates_scores.append((score, candidate))

            # 5. Sort by score descending
            candidates_scores.sort(key=lambda x: x[0], reverse=True)

            # 6. Apply Diversity Filter (Limit games from the exact same franchise)
            final_selection = []
            same_franchise_count = 0

            for score, candidate in candidates_scores:
                if len(final_selection) >= 6: # Store top 6 recommendations
                    break
                
                candidate_root = self._get_title_root(candidate.title)
                if game_root and candidate_root and game_root == candidate_root:
                    if same_franchise_count >= 2:
                        continue # Skip to ensure diversity
                    same_franchise_count += 1
                
                final_selection.append(candidate)

            # 7. Update Database (ManyToMany relation)
            if final_selection:
                game.similar_games.set(final_selection)
            
            count_updated += 1

            if index % 100 == 0:
                self.stdout.write(f"   Processed {index}/{total}")

        self.stdout.write(self.style.SUCCESS(f"✅ Finished. {count_updated} games updated with new recommendations."))

    def _check_strict_genres(self, g1, g2, strict_list):
        """Ensures fundamental genre incompatibilities are respected."""
        for genre in strict_list:
            if (genre in g1) != (genre in g2):
                return False
        return True

    def _get_stopwords(self):
        """Returns a set of common words to ignore during semantic keyword extraction."""
        return {
            'the', 'a', 'an', 'and', 'or', 'of', 'to', 'in', 'on', 'at', 'with', 'by', 'from',
            'game', 'play', 'player', 'world', 'story', 'new', 'best', 'experience', 'character',
            'level', 'mode', 'edition', 'version', 'series', 'explore', 'fight', 'action', 'adventure',
            'gameplay', 'system', 'features', 'time', 'original', 'classic', 'set', 'take', 'control',
            'find', 'make', 'use', 'get', 'one', 'two', 'three', 'first', 'second', 'third'
        }

    def _extract_keywords(self, text, stopwords):
        """Extracts meaningful keywords from a text block."""
        if not text: 
            return set()
        text_clean = re.sub(r'[^\w\s]', '', text.lower())
        words = text_clean.split()
        return {w for w in words if len(w) > 3 and w not in stopwords}

    def _get_title_root(self, title):
        """Extracts the base franchise name from a title to detect sequels/spin-offs."""
        if not title: 
            return ""
        t = title.lower()
        t = re.sub(r'\b(i|ii|iii|iv|v|vi|vii|viii|ix|x)\b', '', t) # Remove isolated roman numerals
        t = re.sub(r'[^\w\s]', '', t)
        for prefix in ['the ', 'a ', 'super ']:
            if t.startswith(prefix):
                t = t[len(prefix):]
        return t.split()[0] if t.split() else ""