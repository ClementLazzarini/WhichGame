from django.urls import path
from .views import HomeListView, HomeView

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('explorer/', HomeListView.as_view(), name='game_list'),
]