import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

# Create your tests here.
from UsuarioApp.models import Position, Profile
from homeApp.models import Company

from .models import (
    FuelInventory,
    Island,
    Machine,
    MachineFuelInventory,
    Nozzle,
    ServiceSession,
    Shift,
    Sucursal,
)


class SucursalRelatedViewsTests(TestCase):
    def setUp(self) -> None:
        self.owner_position, _ = Position.objects.get_or_create(
            user_position="Dueño", defaults={"permission_code": "OWNER"}
        )
        self.owner_position.permission_code = "OWNER"
        self.owner_position.save()
        self.admin_position, _ = Position.objects.get_or_create(
            user_position="Administrador",
            defaults={"permission_code": "ADMINISTRATOR"},
        )
        self.admin_position.permission_code = "ADMINISTRATOR"
        self.admin_position.save()

        self.owner_user = User.objects.create_user(
            username="owner", password="password123", email="owner@example.com"
        )
        self.owner_profile = Profile.objects.create(
            user_FK=self.owner_user, position_FK=self.owner_position
        )
        self.company, _ = Company.objects.get_or_create(
            profile=self.owner_profile,
            defaults={
                "rut": "11.111.111-1",
                "business_name": "Empresa Test",
                "tax_address": "Av. Principal 123",
            },
        )
        self.company.rut = "11.111.111-1"
        self.company.business_name = "Empresa Test"
        self.company.tax_address = "Av. Principal 123"
        self.company.save()
        self.branch = Sucursal.objects.create(
            company=self.company,
            name="Sucursal Centro",
            address="Calle 1",
            city="Santiago",
            region="Metropolitana",
            phone="123456789",
            email="branch@example.com",
        )

        self.inventory = FuelInventory.objects.create(
            sucursal=self.branch,
            code="INV-1",
            fuel_type="Gasolina 93",
            capacity=1000,
            liters=800,
        )

        self.client.force_login(self.owner_user)

    def test_owner_can_create_related_entities(self):
        island_create_url = reverse("sucursal_island_create", args=[self.branch.pk])
        response = self.client.post(
            island_create_url,
            {"sucursal": self.branch.pk, "number": 1, "description": "Isla 1"},
        )
        self.assertRedirects(
            response,
            reverse("sucursal_update", args=[self.branch.pk]),
            fetch_redirect_response=False,
        )
        island = Island.objects.get(sucursal=self.branch, number=1)

        machine_create_url = reverse(
            "sucursal_machine_create", args=[self.branch.pk, island.pk]
        )
        response = self.client.post(
            machine_create_url,
            {
                "island": island.pk,
                "number": 1,
                "fuel_inventories": [self.inventory.pk],
                f"numeral_{self.inventory.pk}": "10.00",
                "description": "Máquina 1",
            },
        )
        self.assertRedirects(
            response,
            reverse("sucursal_update", args=[self.branch.pk]),
            fetch_redirect_response=False,
        )
        machine = Machine.objects.get(island=island, number=1)

        nozzle_create_url = reverse("sucursal_nozzle_create", args=[machine.pk])
        response = self.client.post(
            nozzle_create_url,
            {
                "machine": machine.pk,
                "number": 1,
                "fuel_inventory": self.inventory.pk,
                "description": "Pistola 1",
            },
        )
        self.assertRedirects(
            response,
            reverse("sucursal_update", args=[self.branch.pk]),
            fetch_redirect_response=False,
        )
        nozzle = Nozzle.objects.get(machine=machine, number=1)

        self.assertEqual(island.sucursal, self.branch)
        self.assertEqual(machine.island, island)
        self.assertEqual(nozzle.machine, machine)
    def test_inline_create_forms_accept_template_field_names(self):
        update_url = reverse("sucursal_update", args=[self.branch.pk])
        response = self.client.get(update_url)
        island_form = response.context["island_create_form"]
        island_data = {
            island_form["sucursal"].html_name: self.branch.pk,
            island_form["number"].html_name: 7,
            island_form["description"].html_name: "Isla inline",
        }
        island_create_url = reverse("sucursal_island_create", args=[self.branch.pk])
        response = self.client.post(island_create_url, island_data)
        self.assertRedirects(
            response,
            reverse("sucursal_update", args=[self.branch.pk]),
            fetch_redirect_response=False,
        )
        island = Island.objects.get(number=7, sucursal=self.branch)

        response = self.client.get(update_url)
        island_from_context = list(response.context["islands"])[0]
        machine_form = island_from_context.machine_create_form
        machine_data = {
            machine_form["island"].html_name: island.pk,
            machine_form["number"].html_name: 3,
            machine_form["fuel_inventories"].html_name: [self.inventory.pk],
            f"numeral_{self.inventory.pk}": "150.00",
            machine_form["description"].html_name: "Máquina inline",
        }
        machine_create_url = reverse(
            "sucursal_machine_create", args=[self.branch.pk, island.pk]
        )
        response = self.client.post(machine_create_url, machine_data)
        self.assertRedirects(
            response,
            reverse("sucursal_update", args=[self.branch.pk]),
            fetch_redirect_response=False,
        )
        machine = Machine.objects.get(number=3, island=island)

        response = self.client.get(update_url)
        island_from_context = list(response.context["islands"])[0]
        machine_from_context = list(island_from_context.machines.all())[0]
        nozzle_form = machine_from_context.nozzle_create_form
        nozzle_data = {
            nozzle_form["machine"].html_name: machine.pk,
            nozzle_form["number"].html_name: 9,
            nozzle_form["fuel_inventory"].html_name: self.inventory.pk,
            nozzle_form["description"].html_name: "Pistola inline",
        }
        nozzle_create_url = reverse("sucursal_nozzle_create", args=[machine.pk])
        response = self.client.post(nozzle_create_url, nozzle_data)
        self.assertRedirects(
            response,
            reverse("sucursal_update", args=[self.branch.pk]),
            fetch_redirect_response=False,
        )

        self.assertTrue(
            Nozzle.objects.filter(number=9, machine=machine, description="Pistola inline").exists()
        )

    def test_owner_can_edit_related_entities(self):
        island = Island.objects.create(
            sucursal=self.branch, number=2, description="Isla original"
        )
        machine = Machine.objects.create(
            island=island,
            number=2,
            description="Máquina original",
        )
        MachineFuelInventory.objects.create(
            machine=machine, fuel_inventory=self.inventory, numeral=0
        )
        nozzle = Nozzle.objects.create(
            machine=machine,
            number=2,
            fuel_inventory=self.inventory,
            description="Pistola original",
        )

        response = self.client.post(
            reverse(
                "sucursal_island_update",
                kwargs={"branch_pk": self.branch.pk, "pk": island.pk},
            ),
            {
                "sucursal": self.branch.pk,
                "number": 3,
                "description": "Isla editada",
            },
        )
        self.assertRedirects(
            response,
            reverse("sucursal_update", args=[self.branch.pk]),
            fetch_redirect_response=False,
        )
        island.refresh_from_db()
        self.assertEqual(island.number, 3)
        self.assertEqual(island.description, "Isla editada")

        response = self.client.post(
            reverse("sucursal_machine_update", args=[machine.pk]),
            {
                "island": island.pk,
                "number": 4,
                "fuel_inventories": [self.inventory.pk],
                f"numeral_{self.inventory.pk}": "40.00",
                "description": "Máquina editada",
            },
        )
        self.assertRedirects(
            response,
            reverse("sucursal_update", args=[self.branch.pk]),
            fetch_redirect_response=False,
        )
        machine.refresh_from_db()
        self.assertEqual(machine.number, 4)
        self.assertEqual(machine.fuel_type, self.inventory.fuel_type)

        response = self.client.post(
            reverse("sucursal_nozzle_update", args=[nozzle.pk]),
            {
                "machine": machine.pk,
                "number": 5,
                "fuel_inventory": self.inventory.pk,
                "description": "Pistola editada",
            },
        )
        self.assertRedirects(
            response,
            reverse("sucursal_update", args=[self.branch.pk]),
            fetch_redirect_response=False,
        )
        nozzle.refresh_from_db()
        self.assertEqual(nozzle.number, 5)
        self.assertEqual(nozzle.fuel_type, self.inventory.fuel_type)

    def test_only_owner_can_manage_branch(self):
        self.client.logout()
        user = User.objects.create_user(
            username="employee", password="password123", email="emp@example.com"
        )
        Profile.objects.create(user_FK=user, position_FK=self.admin_position)

        self.client.force_login(user)
        island_create_url = reverse("sucursal_island_create", args=[self.branch.pk])

        response = self.client.get(island_create_url)
        self.assertRedirects(
            response,
            reverse("Home"),
            fetch_redirect_response=False,
        )

        response = self.client.post(
            island_create_url,
            {"sucursal": self.branch.pk, "number": 99, "description": "No permitido"},
        )
        self.assertRedirects(
            response,
            reverse("Home"),
            fetch_redirect_response=False,
        )
        self.assertFalse(Island.objects.filter(number=99).exists())


class ServiceSessionClosingFlowTests(TestCase):
    def setUp(self) -> None:
        self.owner_position, _ = Position.objects.get_or_create(
            user_position="Dueño", defaults={"permission_code": "OWNER"}
        )
        self.owner_position.permission_code = "OWNER"
        self.owner_position.save()

        self.head_position = Position.objects.filter(
            permission_code="HEAD_ATTENDANT"
        ).first()
        if not self.head_position:
            self.head_position = Position.objects.create(
                user_position="Jefe de isla",
                permission_code="HEAD_ATTENDANT",
            )
        elif self.head_position.permission_code != "HEAD_ATTENDANT":
            self.head_position.permission_code = "HEAD_ATTENDANT"
            self.head_position.save(update_fields=["permission_code"])

        self.owner_user = User.objects.create_user(
            username="owner", password="password123", email="owner@example.com"
        )
        self.owner_profile = Profile.objects.create(
            user_FK=self.owner_user, position_FK=self.owner_position
        )

        manager_user = User.objects.create_user(
            username="manager", password="password123", email="manager@example.com"
        )
        self.manager_profile = Profile.objects.create(
            user_FK=manager_user, position_FK=self.head_position
        )

        self.company, _ = Company.objects.get_or_create(
            profile=self.owner_profile,
            defaults={
                "rut": "11.111.111-1",
                "business_name": "Empresa Test",
                "tax_address": "Av. Principal 123",
            },
        )
        self.company.rut = "11.111.111-1"
        self.company.business_name = "Empresa Test"
        self.company.tax_address = "Av. Principal 123"
        self.company.save()

        self.branch = Sucursal.objects.create(
            company=self.company,
            name="Sucursal Centro",
            address="Calle 1",
            city="Santiago",
            region="Metropolitana",
            phone="123456789",
            email="branch@example.com",
        )

        self.inventory = FuelInventory.objects.create(
            sucursal=self.branch,
            code="INV-1",
            fuel_type="Gasolina 93",
            capacity=1500,
            liters=Decimal("1200"),
        )

        island = Island.objects.create(
            sucursal=self.branch, number=1, description="Isla de prueba"
        )
        self.machine_one = Machine.objects.create(
            island=island,
            number=1,
            fuel_inventory=self.inventory,
            description="Máquina 1",
        )
        self.machine_two = Machine.objects.create(
            island=island,
            number=2,
            fuel_inventory=self.inventory,
            description="Máquina 2",
        )
        MachineFuelInventory.objects.create(
            machine=self.machine_one,
            fuel_inventory=self.inventory,
            numeral=Decimal("100.00"),
        )
        MachineFuelInventory.objects.create(
            machine=self.machine_two,
            fuel_inventory=self.inventory,
            numeral=Decimal("200.00"),
        )

        self.shift = Shift.objects.create(
            sucursal=self.branch,
            code="T-1",
            description="Turno de prueba",
            start_time=datetime.time(8, 0),
            end_time=datetime.time(16, 0),
            manager=self.manager_profile,
        )
        self.service_session = ServiceSession.objects.create(
            shift=self.shift, coins_amount=0, cash_amount=0
        )

        self.client.force_login(self.owner_user)

    def test_shared_inventory_uses_individual_machine_numerals(self):
        close_url = reverse(
            "service_session_detail", args=[self.service_session.pk]
        )
        branch_links = list(
            MachineFuelInventory.objects.filter(machine__island__sucursal=self.branch)
            .select_related("machine", "fuel_inventory", "machine__island")
            .order_by("machine__island__number", "machine__number", "fuel_inventory__code")
        )

        new_numerals = {
            self.machine_one.pk: Decimal("160.00"),
            self.machine_two.pk: Decimal("255.00"),
        }

        form_data = {
            "form_type": "close-session",
            "close_action": "close",
            "close_session-TOTAL_FORMS": str(len(branch_links)),
            "close_session-INITIAL_FORMS": str(len(branch_links)),
            "close_session-MIN_NUM_FORMS": "0",
            "close_session-MAX_NUM_FORMS": "1000",
        }

        for index, link in enumerate(branch_links):
            form_data[f"close_session-{index}-machine_id"] = link.machine_id
            form_data[f"close_session-{index}-fuel_inventory_id"] = (
                link.fuel_inventory_id
            )
            form_data[f"close_session-{index}-numeral"] = str(
                new_numerals.get(link.machine_id)
            )

        response = self.client.post(close_url, data=form_data)

        self.assertRedirects(
            response, reverse("service_session_start"), fetch_redirect_response=False
        )

        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.liters, Decimal("1085.00"))

        updated_links = MachineFuelInventory.objects.filter(
            machine__in=(self.machine_one, self.machine_two)
        )
        numerals_by_machine = {
            link.machine_id: link.numeral for link in updated_links
        }
        self.assertEqual(numerals_by_machine[self.machine_one.pk], Decimal("160.00"))
        self.assertEqual(numerals_by_machine[self.machine_two.pk], Decimal("255.00"))

        self.machine_one.refresh_from_db()
        self.machine_two.refresh_from_db()
        self.assertEqual(self.machine_one.numeral, Decimal("160.00"))
        self.assertEqual(self.machine_two.numeral, Decimal("255.00"))

        self.service_session.refresh_from_db()
        self.assertIsNotNone(self.service_session.ended_at)
