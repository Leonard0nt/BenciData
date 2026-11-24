"""Carga una estación ficticia con `python manage.py shell < demo/seed.py`."""

import os
from datetime import time
from decimal import Decimal

from allauth.account.models import EmailAddress
from django.contrib.auth.models import User
from django.db import transaction
from django.urls import reverse

from sucursalApp.models import (
    FuelInventory, FuelPrice, Island, Machine, MachineFuelInventoryNumeral, Nozzle,
    ServiceSession, Shift, Sucursal, SucursalStaff,
)
from UsuarioApp.models import Position, Profile

with transaction.atomic():
    owner, created = User.objects.get_or_create(
        username="bencidata-demo-owner",
        defaults={"is_staff": True, "is_superuser": True},
    )
    role = Position.objects.get(permission_code="OWNER")
    owner_profile, _ = Profile.objects.get_or_create(
        user_FK=owner, defaults={"position_FK": role}
    )
    company = owner_profile.company
    company.business_name = "Estación Demo"
    company.save(update_fields=["business_name"])
    branch, _ = Sucursal.objects.get_or_create(
        company=company, name="Sucursal Demo",
        defaults={"address": "Av. Demo 100", "city": "Santiago", "region": "RM"},
    )
    email = "operador@bencidata.demo"
    operator, _ = User.objects.get_or_create(
        username="operador-demo",
        defaults={"email": email, "first_name": "Alex", "last_name": "Demo"},
    )
    operator.set_password(os.environ["BENCIDATA_DEMO_PASSWORD"])
    operator.save(update_fields=["password"])
    EmailAddress.objects.get_or_create(
        user=operator, email=email, defaults={"verified": True, "primary": True}
    )
    profile, _ = Profile.objects.get_or_create(
        user_FK=operator,
        defaults={
            "position_FK": Position.objects.get(permission_code="HEAD_ATTENDANT"),
            "current_branch": branch,
            "codigo_identificador": "DEMO-NFC-01",
        },
    )
    SucursalStaff.objects.get_or_create(
        sucursal=branch, profile=profile, defaults={"role": "HEAD_ATTENDANT"}
    )
    shift, _ = Shift.objects.get_or_create(
        sucursal=branch, code="DEMO-AM",
        defaults={"manager": profile, "start_time": time(8), "end_time": time(16)},
    )
    session, _ = ServiceSession.objects.get_or_create(shift=shift, ended_at=None)
    session.attendants.add(profile)
    tank, _ = FuelInventory.objects.get_or_create(
        sucursal=branch, code="DEMO-DSL",
        defaults={"fuel_type": "Diesel", "capacity": 5000, "liters": 2800},
    )
    diesel_price = Decimal("927.00")
    prices = FuelPrice.objects.filter(sucursal=branch, fuel_type=tank.fuel_type)
    if prices.values_list("price", flat=True).first() != diesel_price:
        prices.create(sucursal=branch, fuel_type=tank.fuel_type, price=diesel_price)

    island, _ = Island.objects.get_or_create(sucursal=branch, number=1)
    machine, _ = Machine.objects.get_or_create(
        island=island, number=1, defaults={"fuel_inventory": tank}
    )
    machine.fuel_inventories.add(tank)
    numeral, _ = MachineFuelInventoryNumeral.objects.get_or_create(
        machine=machine, fuel_inventory=tank, slot=1, defaults={"numeral": Decimal("1000")},
    )
    Nozzle.objects.get_or_create(
        code="DEMO-N1", defaults={"machine": machine, "number": 1, "fuel_numeral": numeral}
    )

print(reverse("service_session_detail", args=[session.pk]))
