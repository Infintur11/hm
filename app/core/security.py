import hashlib
import hmac
import base64
import json
import time
from typing import Optional, Dict, Any
from app.core.config import settings

def hash_password(password: str) -> str:
    """Generates a secure PBKDF2-HMAC-SHA256 salted password hash."""
    salt = settings.SECRET_KEY[:16].encode("utf-8")
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return base64.b64encode(key).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against the stored hash."""
    return hash_password(plain_password) == hashed_password

def create_access_token(data: Dict[str, Any], expires_delta: Optional[int] = None) -> str:
    """Generates a tamper-proof HMAC-SHA256 signed bearer token."""
    to_encode = data.copy()
    expire = int(time.time()) + (expires_delta or settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    to_encode.update({"exp": expire})
    
    payload_str = json.dumps(to_encode, separators=(",", ":"))
    payload_b64 = base64.urlsafe_b64encode(payload_str.encode("utf-8")).decode("utf-8").rstrip("=")
    
    signature = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    
    return f"{payload_b64}.{signature}"

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodes and cryptographically verifies token integrity and expiration."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, signature = parts
        
        # Verify signature
        expected_sig = hmac.new(
            settings.SECRET_KEY.encode("utf-8"),
            payload_b64.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_sig):
            return None
            
        # Add padding back if necessary
        padded_b64 = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload_json = base64.urlsafe_b64decode(padded_b64.encode("utf-8")).decode("utf-8")
        payload = json.loads(payload_json)
        
        # Verify expiration
        if payload.get("exp", 0) < int(time.time()):
            return None
            
        return payload
    except Exception:
        return None
