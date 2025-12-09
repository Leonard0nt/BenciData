from django.test import TestCase

from decimal import Decimal
import json
from datetime import time

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from homeApp.models import Company
from sucursalApp.models import (
    FuelInventory,
    Island,
    Machine,
    MachineFuelInventoryNumeral,
    Nozzle,
    ServiceSession,
    Shift,
    Sucursal,
)
from UsuarioApp.models import Position, Profile
from .models import DispenseEvent


class RecibirDatosProxyTests(TestCase):
    def setUp(self):
        self.head_position = Position.objects.create(
            user_position="Head Attendant", permission_code="HEAD_ATTENDANT"
        )
        self.manager_user = User.objects.create_user(
            username="manager", password="password123"
        )
        self.manager_profile = Profile.objects.create(
            user_FK=self.manager_user, position_FK=self.head_position
        )

        self.company = Company.objects.create(
            rut="12345678-9",
            business_name="Test Company",
            tax_address="123 Test St",
            profile=self.manager_profile,
        )
        self.branch = Sucursal.objects.create(
            company=self.company,
            name="Sucursal Central",
            address="Av. Principal 123",
            city="Santiago",
            region="RM",
        )
        self.shift = Shift.objects.create(
            sucursal=self.branch,
            code="SHIFT-1",
            start_time=time(8, 0),
            end_time=time(16, 0),
            manager=self.manager_profile,
        )
        self.service_session = ServiceSession.objects.create(shift=self.shift)

        self.fuel_inventory = FuelInventory.objects.create(
            sucursal=self.branch,
            code="FI-001",
            fuel_type="Diesel",
            capacity=Decimal("1000.00"),
            liters=Decimal("500.00"),
        )
        self.island = Island.objects.create(sucursal=self.branch, number=1)
        self.machine = Machine.objects.create(
            island=self.island, number=1, fuel_inventory=self.fuel_inventory
        )
        self.numeral = MachineFuelInventoryNumeral.objects.create(
            machine=self.machine,
            fuel_inventory=self.fuel_inventory,
            slot=1,
            numeral=Decimal("100.00"),
        )
        self.nozzle = Nozzle.objects.create(
            machine=self.machine, number=1, code="N1", fuel_numeral=self.numeral
        )

        self.firefighter_user = User.objects.create_user(
            username="firefighter", password="password123"
        )
        self.firefighter = Profile.objects.create(
            user_FK=self.firefighter_user,
            codigo_identificador="UID-12345",
            current_branch=self.branch,
        )

    def test_recibir_datos_proxy_creates_dispense_event_and_updates_numeral(self):
        payload = {
            "uid": "UID-12345",
            "litros": 10.5,
            "pistola": "N1",
            "timestamp": "2024-01-01T12:00:00Z",
        }

        response = self.client.post(
            reverse("recibir_datos_proxy"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "ok")
        self.assertIn("event_id", data)

        event = DispenseEvent.objects.get(pk=data["event_id"])
        self.assertEqual(event.uid, payload["uid"])
        self.assertEqual(event.litros, payload["litros"])
        self.assertEqual(event.pistola, payload["pistola"])
        self.assertEqual(event.nozzle, self.nozzle)
        self.assertEqual(event.fuel_numeral, self.numeral)
        self.assertEqual(event.firefighter, self.firefighter)
        self.assertEqual(event.service_session, self.service_session)
        self.assertEqual(event.timestamp_arduino, payload["timestamp"])

# Create your tests here.
        self.numeral.refresh_from_db()
        self.assertEqual(self.numeral.numeral, Decimal("89.50"))
# Create your tests here.
