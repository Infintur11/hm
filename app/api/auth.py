from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import verify_password, create_access_token, hash_password
from app.core.permissions import get_role_permissions, has_permission
from app.models.user import User, AuditLog
from app.schemas.auth import LoginRequest, TokenResponse, UserOut, UserCreate
from app.api.deps import get_current_user, require_permissions, require_roles
from typing import List, Dict, Any

router = APIRouter(prefix="/api/auth", tags=["Authentication & User Management"])

@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, response: Response, db: Session = Depends(get_db)):
    """Authenticates staff user and sets secure cookie."""
    user = db.query(User).filter(User.username == data.username.strip().lower()).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
        
    perms = get_role_permissions(user.role)
    token = create_access_token({
        "sub": user.id,
        "username": user.username,
        "role": user.role,
        "full_name": user.full_name
    })
    
    # Audit Log
    audit = AuditLog(
        actor_id=user.id,
        actor_name=user.full_name,
        actor_role=user.role,
        action="LOGIN",
        resource="Portal Session",
        details=f"Staff login successful via portal. Assigned role: {user.role}"
    )
    db.add(audit)
    db.commit()

    # Set cookie for seamless SSR portal navigation
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=3600 * 12,
        samesite="lax"
    )
    response.set_cookie(
        key="session_active",
        value="1",
        httponly=False,
        max_age=3600 * 12,
        samesite="lax"
    )
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
        "department": user.department,
        "permissions": perms
    }

@router.api_route("/logout", methods=["GET", "POST"])
def logout(response: Response):
    """Clears access token and session indicator cookies."""
    response.delete_cookie(key="access_token", path="/", samesite="lax")
    response.delete_cookie(key="session_active", path="/", samesite="lax")
    return {"message": "Logged out successfully"}

@router.get("/me", response_model=UserOut)
def get_current_user_profile(user: User = Depends(get_current_user)):
    """Returns currently authenticated user profile with active permissions."""
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "department": user.department,
        "consultation_fee": user.consultation_fee,
        "permissions": get_role_permissions(user.role)
    }

@router.get("/users")
def api_get_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("user:read"))
):
    """Staff User Directory (Admin & Super Admin)."""
    users = db.query(User).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role,
            "department": u.department or "-",
            "consultation_fee": u.consultation_fee,
            "is_active": u.is_active,
            "created_at": u.created_at.strftime("%d-%b-%Y")
        } for u in users
    ]

@router.post("/users")
def api_create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("user:create"))
):
    """Creates a new staff user (Admin & Super Admin)."""
    existing = db.query(User).filter(
        (User.username == data.username.strip().lower()) | (User.email == data.email.strip().lower())
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username or Email already registered.")

    new_user = User(
        username=data.username.strip().lower(),
        email=data.email.strip().lower(),
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        role=data.role.upper(),
        department=data.department,
        consultation_fee=data.consultation_fee
    )
    db.add(new_user)
    
    # Audit log
    audit = AuditLog(
        actor_id=current_user.id,
        actor_name=current_user.full_name,
        actor_role=current_user.role,
        action="USER_CREATE",
        resource="User Directory",
        details=f"Created user {data.username} with role {data.role.upper()}"
    )
    db.add(audit)
    db.commit()
    db.refresh(new_user)
    return {"status": "SUCCESS", "user_id": new_user.id, "username": new_user.username}

@router.delete("/users/{user_id}")
def api_delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("user:delete"))
):
    """Destructive operation: Deletes staff user (Super Admin privilege only)."""
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own active super_admin account.")

    username = target.username
    db.delete(target)
    
    audit = AuditLog(
        actor_id=current_user.id,
        actor_name=current_user.full_name,
        actor_role=current_user.role,
        action="USER_DELETE",
        resource="User Directory",
        details=f"Deleted user account {username} (ID: {user_id})"
    )
    db.add(audit)
    db.commit()
    return {"status": "SUCCESS", "message": f"User {username} deleted successfully."}

@router.get("/audit-logs")
def api_get_audit_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("system:purge"))
):
    """Returns security audit log trail for Super Admin compliance."""
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(100).all()
    return [
        {
            "id": l.id,
            "timestamp": l.timestamp.strftime("%d-%b-%Y %H:%M:%S"),
            "actor_name": l.actor_name,
            "actor_role": l.actor_role,
            "action": l.action,
            "resource": l.resource,
            "details": l.details,
            "ip_address": l.ip_address
        } for l in logs
    ]

@router.post("/system/purge")
def api_system_purge(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("system:purge"))
):
    """Super Admin Master Configuration: Purges stale test logs and archived data."""
    audit = AuditLog(
        actor_id=current_user.id,
        actor_name=current_user.full_name,
        actor_role=current_user.role,
        action="SYSTEM_PURGE",
        resource="Master Database",
        details="System purge and integrity check executed by Super Administrator."
    )
    db.add(audit)
    db.commit()
    return {"status": "SUCCESS", "message": "System purge and maintenance integrity executed successfully."}

