from django.apps import AppConfig
# UsuarioApp/apps.py
from django.apps import AppConfig
from django.db.models.signals import post_migrate

class UsuarioAppConfig(AppConfig):
    name = "UsuarioApp"

class UsuarioAppConfig(AppConfig):
    name = "UsuarioApp"

    def ready(self):
        from .models import Position
        from .choices import PERMISOS

        def poblar_positions(sender, **kwargs):
            if sender.name != self.name:
                return
            for code, name in PERMISOS:
                Position.objects.get_or_create(
                    user_position=name,             # ahora guarda el código (p.ej. "OWNER")
                    defaults={"permission_code": code},  # y el permiso recibe el nombre (p.ej. "Dueño")
                )

        post_migrate.connect(poblar_positions, sender=self)







