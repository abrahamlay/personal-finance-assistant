from cryptography.fernet import Fernet

from src.config import get_settings


def _get_fernet() -> Fernet:
    return Fernet(get_settings().fernet_key.encode())


def encrypt_token(plaintext: str) -> str:
    """Encrypt OAuth refresh token for storage."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    """Decrypt OAuth refresh token from storage."""
    return _get_fernet().decrypt(ciphertext.encode()).decode()


def generate_key() -> str:
    """Generate a new Fernet key. Call once and save to the FERNET_KEY env var."""
    return Fernet.generate_key().decode()
