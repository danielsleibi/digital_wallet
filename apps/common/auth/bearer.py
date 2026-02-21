from ninja.security import HttpBearer
from apps.users.repository import UserRepository
from apps.users.domain.user import User as DomainUser
from apps.common.auth.jwt import decode_token
from apps.common.exceptions import AuthenticationError

class JWTAuth(HttpBearer):
    def authenticate(self, request, token):
        try:
            payload = decode_token(token)
            if payload.get("type") != "access":
                return None
            
            user_id = payload.get("sub")
            if not user_id:
                return None
                
            # Fetch user from database
            user_model = UserRepository.get_by_id(user_id)
            
            # Use domain user for the request context to keep layers decoupled
            return DomainUser.from_model(user_model)
            
        except (AuthenticationError, Exception):
            # Exception handles DoesNotExist from repository or other errors safely
            return None
