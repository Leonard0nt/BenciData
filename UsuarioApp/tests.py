from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from UsuarioApp.models import Profile, Position, RESTRICTED_PERMISSION_CODE
from homeApp.models import Company
from sucursalApp.models import Sucursal, SucursalStaff

class ProfileHasRoleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner_position = Position.objects.create(
            user_position="Owner",
            permission_code="OWNER",
        )
        cls.attendant_position = Position.objects.create(
            user_position="Attendant",
            permission_code="ATTENDANT",
        )
        cls.restricted_position = Position.objects.create(
            user_position="Restricted",
            permission_code=RESTRICTED_PERMISSION_CODE,
        )

    def _create_profile(self, username: str, position: Position) -> Profile:
        user = User.objects.create_user(username=username, password="testpass123")
        return Profile.objects.create(user_FK=user, position_FK=position)

    def test_has_role_none_allows_non_restricted(self):
        profile = self._create_profile("owner_user", self.owner_position)
        self.assertTrue(profile.has_role())

    def test_has_role_none_blocks_restricted(self):
        profile = self._create_profile("restricted_user", self.restricted_position)
        self.assertFalse(profile.has_role())

    def test_has_role_with_iterables_and_strings(self):
        profile = self._create_profile("attendant_user", self.attendant_position)
        self.assertTrue(profile.has_role(["ATTENDANT", "ADMIN"]))
        self.assertTrue(profile.has_role("ATTENDANT"))
        self.assertFalse(profile.has_role(["OWNER", "ADMIN"]))


class PermitsPositionMixinTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner_position = Position.objects.create(
            user_position="Owner View",
            permission_code="OWNER",
        )
        cls.restricted_position = Position.objects.create(
            user_position="Restricted View",
            permission_code=RESTRICTED_PERMISSION_CODE,
        )

    def _login_with_position(self, username: str, position: Position):
        user = User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="testpass123",
        )
        Profile.objects.create(user_FK=user, position_FK=position)
        self.client.force_login(user)

    def test_owner_can_access_user_create_view(self):
        self._login_with_position("owner_access", self.owner_position)
        response = self.client.get(reverse("Register"))
        self.assertEqual(response.status_code, 200)

    def test_restricted_role_is_redirected(self):
        self._login_with_position("restricted_access", self.restricted_position)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("Home"))


class UserDeleteViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner_position = Position.objects.create(
            user_position="Owner Role",
            permission_code="OWNER",
        )
        cls.admin_position = Position.objects.create(
            user_position="Admin Role",
            permission_code="ADMINISTRATOR",
        )
        cls.attendant_position = Position.objects.create(
            user_position="Attendant Role",
            permission_code="ATTENDANT",
        )

    def _create_user(self, username: str, position: Position, **profile_kwargs):
        user = User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="testpass123",
        )
        profile = Profile.objects.create(
            user_FK=user,
            position_FK=position,
            **profile_kwargs,
        )
        return user, profile

    def _create_company_with_owner(self):
        owner_user, owner_profile = self._create_user(
            "owner_user",
            self.owner_position,
        )
        company = Company.objects.create(
            rut="12.345.678-5",
            business_name="Gas Station SA",
            tax_address="Av. Principal 123",
            profile=owner_profile,
        )
        owner_profile.company_rut = company.rut
        owner_profile.save(update_fields=["company_rut"])
        return company, owner_user, owner_profile

    def _create_branch(self, company: Company, name: str = "Casa Matriz") -> Sucursal:
        return Sucursal.objects.create(
            company=company,
            name=name,
            address="Calle 1",
            city="Santiago",
            region="Metropolitana",
            phone="123456789",
            email="contacto@example.com",
            islands=1,
        )

    def test_owner_can_deactivate_user_and_cleanup_staff(self):
        company, owner_user, owner_profile = self._create_company_with_owner()
        branch = self._create_branch(company)

        target_user, target_profile = self._create_user(
            "employee_user",
            self.attendant_position,
            company_rut=company.rut,
            current_branch=branch,
        )
        SucursalStaff.objects.create(sucursal=branch, profile=target_profile)

        self.client.force_login(owner_user)
        response = self.client.post(reverse("UserDelete", args=[target_user.pk]))

        self.assertRedirects(response, reverse("User"))
        target_user.refresh_from_db()
        self.assertFalse(target_user.is_active)
        self.assertFalse(
            SucursalStaff.objects.filter(profile=target_profile).exists()
        )

    def test_non_privileged_user_is_redirected(self):
        company, _, _ = self._create_company_with_owner()
        branch = self._create_branch(company)

        target_user, target_profile = self._create_user(
            "restricted_employee",
            self.attendant_position,
            company_rut=company.rut,
            current_branch=branch,
        )
        attendant_user, attendant_profile = self._create_user(
            "attendant",
            self.attendant_position,
            company_rut=company.rut,
            current_branch=branch,
        )
        SucursalStaff.objects.create(sucursal=branch, profile=target_profile)
        SucursalStaff.objects.create(sucursal=branch, profile=attendant_profile)

        self.client.force_login(attendant_user)
        response = self.client.post(reverse("UserDelete", args=[target_user.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("Home"))
        target_user.refresh_from_db()
        self.assertTrue(target_user.is_active)

    def test_administrator_requires_shared_branch(self):
        company, _, _ = self._create_company_with_owner()
        branch = self._create_branch(company)

        admin_user, admin_profile = self._create_user(
            "branch_admin",
            self.admin_position,
            company_rut=company.rut,
        )
        SucursalStaff.objects.create(sucursal=branch, profile=admin_profile)

        target_user, target_profile = self._create_user(
            "branch_employee",
            self.attendant_position,
            company_rut=company.rut,
            current_branch=branch,
        )
        SucursalStaff.objects.create(sucursal=branch, profile=target_profile)

        self.client.force_login(admin_user)
        response = self.client.post(reverse("UserDelete", args=[target_user.pk]))

        self.assertRedirects(response, reverse("User"))
        target_user.refresh_from_db()
        self.assertFalse(target_user.is_active)
