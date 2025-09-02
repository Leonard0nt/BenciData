# UsuarioApp/signals.py
from django.apps import apps
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.contrib.auth.models import Permission

@receiver(post_migrate)
def create_positions_from_perms(sender, **kwargs):
    if sender.name != "UsuarioApp":
        return

    Position = apps.get_model("UsuarioApp", "Position")

    # codename -> nombre del Position
    POSITION_FROM_PERM = {
        ("OWNER", "Dueño"),
        ("ADMINISTRATOR", "Administrador"),
        ("ACCOUNTANT", "Contador"),
        ("HEAD_ATTENDANT", "Bombero encargado"),
        ("ATTENDANT", "Bombero normal"),
    }

    for codename, pos_name in POSITION_FROM_PERM.items():
        try:
            perm = Permission.objects.get(codename=codename)
        except Permission.DoesNotExist:
            continue
        position, _ = Position.objects.get_or_create(name=pos_name)
        position.permissions.set([perm])
