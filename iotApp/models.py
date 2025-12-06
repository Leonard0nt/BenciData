from django.db import models

# Create your models here.

class DispenseEvent(models.Model):
    uid = models.CharField(max_length=100)          # UID NFC del bombero
    litros = models.FloatField()                    # Litros despachados
    pistola = models.IntegerField(null=True, blank=True)  # ID de la pistola
    timestamp_arduino = models.CharField(
        max_length=100, null=True, blank=True
    )  # lo que te mande el Arduino (epoch, ISO, etc.)
    created_at = models.DateTimeField(auto_now_add=True)  # cuándo lo recibió Django

    def __str__(self):
        return f"{self.uid} - {self.litros} L - pistola {self.pistola}"
