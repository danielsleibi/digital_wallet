import os
from django.test import TestCase
from apps.users.services import UserService
from apps.common.exceptions import AuthenticationError

class UserServiceTests(TestCase):
    def test_register_creates_user(self):
        user = UserService.register_user(
            username="johndoe",
            email="john@example.com",
            password="securepassword123",
            first_name="John",
            last_name="Doe"
        )
        self.assertEqual(user.username, "johndoe")
        self.assertEqual(user.email, "john@example.com")
        self.assertIsNotNone(user.id)

    def test_register_duplicate_username_fails(self):
        UserService.register_user(
            username="johndoe",
            email="john@example.com",
            password="securepassword123",
            first_name="John",
            last_name="Doe"
        )
        with self.assertRaisesMessage(ValueError, "Username already exists"):
            UserService.register_user(
                username="johndoe",
                email="john2@example.com",
                password="securepassword123",
                first_name="John",
                last_name="Doe"
            )

    def test_register_duplicate_email_fails(self):
        UserService.register_user(
            username="johndoe",
            email="john@example.com",
            password="securepassword123",
            first_name="John",
            last_name="Doe"
        )
        with self.assertRaisesMessage(ValueError, "Email already exists"):
            UserService.register_user(
                username="johndoe2",
                email="john@example.com",
                password="securepassword123",
                first_name="John",
                last_name="Doe"
            )

    def test_authenticate_valid_credentials(self):
        UserService.register_user(
            username="johndoe",
            email="john@example.com",
            password="securepassword123",
            first_name="John",
            last_name="Doe"
        )
        
        user, access, refresh = UserService.authenticate_user(
            username="johndoe",
            password="securepassword123"
        )
        self.assertEqual(user.username, "johndoe")
        self.assertIsNotNone(access)
        self.assertIsNotNone(refresh)

    def test_authenticate_wrong_password_fails(self):
        UserService.register_user(
            username="johndoe",
            email="john@example.com",
            password="securepassword123",
            first_name="John",
            last_name="Doe"
        )
        
        with self.assertRaises(AuthenticationError):
            UserService.authenticate_user(
                username="johndoe",
                password="wrongpassword"
            )

    def test_authenticate_nonexistent_username_fails(self):
        with self.assertRaises(AuthenticationError):
            UserService.authenticate_user(
                username="unknownuser",
                password="password123"
            )
