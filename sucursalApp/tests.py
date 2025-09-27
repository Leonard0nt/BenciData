from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

# Create your tests here.
from UsuarioApp.models import Position, Profile
from homeApp.models import Company

from .models import Island, Machine, Nozzle, Sucursal


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
                "initial_numeral": "10.00",
                "final_numeral": "20.00",
                "fuel_type": "Gasolina 93",
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
                "initial_numeral": "5.00",
                "final_numeral": "15.00",
                "fuel_type": "Gasolina 93",
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

    def test_owner_can_edit_related_entities(self):
        island = Island.objects.create(
            sucursal=self.branch, number=2, description="Isla original"
        )
        machine = Machine.objects.create(
            island=island,
            number=2,
            initial_numeral=0,
            final_numeral=0,
            fuel_type="93",
            description="Máquina original",
        )
        nozzle = Nozzle.objects.create(
            machine=machine,
            number=2,
            initial_numeral=0,
            final_numeral=0,
            fuel_type="93",
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
                "initial_numeral": "30.00",
                "final_numeral": "40.00",
                "fuel_type": "95",
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
        self.assertEqual(machine.fuel_type, "95")

        response = self.client.post(
            reverse("sucursal_nozzle_update", args=[nozzle.pk]),
            {
                "machine": machine.pk,
                "number": 5,
                "initial_numeral": "50.00",
                "final_numeral": "60.00",
                "fuel_type": "Diesel",
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
        self.assertEqual(nozzle.fuel_type, "Diesel")

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