# views.py
from django.views.generic import ListView
from .models import Game # Ou ton modèle

class HomeListView(ListView):
    model = Game

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Récupération des paramètres GET
        price = self.request.GET.get('price')
        duration = self.request.GET.get('duration')

        # Filtre Prix
        if price:
            try:
                # On filtre les jeux dont le prix est <= à la valeur
                queryset = queryset.filter(price_current__lte=float(price))
            except ValueError:
                pass # Si l'utilisateur met n'importe quoi dans l'URL

        # Filtre Durée (Logique approximative selon tes données)
        if duration == 'short':
            queryset = queryset.filter(playtime_main__lte=10)
        elif duration == 'medium':
            queryset = queryset.filter(playtime_main__gt=10, playtime_main__lte=30)
        elif duration == 'long':
            queryset = queryset.filter(playtime_main__gt=30)

        return queryset
