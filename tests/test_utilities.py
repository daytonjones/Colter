# tests/test_utilities.py

import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from cryptography.fernet import Fernet

# Adjust the path to import modules from the parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _utilities import derive_key, encrypt_data, decrypt_data


@pytest.fixture
def master_password():
    return "strong_master_password"


@pytest.fixture
def salt():
    return Fernet.generate_key()


def test_derive_key_success(master_password, salt):
    """
    Test successful key derivation with valid master password and salt.
    """
    key = derive_key(master_password, salt)
    assert isinstance(key, bytes)
    assert len(key) == 44  # Fernet keys are 32-byte base64-encoded (44 characters when encoded)


def test_derive_key_invalid_inputs():
    """
    Test key derivation with invalid inputs.
    """
    with pytest.raises(TypeError):
        derive_key(None, b'some_salt')
    with pytest.raises(TypeError):
        derive_key("password", None)


def test_encrypt_decrypt_data_success(master_password, salt):
    """
    Test that data encrypted and then decrypted matches the original.
    """
    key = derive_key(master_password, salt)
    fernet = Fernet(key)  # Instantiate Fernet with the derived key
    original_data = "Sensitive Information"
    encrypted = encrypt_data(original_data, fernet)
    assert isinstance(encrypted, str)
    
    decrypted = decrypt_data(encrypted, fernet)
    assert decrypted == original_data


def test_encrypt_data_with_invalid_key(master_password, salt):
    """
    Test behavior when decrypting data with an invalid key.
    """
    key = derive_key(master_password, salt)
    fernet_valid = Fernet(key)
    original_data = "Sensitive Information"
    encrypted = encrypt_data(original_data, fernet_valid)
    
    invalid_key = Fernet.generate_key()  # Different key
    fernet_invalid = Fernet(invalid_key)
    
    with pytest.raises(Exception):
        decrypt_data(encrypted, fernet_invalid)


def test_decrypt_data_with_corrupted_cipher(master_password, salt):
    """
    Test decrypting corrupted ciphertext.
    """
    key = derive_key(master_password, salt)
    fernet = Fernet(key)
    original_data = "Sensitive Information"
    encrypted = encrypt_data(original_data, fernet)
    
    # Corrupt the encrypted data
    corrupted_encrypted = encrypted[:-1] + '0'
    with pytest.raises(Exception):
        decrypt_data(corrupted_encrypted, fernet)

