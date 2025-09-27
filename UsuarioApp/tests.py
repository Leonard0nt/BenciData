from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from UsuarioApp.models import Profile, Position, RESTRICTED_PERMISSION_CODE


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
        response = self.client.get(reverse("Register"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("Home"))
