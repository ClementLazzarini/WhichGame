from django.db import models

class Game(models.Model):
    igdb_id = models.IntegerField(unique=True, null=True, blank=True, db_index=True)
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    cover_url = models.URLField(blank=True, max_length=500)
    platforms = models.JSONField(default=list)
    genres = models.JSONField(default=list)
    rating = models.IntegerField(null=True, blank=True , db_index=True)      
    price_current = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, db_index=True) 
    playtime_main = models.IntegerField(null=True, blank=True, db_index=True)
    release_year = models.IntegerField(null=True, blank=True, db_index=True)
    game_type = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True) 
    
    def __str__(self):
        return self.title