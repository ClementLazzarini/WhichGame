from django.urls import path
from .views import HomeListView, HomeView, GameDetailView, delete_game

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('explorer/', HomeListView.as_view(), name='game_list'),
    path('game/<slug:slug>/', GameDetailView.as_view(), name='game_detail'),
    path('game/<int:pk>/delete/', delete_game, name='delete_game'),
]