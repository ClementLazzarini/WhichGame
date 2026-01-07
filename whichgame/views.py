from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import ListView, TemplateView
from django.db.models import Q
from .models import Game 
import datetime

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
            ('2025', '2025 - 2026'),
            ('2024', 'Après 2024'),
            ('2020', 'Après 2020'),
            ('2015', 'Après 2015'),
            ('2010', 'Après 2010'),
            ('retro', 'Rétro (Avant 2010)')
        ]
        return context


class HomeView(TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # --- FILTRE QUALITÉ GLOBAL (LE GARDEN KEEPER 🛡️) ---
        # On définit ici les critères stricts pour apparaître sur l'accueil.
        base_qs = Game.objects.filter(
            rating__isnull=False,           # Doit avoir une note
            cover_url__isnull=False,        # Doit avoir une jaquette
            playtime_main__gt=0,            # Doit durer plus de 0h (Exit les "Unknown")
            price_current__isnull=False     # Doit avoir un prix connu (Même 0€ c'est ok, mais pas None)
        ).exclude(cover_url="")             # Sécurité supplémentaire pour les chaines vides

        # 1. LES INCONTOURNABLES (Note > 90)
        context['top_rated'] = base_qs.filter(rating__gte=90).order_by('-rating')[:4]

        # 2. LES DERNIÈRES PÉPITES (Sorties Récentes + Bonne note)
        current_year = datetime.date.today().year
        context['new_releases'] = base_qs.filter(
            release_year__gte=current_year-1, 
            rating__gte=80
        ).order_by('-release_year', '-rating')[:4]

        # 3. PETITS BUDGETS (Moins de 10€ et > 80 de note)
        # Note : price_current__gt=0 exclut les jeux Gratuits ici. 
        context['budget_gems'] = base_qs.filter(
            price_current__lt=10, 
            price_current__gt=0,
            rating__gte=80
        ).order_by('-rating')[:4]

        # 4. COURTES AVENTURES (Moins de 10h et > 85 de note)
        context['short_games'] = base_qs.filter(
            playtime_main__lte=10,
            rating__gte=85
        ).order_by('-rating')[:4]

        return context


@staff_member_required
def delete_game(request, pk):
    game = get_object_or_404(Game, pk=pk)
    game.delete()
    return redirect(request.META.get('HTTP_REFERER', 'home'))