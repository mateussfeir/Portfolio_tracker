from django import template

register = template.Library()

@register.filter
def currency(value, symbol='$'):
    try:
        value = float(value)
        return f"{symbol}{value:,.2f}"
    except (ValueError, TypeError):
        return f"{symbol}0.00" 