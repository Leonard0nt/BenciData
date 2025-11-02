from __future__ import annotations
from typing import Iterable, Sequence


from django.db import models
from django.db.models import QuerySet

from UsuarioApp.choices import PERMISOS


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
        islands = SucursalStaff._get_related_items(self, "branch_islands")
        return sum(
            SucursalStaff._count_items(
                SucursalStaff._get_related_items(island, "machines")
            )
            for island in islands
        )

    @property
    def nozzles_count(self) -> int:
        return sum(
            machine.nozzles.count()
            for island in self.branch_islands.all()
            for machine in island.machines.all()
        )

    @property
    def shifts_count(self) -> int:
        return self.shifts.count()

    @property
    def fuel_inventories_count(self) -> int:
        return self.fuel_inventories.count()

    @property
    def products_count(self) -> int:
        return self.products.count()

    def get_staff_for_role(self, role: str | Iterable[str]):
        """Return the profiles assigned to the sucursal for the given role or roles."""

        if isinstance(role, str):
            roles: Sequence[str | None] = (role,)
        else:
            roles = tuple(role)
        assignments = [
            assignment
            for assignment in self.staff.all()
            if assignment.role in roles
        ]
        return [assignment.profile for assignment in assignments]

    @property
    def administrators(self):
        return self.get_staff_for_role("ADMINISTRATOR")

    @property
    def accountants(self):
        return self.get_staff_for_role("ACCOUNTANT")

    @property
    def firefighters(self):
        return self.get_staff_for_role(("ATTENDANT", "HEAD_ATTENDANT"))


class SucursalStaff(models.Model):
    """Relaciona una sucursal con los perfiles asignados y su rol."""

    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.CASCADE,
        related_name="staff",
        verbose_name="Sucursal",
    )
    profile = models.ForeignKey(
        "UsuarioApp.Profile",
        on_delete=models.CASCADE,
        related_name="sucursal_staff",
        verbose_name="Perfil",
    )
    role = models.CharField(
        "Rol",
        max_length=25,
        choices=PERMISOS,
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Personal de sucursal"
        verbose_name_plural = "Personal de sucursal"
        constraints = [
            models.UniqueConstraint(
                fields=["sucursal", "profile"],
                name="unique_sucursal_profile",
            )
        ]

    def save(self, *args, **kwargs):
        if self.role is None and getattr(self.profile, "position_FK", None):
            self.role = self.profile.position_FK.permission_code
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        profile_name = getattr(self.profile, "user_FK", None)
        if profile_name:
            profile_name = profile_name.get_full_name() or profile_name.username
        else:
            profile_name = str(self.profile)
        return f"{profile_name} - {self.sucursal.name} ({self.role})"

    @staticmethod
    def _get_related_items(instance: models.Model, related_name: str):
        cache = getattr(instance, "_prefetched_objects_cache", {}) or {}
        if related_name in cache:
            return cache[related_name]
        manager = getattr(instance, related_name)
        return manager.all()

    @staticmethod
    def _count_items(items) -> int:
        if isinstance(items, QuerySet):
            return items.count()
        return len(items)


class Island(models.Model):
    """Representa una isla dentro de una sucursal."""

    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.CASCADE,
        related_name="branch_islands",
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


class Shift(models.Model):
    """Gestiona los turnos configurados para una sucursal."""

    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.CASCADE,
        related_name="shifts",
        verbose_name="Sucursal",
    )
    code = models.CharField("Código", max_length=25)
    description = models.CharField(
        "Descripción",
        max_length=255,
        blank=True,
        help_text="Resume las funciones principales y responsabilidades del turno.",
    )
    start_time = models.TimeField("Hora de inicio")
    end_time = models.TimeField("Hora de término")
    manager = models.ForeignKey(
        "UsuarioApp.Profile",
        on_delete=models.PROTECT,
        related_name="managed_shifts",
        verbose_name="Encargado del turno",
    )
    attendants = models.ManyToManyField(
        "UsuarioApp.Profile",
        blank=True,
        related_name="assigned_shifts",
        verbose_name="Bomberos asignados",
        help_text="Selecciona los bomberos que trabajarán en este turno.",
    )
    created_at = models.DateTimeField("Fecha de creación", auto_now_add=True)
    updated_at = models.DateTimeField("Fecha de actualización", auto_now=True)

    class Meta:
        verbose_name = "Turno"
        verbose_name_plural = "Turnos"
        ordering = ("sucursal__name", "start_time")
        constraints = [
            models.UniqueConstraint(
                fields=["sucursal", "code"],
                name="unique_sucursal_shift_code",
            )
        ]

    def __str__(self) -> str:
        return f"Turno {self.code} - {self.sucursal.name}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._ensure_manager_is_head_attendant()

    def _ensure_manager_is_head_attendant(self) -> None:
        if not self.manager_id:
            return
        manager_profile = self.manager
        try:
            from UsuarioApp.models import Position

            head_attendant_position = Position.objects.get(
                permission_code="HEAD_ATTENDANT"
            )
        except (ImportError, Position.DoesNotExist):
            return

        if manager_profile.position_FK_id != head_attendant_position.id:
            manager_profile.position_FK = head_attendant_position
            manager_profile.save(update_fields=["position_FK"])

        assignment, _ = SucursalStaff.objects.get_or_create(
            sucursal=self.sucursal,
            profile=manager_profile,
            defaults={"role": "HEAD_ATTENDANT"},
        )
        if assignment.role != "HEAD_ATTENDANT":
            assignment.role = "HEAD_ATTENDANT"
            assignment.save(update_fields=["role"])


class BranchProduct(models.Model):
    """Registra los productos disponibles en una sucursal."""

    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.CASCADE,
        related_name="products",
        verbose_name="Sucursal",
    )
    product_type = models.CharField("Tipo", max_length=150)
    quantity = models.PositiveIntegerField("Cantidad")
    arrival_date = models.DateField("Fecha de llegada")
    batch_number = models.CharField("Número de lote", max_length=100)
    value = models.DecimalField("Valor", max_digits=12, decimal_places=2)
    created_at = models.DateTimeField("Fecha de creación", auto_now_add=True)
    updated_at = models.DateTimeField("Fecha de actualización", auto_now=True)

    class Meta:
        verbose_name = "Producto de sucursal"
        verbose_name_plural = "Productos de sucursal"
        ordering = ("product_type", "arrival_date")

    def __str__(self) -> str:
        return f"{self.product_type} - {self.sucursal.name}"


class FuelInventory(models.Model):
    """Gestiona el inventario de combustibles asignado a una sucursal."""

    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.CASCADE,
        related_name="fuel_inventories",
        verbose_name="Sucursal",
    )
    code = models.CharField("Código", max_length=30)
    fuel_type = models.CharField("Tipo de combustible", max_length=100)
    capacity = models.DecimalField(
        "Capacidad del tanque (L)", max_digits=12, decimal_places=2
    )
    liters = models.DecimalField(
        "Litraje disponible (L)", max_digits=12, decimal_places=2
    )
    created_at = models.DateTimeField("Fecha de creación", auto_now_add=True)
    updated_at = models.DateTimeField("Fecha de actualización", auto_now=True)

    class Meta:
        verbose_name = "Inventario de combustible"
        verbose_name_plural = "Inventarios de combustible"
        ordering = ("code",)
        constraints = [
            models.UniqueConstraint(
                fields=["sucursal", "code"],
                name="unique_inventory_code_per_branch",
            )
        ]

    def __str__(self) -> str:
        return f"{self.code} - {self.sucursal.name} ({self.fuel_type})"