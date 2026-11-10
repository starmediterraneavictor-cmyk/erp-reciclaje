from decimal import Decimal
from django.db import models
from django.db.models import Max, Sum
from django.utils import timezone
from clientes.models import Cliente
from proveedores.models import Proveedor
from inventario.models import Material


class Pedido(models.Model):
    TIPO_OPERACION = [
        ('VENTA_MAT', 'Venta de Material'),
        ('COMPRA_MAT', 'Compra de Material'),
        ('MAQUILA', 'Maquila'),
    ]
    
    ESTADO_PEDIDO = [
        ('PREVISION','Previsión (sin material)'),
        ('PENDIENTE', 'Pendiente'),
        ('PROCESANDO', 'Procesando'),
        ('COMPLETADO', 'Completado'),
        ('CANCELADO', 'Cancelado'),
    ]
    
    INCOTERM_CHOICES = [
        ('', '-- Sin incoterm --'),
        ('EXW', 'EXW - En fábrica'),
        ('FOB', 'FOB - Libre a bordo'),
        ('CIF', 'CIF - Coste, seguro y flete'),
        ('CFR', 'CFR - Coste y flete'),
        ('DAP', 'DAP - Entrega en destino'),
        ('DDP', 'DDP - Entrega con derechos pagados'),
    ]
    
    numero_pedido = models.CharField(max_length=50, unique=True, blank=True)
    tipo = models.CharField(max_length=20, choices=TIPO_OPERACION, default='VENTA_MAT')
    estado = models.CharField(max_length=20, choices=ESTADO_PEDIDO, default='PREVISION')
    fecha = models.DateTimeField(default=timezone.now)
    
    cliente = models.ForeignKey(
        Cliente, on_delete=models.PROTECT,
        null=True, blank=True, related_name='pedidos'
    )
    proveedor = models.ForeignKey(
        Proveedor, on_delete=models.PROTECT,
        null=True, blank=True, related_name='pedidos'
    )
    
    incoterm = models.CharField(
        max_length=10, choices=INCOTERM_CHOICES,
        blank=True, default='', verbose_name="Incoterm"
    )

    pedido_origen = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pedidos_venta',
        limit_choices_to={'tipo__in': ['COMPRA_MAT']},
        verbose_name="Pedido de compra origen"
    )

    peso_real_tn = models.DecimalField(
        max_digits=12, decimal_places=2, 
        null=True, blank=True, 
        verbose_name="Peso real en báscula (tn)"
    )

    notas = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.numero_pedido} - {self.entidad_nombre}"
    
    @property
    def es_internacional(self):
        pais = 'España'
        if self.cliente:
            pais = self.cliente.pais
        elif self.proveedor:
            pais = self.proveedor.pais
        return pais != 'España'
    
    @property
    def entidad(self):
        if self.tipo == 'VENTA_MAT':
            return self.cliente
        else:
            return self.proveedor
    
    @property
    def entidad_nombre(self):
        ent = self.entidad
        return ent.nombre if ent else '—'
    
    def save(self, *args, **kwargs):
        if not self.numero_pedido:
            year = timezone.now().year
            prefijo = 'E' if self.tipo == 'COMPRA_MAT' else 'S'
            
            ultimo = Pedido.objects.filter(
                numero_pedido__startswith=f"{year}{prefijo}"
            ).aggregate(max_num=Max('numero_pedido'))['max_num']
            
            if ultimo:
                try:
                    siguiente = int(ultimo[-4:]) + 1
                except (ValueError, TypeError):
                    siguiente = 1
            else:
                siguiente = 1
            
            self.numero_pedido = f"{year}{prefijo}{siguiente:04d}"
        super().save(*args, **kwargs)
    
    @property
    def total_kg(self):
        total = Decimal('0')
        for d in self.detalles.all():
            total += Decimal(str(d.cantidad))
        return total

    @property
    def tipos_materiales(self):
        tipos = set()
        for detalle in self.detalles.all():
            tipo_mat = getattr(detalle.material, 'tipo', None) or getattr(detalle.material, 'categoria', None)
            if tipo_mat:
                if hasattr(tipo_mat, 'nombre'):
                    tipos.add(str(tipo_mat.nombre))
                else:
                    tipos.add(str(tipo_mat))
        return list(tipos)
    
    @property
    def total_importe(self):
        total = Decimal('0')
        for d in self.detalles.all():
            total += d.subtotal
        return total

    @property
    def precio_venta_tn(self):
        if self.total_kg == 0:
            return Decimal('0')
        return self.total_importe / self.total_kg
    
    @property
    def precio_compra_tn(self):
        if self.total_kg == 0:
            return Decimal('0')
        return self.total_importe / self.total_kg
    
    @property
    def coste_compra_tn(self):
        if not self.origenes_venta.exists():
            return None
        tn_total = Decimal('0')
        coste_total = Decimal('0')
        for origen in self.origenes_venta.all():
            tn = Decimal(str(origen.cantidad_tn))
            tn_total += tn
            coste_total += tn * Decimal(str(origen.precio_compra_tn))
        if tn_total == 0:
            return None
        return coste_total / tn_total
    
    @property
    def transporte_total(self):
        total = Decimal('0')
        for d in self.detalles.all():
            total += Decimal(str(d.transporte))
        return total
    
    @property
    def coste_transporte_tn(self):
        total_tn = self.total_kg
        if total_tn == 0:
            return Decimal('0')
        
        total_transporte = self.transporte_total
        
        for origen in self.origenes_venta.all():
            if origen.pedido_compra.total_kg > 0:
                proporcion = Decimal(str(origen.cantidad_tn)) / origen.pedido_compra.total_kg
                total_transporte += origen.pedido_compra.transporte_total * proporcion
        
        return total_transporte / total_tn     
    
    @property
    def beneficio_tn(self):
        if not self.origenes_venta.exists():
            return None
        coste_compra = self.coste_compra_tn
        coste_trans = self.coste_transporte_tn
        venta = self.precio_venta_tn
        if coste_compra is None:
            return None
        return venta - coste_compra - coste_trans
    
    @property
    def beneficio_total(self):
        if not self.origenes_venta.exists():
            return None
        if self.beneficio_tn is None:
            return None
        return self.beneficio_tn * self.total_kg
    
    @property
    def margen_pct(self):
        if not self.origenes_venta.exists() or self.precio_venta_tn == 0:
            return None
        if self.beneficio_tn is None:
            return None
        return (self.beneficio_tn / self.precio_venta_tn) * 100

    @property
    def total_cobrado(self):
        from finanzas.models import CuentaPorCobrar
        cuenta = CuentaPorCobrar.objects.filter(
            concepto__icontains=self.numero_pedido
        ).first()
        if cuenta and cuenta.estado == 'ANULADO':
            return Decimal('0')
        if cuenta:
            return sum((c.importe for c in cuenta.cobros.all()), Decimal('0'))
        return Decimal('0')
    
    @property
    def saldo_pendiente_cobro(self):
        return self.total_importe - self.total_cobrado

    @property
    def tiene_factura_activa(self):
        return self.facturas.exclude(estado_pago='ANULADO').exists()

    @property
    def factura_activa(self):
        return self.facturas.exclude(estado_pago='ANULADO').first()

    @property
    def tiene_cobros(self):
        from finanzas.models import CuentaPorCobrar
        factura = self.facturas.exclude(estado_pago='ANULADO').first()
        if not factura:
            return False
        cuenta = CuentaPorCobrar.objects.filter(numero_factura=factura.numero_factura).first()
        if not cuenta:
            return False
        return cuenta.cobros.exists()

    @property
    def total_pendiente_cobro(self):
        from finanzas.models import CuentaPorCobrar
        cuenta = CuentaPorCobrar.objects.filter(
            concepto__icontains=self.numero_pedido
        ).first()
        
        if cuenta and cuenta.estado == 'ANULADO':
            return Decimal('0')
        
        return self.total_importe - self.total_cobrado

    @property
    def peso_original_notas(self):
        import re
        if self.notas:
            match = re.search(r'Peso original:\s*([\d\.]+)', self.notas)
            if match:
                return Decimal(match.group(1))
        return self.total_kg
    
    @property
    def diferencia_peso_tn(self):
        if self.peso_real_tn is None:
            return Decimal('0')
        return self.peso_real_tn - self.peso_original_notas

    @property
    def importe_ajuste(self):
        if self.peso_real_tn is None:
            return Decimal('0')
        return self.diferencia_peso_tn * self.precio_compra_tn

    @property
    def tn_disponibles(self):
        if self.tipo != 'COMPRA_MAT':
            return self.total_kg
        
        # 🆕 Si hay un peso real ajustado, usamos ese. Si no, el previsto.
        base_tn = self.peso_real_tn if self.peso_real_tn is not None else self.total_kg
        
        tn_vendidas = sum(o.cantidad_tn for o in self.ventas_asociadas.all())
        return base_tn - tn_vendidas

    @property
    def total_comisiones(self):
        return sum((c.importe_comision for c in self.comisiones.all()), Decimal('0'))

    @property
    def beneficio_real_total(self):
        if self.beneficio_total is None:
            return None
        return self.beneficio_total - self.total_comisiones

    @property
    def beneficio_real_tn(self):
        if self.total_kg == 0 or self.beneficio_real_total is None:
            return None
        return self.beneficio_real_total / self.total_kg
    
    class Meta:
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"
        ordering = ['-fecha']


class DetallePedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='detalles')
    material = models.ForeignKey(Material, on_delete=models.PROTECT)
    cantidad = models.DecimalField(max_digits=12, decimal_places=2)
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    transporte = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    def __str__(self):
        return f"{self.pedido.numero_pedido} - {self.material.codigo}"
    
    @property
    def subtotal(self):
        cantidad = Decimal(str(self.cantidad))
        precio = Decimal(str(self.precio_unitario))
        return cantidad * precio
    
    @property
    def subtotal_con_transporte(self):
        cantidad = Decimal(str(self.cantidad))
        precio = Decimal(str(self.precio_unitario))
        transporte = Decimal(str(self.transporte))
        return (cantidad * precio) + transporte

    @property
    def transporte_tn(self):
        if self.cantidad and self.cantidad > 0:
            return self.transporte / self.cantidad
        return 0
    
    class Meta:
        verbose_name = "Detalle de pedido"
        verbose_name_plural = "Detalles de pedidos"


class CondicionPago(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    porcentaje_anticipo = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    dias_antes_llegada = models.IntegerField(default=0)
    activo = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.nombre} ({self.porcentaje_anticipo}% + resto {self.dias_antes_llegada}d antes)"
    
    class Meta:
        verbose_name = "Condición de pago"
        verbose_name_plural = "Condiciones de pago"


class PedidoInternacional(models.Model):
    AMBITO_CHOICES = [
        ('NACIONAL', 'Nacional'),
        ('INTERNACIONAL', 'Internacional'),
    ]
    
    ambito = models.CharField(max_length=20, choices=AMBITO_CHOICES, default='INTERNACIONAL')
    provincia_destino = models.CharField(max_length=100, blank=True, help_text="Solo para nacional")
    
    ESTADO_CHOICES = [
        ('ABIERTO', 'Abierto / En preparación'),
        ('EN_TRANSITO', 'En tránsito marítimo'),
        ('EN_DESTINO', 'En destino / Aduana'),
        ('ENTREGADO', 'Entregado al cliente'),
        ('CERRADO', 'Cerrado y cobrado'),
    ]
    
    INCOTERM_CHOICES = [
        ('EXW', 'EXW - En fábrica'),
        ('FOB', 'FOB - Libre a bordo'),
        ('CIF', 'CIF - Coste, seguro y flete'),
        ('CFR', 'CFR - Coste y flete'),
        ('DAP', 'DAP - Entrega en destino'),
        ('DDP', 'DDP - Entrega con derechos pagados'),
    ]
    
    pedido = models.OneToOneField(Pedido, on_delete=models.CASCADE, related_name='internacional')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='ABIERTO')
    incoterm = models.CharField(max_length=10, choices=INCOTERM_CHOICES, default='CIF')
    condicion_pago = models.ForeignKey(CondicionPago, on_delete=models.SET_NULL, null=True, blank=True)
    
    numero_contenedor = models.CharField(max_length=50, blank=True)
    numero_precinto = models.CharField(max_length=50, blank=True)
    naviera = models.CharField(max_length=100, blank=True)
    numero_bl = models.CharField(max_length=50, blank=True, verbose_name="Nº Bill of Lading")
    buque = models.CharField(max_length=100, blank=True)
    
    fecha_carga = models.DateField(null=True, blank=True)
    fecha_salida = models.DateField(null=True, blank=True)
    fecha_eta = models.DateField(null=True, blank=True, verbose_name="Fecha estimada de llegada (ETA)")
    fecha_entrega_real = models.DateField(null=True, blank=True)
    
    valor_total = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Valor total (€)")
    coste_flete = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Coste flete (€)")
    peso_total_kg = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Peso total (tn)")
    
    puerto_origen = models.CharField(max_length=100, blank=True, default="Barcelona")
    puerto_destino = models.CharField(max_length=100, blank=True)
    
    notas = models.TextField(blank=True)
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.pedido.numero_pedido} - {self.puerto_destino} ({self.get_estado_display()})"
    
    @property
    def total_pagado(self):
        return self.pagos.aggregate(t=Sum('cantidad'))['t'] or Decimal('0')
    
    @property
    def porcentaje_pagado(self):
        if self.valor_total and self.valor_total > 0:
            return (self.total_pagado / self.valor_total) * 100
        return 0
    
    @property
    def saldo_pendiente(self):
        return self.valor_total - self.total_pagado
    
    @property
    def dias_para_llegada(self):
        if self.fecha_eta:
            from datetime import date
            delta = (self.fecha_eta - date.today()).days
            return delta
        return None
    
    @property
    def alerta_cobro(self):
        if not self.fecha_eta or not self.condicion_pago:
            return False
        if self.saldo_pendiente > 0:
            dias = self.dias_para_llegada
            if dias is not None and dias <= self.condicion_pago.dias_antes_llegada:
                return True
        return False
    
    class Meta:
        verbose_name = "Pedido internacional"
        verbose_name_plural = "Pedidos internacionales"
        ordering = ['-fecha_creacion']


class PagoInternacional(models.Model):
    TIPO_PAGO = [
        ('ANTICIPO', 'Anticipo'),
        ('SALDO', 'Saldo final'),
        ('PARCIAL', 'Pago parcial'),
        ('OTRO', 'Otro'),
    ]
    
    pedido_internacional = models.ForeignKey(
        PedidoInternacional,
        on_delete=models.CASCADE,
        related_name='pagos'
    )
    tipo = models.CharField(max_length=20, choices=TIPO_PAGO, default='ANTICIPO')
    cantidad = models.DecimalField(max_digits=15, decimal_places=2)
    fecha = models.DateField()
    metodo = models.CharField(max_length=50, blank=True, help_text="Transferencia, LC, etc.")
    referencia = models.CharField(max_length=100, blank=True, help_text="Nº referencia bancaria")
    notas = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.pedido_internacional.pedido.numero_pedido} - {self.tipo}: {self.cantidad}€"
        
    class Meta:
        verbose_name = "Pago internacional"
        verbose_name_plural = "Pagos internacionales"
        ordering = ['-fecha']


class OrigenVenta(models.Model):
    pedido_venta = models.ForeignKey(
        Pedido, on_delete=models.CASCADE,
        related_name='origenes_venta',
        limit_choices_to={'tipo': 'VENTA_MAT'}
    )
    pedido_compra = models.ForeignKey(
        Pedido, on_delete=models.PROTECT,
        related_name='ventas_asociadas',
        limit_choices_to={'tipo__in': ['COMPRA_MAT', 'MAQUILA']}
    )
    cantidad_tn = models.DecimalField(
        max_digits=12, decimal_places=2,
        verbose_name="Cantidad (tn) de este origen"
    )
    fecha_asignacion = models.DateTimeField(auto_now_add=True)
    notas = models.TextField(blank=True)

    def __str__(self):
        return f"{self.pedido_venta.numero_pedido} ← {self.pedido_compra.numero_pedido} ({self.cantidad_tn} tn)"

    @property
    def precio_compra_tn(self):
        if self.pedido_compra.total_kg > 0:
            return self.pedido_compra.total_importe / self.pedido_compra.total_kg
        return Decimal('0')

    @property
    def coste_total(self):
        return self.cantidad_tn * self.precio_compra_tn

    class Meta:
        verbose_name = "Origen de venta"
        verbose_name_plural = "Orígenes de venta"
        ordering = ['-fecha_asignacion']   


def recalcular_stock_material(material):
    from inventario.models import Inventario
    from decimal import Decimal
    
    detalles_compra = DetallePedido.objects.filter(
        material=material,
        pedido__tipo__in=['COMPRA_MAT', 'MAQUILA']
    ).exclude(pedido__estado__in=['CANCELADO', 'PREVISION'])
    
    total_disponible = Decimal('0')
    
    for detalle in detalles_compra:
        pedido = detalle.pedido
        
        # 🆕 Calculamos la proporción de este detalle sobre el total del pedido
        if pedido.total_kg > 0:
            proporcion = Decimal(str(detalle.cantidad)) / pedido.total_kg
        else:
            proporcion = Decimal('0')
            
        # 🆕 Si hay peso real, aplicamos la proporción al peso real
        if pedido.peso_real_tn is not None:
            tn_compradas_linea = pedido.peso_real_tn * proporcion
        else:
            tn_compradas_linea = detalle.cantidad
            
        tn_asignadas = sum(o.cantidad_tn for o in pedido.ventas_asociadas.all())
        libre = tn_compradas_linea - tn_asignadas
        
        if libre > 0:
            total_disponible += libre

    inventario, _ = Inventario.objects.get_or_create(material=material)
    inventario.cantidad = total_disponible
    inventario.save()
    
    return total_disponible


class Comercial(models.Model):
    nombre = models.CharField(max_length=200)
    telefono = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    activo = models.BooleanField(default=True)
    
    def __str__(self):
        return self.nombre
    
    class Meta:
        verbose_name = "Comercial"
        verbose_name_plural = "Comerciales"
        ordering = ['nombre']


class Comision(models.Model):
    TIPO_CHOICES = [
        ('PORCENTAJE', 'Porcentaje (%)'),
        ('FIJO', 'Importe Fijo (€)'),
        ('TN', 'Euros por Tonelada (€/tn)'),
    ]
    
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='comisiones')
    comercial = models.ForeignKey(Comercial, on_delete=models.PROTECT)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='TN')
    valor = models.DecimalField(max_digits=10, decimal_places=2, help_text="Porcentaje (ej: 5) o importe fijo en €")
    notas = models.TextField(blank=True)

    def __str__(self):
        return f"{self.comercial.nombre} - {self.pedido.numero_pedido}"

    @property
    def importe_comision(self):
        if self.tipo == 'PORCENTAJE':
            return self.pedido.total_importe * (self.valor / 100)
        elif self.tipo == 'TN':
            return self.pedido.total_kg * self.valor
        return self.valor

    class Meta:
        verbose_name = "Comisión"
        verbose_name_plural = "Comisiones"


# ============================================
# NUEVO MODELO: PESADAS DE CAMIÓN
# ============================================
class PesadaCamion(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='pesadas')
    fecha = models.DateField(default=timezone.now)
    matricula = models.CharField(max_length=20, blank=True, verbose_name="Matrícula / Camión")
    peso_previsto_tn = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Peso Previsto (tn)")
    peso_real_tn = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Peso Real (tn)")
    notas = models.TextField(blank=True)
    ajuste_generado = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.pedido.numero_pedido} - {self.matricula} ({self.peso_real_tn} tn)"

    @property
    def diferencia_tn(self):
        return self.peso_real_tn - self.peso_previsto_tn

    @property
    def impacto_economico(self):
        if self.pedido.total_kg == 0:
            return 0
        precio_tn = self.pedido.total_importe / self.pedido.total_kg
        return self.diferencia_tn * precio_tn

    class Meta:
        verbose_name = "Pesada de camión"
        verbose_name_plural = "Pesadas de camiones"
        ordering = ['-fecha']