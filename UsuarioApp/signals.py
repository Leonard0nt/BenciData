# UsuarioApp/signals.py
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Position, Profile
from homeApp.models import Company

@receiver(post_save, sender=User)
def create_profile_for_superuser(sender, instance, created, **kwargs):
    if created and instance.is_superuser:
        owner_pos = Position.objects.get(permission_code="OWNER")
        Profile.objects.get_or_create(
            user_FK=instance,
            defaults={"position_FK": owner_pos}
        )

@receiver(post_save, sender=Profile)
def ensure_company_for_owner(sender, instance: Profile, created: bool, **kwargs):
    if not instance.is_owner():
        return

    try:
        instance.company
    except Company.DoesNotExist:
        Company.objects.create(
            profile=instance,
            rut=f"{instance.pk:08d}-0",
            business_name=instance.user_FK.get_full_name() or instance.user_FK.username,
            tax_address="",
        )