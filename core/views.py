from django.shortcuts import render
from django.db.models import Sum, Count
from datetime import datetime
from pedidos.models import Pedido
from finanzas.models import Factura
from clientes.models import Cliente
from inventario.models import Material, Inventario
from django.contrib.auth.decorators import login_required
from inventario.models import Inventario, Material
from pedidos.models import DetallePedido, OrigenVenta
from decimal import Decimal


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
    # INGRESOS (MES ACTUAL Y TOTAL HISTÓRICO)
    # ============================================
    ingresos_mes = Factura.objects.filter(
        tipo='INGRESO',
        fecha__month=hoy.month,
        fecha__year=hoy.year
    ).exclude(estado_pago='ANULADO').aggregate(total=Sum('total'))['total'] or 0
    
    ingresos_totales = Factura.objects.filter(
        tipo='INGRESO'
    ).exclude(estado_pago='ANULADO').aggregate(total=Sum('total'))['total'] or 0
    
    # ============================================
    # STOCK TOTAL (RECALCULADO DESDE CERO)
    # ============================================
        
    stock_total = 0
    materiales_con_stock = []

    for mat in Material.objects.all():
        total_disponible = Decimal('0')
        
        # Buscar todos los pedidos de compra/maquila de este material
        detalles_compra = DetallePedido.objects.filter(
            material=mat,
            pedido__tipo__in=['COMPRA_MAT', 'MAQUILA']
        ).exclude(pedido__estado__in=['CANCELADO', 'PREVISION'])
        
        for detalle in detalles_compra:
            pedido = detalle.pedido
            
            # Cuánto se ha comprado en esta línea
            tn_compradas_linea = detalle.cantidad
            
            # Cuánto se ha asignado a ventas
            tn_asignadas = sum(o.cantidad_tn for o in pedido.ventas_asociadas.all())
            
            # Lo que queda libre
            libre = tn_compradas_linea - tn_asignadas
            if libre > 0:
                total_disponible += libre
        
        # Actualizar el inventario en la base de datos (para que coincida)
        try:
            inv = Inventario.objects.get(material=mat)
        except Inventario.DoesNotExist:
            inv = Inventario(material=mat)
        
        inv.cantidad = total_disponible
        inv.save()
        
        # Solo añadir a la lista si tiene stock > 0
        if total_disponible > 0:
            stock_total += float(total_disponible)
            materiales_con_stock.append({
                'nombre': mat.nombre,
                'codigo': mat.codigo,
                'stock': float(total_disponible),
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
        'ingresos_mes': ingresos_mes,
        'ingresos_totales': ingresos_totales,
        'stock_total': stock_total,
        'materiales': materiales_con_stock,
        'demanda': demanda,
    }
    return render(request, 'core/dashboard.html', context)