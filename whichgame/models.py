from django.db import models

class Game(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True) # Pour l'URL et ID IGDB
    cover_url = models.URLField(blank=True)
    
    # Filtres principaux
    platforms = models.JSONField(default=list) # ex: ["PC", "PS5"]
    genres = models.JSONField(default=list)    # ex: ["RPG", "Action"]
    
    # Les stats (Ce que l'utilisateur cherche)
    rating = models.FloatField(null=True)      # Note sur 100
    price_current = models.DecimalField(max_digits=6, decimal_places=2, null=True) # Prix actuel
    playtime_main = models.IntegerField(null=True) # Heures pour finir l'histoire
    
    updated_at = models.DateTimeField(auto_now=True) # Pour savoir quand rafraichir
    
    def __str__(self):
        return self.title