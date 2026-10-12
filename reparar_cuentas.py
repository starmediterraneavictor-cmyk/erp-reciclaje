"""
Script para reparar importes de cuentas.
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from finanzas.models import CuentaPorCobrar, CuentaPorPagar
from decimal import Decimal

# Cuentas por cobrar
for c in CuentaPorCobrar.objects.all():
    total_cobrado = sum((cobro.importe for cobro in c.cobros.all()), Decimal('0'))
    if total_cobrado != c.importe_cobrado:
        print(f"Reparando {c.concepto}: importe_cobrado {c.importe_cobrado} -> {total_cobrado}")
        c.importe_cobrado = total_cobrado
        c.save()
    
    # Recalcular estado
    if c.importe_cobrado >= c.importe_total:
        c.estado = 'COBRADO'
    elif c.importe_cobrado > 0:
        c.estado = 'PARCIAL'
    else:
        c.estado = 'PENDIENTE'
    c.save()

# Cuentas por pagar
for c in CuentaPorPagar.objects.all():
    total_pagado = sum((pago.importe for pago in c.pagos.all()), Decimal('0'))
    if total_pagado != c.importe_pagado:
        print(f"Reparando {c.concepto}: importe_pagado {c.importe_pagado} -> {total_pagado}")
        c.importe_pagado = total_pagado
        c.save()
    
    if c.importe_pagado >= c.importe_total:
        c.estado = 'PAGADO'
    elif c.importe_pagado > 0:
        c.estado = 'PARCIAL'
    else:
        c.estado = 'PENDIENTE'
    c.save()

print("✅ Completado")