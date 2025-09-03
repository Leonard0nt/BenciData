# UsuarioApp/signals.py
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile, Position

@receiver(post_save, sender=User)
def create_profile_for_superuser(sender, instance, created, **kwargs):
    if created and instance.is_superuser:
        owner_pos = Position.objects.get(permission_code="OWNER")
        Profile.objects.get_or_create(
            user_FK=instance,
            defaults={"position_FK": owner_pos}
        )
