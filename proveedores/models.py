from django.db import models


class Proveedor(models.Model):
    TIPO_PROVEEDOR = [
        ('MATERIAL', 'Material'),
        ('SERVICIO', 'Servicio'),
        ('SUMINISTRO', 'Suministro'),
        ('IMPUESTO', 'Impuesto / Administración'),
        ('OTRO', 'Otro'),
    ]
    
    ESTADO_CHOICES = [
        ('ACTIVO', 'Activo'),
        ('INACTIVO', 'Inactivo'),
    ]
    
    nombre = models.CharField(max_length=200)
    nif = models.CharField(max_length=20, blank=True)
    pais = models.CharField(max_length=100, default='España')
    email = models.EmailField(blank=True)
    telefono = models.CharField(max_length=50, blank=True)
    direccion = models.CharField(max_length=300, blank=True)
    codigo_nima = models.CharField(max_length=50, blank=True,verbose_name="Código NIMA")
    numero_gestor = models.CharField(max_length=50, blank=True,verbose_name="Nº Gestor de Residuos")
    
    tipo = models.CharField(max_length=20, choices=TIPO_PROVEEDOR, default='MATERIAL')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='ACTIVO')
    
    iban = models.CharField(max_length=50, blank=True)
    notas = models.TextField(blank=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.nombre
    
    class Meta:
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"
        ordering = ['nombre']