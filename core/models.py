from django.db import models


class DatosEmpresa(models.Model):
    """Datos fiscales de la empresa para las facturas"""
    
    # Datos básicos
    nombre = models.CharField(max_length=200, default="STAR MEDI RECYCLING SL")
    nif = models.CharField(max_length=20, default="B12345678")
    direccion = models.CharField(max_length=300, default="Calle Ejemplo, 123")
    ciudad = models.CharField(max_length=100, default="Barcelona")
    codigo_postal = models.CharField(max_length=10, default="08001")
    provincia = models.CharField(max_length=100, default="Barcelona")
    pais = models.CharField(max_length=100, default="España")
    
    # Contacto
    telefono = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    web = models.URLField(blank=True)
    
    # Datos bancarios
    iban = models.CharField(max_length=50, blank=True, default="ES21 2101 8249 1592 0201 7568")
    banco = models.CharField(max_length=100, blank=True, default="BBVA")
    swift = models.CharField(max_length=20, blank=True, default="BBVAESMMXXX")
    
    # Logo
    logo = models.ImageField(upload_to='logos/', blank=True, null=True)
    
    # Pie de página
    texto_pie = models.TextField(blank=True, default="VAT EXEMPT ACCORDING TO ARTICLE 21 LAW 37/1992")
    
    def __str__(self):
        return self.nombre
    
    class Meta:
        verbose_name = "Datos de la Empresa"
        verbose_name_plural = "Datos de la Empresa"