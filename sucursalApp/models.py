from __future__ import annotations
from typing import Iterable, Sequence

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, QuerySet
from django.utils import timezone

from UsuarioApp.choices import PERMISOS


class ShiftAssignmentQuerySet(models.QuerySet):
    """QuerySet helper for filtering shift assignments."""

    def active(self):
        """Return the assignments that are currently active."""
        return self.filter(is_active=True)



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


class Shift(models.Model):
    """Representa un turno de trabajo asociado a una sucursal."""

    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.CASCADE,
        related_name="shifts",
        verbose_name="Sucursal",
    )
    name = models.CharField("Nombre", max_length=150)
    description = models.TextField("Descripción", blank=True)
    created_at = models.DateTimeField("Fecha de creación", auto_now_add=True)
    updated_at = models.DateTimeField("Fecha de actualización", auto_now=True)

    class Meta:
        verbose_name = "Turno"
        verbose_name_plural = "Turnos"
        ordering = ("sucursal__name", "name")

    def __str__(self) -> str:
        return f"{self.name} - {self.sucursal.name}"

    def get_schedule_summary(self) -> list[dict[str, str]]:
        """Devuelve un resumen del horario configurado para el turno."""

        summary = []
        for schedule in self.schedules.order_by("day_of_week", "start_time"):
            summary.append(
                {
                    "day": schedule.get_day_of_week_display(),
                    "start": schedule.start_time.strftime("%H:%M"),
                    "end": schedule.end_time.strftime("%H:%M"),
                }
            )
        return summary


class ShiftSchedule(models.Model):
    """Define los horarios disponibles para un turno determinado."""

    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6

    DAYS_OF_WEEK = (
        (MONDAY, "Lunes"),
        (TUESDAY, "Martes"),
        (WEDNESDAY, "Miércoles"),
        (THURSDAY, "Jueves"),
        (FRIDAY, "Viernes"),
        (SATURDAY, "Sábado"),
        (SUNDAY, "Domingo"),
    )

    shift = models.ForeignKey(
        Shift,
        on_delete=models.CASCADE,
        related_name="schedules",
        verbose_name="Turno",
    )
    day_of_week = models.PositiveSmallIntegerField(
        "Día de la semana", choices=DAYS_OF_WEEK
    )
    start_time = models.TimeField("Hora de inicio")
    end_time = models.TimeField("Hora de término")

    class Meta:
        verbose_name = "Horario de turno"
        verbose_name_plural = "Horarios de turno"
        unique_together = ("shift", "day_of_week")
        ordering = ("day_of_week", "start_time")

    def __str__(self) -> str:
        return (
            f"{self.get_day_of_week_display()} {self.start_time:%H:%M}-"
            f"{self.end_time:%H:%M} ({self.shift})"
        )

    def clean(self) -> None:
        super().clean()
        if self.start_time >= self.end_time:
            raise ValidationError(
                {"end_time": "La hora de término debe ser posterior a la de inicio."}
            )


class ShiftAssignment(models.Model):
    """Asigna turnos a perfiles pertenecientes a una sucursal."""

    shift = models.ForeignKey(
        Shift,
        on_delete=models.CASCADE,
        related_name="assignments",
        verbose_name="Turno",
    )
    profile = models.ForeignKey(
        "UsuarioApp.Profile",
        on_delete=models.CASCADE,
        related_name="shift_assignments",
        verbose_name="Perfil",
    )
    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.CASCADE,
        related_name="shift_assignments",
        verbose_name="Sucursal",
    )
    is_active = models.BooleanField("Activo", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ShiftAssignmentQuerySet.as_manager()

    class Meta:
        verbose_name = "Asignación de turno"
        verbose_name_plural = "Asignaciones de turnos"
        constraints = [
            models.UniqueConstraint(
                fields=["shift", "profile"],
                condition=Q(is_active=True),
                name="unique_active_shift_profile",
            )
        ]
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.profile} → {self.shift}"

    def clean(self) -> None:
        super().clean()
        if self.sucursal_id and self.shift_id and self.shift.sucursal_id != self.sucursal_id:
            raise ValidationError(
                {"sucursal": "La sucursal de la asignación debe coincidir con la del turno."}
            )

    def save(self, *args, **kwargs):
        if not self.sucursal_id and self.shift_id:
            self.sucursal = self.shift.sucursal
        self.full_clean()
        return super().save(*args, **kwargs)

    def is_current(self) -> bool:
        """Indica si la asignación está vigente en la fecha actual."""
        return self.is_active