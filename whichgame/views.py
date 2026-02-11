import io
import time

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect
from django.core.management import call_command
from django.contrib import messages
from django.utils.html import format_html
from django.http import HttpResponse
from django.template import Template, RequestContext
from django.views.generic import ListView, TemplateView
from django.db.models import Q
from .models import Game , GameCollection

class HomeListView(ListView):
    model = Game
    paginate_by = 24

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Récupération des paramètres GET
        price = self.request.GET.get('price')
        duration = self.request.GET.get('duration')
        platform = self.request.GET.get('platform')
        genre = self.request.GET.get('genre')
        year = self.request.GET.get('year')
        search = self.request.GET.get('search')
        wishlist_ids = self.request.GET.get('wishlist_ids')

        # 1. Barre de Recherche (Recherche dans le titre OU le slug)
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(slug__icontains=search)
            )

        # 2. Filtre Prix
        if price:
            try:
                price_val = float(price)
                # On garde les jeux MOINS CHERS que la limite OU ceux qui n'ont PAS DE PRIX (None)
                queryset = queryset.filter(
                    Q(price_current__lte=price_val) | Q(price_current__isnull=True)
                )
            except ValueError:
                pass

        # 3. Filtre Durée
        if duration == 'short':
            queryset = queryset.filter(playtime_main__lte=10)
        elif duration == 'medium':
            queryset = queryset.filter(playtime_main__gt=10, playtime_main__lte=30)
        elif duration == 'long':
            queryset = queryset.filter(playtime_main__gt=30)

        # 4. Filtre Plateforme (JSONField)
        if platform:
            # Comme platforms est une liste JSON ["PC", "PS5"], on utilise 'icontains'
            # pour voir si le mot existe dans la liste.
            queryset = queryset.filter(platforms__icontains=platform)
        
        # 5. Filtre Genre (JSONField)
        if genre:
            queryset = queryset.filter(genres__icontains=genre)

        # 6. Filtre Année
        year_min = self.request.GET.get('year_min')
        year_max = self.request.GET.get('year_max')

        if year_min:
            try:
                queryset = queryset.filter(release_year__gte=int(year_min))
            except ValueError:
                pass
        
        if year_max:
            try:
                queryset = queryset.filter(release_year__lte=int(year_max))
            except ValueError:
                pass
        
       
        if wishlist_ids:
            try:
                ids_list = [int(id) for id in wishlist_ids.split(',')]
                queryset = queryset.filter(id__in=ids_list)
            except ValueError:
                pass

        params = self.request.GET.copy()
        
        if 'page' in params:
            del params['page']

        if params:
             queryset = queryset.filter(total_rating_count__gte=5)
             return queryset.order_by('-rating', '-total_rating_count')

        return queryset.order_by('-total_rating_count', '-rating')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # On envoie la liste des plateformes pour le menu déroulant
        # (Pour un MVP, on les écrit en dur pour éviter des requêtes complexes sur JSON)
        context['platforms_list'] = [
            "PC", "Mac", "Linux", 
            "PlayStation 5", "PlayStation 4", 
            "Xbox Series X|S", "Xbox One", 
            "Nintendo Switch"
        ]

        # Liste des genres populaires (Statique pour MVP)
        context['genres_list'] = [
            "Role-playing (RPG)", "Adventure", "Shooter", 
            "Platform", "Puzzle", "Strategy", "Indie", 
            "Sport", "Racing", "Fighting", "Simulator"
        ]
        
        return context


class HomeView(TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # On récupère toutes les collections actives, triées par ordre
        # .prefetch_related('games') est CRUCIAL pour la performance (évite 50 requêtes SQL)
        context['collections'] = GameCollection.objects.filter(
            is_active=True
        ).order_by('display_order').prefetch_related('games')
        
        return context


@staff_member_required
def delete_game(request, pk):
    game = get_object_or_404(Game, pk=pk)
    game.delete()
    return redirect(request.META.get('HTTP_REFERER', 'home'))


@staff_member_required
def run_command(request, cmd_name):
    """
    Lance une commande SANS argument (ex: Recalcul IA, Import Global)
    """
    # Liste blanche
    ALLOWED_COMMANDS = {
        'import_games': "Import Global des Jeux",
        'calculate_recommendations': "Recalcul de l'IA",
    }
    
    # 1. Vérification
    if cmd_name not in ALLOWED_COMMANDS:
        messages.error(request, f"⛔ Commande '{cmd_name}' inconnue.")
        return redirect('admin:index')

    print(f"🚀 [ADMIN] Lancement de la commande : {cmd_name}...") # Log console

    try:
        start_time = time.time()
        
        # 2. Capture des logs
        out = io.StringIO()
        
        # Astuce : On passe stdout ET stderr pour capturer les erreurs aussi
        call_command(cmd_name, stdout=out, stderr=out)
        
        result = out.getvalue()
        duration = round(time.time() - start_time, 2)
        
        print(f"✅ [ADMIN] Terminé en {duration}s") # Log console

        # 3. Message de succès (limité à 1000 caractères pour ne pas casser l'affichage)
        short_result = (result[:1000] + '...') if len(result) > 1000 else result
        
        messages.success(request, format_html(
            f"✅ <b>{ALLOWED_COMMANDS[cmd_name]}</b> terminé en {duration}s !<br>"
            f"<div style='background:#1e293b; color:#10b981; padding:10px; border-radius:5px; "
            f"max-height:200px; overflow-y:auto; font-family:monospace; margin-top:5px;'>"
            f"{short_result.replace(chr(10), '<br>')}"
            f"</div>"
        ))

    except Exception as e:
        print(f"❌ [ADMIN] Erreur : {str(e)}") # Log console
        messages.error(request, f"❌ Erreur critique : {str(e)}")

    # 4. Redirection FORCÉE vers l'accueil admin (plus sûr que Referer)
    return redirect('admin:index')


@staff_member_required
def import_franchise_view(request):
    """
    Affiche un petit formulaire pour choisir la franchise à importer
    """
    if request.method == "POST":
        franchise_name = request.POST.get("franchise_name")
        if franchise_name:
            try:
                out = io.StringIO()
                call_command('import_franchise', franchise_name, stdout=out, stderr=out)
                result = out.getvalue()
                messages.success(request, format_html(f"✅ Import de <b>{franchise_name}</b> terminé !<br><pre>{result}</pre>"))
            except Exception as e:
                messages.error(request, f"❌ Erreur : {str(e)}")
        else:
            messages.warning(request, "Veuillez entrer un nom.")
            
        return redirect('admin:index')

    # --- LE TEMPLATE HTML ---
    html_content = """
    {% extends "admin/base_site.html" %}
    
    {% block content %}
    <div style="max-width: 500px; margin: 40px auto; background: #1e293b; padding: 30px; border-radius: 10px; color: white; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
        <h1 style="color: #a78bfa; margin-bottom: 20px; font-size: 1.5rem;"><i class="fas fa-boxes"></i> Importer une Franchise</h1>
        
        <form method="POST">
            {% csrf_token %}
            <label style="display:block; margin-bottom:10px; color: #cbd5e1;">Nom de la franchise (ex: Mario, Zelda) :</label>
            
            <input type="text" name="franchise_name" placeholder="Tapez ici..." 
                   style="width: 100%; padding: 12px; border-radius: 6px; border: 1px solid #475569; margin-bottom: 20px; background: #0f172a; color: white;" required>
            
            <button type="submit" 
                    style="background: #7c3aed; color: white; padding: 12px 20px; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; width: 100%; transition: background 0.3s;">
                Lancer l'import 🚀
            </button>
        </form>
        
        <br>
        <div style="text-align: center;">
            <a href="/admin/" style="color: #94a3b8; text-decoration: none; font-size: 0.9rem;">← Retour au tableau de bord</a>
        </div>
    </div>
    {% endblock %}
    """
    
    # --- RENDU CORRECT AVEC REQUESTCONTEXT ---
    template = Template(html_content)
    
    # RequestContext prend 'request' en 1er argument.
    # Il injecte AUTOMATIQUEMENT : user, messages, csrf_token, perms... et request !
    context = RequestContext(request, {
        'site_header': 'WhichGame Admin',
        'site_title': 'WhichGame Admin',
    })
    
    return HttpResponse(template.render(context))