"""
URL configuration for config project.
"""
from django.contrib import admin
from . import settings
from django.conf.urls.static import static
from django.urls import path, include
from django.views.generic import TemplateView
from whichgame.views import run_command, import_franchise_view
from django.contrib.sitemaps.views import sitemap
from whichgame.sitemaps import StaticViewSitemap, GameSitemap
from django.conf.urls.i18n import i18n_patterns # 👈 NOUVEL IMPORT

sitemaps = {
    'static': StaticViewSitemap,
    'games': GameSitemap,
}

# ---------------------------------------------------------
# 1. URLs TECHNIQUES (Ne changent pas selon la langue)
# ---------------------------------------------------------
urlpatterns = [
    # Route vitale pour le fonctionnement du sélecteur de langue (Phase 5)
    path('i18n/', include('django.conf.urls.i18n')),
    
    # Fichiers SEO obligatoires à la racine pure du domaine
    path('robots.txt', TemplateView.as_view(template_name="robots.txt", content_type="text/plain")),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
]

# ---------------------------------------------------------
# 2. URLs TRADUITES (Auront le préfixe /fr/ ou rien pour l'anglais)
# ---------------------------------------------------------
urlpatterns += i18n_patterns(
    # Tes routes principales
    path('', include('whichgame.urls')),
    
    # Tes routes d'administration et scripts
    path('admin/cmd/<str:cmd_name>/', run_command, name='run_admin_command'),
    path('admin/wizard/franchise/', import_franchise_view, name='import_franchise_wizard'),
    path('admin/', admin.site.urls),
    
    # Tes pages statiques
    path('about/', TemplateView.as_view(template_name="about.html"), name='about'),
    path('legal/', TemplateView.as_view(template_name="legal.html"), name='legal'),
    
    # False = l'anglais sera sur mondomaine.com/ et le français sur mondomaine.com/fr/
    prefix_default_language=False 
)

# Fichiers statiques et médias en mode développement
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)