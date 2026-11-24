from django.apps import AppConfig
from django.db.models.signals import post_migrate

class UsuarioAppConfig(AppConfig):
    name = "UsuarioApp"

    def ready(self):
        from . import signals  # noqa: F401 - registra las señales de usuarios.
        from .models import Position
        from .choices import PERMISOS

        def poblar_positions(sender, **kwargs):
            if sender.name != self.name:
                return
            for code, name in PERMISOS:
                Position.objects.get_or_create(
                    user_position=name.strip(),
                    defaults={"permission_code": code},
                )

        post_migrate.connect(poblar_positions, sender=self)
