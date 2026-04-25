"""
Supabase Authentication Integration
Handles user authentication via Supabase Auth instead of local JWT
"""
from typing import Optional, Dict, Any
from supabase import create_client, Client
from fastapi import HTTPException, status
from zendaya_backend.core.config import settings

class SupabaseAuth:
    """Supabase authentication manager"""

    def __init__(self):
        self.client: Client = create_client(
            settings.supabase_url,
            settings.supabase_anon_key
        )
        print("✅ Supabase Auth client initialized")

    async def sign_up(self, email: str, password: str, user_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Register a new user with Supabase Auth

        Args:
            email: User's email address
            password: User's password
            user_metadata: Additional user data (username, full_name, etc.)

        Returns:
            User data and session information
        """
        try:
            response = self.client.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": user_metadata or {}
                }
            })

            if not response.user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User registration failed"
                )

            return {
                "user_id": response.user.id,
                "email": response.user.email,
                "access_token": response.session.access_token if response.session else None,
                "refresh_token": response.session.refresh_token if response.session else None,
            }

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Registration failed: {str(e)}"
            )

    async def sign_in(self, email: str, password: str) -> Dict[str, Any]:
        """
        Authenticate user with Supabase Auth

        Args:
            email: User's email
            password: User's password

        Returns:
            Session tokens and user information
        """
        try:
            response = self.client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })

            if not response.user or not response.session:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials"
                )

            return {
                "user_id": response.user.id,
                "email": response.user.email,
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
                "expires_at": response.session.expires_at,
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Authentication failed: {str(e)}"
            )

    async def verify_token(self, access_token: str) -> Dict[str, Any]:
        """
        Verify JWT token with Supabase

        Args:
            access_token: JWT access token from Supabase

        Returns:
            User information if token is valid
        """
        try:
            response = self.client.auth.get_user(access_token)

            if not response.user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token"
                )

            return {
                "user_id": response.user.id,
                "email": response.user.email,
                "user_metadata": response.user.user_metadata,
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token verification failed: {str(e)}"
            )

    async def sign_out(self, access_token: str) -> bool:
        """
        Sign out user (invalidate token)

        Args:
            access_token: Current user's access token

        Returns:
            True if successful
        """
        try:
            self.client.auth.sign_out()
            return True
        except Exception as e:
            print(f"Sign out error: {e}")
            return False

    async def refresh_session(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh expired access token

        Args:
            refresh_token: Refresh token from previous session

        Returns:
            New session tokens
        """
        try:
            response = self.client.auth.refresh_session(refresh_token)

            if not response.session:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Failed to refresh session"
                )

            return {
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
                "expires_at": response.session.expires_at,
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Session refresh failed: {str(e)}"
            )

    async def update_user(self, access_token: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update user metadata

        Args:
            access_token: User's access token
            user_data: Fields to update

        Returns:
            Updated user information
        """
        try:
            # Set the session for this request
            self.client.auth.set_session(access_token, "")

            response = self.client.auth.update_user({
                "data": user_data
            })

            if not response.user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User update failed"
                )

            return {
                "user_id": response.user.id,
                "email": response.user.email,
                "user_metadata": response.user.user_metadata,
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Update failed: {str(e)}"
            )


# Global instance
supabase_auth = SupabaseAuth()
