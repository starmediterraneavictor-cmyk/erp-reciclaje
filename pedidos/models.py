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

    # NUEVO: enlace al pedido de compra origen (solo para ventas)
    pedido_origen = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pedidos_venta',
        limit_choices_to={'tipo__in': ['COMPRA_MAT']},
        verbose_name="Pedido de compra origen"
    )

    
    notas = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.numero_pedido} - {self.entidad_nombre}"
    
    @property
    def es_internacional(self):
        """Es internacional si el cliente o proveedor NO es de España"""
        pais = 'España'
        if self.cliente:
            pais = self.cliente.pais
        elif self.proveedor:
            pais = self.proveedor.pais
        return pais != 'España'
    
    @property
    def entidad(self):
        """Devuelve el cliente o el proveedor según tipo"""
        if self.tipo == 'VENTA_MAT':
            return self.cliente
        else:
            return self.proveedor
    
    @property
    def entidad_nombre(self):
        """Nombre de la entidad o '—' si no hay"""
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
    def total_importe(self):
        total = Decimal('0')
        for d in self.detalles.all():
            total += d.subtotal
        return total

    @property
    def precio_venta_tn(self):
        """€/TN de venta (importe total / cantidad total)"""
        if self.total_kg == 0:
            return Decimal('0')
        return self.total_importe / self.total_kg
    
    @property
    def precio_compra_tn(self):
        """€/TN del pedido (para compras)"""
        if self.total_kg == 0:
            return Decimal('0')
        return self.total_importe / self.total_kg
    
    @property
    def coste_compra_tn(self):
        """Solo para ventas: €/TN del pedido de compra origen"""
        if not self.pedido_origen:
            return None
        return self.pedido_origen.precio_compra_tn
    
    @property
    def transporte_total(self):
        """Suma total de transporte del pedido"""
        total = Decimal('0')
        for d in self.detalles.all():
            total += Decimal(str(d.transporte))
        return total
    
    @property
    def coste_transporte_tn(self):
        """€/TN de transporte (propio + del pedido origen si es venta)"""
        total_tn = self.total_kg
        if total_tn == 0:
            return Decimal('0')
        
        total_transporte = self.transporte_total
        # Sumar transporte del pedido origen si es venta
        if self.pedido_origen:
            total_transporte += self.pedido_origen.transporte_total
        
        return total_transporte / total_tn
    
    @property
    def beneficio_tn(self):
        """
        €/TN de beneficio (solo para ventas con pedido origen).
        Beneficio = precio venta - coste compra - coste transporte
        """
        if not self.pedido_origen:
            return None
        coste_compra = self.coste_compra_tn
        coste_trans = self.coste_transporte_tn
        venta = self.precio_venta_tn
        return venta - coste_compra - coste_trans
    
    @property
    def beneficio_total(self):
        """Beneficio total del pedido (solo ventas con origen)"""
        if not self.pedido_origen:
            return None
        return self.beneficio_tn * self.total_kg
    
    @property
    def margen_pct(self):
        """Margen % (solo ventas con origen)"""
        if not self.pedido_origen or self.precio_venta_tn == 0:
            return None
        return (self.beneficio_tn / self.precio_venta_tn) * 100
    
    
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
    
    class Meta:
        verbose_name = "Detalle de pedido"
        verbose_name_plural = "Detalles de pedidos"


class CondicionPago(models.Model):
    """Condiciones de pago configurables para pedidos internacionales"""
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
    """Seguimiento de pedidos internacionales"""
    
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
    """Registro de pagos recibidos de pedidos internacionales"""
    
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