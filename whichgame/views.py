# views.py
from django.views.generic import ListView
from django.db.models import Q
from .models import Game 

class HomeListView(ListView):
    model = Game
    paginate_by = 24

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Récupération des paramètres GET
        price = self.request.GET.get('price')
        duration = self.request.GET.get('duration')
        platform = self.request.GET.get('platform')
        genre = self.request.GET.get('genre')
        year = self.request.GET.get('year')
        search = self.request.GET.get('search')
        wishlist_ids = self.request.GET.get('wishlist_ids')

        # 1. Barre de Recherche (Recherche dans le titre OU le slug)
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(slug__icontains=search)
            )

        # 2. Filtre Prix
        if price:
            try:
                price_val = float(price)
                # On garde les jeux MOINS CHERS que la limite OU ceux qui n'ont PAS DE PRIX (None)
                queryset = queryset.filter(
                    Q(price_current__lte=price_val) | Q(price_current__isnull=True)
                )
            except ValueError:
                pass

        # 3. Filtre Durée
        if duration == 'short':
            queryset = queryset.filter(playtime_main__lte=10)
        elif duration == 'medium':
            queryset = queryset.filter(playtime_main__gt=10, playtime_main__lte=30)
        elif duration == 'long':
            queryset = queryset.filter(playtime_main__gt=30)

        # 4. Filtre Plateforme (JSONField)
        if platform:
            # Comme platforms est une liste JSON ["PC", "PS5"], on utilise 'icontains'
            # pour voir si le mot existe dans la liste.
            queryset = queryset.filter(platforms__icontains=platform)
        
        # 5. Filtre Genre (JSONField)
        if genre:
            queryset = queryset.filter(genres__icontains=genre)

        # 6. Filtre Année
        if year:
            try:
                if year == 'retro':
                    queryset = queryset.filter(release_year__lt=2010)
                else:
                    year_val = int(year)
                    queryset = queryset.filter(release_year__gte=year_val)
            except ValueError:
                pass
        
       
        if wishlist_ids:
            try:
                ids_list = [int(id) for id in wishlist_ids.split(',')]
                queryset = queryset.filter(id__in=ids_list)
            except ValueError:
                pass

        return queryset.order_by('-rating') # On trie par note par défaut
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # On envoie la liste des plateformes pour le menu déroulant
        # (Pour un MVP, on les écrit en dur pour éviter des requêtes complexes sur JSON)
        context['platforms_list'] = [
            "PC", "Mac", "Linux", 
            "PlayStation 5", "PlayStation 4", 
            "Xbox Series X|S", "Xbox One", 
            "Nintendo Switch"
        ]

        # Liste des genres populaires (Statique pour MVP)
        context['genres_list'] = [
            "Role-playing (RPG)", "Adventure", "Shooter", 
            "Platform", "Puzzle", "Strategy", "Indie", 
            "Sport", "Racing", "Fighting", "Simulator"
        ]
        
        # Format : (valeur_url, etiquette_affichage)
        context['years_list'] = [
            ('2024', '2024 - 2025'),
            ('2023', 'Après 2023'),
            ('2020', 'Après 2020'),
            ('2015', 'Après 2015'),
            ('2010', 'Après 2010'),
            ('retro', 'Rétro (Avant 2010)')
        ]
        return context
