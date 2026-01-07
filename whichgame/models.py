from django.db import models

class Game(models.Model):
    # --- Identifiants ---
    igdb_id = models.IntegerField(unique=True, null=True, blank=True, db_index=True)
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    
    # --- Infos Principales ---
    cover_url = models.URLField(blank=True, max_length=500)
    summary = models.TextField(null=True, blank=True)  # Indispensable pour l'IA (analyse sémantique)
    
    # --- Système de Recommandation (IA) ---
    # related_name='related_from' permet d'avoir la relation inverse si besoin
    similar_games = models.ManyToManyField('self', blank=True, symmetrical=False, related_name='recommended_by')
    
    # --- Données de Classification (Nourriture pour l'IA) ---
    platforms = models.JSONField(default=list)
    genres = models.JSONField(default=list)
    themes = models.JSONField(default=list, blank=True) # NOUVEAU : ex ["Survival", "Sci-Fi"]
    
    # --- Chiffres & Dates ---
    rating = models.IntegerField(null=True, blank=True, db_index=True)      
    total_rating_count = models.IntegerField(null=True, blank=True, db_index=True) # Filtre Anti-Poubelle
    price_current = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, db_index=True) 
    playtime_main = models.IntegerField(null=True, blank=True, db_index=True)
    
    release_year = models.IntegerField(null=True, blank=True, db_index=True)
    first_release_date = models.DateField(null=True, blank=True) # NOUVEAU : Date précise
    
    # --- Technique ---
    game_type = models.IntegerField(default=0) # 0=Main, 8=Remake...
    remake_slug = models.CharField(max_length=255, null=True, blank=True)
    video_id = models.CharField(max_length=50, null=True, blank=True)
    screenshots = models.JSONField(default=list, blank=True)
    
    updated_at = models.DateTimeField(auto_now=True) 
    
    def __str__(self):
        return self.title