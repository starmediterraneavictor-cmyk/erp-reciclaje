from django.db import models
from django.utils import timezone
from datetime import date, timedelta

from clientes.models import Cliente
from proveedores.models import Proveedor


class SectorContacto(models.Model):
    """Catálogo maestro de sectores (G.R, RESIDUOS, METALES, PAPEL, etc.)"""
    TIPO = [
        ('PROVEEDOR', 'Proveedor'),
        ('CLIENTE', 'Cliente'),
        ('AMBOS', 'Ambos'),
    ]

    nombre = models.CharField(max_length=100, unique=True)
    tipo = models.CharField(max_length=20, choices=TIPO, default='AMBOS')
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Sector de contacto"
        verbose_name_plural = "Sectores de contacto"
        ordering = ['nombre']


class EstadoContacto(models.Model):
    """Estados de la hoja 'Listas' (ESP. RESPUESTA, SEGUIMIENTO, EN PAUSA, etc.)"""
    nombre = models.CharField(max_length=50, unique=True)
    orden = models.PositiveSmallIntegerField(default=0)
    color = models.CharField(
        max_length=20, default='secondary',
        help_text="Clase Bootstrap: secondary, success, warning, danger, info"
    )
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Estado de contacto"
        verbose_name_plural = "Estados de contacto"
        ordering = ['orden', 'nombre']


class Contacto(models.Model):
    """
    Ficha CRM unificada. Puede ser prospecto, cliente o proveedor.
    Si se convierte en cliente o proveedor real, se enlaza mediante
    OneToOneField, pero la ficha CRM sigue existiendo con su historial.
    """
    TIPO_CONTACTO = [
        ('PROSPECTO', 'Prospecto'),
        ('CLIENTE', 'Cliente'),
        ('PROVEEDOR', 'Proveedor'),
        ('AMBOS', 'Ambos'),
    ]

    # --- Vinculación opcional con el ERP comercial ---
    cliente = models.OneToOneField(
        Cliente, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='contacto_crm',
        help_text="Se rellena si el contacto es también un cliente real"
    )
    proveedor = models.OneToOneField(
        Proveedor, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='contacto_crm',
        help_text="Se rellena si el contacto es también un proveedor real"
    )

    # --- Datos básicos ---
    nombre = models.CharField(max_length=200)
    tipo = models.CharField(
        max_length=20, choices=TIPO_CONTACTO, default='PROSPECTO'
    )
    pais = models.CharField(max_length=100, blank=True)
    ubicacion = models.CharField(
        max_length=200, blank=True,
        help_text="Ubicación general o nave"
    )
    provincia = models.CharField(max_length=100, blank=True)
    localidad = models.CharField(max_length=100, blank=True)
    web = models.URLField(blank=True)

    # --- Datos de contacto ---
    persona_contacto = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    telefono = models.CharField(max_length=50, blank=True)
    movil = models.CharField(max_length=50, blank=True)

    # --- CRM ---
    sector = models.ForeignKey(
        SectorContacto, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='contactos'
    )
    estado = models.ForeignKey(
        EstadoContacto, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='contactos'
    )
    actividad = models.CharField(
        max_length=100, blank=True,
        help_text="Ej: DIESEL, TEXTILES, METALES, PAPELERA, G.R..."
    )
    notas = models.TextField(
        blank=True,
        help_text="Notas generales del contacto (histórico del Excel)"
    )
    codigo_gestor = models.CharField(max_length=50, blank=True)

    # --- Seguimiento ---
    ultima_fecha_contacto = models.DateField(
        null=True, blank=True,
        verbose_name="Última fecha de contacto"
    )
    dias_alerta = models.PositiveSmallIntegerField(
        default=9,
        help_text="Días para marcar la alerta 'TOMAR ACCIÓN'"
    )

    # --- Auditoría ---
    fecha_alta = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nombre

    # -------------------------
    # Propiedades calculadas
    # -------------------------
    @property
    def dias_sin_contacto(self):
        if not self.ultima_fecha_contacto:
            return None
        return (date.today() - self.ultima_fecha_contacto).days

    @property
    def proxima_accion(self):
        """Fecha en la que salta la alerta."""
        if not self.ultima_fecha_contacto:
            return None
        return self.ultima_fecha_contacto + timedelta(days=self.dias_alerta)

    @property
    def alerta(self):
        """True si toca llamar ya."""
        if not self.ultima_fecha_contacto:
            return False
        if self.estado and self.estado.nombre in ('EN PAUSA', 'DESCARTADO'):
            return False
        return date.today() >= self.proxima_accion

    @property
    def dias_para_alerta(self):
        """Días que faltan (negativo si ya ha saltado)."""
        if not self.proxima_accion:
            return None
        return (self.proxima_accion - date.today()).days

    @property
    def nivel_alerta(self):
        """Devuelve 'urgente', 'pronto', 'ok' o None. Para pintar el semáforo."""
        if self.estado and self.estado.nombre in ('EN PAUSA', 'DESCARTADO'):
            return None
        if not self.ultima_fecha_contacto:
            return None
        d = self.dias_para_alerta
        if d is None:
            return None
        if d <= 0:
            return 'urgente'   # 🔴
        if d <= 3:
            return 'pronto'    # 🟠
        return 'ok'            # 🟢

    @property
    def intereses_compra(self):
        return self.intereses.filter(accion='COMPRO')

    @property
    def intereses_venta(self):
        return self.intereses.filter(accion='VENDEMOS')

    class Meta:
        verbose_name = "Contacto"
        verbose_name_plural = "Contactos"
        ordering = ['nombre']


class InteresMaterial(models.Model):
    """
    Fila de la matriz CONSULTA MAT VS PROV-CLIENTE.
    Relaciona un contacto con un material, indicando si COMPRA o VENDE.
    """
    ACCION = [
        ('COMPRO', '🟢 Compra'),
        ('VENDEMOS', '🔵 Vende'),
    ]

    contacto = models.ForeignKey(
        Contacto, on_delete=models.CASCADE,
        related_name='intereses'
    )
    accion = models.CharField(max_length=20, choices=ACCION)
    material = models.ForeignKey(
        'inventario.Material', on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='intereses_contactos'
    )
    tipo_material = models.CharField(
        max_length=100, blank=True,
        help_text="Ej: HDPE, LDPE, PP, PS, PET... si no hay material concreto"
    )
    detalle = models.CharField(
        max_length=300, blank=True,
        help_text="Ej: 'TRITURADO LAVADO GARRAFA 25L', 'CUALQUIER FORMATO'..."
    )
    notas = models.TextField(blank=True)

    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        mat = self.material.nombre if self.material else (self.tipo_material or '—')
        return f"{self.contacto.nombre} · {self.accion} · {mat}"

    class Meta:
        verbose_name = "Interés de material"
        verbose_name_plural = "Intereses de material"
        ordering = ['contacto__nombre', 'accion', 'tipo_material']
        # Evitamos duplicar el mismo material para el mismo contacto y misma acción
        constraints = [
            models.UniqueConstraint(
                fields=['contacto', 'accion', 'tipo_material'],
                name='unique_contacto_accion_tipo'
            )
        ]


class Interaccion(models.Model):
    """
    Histórico de interacciones con un contacto.
    Cada vez que registras una llamada, email, visita... se guarda aquí.
    Al guardar, actualiza automáticamente la fecha de último contacto.
    """
    TIPO = [
        ('LLAMADA', '📞 Llamada'),
        ('EMAIL', '✉️ Email'),
        ('VISITA', '🤝 Visita'),
        ('WHATSAPP', '💬 WhatsApp'),
        ('OTRO', '📝 Otro'),
    ]

    contacto = models.ForeignKey(
        Contacto, on_delete=models.CASCADE,
        related_name='interacciones'
    )
    fecha = models.DateField(default=timezone.now)
    tipo = models.CharField(max_length=20, choices=TIPO, default='LLAMADA')
    resumen = models.TextField(help_text="Resumen de la conversación o motivo")
    autor = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.contacto.nombre} · {self.get_tipo_display()} · {self.fecha}"

    def save(self, *args, **kwargs):
        # Al guardar una interacción, actualizamos la fecha de último contacto
        # del contacto si esta es más reciente que la que ya tenía.
        super().save(*args, **kwargs)
        c = self.contacto
        if not c.ultima_fecha_contacto or self.fecha > c.ultima_fecha_contacto:
            c.ultima_fecha_contacto = self.fecha
            c.save(update_fields=['ultima_fecha_contacto'])

    class Meta:
        verbose_name = "Interacción"
        verbose_name_plural = "Interacciones"
        ordering = ['-fecha', '-fecha_creacion']
