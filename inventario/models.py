from django.db import models


class TipoMaterial(models.Model):
    """Tipos principales: Plástico, Metal, Papel..."""
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)
    
    def __str__(self):
        return self.nombre
    
    class Meta:
        verbose_name = "Tipo de material"
        verbose_name_plural = "Tipos de material"
        ordering = ['nombre']


class SubgrupoMaterial(models.Model):
    """Subgrupos: PP, HDPE, PET, Cobre, Aluminio..."""
    tipo = models.ForeignKey(TipoMaterial, on_delete=models.CASCADE, related_name='subgrupos')
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.tipo.nombre} - {self.nombre}"
    
    class Meta:
        verbose_name = "Subgrupo de material"
        verbose_name_plural = "Subgrupos de material"
        ordering = ['tipo__nombre', 'nombre']
        unique_together = ['tipo', 'nombre']


class Material(models.Model):
    UNIDADES = [
        ('KG', 'Kilogramos'),
        ('TN', 'Toneladas'),
        ('UD', 'Unidades'),
    ]
    
    codigo = models.CharField(max_length=50, unique=True)
    nombre = models.CharField(max_length=200)
    tipo = models.ForeignKey(TipoMaterial, on_delete=models.PROTECT, related_name='materiales')
    subgrupo = models.ForeignKey(SubgrupoMaterial, on_delete=models.PROTECT, related_name='materiales', null=True, blank=True)
    unidad = models.CharField(max_length=5, choices=UNIDADES, default='TN')
    precio_compra = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    precio_venta = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    descripcion = models.TextField(blank=True)

    stock_minimo_critico = models.DecimalField(
        max_digits=12, decimal_places=2, default=100,
        verbose_name="Stock mínimo crítico (tn)"
    )
    stock_minimo_bajo = models.DecimalField(
        max_digits=12, decimal_places=2, default=500,
        verbose_name="Stock mínimo bajo (tn)"
    )
    
    def __str__(self):
        return f"{self.codigo} - {self.nombre}"
    
    class Meta:
        verbose_name = "Material"
        verbose_name_plural = "Materiales"
        ordering = ['tipo__nombre', 'subgrupo__nombre', 'nombre']


class Inventario(models.Model):
    material = models.OneToOneField(Material, on_delete=models.CASCADE)
    cantidad = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.material.codigo}: {self.cantidad} {self.material.unidad}"
    
    class Meta:
        verbose_name = "Inventario"
        verbose_name_plural = "Inventario"