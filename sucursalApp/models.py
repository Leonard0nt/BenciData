from __future__ import annotations
from decimal import Decimal
from typing import Iterable, Sequence


from django.db import models
from django.db.models import QuerySet
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from UsuarioApp.choices import PERMISOS
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

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
    number = models.PositiveIntegerField("Identificador de máquina")
    fuel_inventory = models.ForeignKey(
        "FuelInventory",
        on_delete=models.SET_NULL,
        related_name="machines",
        verbose_name="Estanque principal",
        blank=True,
        null=True,
    )
    fuel_inventories = models.ManyToManyField(
        "FuelInventory",
        related_name="associated_machines",
        verbose_name="Estanques",
        blank=True,
    )
    fuel_type = models.CharField(
        "Tipo de combustible",
        max_length=50,
        blank=True,
    )
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

    def save(self, *args, **kwargs):
        if self.fuel_inventory:
            self.fuel_type = self.fuel_inventory.fuel_type
        elif self.pk:
            primary_inventory = self.fuel_inventories.order_by("pk").first()
            self.fuel_type = primary_inventory.fuel_type if primary_inventory else ""
        else:
            self.fuel_type = ""

        super().save(*args, **kwargs)

    def get_fuel_inventories(self):
        inventories = list(self.fuel_inventories.all())
        primary_inventory = self.fuel_inventory
        if primary_inventory and primary_inventory not in inventories:
            inventories.insert(0, primary_inventory)
        return inventories

    def get_numerals_for_inventory(
        self, fuel_inventory: "FuelInventory" | None
    ) -> list["MachineFuelInventoryNumeral"]:
        if fuel_inventory is None or not self.pk:
            return []

        numerals = list(
            MachineFuelInventoryNumeral.objects.filter(
                machine=self, fuel_inventory=fuel_inventory
            ).order_by("slot", "pk")
        )

        if not numerals:
            numerals.append(
                MachineFuelInventoryNumeral.objects.create(
                    machine=self,
                    fuel_inventory=fuel_inventory,
                    slot=1,
                    numeral=Decimal("0"),
                )
            )

        return numerals

    def get_numeral_for_inventory(self, fuel_inventory: "FuelInventory" | None):
        numerals = self.get_numerals_for_inventory(fuel_inventory)
        if not numerals:
            return Decimal("0")
        return numerals[0].numeral

    @property
    def numeral(self) -> Decimal:
        return self.get_numeral_for_inventory(self.primary_fuel_inventory)

    @property
    def primary_fuel_inventory(self):
        return self.fuel_inventory or self.fuel_inventories.order_by("pk").first()

    @property
    def fuel_types(self) -> list[str]:
        return list(
            self.fuel_inventories.order_by("fuel_type")
            .values_list("fuel_type", flat=True)
            .distinct()
        )


class MachineFuelInventoryNumeral(models.Model):
    """Registra el numeral por combinación de máquina y estanque."""

    machine = models.ForeignKey(
        Machine,
        on_delete=models.CASCADE,
        related_name="fuel_numerals",
        verbose_name="Máquina",
    )
    fuel_inventory = models.ForeignKey(
        "FuelInventory",
        on_delete=models.CASCADE,
        related_name="machine_numerals",
        verbose_name="Estanque",
    )
    slot = models.PositiveIntegerField("Posición", default=1)
    numeral = models.DecimalField("Numeral", max_digits=12, decimal_places=3, default=0)
    created_at = models.DateTimeField("Fecha de creación", auto_now_add=True)
    updated_at = models.DateTimeField("Fecha de actualización", auto_now=True)

    class Meta:
        verbose_name = "Numeral de máquina"
        verbose_name_plural = "Numerales de máquina"
        ordering = ("machine", "fuel_inventory", "slot", "pk")
        unique_together = (("machine", "fuel_inventory", "slot"),)

    def __str__(self) -> str:
        return (
            f"Máquina {self.machine.number} · "
            f"Estanque {self.fuel_inventory.code} · "
            f"Numeral {self.numeral} · Slot #{self.slot}"
        )


class Nozzle(models.Model):
    """Representa una pistola asociada a una máquina."""

    machine = models.ForeignKey(
        Machine,
        on_delete=models.CASCADE,
        related_name="nozzles",
        verbose_name="Máquina",
    )
    number = models.PositiveIntegerField("Número")
    code = models.CharField(
        "Código IoT",
        max_length=50,
        unique=True,
        blank=True,
        null=True,
        help_text="Código enviado por la pistola para vincular lecturas IoT.",
    )
    
    fuel_type = models.CharField(
        "Tipo de combustible",
        max_length=50,
        blank=True,
    )
    fuel_numeral = models.ForeignKey(
        MachineFuelInventoryNumeral,
        on_delete=models.PROTECT,
        related_name="nozzles",
        verbose_name="Numeral",
        blank=True,
        null=True,
    )
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

    def save(self, *args, **kwargs):
        if self.fuel_numeral:
            self.fuel_type = self.fuel_numeral.fuel_inventory.fuel_type
        elif self.machine:
            primary_inventory = getattr(self.machine, "primary_fuel_inventory", None)
            if primary_inventory:
                primary_numeral = (
                    MachineFuelInventoryNumeral.objects.filter(
                        machine=self.machine, fuel_inventory=primary_inventory
                    )
                    .order_by("slot", "pk")
                    .first()
                )
                self.fuel_numeral = primary_numeral
                self.fuel_type = getattr(primary_inventory, "fuel_type", "")
            else:
                self.fuel_type = ""
        else:
            self.fuel_type = ""

        super().save(*args, **kwargs)

    @property
    def fuel_inventory(self):
        if self.fuel_numeral:
            return self.fuel_numeral.fuel_inventory
        return None

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
        previous_manager_id = None
        if self.pk:
            previous_manager_id = (
                Shift.objects.filter(pk=self.pk)
                .values_list("manager_id", flat=True)
                .first()
            )

        super().save(*args, **kwargs)
        self._ensure_manager_is_head_attendant()
        if previous_manager_id and previous_manager_id != self.manager_id:
            _cleanup_branch_attendants(self.sucursal, (previous_manager_id,))
            _revoke_head_attendant_status(previous_manager_id)
    def delete(self, *args, **kwargs):
        branch = self.sucursal
        attendants_ids = list(self.attendants.values_list("pk", flat=True))
        manager_id = self.manager_id

        super().delete(*args, **kwargs)

        affected_ids: list[int] = attendants_ids
        if manager_id:
            affected_ids.append(manager_id)
        _cleanup_branch_attendants(branch, affected_ids)

        if manager_id:
            _revoke_head_attendant_status(manager_id)


    def _ensure_manager_is_head_attendant(self) -> None:
        if not self.manager_id:
            return
        manager_profile = self.manager
        try:
            from UsuarioApp.models import Position

            head_attendant_position = (
                Position.objects.filter(permission_code="HEAD_ATTENDANT")
                .order_by("id")
                .first()
            )
        except ImportError:
            return

        if not head_attendant_position:
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

def _cleanup_branch_attendants(
    branch: Sucursal, profile_ids: Iterable[int] | None = None
) -> None:
    """Adjust attendants roles without removing them from the branch.

    Previously this helper deleted attendants that were no longer linked to any
    shift. That behaviour caused branch staff to lose their assignment when
    they were removed from a shift. Now we only downgrade head attendants that
    are no longer managing a shift, keeping every firefighter tied to the
    branch even if they don't have a current shift assignment.
    """

    staff_queryset = SucursalStaff.objects.filter(
        sucursal=branch, role__in=("ATTENDANT", "HEAD_ATTENDANT")
    )
    if profile_ids is not None:
        profile_ids = tuple(profile_ids)
        if not profile_ids:
            return
        staff_queryset = staff_queryset.filter(profile_id__in=profile_ids)

    if not staff_queryset.exists():
        return

    active_manager_ids = set(
        Shift.objects.filter(sucursal=branch)
        .exclude(manager_id__isnull=True)
        .values_list("manager_id", flat=True)
    )

    for assignment in staff_queryset:
        if (
            assignment.role == "HEAD_ATTENDANT"
            and assignment.profile_id not in active_manager_ids
        ):
            assignment.role = "ATTENDANT"
            assignment.save(update_fields=["role"])


def _revoke_head_attendant_status(profile_id: int) -> None:
    """Ensure a profile only keeps the head-attendant status when managing a shift."""

    if Shift.objects.filter(manager_id=profile_id).exists():
        return

    try:
        from UsuarioApp.models import Position, Profile

        profile = Profile.objects.get(pk=profile_id)
    except (ImportError, Profile.DoesNotExist):
        return

    attendant_position = Position.objects.filter(permission_code="ATTENDANT").first()

    if attendant_position and profile.position_FK_id != attendant_position.id:
        profile.position_FK = attendant_position
        profile.save(update_fields=["position_FK"])

    SucursalStaff.objects.filter(
        profile_id=profile_id, role="HEAD_ATTENDANT"
    ).update(role="ATTENDANT")


@receiver(m2m_changed, sender=Shift.attendants.through)
def ensure_attendants_are_branch_staff(
    sender,
    instance: Shift,
    action: str,
    pk_set,
    **_,
) -> None:
    """Ensure attendants belong to the branch staff when added to a shift."""

    if action == "post_add" and pk_set:
        from UsuarioApp.models import Profile

        attendants = Profile.objects.filter(pk__in=pk_set).select_related("position_FK")

        for attendant in attendants:
            role = "ATTENDANT"
            if attendant.position_FK and attendant.position_FK.permission_code in (
                "ATTENDANT",
                "HEAD_ATTENDANT",
            ):
                role = attendant.position_FK.permission_code

            assignment, created = SucursalStaff.objects.get_or_create(
                sucursal=instance.sucursal,
                profile=attendant,
                defaults={"role": role},
            )

            if not created and (
                assignment.role is None
                or assignment.role in ("ATTENDANT", "HEAD_ATTENDANT")
            ) and assignment.role != role:
                assignment.role = role
                assignment.save(update_fields=["role"])
        return

    if action == "post_remove" and pk_set:
        _cleanup_branch_attendants(instance.sucursal, pk_set)
    elif action == "post_clear":
        _cleanup_branch_attendants(instance.sucursal)

@receiver(m2m_changed, sender=Shift.attendants.through)
def ensure_attendants_are_branch_staff(
    sender,
    instance: Shift,
    action: str,
    pk_set,
    **_,
) -> None:
    """Ensure attendants belong to the branch staff when added to a shift."""

    if action != "post_add" or not pk_set:
        return

    from UsuarioApp.models import Profile

    attendants = Profile.objects.filter(pk__in=pk_set).select_related("position_FK")

    for attendant in attendants:
        role = "ATTENDANT"
        if attendant.position_FK and attendant.position_FK.permission_code in (
            "ATTENDANT",
            "HEAD_ATTENDANT",
        ):
            role = attendant.position_FK.permission_code

        assignment, created = SucursalStaff.objects.get_or_create(
            sucursal=instance.sucursal,
            profile=attendant,
            defaults={"role": role},
        )

        if not created and (
            assignment.role is None
            or assignment.role in ("ATTENDANT", "HEAD_ATTENDANT")
        ) and assignment.role != role:
            assignment.role = role
            assignment.save(update_fields=["role"])

class ServiceSession(models.Model):
    """Representa el inicio de un servicio para un turno específico."""

    CLOSE_MODE_NUMERAL = "numeral"
    CLOSE_MODE_PISTOL = "pistola"
    CLOSE_MODE_CHOICES = (
        (CLOSE_MODE_NUMERAL, "Modo numeral"),
        (CLOSE_MODE_PISTOL, "Modo pistola"),
    )

    shift = models.ForeignKey(
        Shift,
        on_delete=models.PROTECT,
        related_name="service_sessions",
        verbose_name="Turno",
    )
    attendants = models.ManyToManyField(
        "UsuarioApp.Profile",
        related_name="service_sessions",
        verbose_name="Bomberos asignados",
        blank=True,
    )
    coins_amount = models.DecimalField(
        "Dinero en monedas",
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    cash_amount = models.DecimalField(
        "Dinero en efectivo",
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    initial_budget = models.DecimalField(
        "Presupuesto inicial",
        max_digits=12,
        decimal_places=2,
        editable=False,
        default=0,
    )
    FLOW_MISMATCH_NONE = "NONE"
    FLOW_MISMATCH_POSITIVE = "POSITIVE"
    FLOW_MISMATCH_NEGATIVE = "NEGATIVE"
    FLOW_MISMATCH_CHOICES = (
        (FLOW_MISMATCH_NONE, "Sin descuadre"),
        (FLOW_MISMATCH_POSITIVE, "Descuadre positivo"),
        (FLOW_MISMATCH_NEGATIVE, "Descuadre negativo"),
    )
    flow_mismatch_amount = models.DecimalField(
        "Monto de descuadre",
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    flow_mismatch_type = models.CharField(
        "Tipo de descuadre",
        max_length=20,
        choices=FLOW_MISMATCH_CHOICES,
        default=FLOW_MISMATCH_NONE,
    )

    ended_at = models.DateTimeField(
        "Fecha de cierre",
        null=True,
        blank=True,
    )
    started_at = models.DateTimeField(
        "Fecha de inicio",
        auto_now_add=True,
    )

    attendants_snapshot = models.JSONField(
        "Personal asignado (copia)",
        default=dict,
        blank=True,
        help_text="Copia de los bomberos asignados al inicio del servicio.",
    )

    close_mode = models.CharField(
        "Modo de cierre",
        max_length=20,
        choices=CLOSE_MODE_CHOICES,
        default=CLOSE_MODE_NUMERAL,
    )
    fuel_sales = models.DecimalField(
        "Ventas de combustible (L)",
        max_digits=12,
        decimal_places=3,
        default=0,
    )
    class Meta:
        verbose_name = "Inicio de servicio"
        verbose_name_plural = "Inicios de servicio"
        ordering = ("-started_at",)

    def __str__(self) -> str:
        return f"Servicio {self.shift.code} - {self.started_at:%Y-%m-%d %H:%M}"

    def save(self, *args, **kwargs):
        self.initial_budget = (self.coins_amount or 0) + (self.cash_amount or 0)
        super().save(*args, **kwargs)

    def get_attendant_names(self) -> list[str]:
        if self.attendants_snapshot:
            return list(self.attendants_snapshot.values())

        return [
            attendant.user_FK.get_full_name() or attendant.user_FK.username
            for attendant in self.attendants.all()
        ]


@receiver(m2m_changed, sender=ServiceSession.attendants.through)
def capture_service_attendants_snapshot(
    sender, instance: ServiceSession, action: str, **kwargs
) -> None:
    """Store a snapshot of attendants when they are assigned to the service."""

    if action != "post_add" or instance.attendants_snapshot:
        return

    attendants = instance.attendants.select_related("user_FK")
    instance.attendants_snapshot = {
        str(attendant.pk): attendant.user_FK.get_full_name()
        or attendant.user_FK.username
        for attendant in attendants
    }
    instance.save(update_fields=["attendants_snapshot"])


class ServiceSessionFuelSale(models.Model):
    """Registra las ventas de combustible por tipo durante un servicio."""

    service_session = models.ForeignKey(
        ServiceSession,
        on_delete=models.CASCADE,
        related_name="fuel_sales_by_type",
        verbose_name="Servicio",
    )
    fuel_type = models.CharField("Tipo de combustible", max_length=100)
    liters_sold = models.DecimalField(
        "Litros vendidos",
        max_digits=12,
        decimal_places=3,
        default=0,
    )
    created_at = models.DateTimeField("Fecha de registro", auto_now_add=True)

    class Meta:
        verbose_name = "Venta de combustible"
        verbose_name_plural = "Ventas de combustible"
        unique_together = ("service_session", "fuel_type")
        ordering = ("-created_at", "fuel_type")

    def __str__(self) -> str:
        return f"{self.fuel_type} - {self.liters_sold} L (Servicio {self.service_session_id})"


class ServiceSessionWithdrawal(models.Model):
    """Registra las tiradas de dinero realizadas durante un servicio."""

    service_session = models.ForeignKey(
        ServiceSession,
        on_delete=models.CASCADE,
        related_name="withdrawals",
        verbose_name="Servicio",
    )
    responsible = models.ForeignKey(
        "UsuarioApp.Profile",
        on_delete=models.PROTECT,
        related_name="service_session_withdrawals",
        verbose_name="Responsable",
    )
    amount = models.DecimalField(
        "Monto retirado",
        max_digits=12,
        decimal_places=2,
    )
    registered_at = models.DateTimeField(
        "Fecha de registro",
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "Tirada de caja"
        verbose_name_plural = "Tiradas de caja"
        ordering = ("-registered_at", "-pk")

    def __str__(self) -> str:
        return (
            f"Tirada #{self.pk} - {self.service_session.shift.sucursal.name}"
            if self.pk
            else "Tirada"
        )


class ServiceSessionTransbankVoucher(models.Model):
    """Registra los vouchers generados por Transbank durante un servicio."""

    service_session = models.ForeignKey(
        ServiceSession,
        on_delete=models.CASCADE,
        related_name="transbank_vouchers",
        verbose_name="Servicio",
    )
    responsible = models.ForeignKey(
        "UsuarioApp.Profile",
        on_delete=models.PROTECT,
        related_name="transbank_vouchers",
        verbose_name="Responsable",
    )
    total_amount = models.DecimalField("Monto total", max_digits=12, decimal_places=2)
    registered_at = models.DateTimeField("Fecha de registro", auto_now_add=True)

    class Meta:
        verbose_name = "Voucher Transbank"
        verbose_name_plural = "Vouchers Transbank"
        ordering = ("-registered_at", "-pk")

    def __str__(self) -> str:
        return (
            f"Voucher #{self.pk} - {self.service_session.shift.sucursal.name}"
            if self.pk
            else "Voucher Transbank"
        )


class ServiceSessionFirefighterPayment(models.Model):
    """Registra los pagos realizados a bomberos durante un servicio."""

    service_session = models.ForeignKey(
        ServiceSession,
        on_delete=models.CASCADE,
        related_name="firefighter_payments",
        verbose_name="Servicio",
    )
    firefighter = models.ForeignKey(
        "UsuarioApp.Profile",
        on_delete=models.PROTECT,
        related_name="firefighter_payments",
        verbose_name="Bombero",
    )
    amount = models.DecimalField(
        "Monto pagado",
        max_digits=12,
        decimal_places=2,
    )
    registered_at = models.DateTimeField(
        "Fecha de registro",
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "Pago a bombero"
        verbose_name_plural = "Pagos a bomberos"
        ordering = ("-registered_at", "-pk")

    def __str__(self) -> str:
        return (
            f"Pago #{self.pk} - {self.service_session.shift.sucursal.name}"
            if self.pk
            else "Pago a bombero"
        )


class ServiceSessionFuelLoad(models.Model):
    """Registra las cargas de combustible realizadas durante un servicio."""

    service_session = models.ForeignKey(
        ServiceSession,
        on_delete=models.CASCADE,
        related_name="fuel_loads",
        verbose_name="Servicio",
    )
    inventory = models.ForeignKey(
        "FuelInventory",
        on_delete=models.CASCADE,
        related_name="fuel_loads",
        verbose_name="Inventario",
    )
    liters_added = models.DecimalField(
        "Litros cargados (L)", max_digits=12, decimal_places=2
    )
    invoice_number = models.CharField("Número de factura", max_length=100)
    responsible = models.ForeignKey(
        "UsuarioApp.Profile",
        on_delete=models.PROTECT,
        related_name="fuel_loads",
        verbose_name="Responsable",
    )
    driver_name = models.CharField("Nombre del chofer", max_length=150)
    license_plate = models.CharField("Patente", max_length=20)
    payment_amount = models.DecimalField(
        "Valor pagado",
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    date = models.DateField("Fecha")
    created_at = models.DateTimeField("Fecha de creación", auto_now_add=True)
    updated_at = models.DateTimeField("Fecha de actualización", auto_now=True)

    class Meta:
        verbose_name = "Carga de combustible"
        verbose_name_plural = "Cargas de combustible"
        ordering = ("-date", "-created_at")

    def __str__(self) -> str:
        return (
            f"{self.inventory.code} - {self.liters_added} L ({self.date:%Y-%m-%d})"
        )

class ServiceSessionProductLoad(models.Model):
    """Registra los ingresos de productos realizados durante un servicio."""

    service_session = models.ForeignKey(
        ServiceSession,
        on_delete=models.CASCADE,
        related_name="product_loads",
        verbose_name="Servicio",
    )
    product = models.ForeignKey(
        "BranchProduct",
        on_delete=models.CASCADE,
        related_name="product_loads",
        verbose_name="Producto",
    )
    quantity_added = models.PositiveIntegerField("Cantidad agregada")
    responsible = models.ForeignKey(
        "UsuarioApp.Profile",
        on_delete=models.PROTECT,
        related_name="product_loads",
        verbose_name="Responsable",
    )
    payment_amount = models.DecimalField(
        "Valor pagado",
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    date = models.DateField("Fecha")
    created_at = models.DateTimeField("Fecha de creación", auto_now_add=True)
    updated_at = models.DateTimeField("Fecha de actualización", auto_now=True)

    class Meta:
        verbose_name = "Ingreso de producto"
        verbose_name_plural = "Ingresos de productos"
        ordering = ("-date", "-created_at")

    def __str__(self) -> str:
        return f"{self.product.product_type} - {self.quantity_added} u. ({self.date:%Y-%m-%d})"


class ServiceSessionCreditSale(models.Model):
    """Registra las ventas realizadas a crédito durante un servicio."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendiente"
        PAID = "PAID", "Pagado"

    service_session = models.ForeignKey(
        ServiceSession,
        on_delete=models.CASCADE,
        related_name="credit_sales",
        verbose_name="Servicio",
    )
    invoice_number = models.CharField("Número de factura", max_length=100)
    customer_name = models.CharField("Nombre del cliente", max_length=255)
    fuel_inventory = models.ForeignKey(
        "FuelInventory",
        on_delete=models.PROTECT,
        related_name="credit_sales",
        verbose_name="Estanque",
    )
    amount = models.DecimalField(
        "Monto del crédito",
        max_digits=12,
        decimal_places=2,
    )
    responsible = models.ForeignKey(
        "UsuarioApp.Profile",
        on_delete=models.PROTECT,
        related_name="credit_sales",
        verbose_name="Responsable",
    )
    status = models.CharField(
        "Estado",
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField("Fecha de registro", auto_now_add=True)
    updated_at = models.DateTimeField("Fecha de actualización", auto_now=True)

    class Meta:
        verbose_name = "Venta a crédito"
        verbose_name_plural = "Ventas a crédito"
        ordering = ("-created_at", "-pk")

    def __str__(self) -> str:
        return f"Crédito #{self.pk} - {self.service_session.shift.sucursal.name}"


class ServiceSessionProductSale(models.Model):
    """Registra la venta de productos realizada durante un servicio."""

    service_session = models.ForeignKey(
        ServiceSession,
        on_delete=models.CASCADE,
        related_name="product_sales",
        verbose_name="Servicio",
    )
    responsible = models.ForeignKey(
        "UsuarioApp.Profile",
        on_delete=models.PROTECT,
        related_name="product_sales",
        verbose_name="Responsable",
    )
    sold_at = models.DateTimeField("Fecha y hora de venta", auto_now_add=True)
    created_at = models.DateTimeField("Fecha de creación", auto_now_add=True)
    updated_at = models.DateTimeField("Fecha de actualización", auto_now=True)

    class Meta:
        verbose_name = "Venta de productos"
        verbose_name_plural = "Ventas de productos"
        ordering = ("-sold_at", "-created_at")

    def __str__(self) -> str:
        return f"Venta #{self.pk} - {self.service_session.shift.sucursal.name} ({self.sold_at:%Y-%m-%d %H:%M})"


class ServiceSessionProductSaleItem(models.Model):
    """Detalle de productos vendidos en una venta del servicio."""

    sale = models.ForeignKey(
        ServiceSessionProductSale,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Venta",
    )
    product = models.ForeignKey(
        "BranchProduct",
        on_delete=models.PROTECT,
        related_name="sale_items",
        verbose_name="Producto",
    )
    quantity = models.PositiveIntegerField("Cantidad vendida")

    class Meta:
        verbose_name = "Producto vendido"
        verbose_name_plural = "Productos vendidos"
        ordering = ("product__product_type",)

    def __str__(self) -> str:
        return f"{self.product.product_type} - {self.quantity} u."


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


class FuelPrice(models.Model):
    """Registra el historial de precios por tipo de combustible en una sucursal."""

    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.CASCADE,
        related_name="fuel_prices",
        verbose_name="Sucursal",
    )
    fuel_type = models.CharField("Tipo de combustible", max_length=100)
    price = models.DecimalField("Precio por litro", max_digits=12, decimal_places=2)
    created_at = models.DateTimeField("Fecha de registro", auto_now_add=True)

    class Meta:
        verbose_name = "Precio de combustible"
        verbose_name_plural = "Precios de combustible"
        ordering = ("-created_at", "-pk")

    def __str__(self) -> str:
        return f"{self.fuel_type} - {self.sucursal.name} (${self.price})"