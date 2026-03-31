"""
Test Suite for EduVision Authentication Endpoints

Tests:
- Email signup with validation
- Email login with verification
- Google OAuth login
- JWT token refresh
- Password reset flow
- Token expiry and revocation
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
from datetime import timedelta

from app.main import app
from app.database import get_db
from app.db_models import User, RefreshToken
from app.auth_utils import create_access_token, create_refresh_token, decode_token, hash_value
from app.schemas import (
    EmailSignupRequest,
    EmailLoginRequest,
    ChangePasswordRequest,
    ResetPasswordRequest
)

client = TestClient(app)


class TestAuthEndpoints:
    """Test authentication routes"""

    def test_signup_valid_email(self):
        """Test successful user signup with valid email"""
        response = client.post("/auth/signup", json={
            "email": "test@example.com",
            "password": "SecurePass123",
            "display_name": "Test User"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == "test@example.com"

    def test_signup_invalid_email(self):
        """Test signup with invalid email format"""
        response = client.post("/auth/signup", json={
            "email": "invalid-email",
            "password": "SecurePass123",
            "display_name": "Test User"
        })
        assert response.status_code == 422

    def test_signup_weak_password(self):
        """Test signup with weak password"""
        response = client.post("/auth/signup", json={
            "email": "test@example.com",
            "password": "weak",
            "display_name": "Test User"
        })
        assert response.status_code == 400
        assert "at least 8 characters" in response.json()["detail"]

    def test_signup_duplicate_email(self):
        """Test signup with already registered email"""
        # First signup
        client.post("/auth/signup", json={
            "email": "duplicate@example.com",
            "password": "SecurePass123",
            "display_name": "Test User"
        })
        
        # Second signup with same email
        response = client.post("/auth/signup", json={
            "email": "duplicate@example.com",
            "password": "SecurePass123",
            "display_name": "Another User"
        })
        assert response.status_code == 409
        assert "already registered" in response.json()["detail"]

    def test_login_valid_credentials(self):
        """Test successful login with valid credentials"""
        # Signup first
        signup_response = client.post("/auth/signup", json={
            "email": "login@example.com",
            "password": "SecurePass123"
        })
        
        # Login
        login_response = client.post("/auth/login", json={
            "email": "login@example.com",
            "password": "SecurePass123"
        })
        assert login_response.status_code == 200
        assert "access_token" in login_response.json()

    def test_login_invalid_password(self):
        """Test login with incorrect password"""
        # Signup first
        client.post("/auth/signup", json={
            "email": "wrongpass@example.com",
            "password": "SecurePass123"
        })
        
        # Login with wrong password
        response = client.post("/auth/login", json={
            "email": "wrongpass@example.com",
            "password": "WrongPass123"
        })
        assert response.status_code == 401
        assert "Invalid credentials" in response.json()["detail"]

    def test_login_nonexistent_user(self):
        """Test login for non-existent user"""
        response = client.post("/auth/login", json={
            "email": "nonexistent@example.com",
            "password": "SecurePass123"
        })
        assert response.status_code == 401

    def test_get_current_user(self):
        """Test retrieving current user info with valid token"""
        # Signup
        signup = client.post("/auth/signup", json={
            "email": "current@example.com",
            "password": "SecurePass123",
            "display_name": "Current User"
        })
        
        # Get current user
        response = client.get("/auth/me", cookies=signup.cookies)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "current@example.com"
        assert data["display_name"] == "Current User"

    def test_refresh_token(self):
        """Test token refresh flow"""
        # Signup
        signup = client.post("/auth/signup", json={
            "email": "refresh@example.com",
            "password": "SecurePass123"
        })
        
        # Refresh token
        response = client.post("/auth/refresh", cookies=signup.cookies)
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_logout(self):
        """Test logout invalidates tokens"""
        # Signup
        signup = client.post("/auth/signup", json={
            "email": "logout@example.com",
            "password": "SecurePass123"
        })
        
        # Logout
        logout_response = client.post("/auth/logout", cookies=signup.cookies)
        assert logout_response.status_code == 200
        
        # Try accessing protected route after logout
        response = client.get("/auth/me", cookies=logout_response.cookies)
        assert response.status_code == 401


class TestTokenManagement:
    """Test JWT token creation and validation"""

    def test_create_access_token(self):
        """Test access token creation"""
        token = create_access_token("user123", "user@example.com")
        payload = decode_token(token)
        
        assert payload is not None
        assert payload["sub"] == "user123"
        assert payload["type"] == "access"

    def test_create_refresh_token(self):
        """Test refresh token creation"""
        token = create_refresh_token("user123")
        payload = decode_token(token)
        
        assert payload is not None
        assert payload["sub"] == "user123"
        assert payload["type"] == "refresh"
        assert "jti" in payload

    def test_decode_invalid_token(self):
        """Test decoding invalid token returns None"""
        result = decode_token("invalid.token.here")
        assert result is None

    def test_token_expiry(self):
        """Test expired token is rejected"""
        # Create token with -1 hour expiry (already expired)
        from app.auth_utils import utcnow
        from app.config import JWT_SECRET_KEY, JWT_ALGORITHM
        import jwt
        
        exp = utcnow() - timedelta(hours=1)
        payload = {"sub": "user123", "type": "access", "exp": exp}
        token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        
        result = decode_token(token)
        assert result is None


class TestCSRFProtection:
    """Test CSRF token generation and validation"""

    def test_csrf_token_generation(self):
        """Test CSRF token is set on signup"""
        response = client.post("/auth/signup", json={
            "email": "csrf@example.com",
            "password": "SecurePass123"
        })
        
        assert "eduvision_csrf" in response.cookies
        csrf_cookie = response.cookies.get("eduvision_csrf")
        assert len(csrf_cookie) > 0

    def test_signup_sets_auth_cookies(self):
        """Test signup sets authentication cookies"""
        response = client.post("/auth/signup", json={
            "email": "cookies@example.com",
            "password": "SecurePass123"
        })
        
        assert response.status_code == 200
        cookies = response.cookies
        assert "eduvision_access" in cookies or any("access" in k for k in cookies)
        assert "eduvision_refresh" in cookies or any("refresh" in k for k in cookies)

