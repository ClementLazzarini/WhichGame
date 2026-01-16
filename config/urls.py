"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from . import settings
from django.conf.urls.static import static
from django.urls import path, include
from django.views.generic import TemplateView
from django.contrib.sitemaps.views import sitemap
from whichgame.sitemaps import StaticViewSitemap, GameSitemap

sitemaps = {
    'static': StaticViewSitemap,
    'games': GameSitemap,
}

urlpatterns = [
    path('', include('whichgame.urls')),
    path('admin/', admin.site.urls),
    path('about/', TemplateView.as_view(template_name="about.html"), name='about'),
    path('legal/', TemplateView.as_view(template_name="legal.html"), name='legal'),
    path('robots.txt', TemplateView.as_view(template_name="robots.txt", 
                                            content_type="text/plain")),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
