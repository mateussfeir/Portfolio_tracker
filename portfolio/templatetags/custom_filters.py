from django import template
from decimal import Decimal, InvalidOperation

register = template.Library()

@register.filter
def intcomma2(value, decimal_places=2):
    try:
        value = float(value)
        return f"{value:,.{decimal_places}f}"
    except (ValueError, TypeError):
        return value

@register.filter
def crypto_amount(value, decimal_places=6):
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return value

    return format(decimal_value, f".{decimal_places}f")

@register.filter
def index(List, i):
    try:
        return List[i]
    except (IndexError, TypeError, ValueError):
        return ''
