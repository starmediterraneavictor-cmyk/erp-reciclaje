from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from proveedores.models import Proveedor
from django.db.models import Q
from finanzas.models import CuentaPorPagar, CuentaPorCobrar, Factura


from .models import (
    Pedido, DetallePedido,
    PedidoInternacional, PagoInternacional, CondicionPago,
    Comercial, Comision  # 🆕 Añadimos los nuevos modelos
)
from clientes.models import Cliente
from inventario.models import Material, Inventario


# ============================================
# PEDIDOS NORMALES
# ============================================

@login_required
def lista_pedidos(request):
    # 🆕 LIMPIEZA AUTOMÁTICA DE ORÍGENES HUÉRFANOS
    from .models import OrigenVenta
    OrigenVenta.objects.filter(pedido_compra__isnull=True).delete()
    # ---------------------------------------------

    # Base queryset
    pedidos = Pedido.objects.all().order_by('-fecha')

    # --- Filtros ---
    tipo = request.GET.get('tipo', '')
    estado = request.GET.get('estado', '')
    desde = request.GET.get('desde', '')
    hasta = request.GET.get('hasta', '')
    buscar = request.GET.get('buscar', '').strip()
    material_tipo = request.GET.get('material_tipo', '')

    if tipo:
        pedidos = pedidos.filter(tipo=tipo)
    if estado:
        pedidos = pedidos.filter(estado=estado)
    if desde:
        pedidos = pedidos.filter(fecha__date__gte=desde)
    if hasta:
        pedidos = pedidos.filter(fecha__date__lte=hasta)

    if buscar:
        pedidos = pedidos.filter(
            Q(numero_pedido__icontains=buscar) |
            Q(cliente__nombre__icontains=buscar) |
            Q(proveedor__nombre__icontains=buscar)
        )

    if material_tipo:
        pedidos = pedidos.filter(detalles__material__tipo=material_tipo).distinct()
    
    # Contadores
    base_para_contadores = Pedido.objects.all()
    if estado:
        base_para_contadores = base_para_contadores.filter(estado=estado)
    if desde:
        base_para_contadores = base_para_contadores.filter(fecha__date__gte=desde)
    if hasta:
        base_para_contadores = base_para_contadores.filter(fecha__date__lte=hasta)
    if buscar:
        base_para_contadores = base_para_contadores.filter(
            Q(numero_pedido__icontains=buscar) |
            Q(cliente__nombre__icontains=buscar) |
            Q(proveedor__nombre__icontains=buscar)
        )

    contadores = {
        'COMPRA_MAT': base_para_contadores.filter(tipo='COMPRA_MAT').count(),
        'VENTA_MAT': base_para_contadores.filter(tipo='VENTA_MAT').count(),
        'MAQUILA': base_para_contadores.filter(tipo='MAQUILA').count(),
        'TODOS': base_para_contadores.count(),
    }

    # Conceptos de cuentas
    conceptos_pagados = set(
        CuentaPorPagar.objects.filter(estado='PAGADO').values_list('concepto', flat=True)
    )
    conceptos_pendientes = set(
        CuentaPorPagar.objects.filter(estado__in=['PENDIENTE', 'PARCIAL']).values_list('concepto', flat=True)
    )

    for p in pedidos:
        concepto = f"Pedido {p.numero_pedido}"
        p.tiene_cuenta_pagada = concepto in conceptos_pagados
        p.tiene_cuenta_pendiente = concepto in conceptos_pendientes
        
        if p.tipo == 'COMPRA_MAT':
            venta_asociada = p.ventas_asociadas.first()
            p.venta_asociada = venta_asociada.pedido_venta if venta_asociada else None
        else:
            p.venta_asociada = None

    total_pedidos = pedidos.count()
    total_importe = sum((p.total_importe for p in pedidos), Decimal('0'))

    # 🆕 Obtener los tipos únicos de material
    from inventario.models import Material, TipoMaterial
    materiales_con_tipo = Material.objects.exclude(tipo__isnull=True).select_related('tipo')
    tipos_dict = {}
    for mat in materiales_con_tipo:
        if mat.tipo and mat.tipo.id not in tipos_dict:
            tipos_dict[mat.tipo.id] = mat.tipo.nombre
    
    tipos_materiales = [{'id': k, 'nombre': v} for k, v in tipos_dict.items()]
    tipos_materiales = sorted(tipos_materiales, key=lambda x: x['nombre'])

    context = {
        'pedidos': pedidos,
        'total_pedidos': total_pedidos,
        'total_importe': total_importe,
        'tipos': Pedido.TIPO_OPERACION,
        'estados': Pedido.ESTADO_PEDIDO,
        'tipo_filtro': tipo,
        'estado_filtro': estado,
        'desde_filtro': desde,
        'hasta_filtro': hasta,
        'buscar_filtro': buscar,
        'contadores': contadores,
        'material_tipo_filtro': material_tipo,
        'tipos_materiales': tipos_materiales,
    }
    return render(request, 'pedidos/lista.html', context)


@login_required
def detalle_pedido(request, pedido_id):
    """Ver detalle completo de un pedido"""
    pedido = get_object_or_404(Pedido, id=pedido_id)

    if request.method == 'POST' and 'peso_real_tn' in request.POST:
        peso_str = request.POST.get('peso_real_tn')
        try:
            pedido.peso_real_tn = Decimal(peso_str) if peso_str else None
            pedido.save()
            messages.success(request, '✅ Peso real guardado correctamente. Revisa el impacto económico.')
        except (ValueError, TypeError):
            messages.error(request, '❌ El peso introducido no es válido.')
        return redirect('detalle_pedido', pedido_id=pedido.id)

    factura_existente = pedido.facturas.exclude(estado_pago='ANULADO').first()

    cuenta_pagar_existente = None
    if pedido.tipo in ['COMPRA_MAT', 'MAQUILA']:
        cuenta_pagar_existente = CuentaPorPagar.objects.filter(
            concepto=f"Pedido {pedido.numero_pedido}"
        ).first()

    url_retorno = request.GET.get('return_url', '')

    context = {
        'pedido': pedido,
        'factura_existente': factura_existente,
        'cuenta_pagar_existente': cuenta_pagar_existente,
        'total_kg': pedido.total_kg,
        'total_importe': pedido.total_importe,
        'comerciales': Comercial.objects.filter(activo=True),
        'comisiones': pedido.comisiones.all(),
        'total_comisiones': pedido.total_comisiones,
        'url_retorno': url_retorno,
    }
    return render(request, 'pedidos/detalle_pedido.html', context)


@login_required
def nuevo_pedido(request):
    """Formulario para crear un nuevo pedido"""
    if request.method == 'POST':
        try:
            with transaction.atomic():
                tipo = request.POST.get('tipo')
                
                cliente_id = None
                proveedor_id = None
                if tipo == 'VENTA_MAT':
                    cliente_id = request.POST.get('cliente') or None
                else:
                    proveedor_id = request.POST.get('proveedor') or None
                
                pedido_origen_id = request.POST.get('pedido_origen') or None
                
                pedido = Pedido.objects.create(
                    tipo=tipo,
                    estado=request.POST.get('estado', 'PREVISION'),
                    cliente_id=cliente_id,
                    proveedor_id=proveedor_id,
                    incoterm=request.POST.get('incoterm', ''),
                    pedido_origen_id=pedido_origen_id,
                    fecha=(request.POST.get('fecha') + 'T00:00') if request.POST.get('fecha') else datetime.now(),
                    notas=request.POST.get('notas', ''),
                )

                materiales = request.POST.getlist('material[]')
                cantidades = request.POST.getlist('cantidad[]')
                precios = request.POST.getlist('precio[]')
                transportes = request.POST.getlist('transporte[]')

                for i, material_id in enumerate(materiales):
                    if material_id and cantidades[i]:
                        try:
                            cantidad = Decimal(cantidades[i])
                            precio = Decimal(precios[i] or '0')
                            transporte = Decimal(transportes[i] or '0')
                        except (InvalidOperation, ValueError, TypeError):
                            raise ValueError(f"Cantidad/precio inválido en línea {i+1}")

                        detalle = DetallePedido.objects.create(
                            pedido=pedido,
                            material_id=material_id,
                            cantidad=cantidad,
                            precio_unitario=precio,
                            transporte=transporte,
                        )

                        # Si el pedido está en PREVISIÓN, NO tocar inventario
                        if pedido.estado == 'PREVISION':
                            continue

                        inventario, created = Inventario.objects.get_or_create(
                            material=detalle.material
                        )

                        if pedido.tipo == 'VENTA_MAT':
                            # 🆕 Para ventas, NO comprobamos el stock aquí (se valida con los orígenes luego)
                            pass
                        else:
                            inventario.cantidad += cantidad
                            inventario.save()

                if pedido.es_internacional:
                    PedidoInternacional.objects.create(
                        pedido=pedido,
                        incoterm=pedido.incoterm or 'CIF',
                        estado='ABIERTO',
                        valor_total=pedido.total_importe,
                        peso_total_kg=pedido.total_kg,
                    )

                # 6. Guardar los orígenes de venta
                if pedido.tipo == 'VENTA_MAT':
                    from .models import OrigenVenta
                    pedido.origenes_venta.all().delete()
                    
                    origenes_pedidos = request.POST.getlist('origen_pedido')
                    origenes_cantidades = request.POST.getlist('origen_cantidad')
                    
                    for i, pedido_compra_id in enumerate(origenes_pedidos):
                        if pedido_compra_id and i < len(origenes_cantidades) and origenes_cantidades[i]:
                            try:
                                cantidad = Decimal(origenes_cantidades[i])
                                OrigenVenta.objects.create(
                                    pedido_venta=pedido,
                                    pedido_compra_id=pedido_compra_id,
                                    cantidad_tn=cantidad,
                                )
                            except (InvalidOperation, ValueError, TypeError):
                                pass

                # 🆕 VALIDACIÓN: Comprobar que los orígenes cubren la venta
                if pedido.tipo == 'VENTA_MAT' and pedido.estado != 'PREVISION':
                    total_origenes = sum(o.cantidad_tn for o in pedido.origenes_venta.all())
                    total_venta = pedido.total_kg
                    if total_origenes < total_venta:
                        raise ValueError(
                            f"❌ No puedes vender {total_venta} tn si solo has asignado {total_origenes} tn en los orígenes de compra. "
                            f"Faltan {total_venta - total_origenes} tn por asignar."
                        )

                messages.success(request, f'✅ Pedido {pedido.numero_pedido} creado correctamente')

                # 🆕 Recalcular stock de los materiales afectados
                from .models import recalcular_stock_material
                for material_id in set(materiales):
                    if material_id:
                        mat = Material.objects.get(id=material_id)
                        recalcular_stock_material(mat)
                
                return redirect('lista_pedidos')

        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')

    # 🆕 Filtrar solo los pedidos de compra que tengan toneladas disponibles
    todos_compra = Pedido.objects.filter(tipo='COMPRA_MAT').exclude(estado='PREVISION').order_by('-fecha')
    pedidos_disponibles = [pc for pc in todos_compra if pc.tn_disponibles > Decimal('0')]

    context = {
        'clientes': Cliente.objects.filter(estado='ACTIVO').order_by('nombre'),
        'proveedores': Proveedor.objects.filter(estado='ACTIVO', tipo='MATERIAL').order_by('nombre'),
        'materiales': Material.objects.all().order_by('nombre'),
        'tipos': Pedido.TIPO_OPERACION,
        'estados': Pedido.ESTADO_PEDIDO,
        'incoterms': Pedido.INCOTERM_CHOICES,
        'pedidos_compra': pedidos_disponibles,
        'fecha_actual': datetime.now().strftime('%Y-%m-%d'),
    }
    return render(request, 'pedidos/nuevo_pedido.html', context)


@login_required
def editar_pedido(request, pedido_id):
    """Formulario para editar un pedido existente (cabecera + detalles + inventario)"""
    pedido = get_object_or_404(Pedido, id=pedido_id)

    url_retorno = request.GET.get('return_url', '')
    
    if request.method == 'POST':
        url_retorno = request.POST.get('return_url', '')

        # Comprobar si hay cobros registrados
        if pedido.tiene_cobros:
            materiales_nuevos = request.POST.getlist('material[]')
            cantidades_nuevas = request.POST.getlist('cantidad[]')
            precios_nuevos = request.POST.getlist('precio[]')
            
            detalles_actuales = list(pedido.detalles.values_list('material_id', 'cantidad', 'precio_unitario'))
            detalles_nuevos = []
            for i, mat in enumerate(materiales_nuevos):
                if mat and i < len(cantidades_nuevas):
                    try:
                        detalles_nuevos.append((int(mat), Decimal(cantidades_nuevas[i]), Decimal(precios_nuevos[i] or '0')))
                    except (ValueError, InvalidOperation):
                        pass
            
            if detalles_actuales != detalles_nuevos:
                messages.error(request, '❌ Este pedido ya tiene cobros registrados. Para modificar los materiales o precios, primero anula la factura desde /finanzas/ y luego vuelve a editar.')
                return redirect('detalle_pedido', pedido_id=pedido.id)

        try:
            with transaction.atomic():
                tipo = request.POST.get('tipo')
                estado_nuevo = request.POST.get('estado')
                estado_antiguo = pedido.estado
                tipo_antiguo = pedido.tipo

                # 1. Revertir inventario (SOLO COMPRAS, las ventas no tocan el stock aquí)
                if estado_antiguo != 'PREVISION' and tipo_antiguo in ['COMPRA_MAT', 'MAQUILA']:
                    for detalle_antiguo in pedido.detalles.all():
                        inventario, _ = Inventario.objects.get_or_create(material=detalle_antiguo.material)
                        inventario.cantidad -= detalle_antiguo.cantidad
                        inventario.save()

                # 2. Actualizar cabecera
                pedido.tipo = tipo
                pedido.estado = estado_nuevo
                if tipo == 'VENTA_MAT':
                    pedido.cliente_id = request.POST.get('cliente') or None
                    pedido.proveedor_id = None
                else:
                    pedido.proveedor_id = request.POST.get('proveedor') or None
                    pedido.cliente_id = None
                pedido.incoterm = request.POST.get('incoterm', '')
                pedido.pedido_origen_id = request.POST.get('pedido_origen') or None
                fecha_str = request.POST.get('fecha')
                pedido.fecha = (fecha_str + 'T00:00') if fecha_str else datetime.now()
                pedido.notas = request.POST.get('notas', '')

                peso_real = request.POST.get('peso_real_tn')
                pedido.peso_real_tn = Decimal(peso_real) if peso_real else None
                
                pedido.save()

                # 3. Borrar detalles antiguos
                pedido.detalles.all().delete()

                # 4. Crear nuevos detalles
                materiales = request.POST.getlist('material[]')
                cantidades = request.POST.getlist('cantidad[]')
                precios = request.POST.getlist('precio[]')
                transportes = request.POST.getlist('transporte[]')

                for i, material_id in enumerate(materiales):
                    if material_id and cantidades[i]:
                        try:
                            cantidad = Decimal(cantidades[i])
                            precio = Decimal(precios[i] or '0')
                            transporte = Decimal(transportes[i] or '0')
                        except (InvalidOperation, ValueError, TypeError):
                            raise ValueError(f"Cantidad/precio inválido en línea {i+1}")

                        detalle = DetallePedido.objects.create(
                            pedido=pedido,
                            material_id=material_id,
                            cantidad=cantidad,
                            precio_unitario=precio,
                            transporte=transporte,
                        )

                        if pedido.estado == 'PREVISION':
                            continue

                        inventario, _ = Inventario.objects.get_or_create(material=detalle.material)

                        if pedido.tipo == 'VENTA_MAT':
                            # 🆕 Para ventas, NO comprobamos el stock aquí (se valida con los orígenes luego)
                            pass
                        else:
                            inventario.cantidad += cantidad
                            inventario.save()

                # 5. Seguimiento internacional
                if pedido.es_internacional and not hasattr(pedido, 'internacional'):
                    PedidoInternacional.objects.create(pedido=pedido, incoterm=pedido.incoterm or 'CIF', estado='ABIERTO', valor_total=pedido.total_importe, peso_total_kg=pedido.total_kg)
                elif not pedido.es_internacional and hasattr(pedido, 'internacional'):
                    try:
                        pedido.internacional.delete()
                    except PedidoInternacional.DoesNotExist:
                        pass

                # 6. Guardar los orígenes de venta
                if pedido.tipo == 'VENTA_MAT':
                    from .models import OrigenVenta
                    origenes_actuales = {o.id: o for o in pedido.origenes_venta.all()}
                    ids_conservar = request.POST.getlist('origen_id_existente')
                    ids_conservar = [int(i) for i in ids_conservar if i]

                    for origen_id, origen in origenes_actuales.items():
                        if origen_id not in ids_conservar:
                            origen.delete()
                    
                    for origen_id in ids_conservar:
                        if origen_id in origenes_actuales:
                            cantidad_str = request.POST.get(f'origen_cantidad_existente_{origen_id}')
                            if cantidad_str:
                                try:
                                    origenes_actuales[origen_id].cantidad_tn = Decimal(cantidad_str)
                                    origenes_actuales[origen_id].save()
                                except (InvalidOperation, ValueError, TypeError):
                                    pass
                    
                    origenes_pedidos = request.POST.getlist('origen_pedido_nuevo')
                    origenes_cantidades = request.POST.getlist('origen_cantidad_nuevo')
                    
                    for i, pedido_compra_id in enumerate(origenes_pedidos):
                        if pedido_compra_id and i < len(origenes_cantidades) and origenes_cantidades[i]:
                            try:
                                cantidad = Decimal(origenes_cantidades[i])
                                OrigenVenta.objects.create(pedido_venta=pedido, pedido_compra_id=pedido_compra_id, cantidad_tn=cantidad)
                            except (InvalidOperation, ValueError, TypeError):
                                pass

                # 🆕 VALIDACIÓN: Comprobar que los orígenes cubren la venta
                if pedido.tipo == 'VENTA_MAT' and pedido.estado != 'PREVISION':
                    total_origenes = sum(o.cantidad_tn for o in pedido.origenes_venta.all())
                    total_venta = pedido.total_kg
                    if total_origenes < total_venta:
                        raise ValueError(
                            f"❌ No puedes vender {total_venta} tn si solo has asignado {total_origenes} tn en los orígenes de compra. "
                            f"Faltan {total_venta - total_origenes} tn por asignar."
                        )

                # 7. Sincronizar la factura
                factura_asociada = pedido.facturas.first()
                if factura_asociada:
                    factura_asociada.base = pedido.total_importe
                    if factura_asociada.categoria == 'COMERCIO_MATERIALES':
                        factura_asociada.iva = Decimal('0')
                        factura_asociada.total = pedido.total_importe
                    else:
                        iva_pct = factura_asociada.iva_porcentaje or Decimal('0')
                        factura_asociada.iva = pedido.total_importe * (iva_pct / Decimal('100'))
                        factura_asociada.total = pedido.total_importe + factura_asociada.iva
                    factura_asociada.save()

                    CuentaPorCobrar.objects.filter(numero_factura=factura_asociada.numero_factura).update(importe_total=factura_asociada.total)
                    CuentaPorPagar.objects.filter(numero_factura=factura_asociada.numero_factura).update(importe_total=factura_asociada.total)

                # 8. Sincronizar seguimiento internacional
                if pedido.es_internacional and hasattr(pedido, 'internacional'):
                    pedido.internacional.valor_total = pedido.total_importe
                    pedido.internacional.peso_total_kg = pedido.total_kg
                    pedido.internacional.save()

                # 🆕 Recalcular stock
                from .models import recalcular_stock_material
                for detalle in pedido.detalles.all():
                    recalcular_stock_material(detalle.material)
                for origen in pedido.origenes_venta.all():
                    for detalle in origen.pedido_compra.detalles.all():
                        recalcular_stock_material(detalle.material)
                
                messages.success(request, f'✅ Pedido {pedido.numero_pedido} actualizado')
                
                if url_retorno:
                    return redirect(f"/pedidos/?{url_retorno}")
                return redirect('lista_pedidos')

        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')

    # ============================================
    # GET: cargar datos para el formulario
    # ============================================
    
    todos_compra = Pedido.objects.filter(tipo='COMPRA_MAT').exclude(id=pedido.id).exclude(estado='PREVISION').order_by('-fecha')
    
    origenes_este_pedido = pedido.origenes_venta.all()
    cantidades_este_pedido = {o.pedido_compra_id: o.cantidad_tn for o in origenes_este_pedido}
    
    pedidos_disponibles = []
    for pc in todos_compra:
        tn_vendidas_otros = sum(o.cantidad_tn for o in pc.ventas_asociadas.exclude(pedido_venta=pedido))
        tn_asignadas_actual = cantidades_este_pedido.get(pc.id, Decimal('0'))
        tn_libres = pc.total_kg - tn_vendidas_otros - tn_asignadas_actual
        
        if tn_libres > Decimal('0'):
            pc.tn_libres_calculadas = tn_libres 
            pedidos_disponibles.append(pc)

    context = {
        'pedido': pedido,
        'clientes': Cliente.objects.filter(estado='ACTIVO').order_by('nombre'),
        'proveedores': Proveedor.objects.filter(estado='ACTIVO', tipo='MATERIAL').order_by('nombre'),
        'materiales': Material.objects.all().order_by('nombre'),
        'tipos': Pedido.TIPO_OPERACION,
        'estados': Pedido.ESTADO_PEDIDO,
        'incoterms': Pedido.INCOTERM_CHOICES,
        'pedidos_compra': pedidos_disponibles,
        'url_retorno': url_retorno,
    }
        
    return render(request, 'pedidos/editar_pedido.html', context)


@login_required
def confirmar_eliminar_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)
    context = {'pedido': pedido}
    return render(request, 'pedidos/confirmar_eliminar.html', context)


@login_required
def eliminar_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)

    if request.method == 'POST':
        numero = pedido.numero_pedido
        entidad = pedido.entidad_nombre

        try:
            with transaction.atomic():
                from .models import OrigenVenta
                
                if pedido.tipo in ['COMPRA_MAT', 'MAQUILA']:
                    OrigenVenta.objects.filter(pedido_compra=pedido).delete()
                
                if pedido.tipo == 'VENTA_MAT':
                    pedido.origenes_venta.all().delete()

                if pedido.estado != 'PREVISION':
                    for detalle in pedido.detalles.all():
                        inventario, created = Inventario.objects.get_or_create(
                            material=detalle.material
                        )
                        if pedido.tipo == 'VENTA_MAT':
                            inventario.cantidad += detalle.cantidad
                        else:
                            inventario.cantidad -= detalle.cantidad
                        inventario.save()

                from .models import recalcular_stock_material
                materiales_afectados = [d.material for d in pedido.detalles.all()]
                if pedido.tipo in ['COMPRA_MAT', 'MAQUILA']:
                    for origen in pedido.ventas_asociadas.all():
                        materiales_afectados.extend([d.material for d in origen.pedido_venta.detalles.all()])
                
                materiales_afectados = list(set(materiales_afectados))
                
                pedido.delete()
                
                for mat in materiales_afectados:
                    recalcular_stock_material(mat)

                messages.success(request, f'✅ Pedido {numero} de {entidad} eliminado y orígenes liberados')
        except Exception as e:
            messages.error(request, f'❌ Error al eliminar: {str(e)}')

        return redirect('lista_pedidos')

    return redirect('confirmar_eliminar_pedido', pedido_id=pedido_id)


@login_required
def generar_factura_desde_pedido(request, pedido_id):
    
    pedido = get_object_or_404(Pedido, id=pedido_id)

    factura_existente = pedido.facturas.exclude(estado_pago='ANULADO').first()
    
    if factura_existente:
        messages.warning(request, f'⚠️ Este pedido ya tiene la factura {factura_existente.numero_factura}')
        return redirect('detalle_pedido', pedido_id=pedido.id)

    if pedido.tipo != 'VENTA_MAT':
        messages.error(request, '❌ No se puede generar factura de un pedido de compra. El proveedor te emite la factura a ti.')
        return redirect('detalle_pedido', pedido_id=pedido.id)

    base = Decimal(str(pedido.total_importe))
    
    if pedido.cliente:
        pais = pedido.cliente.pais
    elif pedido.proveedor:
        pais = pedido.proveedor.pais
    else:
        pais = 'España'

    iva_porcentaje = 0 if pais != 'España' else 21
    iva = base * (Decimal(str(iva_porcentaje)) / Decimal('100'))
    total = base + iva

    if request.method == 'POST':
        try:
            numero_factura = request.POST.get('numero_factura')
            tipo_factura = 'INGRESO'
            es_ingreso = True

            factura = Factura.objects.create(
                numero_factura=numero_factura,
                tipo=tipo_factura,
                fecha=datetime.now().date(),
                cliente=pedido.cliente,
                proveedor=None,
                pedido=pedido,
                categoria='COMERCIO_MATERIALES',
                base=base,
                iva_porcentaje=iva_porcentaje,
                estado_pago='PENDIENTE',
                notas=f'Generada automáticamente desde el pedido {pedido.numero_pedido}',
                numero_albaran=request.POST.get('numero_albaran', ''),
            )

            from finanzas.views import _crear_cuenta_para_factura
            _crear_cuenta_para_factura(factura)

            messages.success(request, f'✅ Factura {factura.numero_factura} creada correctamente')
            return redirect('editar_factura', factura_id=factura.id)

        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')

    year = datetime.now().year
    ultimo = Factura.objects.filter(numero_factura__startswith=str(year)).count() + 1
    numero_sugerido = f"{year}{ultimo:04d}"

    context = {
        'pedido': pedido,
        'base': base,
        'iva_porcentaje': iva_porcentaje,
        'iva': iva,
        'total': total,
        'numero_sugerido': numero_sugerido,
        'fecha_actual': datetime.now().strftime('%Y-%m-%d'),
        'fecha_vencimiento': (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d'),
    }
    return render(request, 'pedidos/generar_factura.html', context)


# ============================================
# PEDIDOS INTERNACIONALES
# ============================================

@login_required
def seguimiento_internacional(request):
    """Vista de seguimiento de pedidos internacionales"""
    estado = request.GET.get('estado', '')

    pedidos = PedidoInternacional.objects.all().order_by('-fecha_creacion')

    if estado:
        pedidos = pedidos.filter(estado=estado)

    abiertos = list(pedidos.exclude(estado__in=['CERRADO', 'ENTREGADO']))
    cerrados = pedidos.filter(estado__in=['CERRADO', 'ENTREGADO'])

    from finanzas.models import CuentaPorCobrar
    numeros_cuentas_anuladas = set(
        CuentaPorCobrar.objects.filter(estado='ANULADO').values_list('numero_factura', flat=True)
    )

    abiertos_filtrados = []
    for p in abiertos:
        factura = p.pedido.facturas.first()
        if factura and factura.numero_factura in numeros_cuentas_anuladas:
            continue
        abiertos_filtrados.append(p)

    abiertos = abiertos_filtrados

    total_valor_abierto = sum((p.pedido.total_importe for p in abiertos), Decimal('0'))
    total_pagado_abierto = sum((p.pedido.total_cobrado for p in abiertos), Decimal('0'))
    total_pendiente = sum((p.pedido.total_pendiente_cobro for p in abiertos), Decimal('0'))

    alertas = [p for p in abiertos if p.alerta_cobro]

    context = {
        'pedidos_abiertos': abiertos,
        'pedidos_cerrados': cerrados,
        'total_valor_abierto': total_valor_abierto,
        'total_pagado_abierto': total_pagado_abierto,
        'total_pendiente': total_pendiente,
        'alertas': alertas,
        'estado_filtro': estado,
        'estados': PedidoInternacional.ESTADO_CHOICES,
    }
    return render(request, 'pedidos/seguimiento_internacional.html', context)


@login_required
def nuevo_pedido_internacional(request, pedido_id):
    """Crear seguimiento internacional para un pedido"""
    pedido = get_object_or_404(Pedido, id=pedido_id)

    if request.method == 'POST':
        try:
            internacional = PedidoInternacional.objects.create(
                pedido=pedido,
                estado=request.POST.get('estado', 'ABIERTO'),
                incoterm=request.POST.get('incoterm', 'CIF'),
                condicion_pago_id=request.POST.get('condicion_pago') or None,
                numero_contenedor=request.POST.get('numero_contenedor', ''),
                numero_precinto=request.POST.get('numero_precinto', ''),
                naviera=request.POST.get('naviera', ''),
                numero_bl=request.POST.get('numero_bl', ''),
                buque=request.POST.get('buque', ''),
                puerto_origen=request.POST.get('puerto_origen', 'Barcelona'),
                puerto_destino=request.POST.get('puerto_destino', ''),
                fecha_carga=request.POST.get('fecha_carga') or None,
                fecha_salida=request.POST.get('fecha_salida') or None,
                fecha_eta=request.POST.get('fecha_eta') or None,
                valor_total=request.POST.get('valor_total', 0),
                coste_flete=request.POST.get('coste_flete', 0),
                peso_total_kg=request.POST.get('peso_total_kg', 0),
                notas=request.POST.get('notas', ''),
            )
            messages.success(request, f'✅ Seguimiento internacional creado para {pedido.numero_pedido}')
            return redirect('detalle_pedido_internacional', int_id=internacional.id)
        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')

    context = {
        'pedido': pedido,
        'condiciones': CondicionPago.objects.filter(activo=True),
        'estados': PedidoInternacional.ESTADO_CHOICES,
        'incoterms': PedidoInternacional.INCOTERM_CHOICES,
    }
    return render(request, 'pedidos/nuevo_pedido_internacional.html', context)


@login_required
def detalle_pedido_internacional(request, int_id):
    """Ver detalle completo de un pedido internacional + añadir pago"""
    pedido_int = get_object_or_404(PedidoInternacional, id=int_id)

    if request.method == 'POST':
        try:
            PagoInternacional.objects.create(
                pedido_internacional=pedido_int,
                tipo=request.POST.get('tipo_pago', 'ANTICIPO'),
                cantidad=request.POST.get('cantidad'),
                fecha=request.POST.get('fecha'),
                metodo=request.POST.get('metodo', ''),
                referencia=request.POST.get('referencia', ''),
                notas=request.POST.get('notas_pago', ''),
            )
            messages.success(request, '✅ Pago registrado correctamente')
            return redirect('detalle_pedido_internacional', int_id=pedido_int.id)
        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')

    context = {
        'pedido_int': pedido_int,
        'pagos': pedido_int.pagos.all().order_by('-fecha'),
        'tipos_pago': PagoInternacional.TIPO_PAGO,
    }
    return render(request, 'pedidos/detalle_pedido_internacional.html', context)


@login_required
def editar_pedido_internacional(request, int_id):
    """Editar seguimiento internacional"""
    pedido_int = get_object_or_404(PedidoInternacional, id=int_id)

    if request.method == 'POST':
        pedido_int.estado = request.POST.get('estado')
        pedido_int.incoterm = request.POST.get('incoterm')
        pedido_int.condicion_pago_id = request.POST.get('condicion_pago') or None
        pedido_int.numero_contenedor = request.POST.get('numero_contenedor', '')
        pedido_int.numero_precinto = request.POST.get('numero_precinto', '')
        pedido_int.naviera = request.POST.get('naviera', '')
        pedido_int.numero_bl = request.POST.get('numero_bl', '')
        pedido_int.buque = request.POST.get('buque', '')
        pedido_int.puerto_origen = request.POST.get('puerto_origen', '')
        pedido_int.puerto_destino = request.POST.get('puerto_destino', '')
        pedido_int.fecha_carga = request.POST.get('fecha_carga') or None
        pedido_int.fecha_salida = request.POST.get('fecha_salida') or None
        pedido_int.fecha_eta = request.POST.get('fecha_eta') or None
        pedido_int.fecha_entrega_real = request.POST.get('fecha_entrega_real') or None
        pedido_int.valor_total = request.POST.get('valor_total', 0)
        pedido_int.coste_flete = request.POST.get('coste_flete', 0)
        pedido_int.peso_total_kg = request.POST.get('peso_total_kg', 0)
        pedido_int.notas = request.POST.get('notas', '')
        pedido_int.save()

        messages.success(request, '✅ Pedido internacional actualizado')
        return redirect('detalle_pedido_internacional', int_id=pedido_int.id)

    context = {
        'pedido_int': pedido_int,
        'condiciones': CondicionPago.objects.filter(activo=True),
        'estados': PedidoInternacional.ESTADO_CHOICES,
        'incoterms': PedidoInternacional.INCOTERM_CHOICES,
    }
    return render(request, 'pedidos/editar_pedido_internacional.html', context)


@login_required
def eliminar_pago_internacional(request, pago_id):
    """Elimina un pago internacional"""
    pago = get_object_or_404(PagoInternacional, id=pago_id)
    int_id = pago.pedido_internacional.id

    if request.method == 'POST':
        pago.delete()
        messages.success(request, '✅ Pago eliminado')
        return redirect('detalle_pedido_internacional', int_id=int_id)

    return redirect('detalle_pedido_internacional', int_id=int_id)


@login_required
def generar_cuenta_pagar_desde_pedido(request, pedido_id):
    
    pedido = get_object_or_404(Pedido, id=pedido_id)

    if pedido.tipo not in ['COMPRA_MAT', 'MAQUILA']:
        messages.error(request, '❌ Solo se pueden generar cuentas por pagar de pedidos de compra o maquila.')
        return redirect('detalle_pedido', pedido_id=pedido.id)

    concepto = f"Pedido {pedido.numero_pedido}"
    if CuentaPorPagar.objects.filter(concepto=concepto).exists():
        messages.warning(request, f'⚠️ Ya existe una cuenta por pagar para el pedido {pedido.numero_pedido}')
        return redirect('detalle_pedido', pedido_id=pedido.id)

    if request.method == 'POST':
        try:
            with transaction.atomic():
                numero_factura = request.POST.get('numero_factura', '')

                factura = Factura.objects.create(
                    numero_factura=numero_factura or f"G-{pedido.numero_pedido}",
                    numero_albaran=request.POST.get('numero_albaran', ''),
                    tipo='GASTO',
                    fecha=request.POST.get('fecha_emision') or datetime.now().date(),
                    fecha_vencimiento=request.POST.get('fecha_vencimiento'),
                    proveedor=pedido.proveedor,
                    pedido=pedido,
                    categoria='COMERCIO_MATERIALES',
                    base=pedido.total_importe,
                    iva_porcentaje=0,
                    estado_pago='PENDIENTE',
                    notas=request.POST.get('notas', '') or f'Generada desde pedido {pedido.numero_pedido}',
                    archivo_justificante=request.FILES.get('archivo_factura') or None,
                )

                cuenta = CuentaPorPagar.objects.create(
                    concepto=concepto,
                    categoria='PROVEEDOR',
                    proveedor=pedido.proveedor,
                    importe_total=pedido.total_importe,
                    fecha_emision=request.POST.get('fecha_emision') or datetime.now().date(),
                    fecha_vencimiento=request.POST.get('fecha_vencimiento'),
                    periodicidad='UNICO',
                    numero_factura=factura.numero_factura,
                    notas=request.POST.get('notas', '') or f'Generada desde pedido {pedido.numero_pedido}',
                    archivo_factura=request.FILES.get('archivo_factura') or None,
                )

                messages.success(request, f'✅ Factura de gasto y cuenta por pagar creadas para el pedido {pedido.numero_pedido}')
                return redirect('cuentas_por_pagar')
        except Exception as e:
            import traceback
            traceback.print_exc()
            messages.error(request, f'❌ Error: {str(e)}')

    context = {
        'pedido': pedido,
        'fecha_actual': datetime.now().strftime('%Y-%m-%d'),
        'fecha_vencimiento_sugerida': (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d'),
    }
    return render(request, 'pedidos/generar_cuenta_pagar.html', context)


@login_required
def generar_ajuste_peso(request, pedido_id):
    """Genera una Cuenta por Cobrar/Pagar y actualiza el pedido con el peso real"""
    pedido = get_object_or_404(Pedido, id=pedido_id)

    if pedido.tipo not in ['COMPRA_MAT', 'MAQUILA']:
        messages.error(request, '❌ Solo se pueden ajustar pedidos de compra o maquila.')
        return redirect('detalle_pedido', pedido_id=pedido.id)

    if pedido.peso_real_tn is None:
        messages.error(request, '❌ Primero debes indicar el peso real.')
        return redirect('detalle_pedido', pedido_id=pedido.id)

    ajuste = pedido.importe_ajuste

    if ajuste == 0:
        messages.info(request, 'ℹ️ No hay diferencia de peso que ajustar.')
        return redirect('detalle_pedido', pedido_id=pedido.id)

    if request.method == 'POST':
        try:
            with transaction.atomic():
                from finanzas.models import CuentaPorCobrar, CuentaPorPagar
                from inventario.models import Inventario
                importe_absoluto = abs(ajuste)
                hoy = datetime.now().date()
                
                if ajuste < 0:
                    CuentaPorCobrar.objects.create(
                        concepto=f"Ajuste peso Pedido {pedido.numero_pedido}",
                        proveedor=pedido.proveedor,
                        importe_total=importe_absoluto,
                        fecha_emision=hoy,
                        fecha_vencimiento=hoy + timedelta(days=30),
                        notas=f"Diferencia de {abs(pedido.diferencia_peso_tn)} tn a favor.",
                    )
                    messages.success(request, f'✅ Creada Cuenta por Cobrar por {importe_absoluto} € al proveedor.')
                else:
                    CuentaPorPagar.objects.create(
                        concepto=f"Ajuste peso Pedido {pedido.numero_pedido}",
                        categoria='PROVEEDOR',
                        proveedor=pedido.proveedor,
                        importe_total=importe_absoluto,
                        fecha_emision=hoy,
                        fecha_vencimiento=hoy + timedelta(days=30),
                        notas=f"Diferencia de {pedido.diferencia_peso_tn} tn a pagar.",
                    )
                    messages.success(request, f'✅ Creada Cuenta por Pagar por {importe_absoluto} €.')

                if pedido.detalles.exists():
                    diferencia_tn = pedido.diferencia_peso_tn
                    
                    if diferencia_tn != 0:
                        detalle = pedido.detalles.first()
                        
                        peso_original = pedido.total_kg
                        nota_auditoria = f"[Auditoría {hoy.strftime('%d/%m/%Y')}] Peso original: {peso_original} tn. Peso real: {pedido.peso_real_tn} tn."
                        pedido.notas = f"{pedido.notas}\n{nota_auditoria}".strip()
                        
                        if pedido.estado != 'PREVISION':
                            inventario, _ = Inventario.objects.get_or_create(material=detalle.material)
                            inventario.cantidad += diferencia_tn 
                            inventario.save()
                        
                        detalle.cantidad = pedido.peso_real_tn
                        detalle.save()
                        
                        pedido.save()
                        messages.success(request, f'✅ Pedido actualizado a {pedido.peso_real_tn} tn reales.')

                return redirect('detalle_pedido', pedido_id=pedido.id)

        except Exception as e:
            messages.error(request, f'❌ Error al generar ajuste: {str(e)}')
            return redirect('detalle_pedido', pedido_id=pedido.id)

    context = {
        'pedido': pedido,
        'ajuste': ajuste,
    }
    return render(request, 'pedidos/confirmar_ajuste_peso.html', context)


@login_required
def nueva_comision(request, pedido_id):
    """Añade una comisión a un pedido"""
    from .models import Comercial, Comision
    pedido = get_object_or_404(Pedido, id=pedido_id)
    
    if request.method == 'POST':
        try:
            comercial_id = request.POST.get('comercial')
            tipo = request.POST.get('tipo')
            valor = Decimal(request.POST.get('valor'))
            
            Comision.objects.create(
                pedido=pedido,
                comercial_id=comercial_id,
                tipo=tipo,
                valor=valor
            )
            messages.success(request, '✅ Comisión añadida correctamente')
        except Exception as e:
            messages.error(request, f'❌ Error al añadir comisión: {str(e)}')
            
    return redirect('detalle_pedido', pedido_id=pedido.id)


@login_required
def eliminar_comision(request, comision_id):
    """Elimina una comisión"""
    from .models import Comision
    comision = get_object_or_404(Comision, id=comision_id)
    pedido_id = comision.pedido.id
    comision.delete()
    messages.success(request, '✅ Comisión eliminada')
    return redirect('detalle_pedido', pedido_id=pedido_id)