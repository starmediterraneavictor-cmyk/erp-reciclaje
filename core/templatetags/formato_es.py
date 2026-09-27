from django import template
from decimal import Decimal, InvalidOperation

register = template.Library()


@register.filter
def formato_es(valor):
    """
    Formatea un número al estilo español: 1.234.567,89
    Uso: {{ valor|formato_es }}
    """
    if valor is None or valor == '':
        return '0,00'
    
    try:
        # Convertir a float
        num = float(valor)
    except (ValueError, TypeError, InvalidOperation):
        return valor
    
    # Formatear con separador de miles inglés (comas) y decimales con punto
    formateado = f"{num:,.2f}"
    # Intercambiar: coma→X, punto→coma, X→punto
    formateado = formateado.replace(',', 'X').replace('.', ',').replace('X', '.')
    return formateado


@register.filter
def formato_es_sin_decimales(valor):
    """
    Formatea un número sin decimales al estilo español: 1.234.567
    """
    if valor is None or valor == '':
        return '0'
    
    try:
        num = float(valor)
    except (ValueError, TypeError, InvalidOperation):
        return valor
    
    formateado = f"{num:,.0f}"
    formateado = formateado.replace(',', 'X').replace('.', ',').replace('X', '.')
    return formateado