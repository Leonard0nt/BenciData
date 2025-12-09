from django.db import models

# Create your models here.

class DispenseEvent(models.Model):
    uid = models.CharField(max_length=100)  # UID NFC del bombero
    litros = models.FloatField()  # Litros despachados
    pistola = models.CharField(
        max_length=50, null=True, blank=True
    )  # ID o código enviado por la pistola
    nozzle = models.ForeignKey(
        "sucursalApp.Nozzle",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dispense_events",
    )
    fuel_numeral = models.ForeignKey(
        "sucursalApp.MachineFuelInventoryNumeral",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dispense_events",
    )
    firefighter = models.ForeignKey(
        "UsuarioApp.Profile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dispense_events",
    )
    service_session = models.ForeignKey(
        "sucursalApp.ServiceSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dispense_events",
    )
    timestamp_arduino = models.CharField(
        max_length=100, null=True, blank=True
    )  # lo que te mande el Arduino (epoch, ISO, etc.)
    created_at = models.DateTimeField(auto_now_add=True)  # cuándo lo recibió Django

    def __str__(self):
        return f"{self.uid} - {self.litros} L - pistola {self.pistola}"
