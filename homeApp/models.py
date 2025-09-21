from django.db import models
from django.core.validators import RegexValidator
from typing import Optional
# Create your models here.

class Company(models.Model):
    rut = models.CharField(
        max_length=12,
        unique=True,
        validators=[
            RegexValidator(
                regex=r"^[0-9.]+-[0-9kK]{1}$",
                message="Ingrese un RUT válido en el formato 12.345.678-9",
            )
        ],
        verbose_name="RUT",
    )
    business_name = models.CharField(
        max_length=255,
        verbose_name="Razón social",
    )
    tax_address = models.CharField(
        max_length=255,
        verbose_name="Dirección tributaria",
    )
    profile = models.OneToOneField(
        "UsuarioApp.Profile",
        on_delete=models.CASCADE,
        related_name="company",
        verbose_name="Perfil",
    )

    class Meta:
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"
        db_table = "UsuarioApp_company"

    def __str__(self) -> str:
        return f"{self.business_name} ({self.rut})"

    @staticmethod
    def normalize_rut(rut: Optional[str]) -> Optional[str]:
        """Return the RUT normalized by removing dots and uppercasing the verifier."""
        if not rut:
            return rut
        normalized = rut.replace(".", "").strip()
        number, *verifier = normalized.split("-")
        if verifier:
            normalized = f"{number}-{verifier[0].upper()}"
        return normalized

    def save(self, *args, **kwargs):
        self.rut = self.normalize_rut(self.rut)
        super().save(*args, **kwargs)