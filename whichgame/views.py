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
        search = self.request.GET.get('search')

        # 1. Barre de Recherche (Recherche dans le titre OU le slug)
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(slug__icontains=search)
            )

        # 2. Filtre Prix
        if price:
            try:
                queryset = queryset.filter(price_current__lte=float(price))
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
        return context
