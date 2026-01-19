from django.contrib import admin
from .models import Game, GameCollection

class GameAdmin(admin.ModelAdmin):
    # 1. LA BARRE DE RECHERCHE 🔍
    # Permet de chercher par Titre OU par Slug (utile si deux jeux ont le même nom)
    search_fields = ['title', 'slug']

    # 2. LES COLONNES VISIBLES DANS LA LISTE 📋
    # Affiche ces infos directement dans le tableau
    list_display = ('title', 'rating', 'total_rating_count', 'price_current', 'playtime_main', 'release_year')

    # 3. FILTRES LATÉRAUX (Optionnel mais pratique)
    # Pour filtrer rapidement par année ou type de jeu (Main, Remake...)
    list_filter = ('release_year', 'game_type')

    # 4. ÉDITION RAPIDE (Optionnel)
    # Permet de modifier le temps de jeu directement depuis la liste sans ouvrir la fiche !
    list_editable = ('playtime_main', 'price_current')

@admin.register(GameCollection)
class GameCollectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'theme_color', 'is_active', 'display_order', 'count_games')
    list_editable = ('is_active', 'display_order', 'theme_color')
    filter_horizontal = ('games',) # Indispensable pour gérer facilement la liste des jeux
    search_fields = ('title',)

    def count_games(self, obj):
        return obj.games.count()
    count_games.short_description = "Jeux inclus"

admin.site.register(Game, GameAdmin)

admin.site.site_header = "WhichGame Administration"
admin.site.site_title = "WhichGame Portal"
admin.site.index_title = "Bienvenue dans la tour de contrôle"