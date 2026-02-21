from ninja import Router
from apps.users.api.schemas import RegisterIn, LoginIn, TokenOut, UserOut, ErrorOut, RefreshIn, AccessTokenOut
from apps.users.services import UserService
from apps.common.auth.bearer import JWTAuth
from apps.common.exceptions import AuthenticationError

router = Router(tags=["Auth"])

@router.post("/register", response={200: UserOut, 400: ErrorOut})
def register(request, payload: RegisterIn):
    try:
        user = UserService.register_user(
            username=payload.username,
            email=payload.email,
            password=payload.password,
            first_name=payload.first_name,
            last_name=payload.last_name
        )
        return 200, user
    except ValueError as e:
        return 400, {"detail": str(e)}

@router.post("/login", response={200: TokenOut, 401: ErrorOut})
def login(request, payload: LoginIn):
    try:
        user, access_token, refresh_token = UserService.authenticate_user(
            username=payload.username,
            password=payload.password
        )
        return 200, {
            "access_token": access_token,
            "refresh_token": refresh_token
        }
    except AuthenticationError as e:
        return 401, {"detail": str(e)}

@router.post("/refresh", response={200: AccessTokenOut, 401: ErrorOut})
def refresh(request, payload: RefreshIn):
    try:
        access_token = UserService.refresh_access_token(refresh_token=payload.refresh_token)
        return 200, {"access_token": access_token}
    except AuthenticationError as e:
        return 401, {"detail": str(e)}

@router.get("/me", auth=JWTAuth(), response={200: UserOut, 401: ErrorOut})
def get_me(request):
    # request.auth is populated by the JWTAuth bearer class with the DomainUser
    if not request.auth:
        return 401, {"detail": "Unauthorized"}
        
    return 200, request.auth
