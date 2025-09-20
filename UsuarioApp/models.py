from django.core.validators import RegexValidator
from django.db import models
from .choices import PERMISOS, GENDER_CHOICES


# Create your models here.

from django.contrib.auth.models import User
from django.utils import timezone
import uuid
import os
from utils.customer_img import resize_image, crop_image, handle_old_image


def profile_picture_path(instance, filename):
    random_filename = str(uuid.uuid4())
    extension = os.path.splitext(filename)[1]
    return f"users/{instance.user_FK.username}/{random_filename}{extension}"


# Create your models here.
class Position(models.Model):
    user_position = models.CharField(max_length=45, unique=True)
    permission_code = models.CharField(
        max_length=25, choices=PERMISOS, default="ATTENDANT"
    )

    class Meta:
        db_table = "position"

    def __str__(self):
        return f"{self.user_position}"


class Profile(models.Model):
    last_activity = models.DateTimeField(null=True, blank=True)
    image = models.ImageField(upload_to=profile_picture_path, default="profile.webp")
    user_FK = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="profile",
    )
    position_FK = models.ForeignKey(
        Position, on_delete=models.SET_NULL, null=True, blank=True
    )
    company_rut = models.CharField(
        max_length=12,
        blank=True,
        null=True,
        validators=[
            RegexValidator(
                regex=r"^[0-9.]+-[0-9kK]{1}$",
                message="Ingrese un RUT válido en el formato 12.345.678-9",
            )
        ],
        verbose_name="RUT Empresa",
    )
    phone = models.CharField(max_length=20, blank=True, verbose_name="Teléfono")
    gender = models.CharField(
        max_length=1,
        choices=GENDER_CHOICES,
        null=True,
        blank=True,
        verbose_name="Sexo",
    )
    date_of_birth = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha de nacimiento",
    )
    salario = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Salario",
    )
    address = models.CharField(max_length=255, blank=True, verbose_name="Dirección")
    date_of_hire = models.DateField(null=True, blank=True, verbose_name="Fecha de contratación")
    is_partime = models.BooleanField(
        default=False,
        choices=[(True, "Tiempo completo"), (False, "Medio tiempo")],
        verbose_name="Tipo de jornada",
    )
    # Documentos
    examen_medico = models.FileField(
        upload_to="documentos/examenes/",
        null=True,
        blank=True,
        verbose_name="Examen médico",
    )
    contrato = models.FileField(
        upload_to="documentos/contratos/",
        null=True,
        blank=True,
        verbose_name="Contrato",
    )
    def save(self, *args, **kwargs):
        update_last_activity = kwargs.pop("update_last_activity", False)

        if update_last_activity:
            self.last_activity = timezone.now()
            kwargs["update_fields"] = ["last_activity"]

        if self.pk:
            handle_old_image(Profile, self.pk, self.image)

        super(Profile, self).save(*args, **kwargs)

        if self.image and os.path.exists(self.image.path):
            resize_image(self.image.path, 300)
            crop_image(self.image.path, 300)

    def has_role(self, roles=None):
        """Check if the profile's position matches the given roles.

        Parameters
        ----------
        roles : Iterable[str] | str | None
            Roles allowed for a view. If ``None`` the method returns ``True``
            when the user has any role other than "RESTRICTED".
        """

        if not self.position_FK:
            return False

        code = self.position_FK.permission_code
        if roles is None:
            return code != "OWNER"

        if isinstance(roles, str):
            roles = [roles]

        return code in roles

    def update_last_activity(self):
        self.save(update_last_activity=True)

    def _has_permission(self, code: str) -> bool:
        """Return True if the profile has the given permission code."""
        return bool(self.position_FK and self.position_FK.permission_code == code)

    def is_owner(self) -> bool:
        return self._has_permission("OWNER")

    def is_admin(self) -> bool:
        return self._has_permission("ADMINISTRATOR")

    def is_accountant(self) -> bool:
        return self._has_permission("ACCOUNTANT")

    def is_head_ATTENDANT(self) -> bool:
        return self._has_permission("HEAD_ATTENDANT")

    def is_ATTENDANT(self) -> bool:
        return self._has_permission("ATTENDANT")

    def __str__(self):
        return self.user_FK.username

    class Meta:
        verbose_name = "Perfil"
        verbose_name_plural = "Perfiles"
        ordering = ["-id"]


class Statistics(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="statistics",
    )
    asistencia = models.PositiveIntegerField(default=0, verbose_name="Asistencia")
    vacaciones = models.PositiveIntegerField(default=0, verbose_name="Vacaciones")
    permisos = models.PositiveIntegerField(default=0, verbose_name="Permisos")

    class Meta:
        db_table = "statistics"
    def __str__(self):
        return f"Estadísticas de {self.user.username}"


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
        Profile,
        on_delete=models.CASCADE,
        related_name="company",
        verbose_name="Perfil",
    )

    class Meta:
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"

    def __str__(self) -> str:
        return f"{self.business_name} ({self.rut})"

    @staticmethod
    def normalize_rut(rut: str) -> str:
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
