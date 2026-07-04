import os
import secrets
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def get_api_key(api_key: str | None = Security(api_key_header)) -> str | None:
    """Validate API Key."""

    # Check if we have an API Key configured in env
    expected_api_key = os.getenv("API_KEY", os.getenv("WEBHOOK_SECRET", ""))

    # If no API key is configured, secure default to reject to prevent unauthenticated access
    if not expected_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfiguration: API_KEY must be set",
        )

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key",
        )

    if not secrets.compare_digest(api_key, expected_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )

    return api_key
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from google.oauth2 import id_token
from google.auth.transport import requests
from pydantic import BaseModel
from typing import Optional
import datetime
from app.core.config import GOOGLE_CLIENT_ID, JWT_SECRET_KEY, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

router = APIRouter()
security = HTTPBearer()

class AuthRequest(BaseModel):
    token: str

class AuthResponse(BaseModel):
    access_token: str
    token_type: str
    user_email: str
    user_name: Optional[str]

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

@router.post("/google", response_model=AuthResponse)
async def google_auth(request: AuthRequest):
    try:
        # Verify the Google ID token
        idinfo = id_token.verify_oauth2_token(request.token, requests.Request(), GOOGLE_CLIENT_ID)

        # Token is valid, get user info
        email = idinfo.get('email')
        name = idinfo.get('name')

        # Issue a JWT
        access_token = create_access_token(data={"sub": email, "name": name})

        return AuthResponse(
            access_token=access_token,
            token_type="Bearer",
            user_email=email,
            user_name=name
        )
    except ValueError as e:
        # Invalid token
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid Google token: {str(e)}")
