from django.contrib.auth.hashers import check_password
from apps.users.repository import UserRepository
from apps.users.domain.user import User as DomainUser
from apps.common.auth.jwt import create_access_token, create_refresh_token, decode_token
from apps.common.exceptions import AuthenticationError

class UserService:
    @staticmethod
    def register_user(*, username: str, email: str, password: str, first_name: str, last_name: str) -> DomainUser:
        if UserRepository.username_exists(username):
            raise ValueError("Username already exists")
            
        if UserRepository.email_exists(email):
            raise ValueError("Email already exists")

        model = UserRepository.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )
        return DomainUser.from_model(model)

    @staticmethod
    def authenticate_user(*, username: str, password: str) -> tuple[DomainUser, str, str]:
        user_model = UserRepository.get_by_username(username)
        
        if not user_model or not check_password(password, user_model.password):
            raise AuthenticationError("Invalid username or password")

        domain_user = DomainUser.from_model(user_model)
        access_token = create_access_token(domain_user.id)
        refresh_token = create_refresh_token(domain_user.id)
        
        return domain_user, access_token, refresh_token

    @staticmethod
    def refresh_access_token(*, refresh_token: str) -> str:
        payload = decode_token(refresh_token)
        
        if payload.get("type") != "refresh":
            raise AuthenticationError("Invalid token type")
            
        user_id = payload.get("sub")
        
        # Verify user still exists
        try:
            UserRepository.get_by_id(user_id)
        except Exception:
            raise AuthenticationError("User not found")
            
        return create_access_token(user_id)
