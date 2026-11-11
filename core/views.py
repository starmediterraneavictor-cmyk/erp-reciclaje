from django.shortcuts import render
from django.db.models import Sum, Count
from datetime import datetime
from decimal import Decimal

from pedidos.models import Pedido, DetallePedido, recalcular_stock_material
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
    # STOCK TOTAL (REAL + PREVISIÓN)
    # ============================================
    stock_total_real = Decimal('0')
    stock_total_prevision = Decimal('0')
    materiales_con_stock = []

    for mat in Material.objects.all():
        # 🆕 Usamos la función unificada para el stock real
        stock_real = recalcular_stock_material(mat)
        
        # 🆕 Calculamos la previsión por separado
        detalles_prevision = DetallePedido.objects.filter(
            material=mat,
            pedido__tipo__in=['COMPRA_MAT', 'MAQUILA'],
            pedido__estado='PREVISION'
        )
        stock_prev = sum(d.cantidad for d in detalles_prevision)

        if stock_real > 0 or stock_prev > 0:
            stock_total_real += stock_real
            stock_total_prevision += stock_prev
            materiales_con_stock.append({
                'nombre': mat.nombre,
                'codigo': mat.codigo,
                'stock_real': float(stock_real),
                'stock_prevision': float(stock_prev),
                'stock_total': float(stock_real + stock_prev),
            })
            
    stock_total = float(stock_total_real) + float(stock_total_prevision)
    materiales_con_stock.sort(key=lambda x: x['stock_total'], reverse=True)

    # ============================================
    # DEMANDA NACIONAL / INTERNACIONAL (por país)
    # ============================================
    paises = (
        Cliente.objects
        .exclude(pais__isnull=True)
        .exclude(pais='')
        .values('pais')
        .annotate(total=Count('id'))
        .order_by('-total')[:3]
    )

    demanda = []
    for p in paises:
        pedidos_pais = Pedido.objects.filter(
            cliente__pais=p['pais'],
            tipo='VENTA_MAT',
        ).count()
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
        'stock_total_real': float(stock_total_real),
        'stock_total_prevision': float(stock_total_prevision),
        'materiales': materiales_con_stock,
        'demanda': demanda,
    }
    return render(request, 'core/dashboard.html', context)

@login_required
def manual_usuario(request):
    """Página de manual de usuario con guías rápidas"""
    return render(request, 'core/manual_usuario.html')