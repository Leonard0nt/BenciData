"""Carga una estación ficticia con `python manage.py shell < demo/seed.py`."""

from datetime import time
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import transaction
from django.urls import reverse

from demo.access import DEMO_ACCOUNTS, DEMO_ROLE, DEMO_USERNAME
from UsuarioApp.choices import PERMISOS

from sucursalApp.models import (
    FuelInventory, FuelPrice, Island, Machine, MachineFuelInventoryNumeral, Nozzle,
    ServiceSession, Shift, Sucursal, SucursalStaff,
)
from UsuarioApp.models import Position, Profile

role_label = dict(PERMISOS)[DEMO_ROLE]


def prepare_demo_user(user, email):
    user.email = email
    user.set_unusable_password()
    user.save(update_fields=["email", "password"])


with transaction.atomic():
    positions = {}
    for code, label in PERMISOS:
        positions[code], _ = Position.objects.get_or_create(
            permission_code=code, defaults={"user_position": label}
        )

    owner, _ = User.objects.get_or_create(username=DEMO_ACCOUNTS["OWNER"])
    role = positions["OWNER"]
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
        username=DEMO_ACCOUNTS["HEAD_ATTENDANT"],
        defaults={"email": email, "first_name": "Alex", "last_name": "Demo"},
    )
    profile, _ = Profile.objects.get_or_create(
        user_FK=operator,
        defaults={
            "position_FK": positions["HEAD_ATTENDANT"],
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
    # Conserva el turno ficticio abierto y las lecturas que ya recibió.
    session, _ = ServiceSession.objects.update_or_create(
        shift=shift,
        ended_at=None,
        defaults={"close_mode": ServiceSession.CLOSE_MODE_PISTOL},
    )
    if DEMO_ROLE == "OWNER":
        prepare_demo_user(owner, "dueno@bencidata.demo")
    elif DEMO_ROLE == "HEAD_ATTENDANT":
        prepare_demo_user(operator, email)
    else:
        role_email = {
            "ADMINISTRATOR": "administrador@bencidata.demo",
            "ACCOUNTANT": "secretaria@bencidata.demo",
            "ATTENDANT": "bombero@bencidata.demo",
        }[DEMO_ROLE]
        demo_user, _ = User.objects.get_or_create(
            username=DEMO_USERNAME,
            defaults={"first_name": role_label, "last_name": "Demo"},
        )
        prepare_demo_user(demo_user, role_email)
        demo_profile, _ = Profile.objects.get_or_create(
            user_FK=demo_user,
            defaults={
                "position_FK": positions[DEMO_ROLE],
                "current_branch": branch,
            },
        )
        SucursalStaff.objects.get_or_create(
            sucursal=branch, profile=demo_profile, defaults={"role": DEMO_ROLE}
        )
        if DEMO_ROLE == "ATTENDANT":
            session.attendants.add(demo_profile)

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
