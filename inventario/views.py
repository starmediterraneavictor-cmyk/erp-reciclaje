from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import ProtectedError

from .models import Material, Inventario, TipoMaterial, SubgrupoMaterial
from django.http import JsonResponse


# ============================================
# LISTA Y ELIMINAR
# ============================================

@login_required
def lista_inventario(request):
    materiales = Material.objects.all().order_by('nombre')
    context = {
        'materiales': materiales,
    }
    return render(request, 'inventario/lista.html', context)


@login_required
def confirmar_eliminar_material(request, material_id):
    material = get_object_or_404(Material, id=material_id)
    context = {
        'material': material,
    }
    return render(request, 'inventario/confirmar_eliminar.html', context)


@login_required
def eliminar_material(request, material_id):
    material = get_object_or_404(Material, id=material_id)

    if request.method == 'POST':
        nombre = material.nombre
        try:
            material.delete()
            messages.success(request, f'✅ Material "{nombre}" eliminado correctamente')
        except ProtectedError:
            messages.error(request, f'❌ No se puede eliminar "{nombre}": tiene pedidos asociados')
        except Exception as e:
            messages.error(request, f'❌ Error inesperado: {str(e)}')
        return redirect('lista_inventario')

    return redirect('confirmar_eliminar_material', material_id=material_id)


# ============================================
# CREAR Y EDITAR MATERIAL
# ============================================

@login_required
def nuevo_material(request):
    """Formulario para crear un nuevo material"""
    if request.method == 'POST':
        try:
            codigo = request.POST.get('codigo')
            nombre = request.POST.get('nombre')
            tipo_id = request.POST.get('tipo')
            subgrupo_id = request.POST.get('subgrupo')
            unidad = request.POST.get('unidad', 'TN')
            precio_compra = request.POST.get('precio_compra', 0)
            precio_venta = request.POST.get('precio_venta', 0)

            material = Material.objects.create(
                codigo=codigo,
                nombre=nombre,
                tipo_id=tipo_id,
                subgrupo_id=subgrupo_id if subgrupo_id else None,
                unidad=unidad,
                precio_compra=precio_compra,
                precio_venta=precio_venta,
                stock_minimo_critico=request.POST.get('stock_minimo_critico', 100) or 100,
                stock_minimo_bajo=request.POST.get('stock_minimo_bajo', 500) or 500,
            )

            messages.success(request, f'✅ Material "{material.nombre}" creado correctamente')
            return redirect('lista_inventario')
        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')

    context = {
        'tipos': TipoMaterial.objects.all(),
        'subgrupos': SubgrupoMaterial.objects.all(),
    }
    return render(request, 'inventario/nuevo_material.html', context)


@login_required
def editar_material(request, material_id):
    """Formulario para editar un material existente"""
    material = get_object_or_404(Material, id=material_id)

    if request.method == 'POST':
        material.codigo = request.POST.get('codigo')
        material.nombre = request.POST.get('nombre')
        material.tipo_id = request.POST.get('tipo')
        subgrupo_id = request.POST.get('subgrupo')
        material.subgrupo_id = subgrupo_id if subgrupo_id else None
        material.unidad = request.POST.get('unidad', 'TN')
        material.precio_compra = request.POST.get('precio_compra', 0)
        material.precio_venta = request.POST.get('precio_venta', 0)
        material.stock_minimo_critico = request.POST.get('stock_minimo_critico', 100) or 100
        material.stock_minimo_bajo = request.POST.get('stock_minimo_bajo', 500) or 500
        material.save()

        messages.success(request, f'✅ Material "{material.nombre}" actualizado')
        return redirect('lista_inventario')

    context = {
        'material': material,
        'tipos': TipoMaterial.objects.all(),
        'subgrupos': SubgrupoMaterial.objects.all(),
    }
    return render(request, 'inventario/editar_material.html', context)


@login_required
def subgrupos_por_tipo(request, tipo_id):
    """Devuelve en JSON los subgrupos que pertenecen a un tipo"""
    subgrupos = SubgrupoMaterial.objects.filter(tipo_id=tipo_id).order_by('nombre')
    data = [{'id': s.id, 'nombre': s.nombre} for s in subgrupos]
    return JsonResponse({'subgrupos': data})

# ============================================
# DETALLE DEL MATERIAL CON ESTADÍSTICAS
# ============================================

@login_required
def detalle_material(request, material_id):
    """Ficha completa de un material con estadísticas de compras y ventas"""
    from decimal import Decimal
    from pedidos.models import DetallePedido
    
    material = get_object_or_404(Material, id=material_id)
    
    # Stock actual
    try:
        inventario = Inventario.objects.get(material=material)
        stock_actual = inventario.cantidad
    except Inventario.DoesNotExist:
        stock_actual = Decimal('0')
    
    # Compras del material (detalles de pedidos de compra)
    compras = DetallePedido.objects.filter(
        material=material,
        pedido__tipo__in=['COMPRA_MAT', 'MAQUILA'],
    ).select_related('pedido', 'pedido__proveedor').order_by('-pedido__fecha')
    
    # Ventas del material (detalles de pedidos de venta)
    ventas = DetallePedido.objects.filter(
        material=material,
        pedido__tipo__in=['VENTA_MAT', 'TRADE'],
    ).select_related('pedido', 'pedido__cliente').order_by('-pedido__fecha')
    
    # Cálculo de medias ponderadas
    tn_compradas = Decimal('0')
    importe_comprado = Decimal('0')
    transporte_compra = Decimal('0')
    for c in compras:
        tn = Decimal(str(c.cantidad))
        tn_compradas += tn
        importe_comprado += tn * Decimal(str(c.precio_unitario))
        transporte_compra += Decimal(str(c.transporte))
    
    tn_vendidas = Decimal('0')
    importe_vendido = Decimal('0')
    transporte_venta = Decimal('0')
    for v in ventas:
        tn = Decimal(str(v.cantidad))
        tn_vendidas += tn
        importe_vendido += tn * Decimal(str(v.precio_unitario))
        transporte_venta += Decimal(str(v.transporte))
    
    precio_medio_compra = (importe_comprado / tn_compradas) if tn_compradas > 0 else None
    precio_medio_venta = (importe_vendido / tn_vendidas) if tn_vendidas > 0 else None
    
    # Transporte total y €/tn
    tn_total = tn_vendidas
    transporte_total = transporte_compra + transporte_venta
    transporte_tn = (transporte_total / tn_total) if tn_total > 0 else None
    
    # Beneficio medio €/tn (venta - compra - transporte)
    beneficio_medio = None
    if precio_medio_compra and precio_medio_venta:
        beneficio_medio = precio_medio_venta - precio_medio_compra
        if transporte_tn:
            beneficio_medio -= transporte_tn
    
    # Beneficio total
    beneficio_total = None
    if precio_medio_venta and tn_vendidas > 0:
        beneficio_total = (precio_medio_venta * tn_vendidas) - importe_comprado - transporte_total
    
    # Último precio de compra y venta
    ultimo_compra = compras.first() if compras.exists() else None
    ultimo_venta = ventas.first() if ventas.exists() else None
    
    context = {
        'material': material,
        'stock_actual': stock_actual,
        'compras': compras[:10],
        'ventas': ventas[:10],
        'total_compras': compras.count(),
        'total_ventas': ventas.count(),
        'tn_compradas': tn_compradas,
        'tn_vendidas': tn_vendidas,
        'importe_comprado': importe_comprado,
        'importe_vendido': importe_vendido,
        'precio_medio_compra': precio_medio_compra,
        'precio_medio_venta': precio_medio_venta,
        'beneficio_medio': beneficio_medio,
        'transporte_tn': transporte_tn,              
        'transporte_total': transporte_total,        
        'beneficio_total': beneficio_total,
        'ultimo_compra': ultimo_compra,
        'ultimo_venta': ultimo_venta,
    }
    return render(request, 'inventario/detalle_material.html', context)