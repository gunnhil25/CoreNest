import hashlib
import hmac
import re
import secrets

SCRYPT_N = 16384
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32
SESSION_COOKIE_NAME = "corenest_session"

_USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")


def hash_password(password: str) -> str:
    """Hash a plaintext password using scrypt with a random 16-byte salt."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    )
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a plaintext password against a stored scrypt hash in constant time."""
    if not isinstance(password, str) or not isinstance(stored_hash, str):
        return False
    parts = stored_hash.split("$")
    if len(parts) != 6 or parts[0] != "scrypt":
        return False
    try:
        n = int(parts[1])
        r = int(parts[2])
        p = int(parts[3])
        salt = bytes.fromhex(parts[4])
        expected = bytes.fromhex(parts[5])
        computed = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            dklen=len(expected),
            maxmem=32 * 1024 * 1024,
        )
        return hmac.compare_digest(computed, expected)
    except (ValueError, TypeError):
        return False


def generate_session_token() -> str:
    """Generate a cryptographically secure random session token."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Hash a session token using SHA-256 for storage lookup."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def normalize_username(username: str) -> str:
    """Normalize a username by trimming whitespace and lowercasing."""
    return (username or "").strip().lower()


def validate_username(username: str) -> str:
    """Normalize and validate username format (3-32 lowercase alphanumeric/._-)."""
    clean = normalize_username(username)
    if not _USERNAME_RE.match(clean):
        raise ValueError(
            "Username must be 3-32 characters, start with a letter or number, "
            "and contain only letters, numbers, dots, underscores, or hyphens."
        )
    return clean


def validate_password(password: str) -> str:
    """Validate password length constraints."""
    if not isinstance(password, str) or len(password) < 6 or len(password) > 128:
        raise ValueError("Password must be between 6 and 128 characters long.")
    return password
