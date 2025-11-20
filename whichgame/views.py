from django.views.generic import ListView
from .models import Game

class HomeListView(ListView):
    model = Game
