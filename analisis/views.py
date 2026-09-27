from django.shortcuts import render
from django.db.models import Sum, Count, Avg
from django.utils import timezone
from datetime import timedelta
from pedidos.models import Pedido, DetallePedido
from finanzas.models import Factura
from inventario.models import Material, Inventario
from clientes.models import Cliente
from datetime import date, timedelta
from decimal import Decimal



def dashboard_analisis(request):
    hoy = timezone.now().date()
    mes_actual = hoy.month
    year_actual = hoy.year

    # ============================================
    # FILTRO DE FECHAS
    # ============================================
    rango = request.GET.get('rango', 'mes')
    hoy = timezone.now().date()
    
    if rango == 'mes':
        fecha_inicio = hoy.replace(day=1)
        fecha_fin = hoy
    elif rango == '3meses':
        fecha_inicio = (hoy.replace(day=1) - timedelta(days=60)).replace(day=1)
        fecha_fin = hoy
    elif rango == '6meses':
        fecha_inicio = (hoy.replace(day=1) - timedelta(days=150)).replace(day=1)
        fecha_fin = hoy
    elif rango == 'año':
        fecha_inicio = date(hoy.year, 1, 1)
        fecha_fin = hoy
    elif rango == 'todo':
        fecha_inicio = date(2020, 1, 1)
        fecha_fin = hoy
    else:
        fecha_inicio = hoy.replace(day=1)
        fecha_fin = hoy
    
    # ============================================
    # BLOQUE 1: ANÁLISIS FINANCIERO
    # ============================================
    facturas_mes = Factura.objects.filter(
        fecha__month=mes_actual,
        fecha__year=year_actual
    )
    
    total_ingresos = facturas_mes.filter(tipo='INGRESO').aggregate(
        total=Sum('total')
    )['total'] or 0
    
    total_gastos = facturas_mes.filter(tipo='GASTO').aggregate(
        total=Sum('total')
    )['total'] or 0
    
    beneficio = total_ingresos - total_gastos
    margen_beneficio = (beneficio / total_ingresos * 100) if total_ingresos > 0 else 0
    
    # Evolución mensual (últimos 6 meses)
    evolucion = []
    for i in range(6):
        mes = mes_actual - i
        year = year_actual
        if mes <= 0:
            mes += 12
            year -= 1
        
        ingresos_mes = Factura.objects.filter(
            tipo='INGRESO', fecha__month=mes, fecha__year=year
        ).aggregate(total=Sum('total'))['total'] or 0
        
        gastos_mes = Factura.objects.filter(
            tipo='GASTO', fecha__month=mes, fecha__year=year
        ).aggregate(total=Sum('total'))['total'] or 0
        
        evolucion.append({
            'etiqueta': f"{mes}/{year}",
            'ingresos': float(ingresos_mes),
            'gastos': float(gastos_mes),
            'beneficio': float(ingresos_mes - gastos_mes),
        })
    evolucion.reverse()
    
     
    # ============================================
    # BLOQUE 2: ANÁLISIS POR CLIENTE
    # ============================================
    clientes_analisis = []
    for cliente in Cliente.objects.all():
        pedidos_cliente = Pedido.objects.filter(
            cliente=cliente,
            fecha__month=mes_actual,
            fecha__year=year_actual
        )
        
        if pedidos_cliente.count() > 0:
            total_cliente = sum(float(p.total_importe) for p in pedidos_cliente)
            ticket_medio = total_cliente / pedidos_cliente.count()
            
            clientes_analisis.append({
                'nombre': cliente.nombre,
                'pais': cliente.pais,
                'pedidos': pedidos_cliente.count(),
                'total': total_cliente,
                'ticket_medio': ticket_medio,
            })
    
    clientes_analisis.sort(key=lambda x: x['total'], reverse=True)
    top_clientes = clientes_analisis[:5]
    
    # ============================================
    # BLOQUE 3: ANÁLISIS DE INVENTARIO
    # ============================================
    inventario_analisis = []
    valor_total_inventario = 0
    alertas_stock = []
    
    for material in Material.objects.all():
        try:
            inv = Inventario.objects.get(material=material)
            cantidad = float(inv.cantidad)
        except Inventario.DoesNotExist:
            cantidad = 0
        
        valor = cantidad * float(material.precio_compra)
        valor_total_inventario += valor
        
        # Estado del stock
        # Usar los umbrales del material (o defaults)
        umbral_critico = float(material.stock_minimo_critico) if material.stock_minimo_critico else 100
        umbral_bajo = float(material.stock_minimo_bajo) if material.stock_minimo_bajo else 500
        
        if cantidad == 0:
            estado = 'Sin stock'
            color_estado = 'danger'
        elif cantidad < umbral_critico:
            estado = 'Crítico'
            color_estado = 'danger'
            alertas_stock.append({
                'material': material.nombre,
                'cantidad': cantidad,
                'faltan': umbral_critico - cantidad,
            })
        elif cantidad < umbral_bajo:
            estado = 'Bajo'
            color_estado = 'warning'
        else:
            estado = 'OK'
            color_estado = 'success'
        
        inventario_analisis.append({
            'nombre': material.nombre,
            'codigo': material.codigo,
            'cantidad': cantidad,
            'valor': valor,
            'estado': estado,
            'color': color_estado,
        })
    
    inventario_analisis.sort(key=lambda x: x['cantidad'], reverse=True)
    
    # ============================================
    # BLOQUE 4: ANÁLISIS INTERNACIONAL
    # ============================================
    # Demanda por país (datos de ejemplo - se pueden reemplazar por modelo)
    demanda_internacional = []
    
    # Agrupar clientes por país
    paises = Cliente.objects.filter(tipo='RECICLAJE').values('pais').annotate(
        total_clientes=Count('id')
    ).order_by('-total_clientes')
    
    for p in paises[:6]:
        pais = p['pais']
        if pais:
            # Obtener pedidos de clientes de ese país
            pedidos_pais = Pedido.objects.filter(
                cliente__pais=pais,
                cliente__tipo='RECICLAJE',
                fecha__month=mes_actual,
                fecha__year=year_actual
                
            )
            
            total_kg = 0
            for pedido in pedidos_pais:
                total_kg += pedido.total_kg
            
            # Determinar interés según actividad
            if pedidos_pais.count() > 3:
                interes = '🔥 Alto'
                color_interes = 'danger'
            elif pedidos_pais.count() > 0:
                interes = '⚡ Medio'
                color_interes = 'warning'
            else:
                interes = '💤 Bajo'
                color_interes = 'secondary'
            
            demanda_internacional.append({
                'pais': pais,
                'clientes': p['total_clientes'],
                'pedidos': pedidos_pais.count(),
                'kg': float(total_kg),
                'interes': interes,
                'color': color_interes,
            })
    
    # ============================================
    # BLOQUE 5: PEDIDOS
    # ============================================
    pedidos_mes = Pedido.objects.filter(
        fecha__month=mes_actual,
        fecha__year=year_actual
    )
    
    total_pedidos = pedidos_mes.count()
    pedidos_completados = pedidos_mes.filter(estado='COMPLETADO').count()
    pedidos_pendientes = pedidos_mes.filter(estado='PENDIENTE').count()

    # ============================================
    # BLOQUE 6: ANÁLISIS €/TN POR MATERIAL
    # ============================================
    # Coger todos los materiales únicos que aparezcan en pedidos del rango
    materiales_ids = DetallePedido.objects.filter(
        pedido__fecha__date__gte=fecha_inicio,
        pedido__fecha__date__lte=fecha_fin,
    ).values_list('material_id', flat=True).distinct()
    
    analisis_por_material = []
    
    for mat_id in materiales_ids:
        try:
            material = Material.objects.get(id=mat_id)
        except Material.DoesNotExist:
            continue
        
        # COMPRAS del material en el rango
        detalles_compra = DetallePedido.objects.filter(
            material=material,
            pedido__tipo__in=['COMPRA_MAT', 'MAQUILA'],
            pedido__fecha__date__gte=fecha_inicio,
            pedido__fecha__date__lte=fecha_fin,
        )
        
        tn_compradas = Decimal('0')
        importe_compra = Decimal('0')
        transporte_compra = Decimal('0')
        for d in detalles_compra:
            tn = Decimal(str(d.cantidad))
            tn_compradas += tn
            importe_compra += tn * Decimal(str(d.precio_unitario))
            transporte_compra += Decimal(str(d.transporte))
        
        precio_compra_tn = (importe_compra / tn_compradas) if tn_compradas > 0 else None
        
        # VENTAS del material en el rango
        detalles_venta = DetallePedido.objects.filter(
            material=material,
            pedido__tipo__in=['VENTA_MAT', 'TRADE'],
            pedido__fecha__date__gte=fecha_inicio,
            pedido__fecha__date__lte=fecha_fin,
        )
        
        tn_vendidas = Decimal('0')
        importe_venta = Decimal('0')
        transporte_venta = Decimal('0')
        beneficio_total = Decimal('0')
        tn_con_beneficio = Decimal('0')
        
        for d in detalles_venta:
            tn = Decimal(str(d.cantidad))
            precio_venta = Decimal(str(d.precio_unitario))
            tn_vendidas += tn
            importe_venta += tn * precio_venta
            transporte_venta += Decimal(str(d.transporte))
            
            # Si la venta tiene pedido_origen → calcular beneficio real
            if d.pedido.pedido_origen:
                compra_origen = d.pedido.pedido_origen
                # Precio medio de compra del pedido origen
                if compra_origen.total_kg > 0:
                    precio_compra_origen = compra_origen.total_importe / compra_origen.total_kg
                    beneficio_linea = (precio_venta - precio_compra_origen) * tn - Decimal(str(d.transporte))
                    beneficio_total += beneficio_linea
                    tn_con_beneficio += tn
        
        precio_venta_tn = (importe_venta / tn_vendidas) if tn_vendidas > 0 else None
        
        # Transporte total €/tn 
        tn_total = tn_vendidas
        transporte_total = transporte_compra + transporte_venta
        transporte_tn = (transporte_total / tn_total) if tn_total > 0 else None
        
        # Beneficio €/tn (solo si tenemos datos de operaciones con origen)
        beneficio_tn = None
        margen_pct = None
        if tn_con_beneficio > 0:
            beneficio_tn = beneficio_total / tn_con_beneficio
            if precio_venta_tn and precio_venta_tn > 0:
                margen_pct = (beneficio_tn / precio_venta_tn) * 100
        
        # Solo añadir si hay movimientos
        if tn_compradas > 0 or tn_vendidas > 0:
            analisis_por_material.append({
                'nombre': material.nombre,
                'codigo': material.codigo,
                'tn_compradas': tn_compradas,
                'precio_compra_tn': precio_compra_tn,
                'tn_vendidas': tn_vendidas,
                'precio_venta_tn': precio_venta_tn,
                'transporte_tn': transporte_tn,
                'beneficio_tn': beneficio_tn,
                'margen_pct': margen_pct,
            })
    
    # Ordenar por volumen (tn compradas + tn vendidas), descendente
    analisis_por_material.sort(
        key=lambda x: x['tn_compradas'] + x['tn_vendidas'],
        reverse=True
    )

    
    # ============================================
    # CONTEXTO FINAL
    # ============================================
    context = {
        # Financiero
        'total_ingresos': float(total_ingresos),
        'total_gastos': float(total_gastos),
        'beneficio': float(beneficio),
        'margen_beneficio': round(margen_beneficio, 1),
        'evolucion': evolucion,
        
        # Materiales
        
        
        # Clientes
        'top_clientes': top_clientes,
        
        # Inventario
        'inventario': inventario_analisis,
        'valor_total_inventario': valor_total_inventario,
        'alertas_stock': alertas_stock,
        
        # Internacional
        'demanda_internacional': demanda_internacional,
        
        # Pedidos
        'total_pedidos': total_pedidos,
        'pedidos_completados': pedidos_completados,
        'pedidos_pendientes': pedidos_pendientes,
        
        # Fecha
        'mes_actual': mes_actual,
        'year_actual': year_actual,
        'fecha': timezone.now(),

        # Análisis €/TN por material
        'analisis_por_material': analisis_por_material,
        'rango_filtro': rango,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
    }
    
    return render(request, 'analisis/dashboard_analisis.html', context)