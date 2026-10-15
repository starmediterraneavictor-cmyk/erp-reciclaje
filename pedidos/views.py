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
    PedidoInternacional, PagoInternacional, CondicionPago
)
from clientes.models import Cliente
from inventario.models import Material, Inventario


# ============================================
# PEDIDOS NORMALES
# ============================================

@login_required
def lista_pedidos(request):
    # Base queryset
    pedidos = Pedido.objects.all().order_by('-fecha')

    # --- Filtros ---
    tipo = request.GET.get('tipo', '')          # pestaña activa
    estado = request.GET.get('estado', '')
    desde = request.GET.get('desde', '')
    hasta = request.GET.get('hasta', '')
    buscar = request.GET.get('buscar', '').strip()

    if tipo:
        pedidos = pedidos.filter(tipo=tipo)
    if estado:
        pedidos = pedidos.filter(estado=estado)
    if desde:
        pedidos = pedidos.filter(fecha__date__gte=desde)
    if hasta:
        pedidos = pedidos.filter(fecha__date__lte=hasta)

    # 🔍 Búsqueda libre: nº pedido, cliente o proveedor
    if buscar:
        pedidos = pedidos.filter(
            Q(numero_pedido__icontains=buscar) |
            Q(cliente__nombre__icontains=buscar) |
            Q(proveedor__nombre__icontains=buscar)
        )

    # --- Contadores para las pestañas (sin filtros de tipo, pero con el resto) ---
    # Para que los badges reflejen los filtros actuales (estado, fechas, búsqueda)
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

    # --- Conceptos de cuentas pagadas y pendientes ---
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

    total_pedidos = pedidos.count()
    total_importe = sum((p.total_importe for p in pedidos), Decimal('0'))

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
    }
    return render(request, 'pedidos/lista.html', context)


@login_required
def detalle_pedido(request, pedido_id):
    """Ver detalle completo de un pedido"""
    
    pedido = get_object_or_404(Pedido, id=pedido_id)
    factura_existente = pedido.facturas.exclude(estado_pago='ANULADO').first()

    # Comprobar si ya existe cuenta por pagar para este pedido
    cuenta_pagar_existente = None
    if pedido.tipo in ['COMPRA_MAT', 'MAQUILA']:
        cuenta_pagar_existente = CuentaPorPagar.objects.filter(
            concepto=f"Pedido {pedido.numero_pedido}"
        ).first()

    context = {
        'pedido': pedido,
        'factura_existente': factura_existente,
        'cuenta_pagar_existente': cuenta_pagar_existente,
        'total_kg': pedido.total_kg,
        'total_importe': pedido.total_importe,
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
                            if inventario.cantidad < cantidad:
                                raise ValueError(
                                    f"Stock insuficiente de {detalle.material.nombre}. "
                                    f"Disponible: {inventario.cantidad}, solicitado: {cantidad}"
                                )
                            inventario.cantidad -= cantidad
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


                
                messages.success(request, f'✅ Pedido {pedido.numero_pedido} creado correctamente')
                return redirect('lista_pedidos')

        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')

    context = {
        'clientes': Cliente.objects.filter(estado='ACTIVO').order_by('nombre'),
        'proveedores': Proveedor.objects.filter(estado='ACTIVO').order_by('nombre'),
        'materiales': Material.objects.all().order_by('nombre'),
        'tipos': Pedido.TIPO_OPERACION,
        'estados': Pedido.ESTADO_PEDIDO,
        'incoterms': Pedido.INCOTERM_CHOICES,
        'pedidos_compra': Pedido.objects.filter(tipo='COMPRA_MAT', ventas_asociadas__isnull=True).order_by('-fecha'),
        'fecha_actual': datetime.now().strftime('%Y-%m-%d'),
    }
    return render(request, 'pedidos/nuevo_pedido.html', context)


@login_required
def editar_pedido(request, pedido_id):
    """Formulario para editar un pedido existente (cabecera + detalles + inventario)"""
    pedido = get_object_or_404(Pedido, id=pedido_id)

    if request.method == 'POST':
        # Comprobar si hay cobros registrados
        if pedido.tiene_cobros:
            # Detectar si se están modificando los materiales
            materiales_nuevos = request.POST.getlist('material[]')
            cantidades_nuevas = request.POST.getlist('cantidad[]')
            precios_nuevos = request.POST.getlist('precio[]')
            
            # Comparar con los actuales
            detalles_actuales = list(pedido.detalles.values_list('material_id', 'cantidad', 'precio_unitario'))
            detalles_nuevos = []
            for i, mat in enumerate(materiales_nuevos):
                if mat and i < len(cantidades_nuevas):
                    try:
                        detalles_nuevos.append((int(mat), Decimal(cantidades_nuevas[i]), Decimal(precios_nuevos[i] or '0')))
                    except (ValueError, InvalidOperation):
                        pass
            
            if detalles_actuales != detalles_nuevos:
                messages.error(
                    request,
                    '❌ Este pedido ya tiene cobros registrados. '
                    'Para modificar los materiales o precios, primero anula la factura '
                    'desde /finanzas/ y luego vuelve a editar.'
                )
                return redirect('detalle_pedido', pedido_id=pedido.id)
            
        try:
            with transaction.atomic():
                tipo = request.POST.get('tipo')
                estado_nuevo = request.POST.get('estado')
                estado_antiguo = pedido.estado
                tipo_antiguo = pedido.tipo
                
                # 1. Revertir inventario de detalles antiguos SOLO si el estado antiguo NO era PREVISIÓN
                if estado_antiguo != 'PREVISION':
                    for detalle_antiguo in pedido.detalles.all():
                        inventario, _ = Inventario.objects.get_or_create(material=detalle_antiguo.material)
                        if tipo_antiguo == 'VENTA_MAT':
                            inventario.cantidad += detalle_antiguo.cantidad
                        else:
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

                        # Si el nuevo estado es PREVISIÓN, NO tocar inventario
                        if pedido.estado == 'PREVISION':
                            continue

                        inventario, _ = Inventario.objects.get_or_create(material=detalle.material)

                        if pedido.tipo == 'VENTA_MAT':
                            if inventario.cantidad < cantidad:
                                raise ValueError(
                                    f"Stock insuficiente de {detalle.material.nombre}. "
                                    f"Disponible: {inventario.cantidad}, solicitado: {cantidad}"
                                )
                            inventario.cantidad -= cantidad
                        else:
                            inventario.cantidad += cantidad

                        inventario.save()

                # 5. Gestionar el seguimiento internacional
                if pedido.es_internacional and not hasattr(pedido, 'internacional'):
                    PedidoInternacional.objects.create(
                        pedido=pedido,
                        incoterm=pedido.incoterm or 'CIF',
                        estado='ABIERTO',
                        valor_total=pedido.total_importe,
                        peso_total_kg=pedido.total_kg,
                    )
                elif not pedido.es_internacional and hasattr(pedido, 'internacional'):
                    try:
                        pedido.internacional.delete()
                    except PedidoInternacional.DoesNotExist:
                        pass

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

                # 7. Sincronizar la factura asociada (si existe)
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

                    # Sincronizar también la cuenta asociada
                    CuentaPorCobrar.objects.filter(numero_factura=factura_asociada.numero_factura).update(
                        importe_total=factura_asociada.total
                    )
                    CuentaPorPagar.objects.filter(numero_factura=factura_asociada.numero_factura).update(
                        importe_total=factura_asociada.total
                    )

                # 8. Sincronizar el seguimiento internacional (SIEMPRE, no solo si hay factura)
                if pedido.es_internacional and hasattr(pedido, 'internacional'):
                    pedido.internacional.valor_total = pedido.total_importe
                    pedido.internacional.peso_total_kg = pedido.total_kg
                    pedido.internacional.save()


                messages.success(request, f'✅ Pedido {pedido.numero_pedido} actualizado')
                return redirect('lista_pedidos')

        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')

    # Pedidos de compra ya asignados a este pedido de venta (vía OrigenVenta)
    origenes_actuales_ids = list(
        pedido.origenes_venta.values_list('pedido_compra_id', flat=True)
    )

    pedidos_disponibles = Pedido.objects.filter(
        tipo='COMPRA_MAT'
    ).filter(
        Q(ventas_asociadas__isnull=True) | Q(id__in=origenes_actuales_ids)
    ).exclude(id=pedido.id).order_by('-fecha')
    
    context = {
        'pedido': pedido,
        'clientes': Cliente.objects.filter(estado='ACTIVO').order_by('nombre'),
        'proveedores': Proveedor.objects.filter(estado='ACTIVO').order_by('nombre'),
        'materiales': Material.objects.all().order_by('nombre'),
        'tipos': Pedido.TIPO_OPERACION,
        'estados': Pedido.ESTADO_PEDIDO,
        'incoterms': Pedido.INCOTERM_CHOICES,
        'pedidos_compra': pedidos_disponibles,
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
                # Solo revertir inventario si el pedido NO estaba en PREVISIÓN
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

                pedido.delete()
                messages.success(request, f'✅ Pedido {numero} de {entidad} eliminado correctamente')
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

    # Solo se pueden generar facturas de pedidos de VENTA
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

    # Excluir pedidos cuya cuenta por cobrar esté ANULADA
    from finanzas.models import CuentaPorCobrar
    numeros_cuentas_anuladas = set(
        CuentaPorCobrar.objects.filter(estado='ANULADO').values_list('numero_factura', flat=True)
    )

    abiertos_filtrados = []
    for p in abiertos:
        factura = p.pedido.facturas.first()
        if factura and factura.numero_factura in numeros_cuentas_anuladas:
            continue  # Saltar los pedidos con cuenta anulada
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

                # 1. Crear la Factura de Gasto
                factura = Factura.objects.create(
                    numero_factura=numero_factura or f"G-{pedido.numero_pedido}",
                    tipo='GASTO',
                    fecha=request.POST.get('fecha_emision') or datetime.now().date(),
                    fecha_vencimiento=request.POST.get('fecha_vencimiento'),
                    proveedor=pedido.proveedor,
                    pedido=pedido,
                    categoria='COMERCIO_MATERIALES',
                    base=pedido.total_importe,
                    iva_porcentaje=0,  # Reciclaje → IVA 0%
                    estado_pago='PENDIENTE',
                    notas=request.POST.get('notas', '') or f'Generada desde pedido {pedido.numero_pedido}',
                    archivo_justificante=request.FILES.get('archivo_factura') or None,
                )

                # 2. Crear la CuentaPorPagar asociada
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