from django.db import models

class Game(models.Model):
    # ID technique IGDB (CRUCIAL pour les mises à jour sans doublons)
    igdb_id = models.IntegerField(unique=True, null=True, blank=True)
    
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True) # J'ai augmenté la taille, certains slugs sont longs
    cover_url = models.URLField(blank=True, max_length=500) # Parfois les URL sont longues
    
    # Filtres principaux (JSONField est parfait ici)
    platforms = models.JSONField(default=list) # ex: ["PC", "PS5"]
    genres = models.JSONField(default=list)    # ex: ["RPG", "Action"]
    
    # Les stats
    rating = models.IntegerField(null=True, blank=True)      
    price_current = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True) 
    playtime_main = models.IntegerField(null=True, blank=True) # En heures
    
    updated_at = models.DateTimeField(auto_now=True) 
    
    def __str__(self):
        return self.title