from django import template

register = template.Library()

@register.filter
def intcomma2(value, decimal_places=2):
    try:
        value = float(value)
        return f"{value:,.{decimal_places}f}"
    except (ValueError, TypeError):
        return value

@register.filter
def index(List, i):
    try:
        return List[i]
    except (IndexError, TypeError, ValueError):
        return ''
