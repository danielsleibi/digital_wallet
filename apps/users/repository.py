from django.contrib.auth import get_user_model

User = get_user_model()

class UserRepository:
    @staticmethod
    def get_by_username(username: str):
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist:
            return None

    @staticmethod
    def get_by_id(user_id):
        return User.objects.get(id=user_id)

    @staticmethod
    def create_user(username: str, email: str, password: str, **extra_fields):
        return User.objects.create_user(
            username=username,
            email=email,
            password=password,
            **extra_fields
        )

    @staticmethod
    def username_exists(username: str) -> bool:
        return User.objects.filter(username=username).exists()

    @staticmethod
    def email_exists(email: str) -> bool:
        return User.objects.filter(email=email).exists()
