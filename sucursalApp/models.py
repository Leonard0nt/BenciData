from django.db import models
from __future__ import annotations


class Sucursal(models.Model):
    """Representa una sucursal perteneciente a una empresa."""

    company = models.ForeignKey(
        "homeApp.Company",
        on_delete=models.CASCADE,
        related_name="branches",
        verbose_name="Empresa",
    )
    name = models.CharField("Nombre", max_length=255)
    address = models.CharField("Dirección", max_length=255)
    city = models.CharField("Ciudad", max_length=100)
    region = models.CharField("Región", max_length=100)
    phone = models.CharField("Teléfono", max_length=30, blank=True)
    email = models.EmailField("Correo electrónico", blank=True)
    islands = models.PositiveIntegerField("Islas", default=0)
    users = models.ManyToManyField(
        "UsuarioApp.Profile",
        related_name="branches",
        blank=True,
        verbose_name="Usuarios asociados",
    )
    created_at = models.DateTimeField("Fecha de creación", auto_now_add=True)
    updated_at = models.DateTimeField("Fecha de actualización", auto_now=True)

    class Meta:
        verbose_name = "Sucursal"
        verbose_name_plural = "Sucursales"
        ordering = ("name",)

    def __str__(self) -> str:
        return f"{self.name} - {self.company.business_name}"

    @property
    def machines_count(self) -> int:
        return sum(island.machines.count() for island in self.islands.all())

    @property
    def nozzles_count(self) -> int:
        return sum(
            machine.nozzles.count()
            for island in self.islands.all()
            for machine in island.machines.all()
        )


class Island(models.Model):
    """Representa una isla dentro de una sucursal."""

    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.CASCADE,
        related_name="islands",
        verbose_name="Sucursal",
    )
    number = models.PositiveIntegerField("Número")
    description = models.CharField("Descripción", max_length=255, blank=True)
    created_at = models.DateTimeField("Fecha de creación", auto_now_add=True)
    updated_at = models.DateTimeField("Fecha de actualización", auto_now=True)

    class Meta:
        verbose_name = "Isla"
        verbose_name_plural = "Islas"
        ordering = ("number",)
        unique_together = ("sucursal", "number")

    def __str__(self) -> str:
        return f"Isla {self.number} - {self.sucursal.name}"


class Machine(models.Model):
    """Representa una máquina asociada a una isla."""

    island = models.ForeignKey(
        Island,
        on_delete=models.CASCADE,
        related_name="machines",
        verbose_name="Isla",
    )
    number = models.PositiveIntegerField("Número")
    initial_numeral = models.DecimalField(
        "Numeral inicial", max_digits=12, decimal_places=2, default=0
    )
    final_numeral = models.DecimalField(
        "Numeral final", max_digits=12, decimal_places=2, default=0
    )
    fuel_type = models.CharField("Tipo de combustible", max_length=50, blank=True)
    description = models.CharField("Descripción", max_length=255, blank=True)
    created_at = models.DateTimeField("Fecha de creación", auto_now_add=True)
    updated_at = models.DateTimeField("Fecha de actualización", auto_now=True)

    class Meta:
        verbose_name = "Máquina"
        verbose_name_plural = "Máquinas"
        ordering = ("number",)
        unique_together = ("island", "number")

    def __str__(self) -> str:
        return f"Máquina {self.number} - {self.island}"


class Nozzle(models.Model):
    """Representa una pistola asociada a una máquina."""

    machine = models.ForeignKey(
        Machine,
        on_delete=models.CASCADE,
        related_name="nozzles",
        verbose_name="Máquina",
    )
    number = models.PositiveIntegerField("Número")
    initial_numeral = models.DecimalField(
        "Numeral inicial", max_digits=12, decimal_places=2, default=0
    )
    final_numeral = models.DecimalField(
        "Numeral final", max_digits=12, decimal_places=2, default=0
    )
    fuel_type = models.CharField("Tipo de combustible", max_length=50, blank=True)
    description = models.CharField("Descripción", max_length=255, blank=True)
    created_at = models.DateTimeField("Fecha de creación", auto_now_add=True)
    updated_at = models.DateTimeField("Fecha de actualización", auto_now=True)

    class Meta:
        verbose_name = "Pistola"
        verbose_name_plural = "Pistolas"
        ordering = ("number",)
        unique_together = ("machine", "number")

    def __str__(self) -> str:
        return f"Pistola {self.number} - {self.machine}"