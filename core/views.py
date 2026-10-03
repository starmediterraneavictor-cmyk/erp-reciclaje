from django.shortcuts import render
from django.db.models import Sum, Count
from datetime import datetime
from pedidos.models import Pedido
from finanzas.models import Factura
from clientes.models import Cliente
from inventario.models import Material, Inventario
from django.contrib.auth.decorators import login_required

@login_required
def dashboard(request):
    hoy = datetime.now()
    
    # ============================================
    # CONTAR REGISTROS
    # ============================================
    total_pedidos = Pedido.objects.count()
    pedidos_venta = Pedido.objects.filter(tipo__in=['VENTA_MAT']).count()
    pedidos_compra = Pedido.objects.filter(tipo__in=['COMPRA_MAT', 'MAQUILA']).count()
    total_clientes = Cliente.objects.count()
    total_materiales = Material.objects.count()
    
    # ============================================
    # INGRESOS DEL MES
    # ============================================
    total_ingresos = Factura.objects.filter(
        tipo='INGRESO',
        fecha__month=hoy.month,
        fecha__year=hoy.year
    ).aggregate(total=Sum('total'))['total'] or 0
    
    # ============================================
    # STOCK TOTAL
    # ============================================
    stock_total = Inventario.objects.aggregate(
        total=Sum('cantidad')
    )['total'] or 0
    
    # ============================================
    # MATERIALES CON MARGEN
    # ============================================
    materiales = []
    for m in Material.objects.all()[:5]:
        margen = 0
        if m.precio_compra and float(m.precio_compra) > 0:
            margen = ((float(m.precio_venta) - float(m.precio_compra)) / float(m.precio_compra)) * 100
        
        if margen > 30:
            color = 'success'
        elif margen > 15:
            color = 'warning'
        else:
            color = 'danger'
        
        try:
            inv = Inventario.objects.get(material=m)
            stock = float(inv.cantidad)
        except Inventario.DoesNotExist:
            stock = 0
        
        materiales.append({
            'nombre': m.nombre,
            'codigo': m.codigo,
            'stock': stock,
            'margen': round(margen, 1),
            'color': color,
        })
    
    # ============================================
    # DEMANDA INTERNACIONAL
    # ============================================
    paises = Cliente.objects.values('pais').annotate(
        total=Count('id')
    ).order_by('-total')[:3]
    
    demanda = []
    for p in paises:
        if p['pais']:
            pedidos_pais = Pedido.objects.filter(cliente__pais=p['pais']).count()
            demanda.append({
                'pais': p['pais'],
                'pedidos': pedidos_pais,
            })
    
    # ============================================
    # CONTEXTO
    # ============================================
    context = {
        'fecha': hoy,
        'total_pedidos': total_pedidos,
        'pedidos_venta': pedidos_venta,
        'pedidos_compra': pedidos_compra,
        'total_clientes': total_clientes,
        'total_materiales': total_materiales,
        'total_ingresos': total_ingresos,
        'stock_total': stock_total,
        'materiales': materiales,
        'demanda': demanda,
    }
    return render(request, 'core/dashboard.html', context)