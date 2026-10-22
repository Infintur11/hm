from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User
from typing import Optional

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Extracts and verifies authenticated user from Authorization header or cookie."""
    token: Optional[str] = None
    
    # 1. Check Bearer Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        
    # 2. Fallback to cookie
    if not token:
        token = request.cookies.get("access_token")
        
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in."
        )
        
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid. Please log in again."
        )
        
    user_id = payload.get("sub") or payload.get("user_id")
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated."
        )
        
    return user

from app.core.permissions import get_role_permissions, has_permission

def require_roles(*allowed_roles):
    """Enforces Role-Based Access Control (RBAC)."""
    def role_checker(current_user: User = Depends(get_current_user)):
        user_role = (current_user.role or "").upper()
        normalized_allowed = [r.upper() for r in allowed_roles]
        if user_role in ["SUPER_ADMIN", "ADMIN"]:
            return current_user
        if user_role not in normalized_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Requires one of roles: {', '.join(allowed_roles)}"
            )
        return current_user
    return role_checker

def require_permissions(*required_permissions):
    """Enforces fine-grained permission-based access control."""
    def permission_checker(current_user: User = Depends(get_current_user)):
        user_role = (current_user.role or "").upper()
        user_perms = get_role_permissions(user_role)
        if "*" in user_perms:
            return current_user
        for req in required_permissions:
            if not has_permission(user_role, req):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: Missing required permission '{req}' for role {user_role}."
                )
        return current_user
    return permission_checker

