from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import Game

class StaticViewSitemap(Sitemap):
    """Gère les pages statiques (Accueil et Explorer)"""
    priority = 0.9
    changefreq = 'daily'

    def items(self):
        return ['home', 'game_list']

    def location(self, item):
        return reverse(item)

class GameSitemap(Sitemap):
    """Gère les liens directs vers chaque jeu"""
    priority = 0.6
    changefreq = 'weekly'

    def items(self):
        return Game.objects.filter(slug__isnull=False).order_by('id')

    def location(self, obj):
        return f"/explorer/?search={obj.slug}" # type: ignore