from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from util.supabse import supabase
from utils.security import verify_password, create_access_token, decode_token, hash_password
from controllers.auth_controller import signup_doctor, login_user_and_create_token, get_user_by_email

router = APIRouter()
bearer_scheme = HTTPBearer()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: str
    password: str


class SignupRequest(BaseModel):
    name: str
    email: str
    password: str



@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest):
    token = login_user_and_create_token(req.email, req.password)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return {"access_token": token, "token_type": "bearer"}


@router.post("/signup")
def signup(req: SignupRequest):
    # Only allow signup as Doctor via this endpoint
    try:
        created = signup_doctor(req.name, req.email, req.password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    created.pop("password_hash", None)
    return created

@router.post("/me")
def get_current_user_info(requests: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    token = requests.credentials
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    user = get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    token = credentials.credentials
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    user = get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_role(*roles):
    def _checker(user = Depends(get_current_user)):
        if user.get("role") not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operation not permitted")
        return user

    return _checker

def get_user_by_email(email: str):
    resp = supabase.table("users").select("*").eq("email", email).limit(1).execute()
    data = resp.data
    if not data:
        return None
    return data[0]