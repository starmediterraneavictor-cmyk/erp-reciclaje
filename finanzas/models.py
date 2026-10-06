from decimal import Decimal
from django.db import models
from django.utils import timezone
from clientes.models import Cliente
from proveedores.models import Proveedor
from pedidos.models import Pedido


class Factura(models.Model):
    TIPO_FACTURA = [
        ('INGRESO', 'Ingreso (venta)'),
        ('GASTO', 'Gasto (compra)'),
    ]
    
    CATEGORIAS = [
        ('COMERCIO_MATERIALES', 'Comercio de Materiales'),
        ('SERVICIOS_PROFESIONALES', 'Servicios Profesionales'),
        ('SUMINISTROS', 'Suministros'),
        ('RENTA_PARKING', 'Renta Parking'),
        ('TRANSPORTE', 'Transporte'),
        ('MANTENIMIENTO', 'Mantenimiento'),
        ('IMPUESTOS', 'Impuestos'),
        ('OTROS', 'Otros'),
    ]
    
    ESTADO_PAGO = [
        ('PENDIENTE', 'Pendiente'),
        ('PAGADO', 'Pagado'),
        ('PARCIAL', 'Pago parcial'),
        ('VENCIDO', 'Vencido'),
    ]
    
    numero_factura = models.CharField(max_length=50, unique=True)
    tipo = models.CharField(max_length=10, choices=TIPO_FACTURA)
    fecha = models.DateField(default=timezone.now)
    fecha_vencimiento = models.DateField(null=True, blank=True)
    
    # NUEVO: cliente para INGRESO, proveedor para GASTO
    cliente = models.ForeignKey(
        Cliente, on_delete=models.PROTECT,
        null=True, blank=True, related_name='facturas'
    )
    proveedor = models.ForeignKey(
        Proveedor, on_delete=models.PROTECT,
        null=True, blank=True, related_name='facturas'
    )
    
    pedido = models.ForeignKey(
        Pedido, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='facturas'
    )
    
    categoria = models.CharField(max_length=50, choices=CATEGORIAS, default='OTROS')
    
    base = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    iva_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=21)
    iva = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    estado_pago = models.CharField(max_length=20, choices=ESTADO_PAGO, default='PENDIENTE')
    notas = models.TextField(blank=True)

    archivo_factura = models.FileField(
        upload_to='facturas_proveedor/%Y/%m/',
        blank=True, null=True,
        verbose_name="Factura del proveedor (PDF)"
    )

    
    def __str__(self):
        entidad = self.cliente.nombre if self.cliente else (self.proveedor.nombre if self.proveedor else '—')
        return f"{self.numero_factura} - {entidad} ({self.total}€)"
    
    @property
    def entidad(self):
        """Devuelve el cliente o el proveedor según tipo"""
        return self.cliente if self.tipo == 'INGRESO' else self.proveedor
    @property
    def entidad_nombre(self):
        """Nombre del cliente o proveedor según tipo"""
        if self.tipo == 'INGRESO':
            return self.cliente.nombre if self.cliente else '—'
        else:
            return self.proveedor.nombre if self.proveedor else '—'
    
    def save(self, *args, **kwargs):
        if self.base:
            # Forzar todo a Decimal (por si llega int, float o str)
            base = Decimal(str(self.base))
            iva_pct = Decimal(str(self.iva_porcentaje))
            
            self.iva = base * (iva_pct / Decimal('100'))
            self.total = base + self.iva
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = "Factura"
        verbose_name_plural = "Facturas"
        ordering = ['-fecha']


class CuentaPorPagar(models.Model):
    """Deudas y pagos pendientes de la empresa"""
    
    CATEGORIA_CHOICES = [
        ('PROVEEDOR', 'Proveedor'),
        ('SS', 'Seguridad Social'),
        ('HACIENDA', 'Hacienda / AEAT'),
        ('AUTONOMO', 'Cuota Autónomo'),
        ('NOMINA', 'Nómina empleado'),
        ('ALQUILER', 'Alquiler'),
        ('SUMINISTRO', 'Suministros (luz, agua...)'),
        ('PRESTAMO', 'Préstamo'),
        ('IMPUESTO', 'Impuestos'),
        ('SERVICIO', 'Servicios profesionales'),
        ('OTRO', 'Otro'),
    ]
    
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('PAGADO', 'Pagado'),
        ('PARCIAL', 'Pago parcial'),
        ('VENCIDO', 'Vencido'),
    ]
    
    PERIODICIDAD = [
        ('UNICO', 'Pago único'),
        ('MENSUAL', 'Mensual'),
        ('TRIMESTRAL', 'Trimestral'),
        ('ANUAL', 'Anual'),
    ]
    
    # Identificación
    concepto = models.CharField(max_length=200)
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES, default='PROVEEDOR')
    proveedor = models.ForeignKey(
        Proveedor, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='cuentas_pagar'
    )
    
    # Importes
    importe_total = models.DecimalField(max_digits=12, decimal_places=2)
    importe_pagado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Fechas
    fecha_emision = models.DateField(default=timezone.now)
    fecha_vencimiento = models.DateField()
    fecha_pago = models.DateField(null=True, blank=True)
    
    # Estado
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='PENDIENTE')
    periodicidad = models.CharField(max_length=20, choices=PERIODICIDAD, default='UNICO')
    
    # Referencias
    numero_factura = models.CharField(max_length=50, blank=True)
    notas = models.TextField(blank=True)
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.concepto} - {self.importe_total}€ ({self.get_estado_display()})"
    
    @property
    def saldo_pendiente(self):
        return self.importe_total - self.importe_pagado
    
    @property
    def dias_para_vencer(self):
        from datetime import date
        return (self.fecha_vencimiento - date.today()).days
    
    @property
    def esta_vencida(self):
        return self.dias_para_vencer < 0 and self.estado != 'PAGADO'
    
    @property
    def alerta(self):
        """Alerta si está vencida o vence en menos de 7 días"""
        if self.estado == 'PAGADO':
            return False
        return self.dias_para_vencer <= 7

    @property
    def tiene_factura(self):
        """Comprueba si hay una factura con este número"""
        from .models import Factura
        return Factura.objects.filter(numero_factura=self.numero_factura).exists() if self.numero_factura else False
    
    class Meta:
        verbose_name = "Cuenta por pagar"
        verbose_name_plural = "Cuentas por pagar"
        ordering = ['fecha_vencimiento']


class PagoCuentaPorPagar(models.Model):
    """Pagos individuales de una cuenta por pagar"""
    
    cuenta = models.ForeignKey(CuentaPorPagar, on_delete=models.CASCADE, related_name='pagos')
    importe = models.DecimalField(max_digits=12, decimal_places=2)
    fecha = models.DateField(default=timezone.now)
    metodo = models.CharField(max_length=50, blank=True)
    referencia = models.CharField(max_length=100, blank=True)
    notas = models.TextField(blank=True)

    archivo_factura = models.FileField(
            upload_to='facturas_proveedor/%Y/%m/',
            blank=True, null=True,
            verbose_name="Factura del proveedor (PDF)"
        )
    
    def __str__(self):
        return f"{self.cuenta.concepto} - {self.importe}€ ({self.fecha})"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Actualizar el importe pagado de la cuenta
        total_pagado = sum((p.importe for p in self.cuenta.pagos.all()), Decimal('0'))
        self.cuenta.importe_pagado = total_pagado
        
        if total_pagado >= self.cuenta.importe_total:
            self.cuenta.estado = 'PAGADO'
            self.cuenta.fecha_pago = self.fecha
        elif total_pagado > 0:
            self.cuenta.estado = 'PARCIAL'
        
        self.cuenta.save()
    
    class Meta:
        verbose_name = "Pago de cuenta por pagar"
        verbose_name_plural = "Pagos de cuentas por pagar"
        ordering = ['-fecha']


class CuentaPorCobrar(models.Model):
    """Dinero que nos deben los clientes"""
    
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('COBRADO', 'Cobrado'),
        ('PARCIAL', 'Cobro parcial'),
        ('VENCIDO', 'Vencido'),
    ]
    
    concepto = models.CharField(max_length=200)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='cuentas_cobrar')
    
    importe_total = models.DecimalField(max_digits=12, decimal_places=2)
    importe_cobrado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    fecha_emision = models.DateField(default=timezone.now)
    fecha_vencimiento = models.DateField()
    fecha_cobro = models.DateField(null=True, blank=True)
    
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='PENDIENTE')
    numero_factura = models.CharField(max_length=50, blank=True)
    notas = models.TextField(blank=True)
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.concepto} - {self.cliente.nombre} - {self.importe_total}€"
    
    @property
    def saldo_pendiente(self):
        return self.importe_total - self.importe_cobrado
    
    @property
    def dias_para_vencer(self):
        from datetime import date
        return (self.fecha_vencimiento - date.today()).days
    
    @property
    def alerta(self):
        if self.estado == 'COBRADO':
            return False
        return self.dias_para_vencer <= 7

    @property
    def tiene_factura(self):
        """Comprueba si hay una factura con este número"""
        from .models import Factura
        return Factura.objects.filter(numero_factura=self.numero_factura).exists() if self.numero_factura else False
    
    class Meta:
        verbose_name = "Cuenta por cobrar"
        verbose_name_plural = "Cuentas por cobrar"
        ordering = ['fecha_vencimiento']


class CobroCuentaPorCobrar(models.Model):
    """Cobros individuales de una cuenta por cobrar"""
    
    cuenta = models.ForeignKey(CuentaPorCobrar, on_delete=models.CASCADE, related_name='cobros')
    importe = models.DecimalField(max_digits=12, decimal_places=2)
    fecha = models.DateField(default=timezone.now)
    metodo = models.CharField(max_length=50, blank=True)
    referencia = models.CharField(max_length=100, blank=True)
    notas = models.TextField(blank=True)

    archivo_factura = models.FileField(
            upload_to='facturas_proveedor/%Y/%m/',
            blank=True, null=True,
            verbose_name="Factura del proveedor (PDF)"
        )
    
    def __str__(self):
        return f"{self.cuenta.concepto} - {self.importe}€"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        total_cobrado = sum((c.importe for c in self.cuenta.cobros.all()),Decimal('0'))
        self.cuenta.importe_cobrado = total_cobrado
        
        if total_cobrado >= self.cuenta.importe_total:
            self.cuenta.estado = 'COBRADO'
            self.cuenta.fecha_cobro = self.fecha
        elif total_cobrado > 0:
            self.cuenta.estado = 'PARCIAL'
        
        self.cuenta.save()
    
    class Meta:
        verbose_name = "Cobro de cuenta por cobrar"
        verbose_name_plural = "Cobros de cuentas por cobrar"
        ordering = ['-fecha']