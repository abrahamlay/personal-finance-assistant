import pytest
from cryptography.fernet import Fernet

from src.auth.encryption import decrypt_token, encrypt_token, generate_key


@pytest.fixture
def valid_key(monkeypatch):
    key = Fernet.generate_key().decode()
    for env_name, value in {
        "TELEGRAM_TOKEN": "token",
        "GOOGLE_CLIENT_ID": "id",
        "GOOGLE_CLIENT_SECRET": "secret",
        "FERNET_KEY": key,
    }.items():
        monkeypatch.setenv(env_name, value)
    monkeypatch.setattr("src.config._settings", None)
    return key


def test_round_trip_encryption(valid_key):
    plaintext = "super_secret_refresh_token"
    ciphertext = encrypt_token(plaintext)
    assert decrypt_token(ciphertext) == plaintext


def test_different_inputs_produce_different_ciphertexts(valid_key):
    c1 = encrypt_token("token_a")
    c2 = encrypt_token("token_b")
    assert c1 != c2


def test_invalid_fernet_key_raises(monkeypatch):
    for env_name, value in {
        "TELEGRAM_TOKEN": "token",
        "GOOGLE_CLIENT_ID": "id",
        "GOOGLE_CLIENT_SECRET": "secret",
        "FERNET_KEY": "invalid_key",
    }.items():
        monkeypatch.setenv(env_name, value)
    monkeypatch.setattr("src.config._settings", None)

    with pytest.raises(ValueError):
        encrypt_token("anything")


def test_generate_key_returns_valid_fernet_key():
    key = generate_key()
    # Fernet validates the key on construction
    assert Fernet(key.encode()) is not None
    assert isinstance(key, str)
