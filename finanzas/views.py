from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.db.models import Sum, Q
from datetime import datetime, timedelta, date
from weasyprint import HTML

from .models import (
    Factura, CuentaPorPagar, PagoCuentaPorPagar,
    CuentaPorCobrar, CobroCuentaPorCobrar
)
from clientes.models import Cliente
from proveedores.models import Proveedor
from pedidos.models import Pedido
from core.models import DatosEmpresa
from django.db import transaction
from decimal import Decimal

# ============================================
# FUNCIÓN AUXILIAR: Crear cuenta para factura
# ============================================

def _crear_cuenta_para_factura(factura):
    """
    Crea la CuentaPorCobrar (si INGRESO) o CuentaPorPagar (si GASTO)
    asociada a una factura. No hace nada si:
    - Ya existe una cuenta con ese numero_factura
    - No hay cliente/proveedor en la factura
    """
    # Evitar duplicados
    if factura.tipo == 'INGRESO':
        if CuentaPorCobrar.objects.filter(numero_factura=factura.numero_factura).exists():
            return None
        if not factura.cliente:
            return None
        
        return CuentaPorCobrar.objects.create(
            concepto=f"Factura {factura.numero_factura}",
            cliente=factura.cliente,
            importe_total=factura.total,
            fecha_emision=factura.fecha,
            fecha_vencimiento=factura.fecha_vencimiento or factura.fecha,
            numero_factura=factura.numero_factura,
            notas=f"Generada desde factura {factura.numero_factura}",
        )
    
    elif factura.tipo == 'GASTO':
        if CuentaPorPagar.objects.filter(numero_factura=factura.numero_factura).exists():
            return None
        if not factura.proveedor:
            return None
        
        return CuentaPorPagar.objects.create(
            concepto=f"Factura {factura.numero_factura}",
            categoria='PROVEEDOR',
            proveedor=factura.proveedor,
            importe_total=factura.total,
            fecha_emision=factura.fecha,
            fecha_vencimiento=factura.fecha_vencimiento or factura.fecha,
            numero_factura=factura.numero_factura,
            notas=f"Generada desde factura {factura.numero_factura}",
        )
    
    return None

# ============================================
# FACTURAS
# ============================================

@login_required
def lista_facturas(request):
    facturas = Factura.objects.exclude(estado_pago='ANULADO').order_by('-fecha')

    totales = facturas.aggregate(
        ingresos=Sum('total', filter=Q(tipo='INGRESO')),
        gastos=Sum('total', filter=Q(tipo='GASTO')),
    )
    total_ingresos = totales['ingresos'] or 0
    total_gastos = totales['gastos'] or 0
    beneficio = total_ingresos - total_gastos

    context = {
        'facturas': facturas,
        'total_ingresos': total_ingresos,
        'total_gastos': total_gastos,
        'beneficio': beneficio,
    }
    return render(request, 'finanzas/lista.html', context)


@login_required
def nueva_factura(request):
    """Formulario para crear una nueva factura"""
    if request.method == 'POST':
        try:
            tipo_factura = request.POST.get('tipo')
            cliente_id = request.POST.get('cliente') if tipo_factura == 'INGRESO' else None
            proveedor_id = request.POST.get('proveedor') if tipo_factura == 'GASTO' else None

            factura = Factura.objects.create(
                numero_factura=request.POST.get('numero_factura'),
                tipo=tipo_factura,
                fecha=request.POST.get('fecha') or datetime.now().date(),
                fecha_vencimiento=request.POST.get('fecha_vencimiento') or None,
                cliente_id=cliente_id or None,
                proveedor_id=proveedor_id or None,
                pedido_id=request.POST.get('pedido') or None,
                categoria=request.POST.get('categoria', 'OTROS'),
                base=request.POST.get('base', 0),
                iva_porcentaje=request.POST.get('iva_porcentaje', 21),
                estado_pago=request.POST.get('estado_pago', 'PENDIENTE'),
                notas=request.POST.get('notas', ''),
                archivo_justificante=request.FILES.get('archivo_factura') or None,
            )
            # Crear cuenta asociada si se ha marcado el checkbox
            if request.POST.get('crear_cuenta'):
                _crear_cuenta_para_factura(factura)

            messages.success(request, f'✅ Factura {factura.numero_factura} creada correctamente')
            return redirect('lista_facturas')

        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')

    context = {
        'clientes': Cliente.objects.all().order_by('nombre'),
        'proveedores': Proveedor.objects.all().order_by('nombre'),
        'pedidos': Pedido.objects.all().order_by('-fecha')[:50],
        'tipos': Factura.TIPO_FACTURA,
        'categorias': Factura.CATEGORIAS,
        'estados': Factura.ESTADO_PAGO,
        'fecha_actual': datetime.now().strftime('%Y-%m-%d'),
    }
    return render(request, 'finanzas/nueva_factura.html', context)


@login_required
def editar_factura(request, factura_id):
    """Formulario para editar una factura existente"""
    factura = get_object_or_404(Factura, id=factura_id)

    if request.method == 'POST':
        try:
            tipo_factura = request.POST.get('tipo')

            factura.numero_factura = request.POST.get('numero_factura')
            factura.tipo = tipo_factura
            factura.fecha = request.POST.get('fecha')
            factura.fecha_vencimiento = request.POST.get('fecha_vencimiento') or None
            factura.cliente_id = request.POST.get('cliente') if tipo_factura == 'INGRESO' else None
            factura.proveedor_id = request.POST.get('proveedor') if tipo_factura == 'GASTO' else None
            factura.pedido_id = request.POST.get('pedido') or None
            factura.categoria = request.POST.get('categoria')
            factura.base = request.POST.get('base', 0)
            factura.iva_porcentaje = request.POST.get('iva_porcentaje', 21)
            factura.estado_pago = request.POST.get('estado_pago')
            factura.notas = request.POST.get('notas', '')
            # Actualizar archivo si se ha subido uno nuevo
            if request.FILES.get('archivo_factura'):
                factura.archivo_factura = request.FILES.get('archivo_factura')

            factura.save()

            messages.success(request, f'✅ Factura {factura.numero_factura} actualizada')
            return redirect('lista_facturas')
        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')

    context = {
        'factura': factura,
        'clientes': Cliente.objects.all().order_by('nombre'),
        'proveedores': Proveedor.objects.all().order_by('nombre'),
        'pedidos': Pedido.objects.all().order_by('-fecha')[:50],
        'tipos': Factura.TIPO_FACTURA,
        'categorias': Factura.CATEGORIAS,
        'estados': Factura.ESTADO_PAGO,
    }
    return render(request, 'finanzas/editar_factura.html', context)


@login_required
def confirmar_eliminar_factura(request, factura_id):
    factura = get_object_or_404(Factura, id=factura_id)
    context = {
        'factura': factura,
    }
    return render(request, 'finanzas/confirmar_eliminar.html', context)


@login_required
def eliminar_factura(request, factura_id):
    factura = get_object_or_404(Factura, id=factura_id)

    if request.method == 'POST':
        numero = factura.numero_factura

        with transaction.atomic():
            # Eliminar cuentas asociadas (con sus pagos/cobros por CASCADE)
            CuentaPorCobrar.objects.filter(numero_factura=numero).delete()
            CuentaPorPagar.objects.filter(numero_factura=numero).delete()

            # Eliminar la factura
            factura.delete()

        messages.success(request, f'✅ Factura {numero} y sus cuentas asociadas eliminadas')

        return redirect('lista_facturas')

    return redirect('confirmar_eliminar_factura', factura_id=factura_id)


@login_required
def factura_pdf(request, factura_id):
    """Genera un PDF profesional de la factura"""
    factura = get_object_or_404(Factura, id=factura_id)

    try:
        empresa = DatosEmpresa.objects.first()
    except DatosEmpresa.DoesNotExist:
        empresa = None

    html_string = render_to_string('finanzas/factura_pdf.html', {
        'factura': factura,
        'empresa': empresa,
        'fecha_actual': datetime.now(),
    })

    html = HTML(string=html_string, base_url=request.build_absolute_uri())
    pdf = html.write_pdf()

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Factura_{factura.numero_factura}.pdf"'
    return response


# ============================================
# CUENTAS POR PAGAR
# ============================================

@login_required
def cuentas_por_pagar(request):
    """Lista de cuentas por pagar (deudas)"""
    cuentas = CuentaPorPagar.objects.all().order_by('fecha_vencimiento')

    categoria = request.GET.get('categoria', '')
    estado = request.GET.get('estado', '')

    if categoria:
        cuentas = cuentas.filter(categoria=categoria)
    if estado:
        cuentas = cuentas.filter(estado=estado)

    pendientes = cuentas.filter(estado__in=['PENDIENTE', 'PARCIAL'])
    vencidas = [c for c in pendientes if c.esta_vencida]

    total_pendiente = sum(c.saldo_pendiente for c in pendientes)
    total_vencido = sum(c.saldo_pendiente for c in vencidas)

    context = {
        'cuentas': cuentas,
        'pendientes': pendientes,
        'vencidas': vencidas,
        'total_pendiente': total_pendiente,
        'total_vencido': total_vencido,
        'categorias': CuentaPorPagar.CATEGORIA_CHOICES,
        'estados': CuentaPorPagar.ESTADO_CHOICES,
        'categoria_filtro': categoria,
        'estado_filtro': estado,
    }
    return render(request, 'finanzas/cuentas_por_pagar.html', context)


@login_required
def nueva_cuenta_por_pagar(request):
    """Crear una nueva cuenta por pagar"""
    if request.method == 'POST':
        try:
            cuenta = CuentaPorPagar.objects.create(
                concepto=request.POST.get('concepto'),
                categoria=request.POST.get('categoria'),
                proveedor_id=request.POST.get('proveedor') or None,
                importe_total=request.POST.get('importe_total'),
                fecha_emision=request.POST.get('fecha_emision'),
                fecha_vencimiento=request.POST.get('fecha_vencimiento'),
                periodicidad=request.POST.get('periodicidad', 'UNICO'),
                numero_factura=request.POST.get('numero_factura', ''),
                notas=request.POST.get('notas', ''),
                archivo_factura=request.FILES.get('archivo_factura') or None,
            )
            messages.success(request, '✅ Cuenta por pagar creada')
            return redirect('cuentas_por_pagar')
        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')

    context = {
        'categorias': CuentaPorPagar.CATEGORIA_CHOICES,
        'periodicidades': CuentaPorPagar.PERIODICIDAD,
        'proveedores': Proveedor.objects.all().order_by('nombre'),
        'fecha_actual': date.today().strftime('%Y-%m-%d'),
    }
    return render(request, 'finanzas/nueva_cuenta_por_pagar.html', context)


@login_required
def registrar_pago_cuenta(request, cuenta_id):
    """Registrar un pago parcial o total"""
    cuenta = get_object_or_404(CuentaPorPagar, id=cuenta_id)

    if request.method == 'POST':
        try:
            PagoCuentaPorPagar.objects.create(
                cuenta=cuenta,
                importe=request.POST.get('importe'),
                fecha=request.POST.get('fecha'),
                metodo=request.POST.get('metodo', ''),
                referencia=request.POST.get('referencia', ''),
                notas=request.POST.get('notas', ''),
                archivo_justificante=request.FILES.get('archivo_justificante') or None,
            )
            messages.success(request, f'✅ Pago registrado: {request.POST.get("importe")}€')
            return redirect('cuentas_por_pagar')
        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')

    context = {
        'cuenta': cuenta,
        'fecha_actual': date.today().strftime('%Y-%m-%d'),
    }
    return render(request, 'finanzas/registrar_pago_cuenta.html', context)


# ============================================
# CUENTAS POR COBRAR
# ============================================

@login_required
def cuentas_por_cobrar(request):
    """Lista de cuentas por cobrar"""
    cuentas = CuentaPorCobrar.objects.all().order_by('fecha_vencimiento')

    estado = request.GET.get('estado', '')
    if estado:
        cuentas = cuentas.filter(estado=estado)

    pendientes = cuentas.filter(estado__in=['PENDIENTE', 'PARCIAL'])
    vencidas = [c for c in pendientes if c.dias_para_vencer < 0]

    total_pendiente = sum(c.saldo_pendiente for c in pendientes)
    total_vencido = sum(c.saldo_pendiente for c in vencidas)

    context = {
        'cuentas': cuentas,
        'pendientes': pendientes,
        'vencidas': vencidas,
        'total_pendiente': total_pendiente,
        'total_vencido': total_vencido,
        'estados': CuentaPorCobrar.ESTADO_CHOICES,
        'estado_filtro': estado,
    }
    return render(request, 'finanzas/cuentas_por_cobrar.html', context)


@login_required
def nueva_cuenta_por_cobrar(request):
    """Crear una nueva cuenta por cobrar"""
    if request.method == 'POST':
        try:
            cuenta = CuentaPorCobrar.objects.create(
                concepto=request.POST.get('concepto'),
                cliente_id=request.POST.get('cliente'),
                importe_total=request.POST.get('importe_total'),
                fecha_emision=request.POST.get('fecha_emision'),
                fecha_vencimiento=request.POST.get('fecha_vencimiento'),
                numero_factura=request.POST.get('numero_factura', ''),
                notas=request.POST.get('notas', ''),
            )
            messages.success(request, '✅ Cuenta por cobrar creada')
            return redirect('cuentas_por_cobrar')
        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')

    context = {
        'clientes': Cliente.objects.all().order_by('nombre'),
        'fecha_actual': date.today().strftime('%Y-%m-%d'),
    }
    return render(request, 'finanzas/nueva_cuenta_por_cobrar.html', context)


@login_required
def registrar_cobro_cuenta(request, cuenta_id):
    """Registrar un cobro"""
    cuenta = get_object_or_404(CuentaPorCobrar, id=cuenta_id)

    if request.method == 'POST':
        try:
            CobroCuentaPorCobrar.objects.create(
                cuenta=cuenta,
                importe=request.POST.get('importe'),
                fecha=request.POST.get('fecha'),
                metodo=request.POST.get('metodo', ''),
                referencia=request.POST.get('referencia', ''),
                notas=request.POST.get('notas', ''),
                archivo_justificante=request.FILES.get('archivo_justificante') or None,
            )
            messages.success(request, '✅ Cobro registrado')
            return redirect('cuentas_por_cobrar')
        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')

    context = {
        'cuenta': cuenta,
        'fecha_actual': date.today().strftime('%Y-%m-%d'),
    }
    return render(request, 'finanzas/registrar_cobro_cuenta.html', context)


# ============================================
# DASHBOARD FINANCIERO
# ============================================

@login_required
def dashboard_financiero(request):
    """Dashboard con resumen de deudas y cobros"""

    pagar_pendientes = CuentaPorPagar.objects.exclude(estado='PAGADO')
    total_pagar = sum(c.saldo_pendiente for c in pagar_pendientes)
    vencidas_pagar = [c for c in pagar_pendientes if c.esta_vencida]
    total_vencido_pagar = sum(c.saldo_pendiente for c in vencidas_pagar)

    cobrar_pendientes = CuentaPorCobrar.objects.exclude(estado='COBRADO')
    total_cobrar = sum(c.saldo_pendiente for c in cobrar_pendientes)
    vencidas_cobrar = [c for c in cobrar_pendientes if c.dias_para_vencer < 0]
    total_vencido_cobrar = sum(c.saldo_pendiente for c in vencidas_cobrar)

    balance = total_cobrar - total_pagar

    categorias = {}
    for c in pagar_pendientes:
        cat = c.get_categoria_display()
        if cat not in categorias:
            categorias[cat] = 0
        categorias[cat] += float(c.saldo_pendiente)

    context = {
        'total_pagar': total_pagar,
        'total_vencido_pagar': total_vencido_pagar,
        'num_pagar_pendientes': pagar_pendientes.count(),
        'num_vencidas_pagar': len(vencidas_pagar),

        'total_cobrar': total_cobrar,
        'total_vencido_cobrar': total_vencido_cobrar,
        'num_cobrar_pendientes': cobrar_pendientes.count(),
        'num_vencidas_cobrar': len(vencidas_cobrar),

        'balance': balance,
        'categorias_pagar': categorias,

        'proximas_pagar': pagar_pendientes.order_by('fecha_vencimiento')[:5],
        'proximas_cobrar': cobrar_pendientes.order_by('fecha_vencimiento')[:5],
    }
    return render(request, 'finanzas/dashboard_financiero.html', context)


# ============================================
# REGISTRAR COBRO/PAGO DESDE FACTURA
# ============================================

@login_required
def registrar_cobro_pago_factura(request, factura_id):
    """Registra un cobro (si es ingreso) o pago (si es gasto) desde una factura"""
    factura = get_object_or_404(Factura, id=factura_id)

    if factura.tipo == 'INGRESO':
        cuenta_existente = CuentaPorCobrar.objects.filter(numero_factura=factura.numero_factura).first()
    else:
        cuenta_existente = CuentaPorPagar.objects.filter(numero_factura=factura.numero_factura).first()

    if cuenta_existente:
        messages.warning(request, '⚠️ Esta factura ya tiene una cuenta asociada')
        if factura.tipo == 'INGRESO':
            return redirect('cuentas_por_cobrar')
        else:
            return redirect('cuentas_por_pagar')

    if request.method == 'POST':
        try:
            fecha_vencimiento = request.POST.get('fecha_vencimiento')

            if factura.tipo == 'INGRESO':
                cuenta = CuentaPorCobrar.objects.create(
                    concepto=f"Factura {factura.numero_factura}",
                    cliente=factura.cliente,
                    importe_total=factura.total,
                    fecha_emision=factura.fecha,
                    fecha_vencimiento=fecha_vencimiento,
                    numero_factura=factura.numero_factura,
                    notas=f"Generada desde la factura {factura.numero_factura}",
                )
                messages.success(request, '✅ Cuenta por cobrar creada')
                return redirect('registrar_cobro_cuenta', cuenta_id=cuenta.id)
            else:
                cuenta = CuentaPorPagar.objects.create(
                    concepto=f"Factura {factura.numero_factura}",
                    categoria='PROVEEDOR',
                    proveedor=factura.proveedor,
                    importe_total=factura.total,
                    fecha_emision=factura.fecha,
                    fecha_vencimiento=fecha_vencimiento,
                    numero_factura=factura.numero_factura,
                    notas=f"Generada desde la factura {factura.numero_factura}",
                )
                messages.success(request, '✅ Cuenta por pagar creada')
                return redirect('registrar_pago_cuenta', cuenta_id=cuenta.id)

        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')

    fecha_sugerida = (factura.fecha + timedelta(days=30)).strftime('%Y-%m-%d')

    context = {
        'factura': factura,
        'fecha_sugerida': fecha_sugerida,
    }
    return render(request, 'finanzas/registrar_cobro_pago_factura.html', context)

# ============================================
# ELIMINAR CUENTAS POR PAGAR / COBRAR
# ============================================

@login_required
def confirmar_eliminar_cuenta_por_pagar(request, cuenta_id):
    """Muestra página de confirmación para eliminar una cuenta por pagar"""
    cuenta = get_object_or_404(CuentaPorPagar, id=cuenta_id)

    # Comprobar si tiene factura asociada
    tiene_factura = Factura.objects.filter(numero_factura=cuenta.numero_factura).exists()

    context = {
        'cuenta': cuenta,
        'tiene_factura': tiene_factura,
    }
    return render(request, 'finanzas/confirmar_eliminar_cuenta_pagar.html', context)


@login_required
def eliminar_cuenta_por_pagar(request, cuenta_id):
    """Elimina definitivamente una cuenta por pagar (solo si no tiene factura)"""
    cuenta = get_object_or_404(CuentaPorPagar, id=cuenta_id)

    # Bloqueo backend: si tiene factura, no se puede borrar
    if Factura.objects.filter(numero_factura=cuenta.numero_factura).exists():
        messages.error(request, '❌ No se puede eliminar: tiene una factura asociada. Elimina primero la factura.')
        return redirect('cuentas_por_pagar')

    if request.method == 'POST':
        concepto = cuenta.concepto
        cuenta.delete()
        messages.success(request, f'✅ Cuenta "{concepto}" eliminada correctamente')
        return redirect('cuentas_por_pagar')

    return redirect('confirmar_eliminar_cuenta_por_pagar', cuenta_id=cuenta_id)


@login_required
def confirmar_eliminar_cuenta_por_cobrar(request, cuenta_id):
    """Muestra página de confirmación para eliminar una cuenta por cobrar"""
    cuenta = get_object_or_404(CuentaPorCobrar, id=cuenta_id)

    tiene_factura = Factura.objects.filter(numero_factura=cuenta.numero_factura).exists()

    context = {
        'cuenta': cuenta,
        'tiene_factura': tiene_factura,
    }
    return render(request, 'finanzas/confirmar_eliminar_cuenta_cobrar.html', context)


@login_required
def eliminar_cuenta_por_cobrar(request, cuenta_id):
    """Elimina definitivamente una cuenta por cobrar (solo si no tiene factura)"""
    cuenta = get_object_or_404(CuentaPorCobrar, id=cuenta_id)

    if Factura.objects.filter(numero_factura=cuenta.numero_factura).exists():
        messages.error(request, '❌ No se puede eliminar: tiene una factura asociada. Elimina primero la factura.')
        return redirect('cuentas_por_cobrar')

    if request.method == 'POST':
        concepto = cuenta.concepto
        cuenta.delete()
        messages.success(request, f'✅ Cuenta "{concepto}" eliminada correctamente')
        return redirect('cuentas_por_cobrar')

    return redirect('confirmar_eliminar_cuenta_por_cobrar', cuenta_id=cuenta_id)

# ============================================
# EXPORTAR A EXCEL
# ============================================

from core.utils import exportar_excel
from datetime import date


@login_required
def exportar_facturas_excel(request):
    """Exporta facturas a Excel."""
    facturas = Factura.objects.exclude(estado_pago='ANULADO').order_by('-fecha')

    # Filtros opcionales
    desde = request.GET.get('desde')
    hasta = request.GET.get('hasta')
    tipo = request.GET.get('tipo')

    if desde:
        facturas = facturas.filter(fecha__gte=desde)
    if hasta:
        facturas = facturas.filter(fecha__lte=hasta)
    if tipo:
        facturas = facturas.filter(tipo=tipo)

    cabeceras = [
        'Nº Factura', 'Tipo', 'Fecha', 'Vencimiento',
        'Cliente/Proveedor', 'Categoría', 'Base (€)', 'IVA (%)', 'IVA (€)', 'Total (€)',
        'Estado Pago', 'Notas'
    ]

    filas = []
    for f in facturas:
        entidad = f.cliente.nombre if f.cliente else (f.proveedor.nombre if f.proveedor else '—')
        filas.append([
            f.numero_factura,
            f.get_tipo_display(),
            f.fecha.strftime('%d/%m/%Y') if f.fecha else '',
            f.fecha_vencimiento.strftime('%d/%m/%Y') if f.fecha_vencimiento else '',
            entidad,
            f.get_categoria_display(),
            float(f.base),
            float(f.iva_porcentaje),
            float(f.iva),
            float(f.total),
            f.get_estado_pago_display(),
            f.notas or '',
        ])

    hoy = date.today().strftime('%Y%m%d')
    nombre = f'Facturas_{hoy}.xlsx'

    return exportar_excel(nombre, cabeceras, filas, titulo_hoja="Facturas")

# ============================================
# LIBRO DE GASTOS E INGRESOS
# ============================================

@login_required
def libro_gastos_ingresos(request):
    """Libro mayor con todas las facturas de gasto e ingreso, con filtros."""
    facturas = Factura.objects.exclude(estado_pago='ANULADO').order_by('-fecha')

    # Filtros
    tipo = request.GET.get('tipo', '')
    categoria = request.GET.get('categoria', '')
    desde = request.GET.get('desde', '')
    hasta = request.GET.get('hasta', '')

    if tipo:
        facturas = facturas.filter(tipo=tipo)
    if categoria:
        facturas = facturas.filter(categoria=categoria)
    if desde:
        facturas = facturas.filter(fecha__gte=desde)
    if hasta:
        facturas = facturas.filter(fecha__lte=hasta)

    # Totales
    totales = facturas.aggregate(
        base=Sum('base'),
        iva=Sum('iva'),
        total=Sum('total'),
    )
    total_base = totales['base'] or Decimal('0')
    total_iva = totales['iva'] or Decimal('0')
    total_total = totales['total'] or Decimal('0')

    context = {
        'facturas': facturas,
        'total_base': total_base,
        'total_iva': total_iva,
        'total_total': total_total,
        'tipos': Factura.TIPO_FACTURA,
        'categorias': Factura.CATEGORIAS,
        'tipo_filtro': tipo,
        'categoria_filtro': categoria,
        'desde_filtro': desde,
        'hasta_filtro': hasta,
        'num_facturas': facturas.count(),
    }
    return render(request, 'finanzas/libro_gastos_ingresos.html', context)

@login_required
def exportar_libro_excel(request):
    """Exporta el libro de gastos e ingresos a Excel con hoja por trimestre."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from datetime import date

    # Filtros (igual que la vista anterior)
    tipo = request.GET.get('tipo', '')
    categoria = request.GET.get('categoria', '')
    desde = request.GET.get('desde', '')
    hasta = request.GET.get('hasta', '')
    year = request.GET.get('year', date.today().year)

    facturas = Factura.objects.exclude(estado_pago='ANULADO').order_by('-fecha')

    if tipo:
        facturas = facturas.filter(tipo=tipo)
    if categoria:
        facturas = facturas.filter(categoria=categoria)
    if desde:
        facturas = facturas.filter(fecha__gte=desde)
    if hasta:
        facturas = facturas.filter(fecha__lte=hasta)

    # Crear Excel
    wb = Workbook()
    wb.remove(wb.active)  # Quitar hoja por defecto

    # Cabeceras comunes
    cabeceras = [
        'Fecha', 'Nº Factura', 'Tipo', 'Entidad', 'Categoría',
        'Base (€)', 'IVA (%)', 'IVA (€)', 'Total (€)', 'Estado', 'Notas'
    ]

    # Estilos
    estilo_cabecera = Font(bold=True, color='FFFFFF')
    fondo_cabecera = PatternFill('solid', fgColor='2D6A4F')

    # Procesar cada trimestre
    for trimestre in range(1, 5):
        mes_inicio = (trimestre - 1) * 3 + 1
        mes_fin = mes_inicio + 2

        facturas_trim = facturas.filter(
            fecha__month__gte=mes_inicio,
            fecha__month__lte=mes_fin
        )

        ws = wb.create_sheet(title=f"T{trimestre} {year}")

        # Cabecera
        for col, cab in enumerate(cabeceras, 1):
            celda = ws.cell(row=1, column=col, value=cab)
            celda.font = estilo_cabecera
            celda.fill = fondo_cabecera
            celda.alignment = Alignment(horizontal='center')

        # Filas
        fila = 2
        total_base_trim = Decimal('0')
        total_iva_trim = Decimal('0')
        total_total_trim = Decimal('0')

        for f in facturas_trim:
            entidad = f.cliente.nombre if f.cliente else (f.proveedor.nombre if f.proveedor else '—')
            ws.cell(row=fila, column=1, value=f.fecha.strftime('%d/%m/%Y'))
            ws.cell(row=fila, column=2, value=f.numero_factura)
            ws.cell(row=fila, column=3, value=f.get_tipo_display())
            ws.cell(row=fila, column=4, value=entidad)
            ws.cell(row=fila, column=5, value=f.get_categoria_display())
            ws.cell(row=fila, column=6, value=float(f.base))
            ws.cell(row=fila, column=7, value=float(f.iva_porcentaje))
            ws.cell(row=fila, column=8, value=float(f.iva))
            ws.cell(row=fila, column=9, value=float(f.total))
            ws.cell(row=fila, column=10, value=f.get_estado_pago_display())
            ws.cell(row=fila, column=11, value=f.notas or '')

            total_base_trim += f.base
            total_iva_trim += f.iva
            total_total_trim += f.total
            fila += 1

        # Fila de totales
        fila += 1
        ws.cell(row=fila, column=1, value='TOTAL TRIMESTRE').font = Font(bold=True)
        ws.cell(row=fila, column=6, value=float(total_base_trim)).font = Font(bold=True)
        ws.cell(row=fila, column=8, value=float(total_iva_trim)).font = Font(bold=True)
        ws.cell(row=fila, column=9, value=float(total_total_trim)).font = Font(bold=True)

    # Guardar
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="Libro_{year}.xlsx"'
    wb.save(response)
    return response

@login_required
def anular_factura(request, factura_id):
    """Anula una factura (no la elimina, la marca como ANULADA)"""
    factura = get_object_or_404(Factura, id=factura_id)

    if request.method == 'POST':
        numero = factura.numero_factura
        factura.estado_pago = 'ANULADO'
        factura.save()
        # Anular también su cuenta asociada
        CuentaPorCobrar.objects.filter(numero_factura=numero).update(estado='ANULADO')
        CuentaPorPagar.objects.filter(numero_factura=numero).update(estado='ANULADO')
        messages.success(request, f'✅ Factura {numero} anulada')
        return redirect('lista_facturas')

    return redirect('lista_facturas')