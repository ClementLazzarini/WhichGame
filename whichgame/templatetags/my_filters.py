from django import template

register = template.Library()

# Ce décorateur permet d'accéder au contexte (donc à 'request')
@register.simple_tag(takes_context=True)
def url_replace(context, **kwargs):
    """
    Retourne une chaîne de paramètres URL encodée.
    Prend les paramètres GET existants et met à jour ou supprime ceux passés en argument.
    Usage: {% url_replace page=3 price=None %}
    """
    # On fait une copie du dictionnaire des paramètres GET actuels (ex: ?price=50&duration=short)
    query = context['request'].GET.copy()

    for key, value in kwargs.items():
        if value is None:
            # Si on passe "None", on supprime le filtre (Reset)
            query.pop(key, None)
        else:
            # Sinon on met à jour ou on ajoute la valeur
            query[key] = value

    # On retourne le tout formaté pour l'URL (ex: "price=50&duration=long")
    return query.urlencode()