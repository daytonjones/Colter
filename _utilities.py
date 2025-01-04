#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# _utilities.py

from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from rich.console import Console
from rich.logging import RichHandler
from typing import Optional
import base64
import json
import keyring
import logging

# Define Paths
CONFIG_PATH = Path.home() / ".colter_config.yaml"
LOG_FILE = Path.home() / "colter.log"
SALT_FILE = Path.home() / ".colter_salt.bin"

# Initialize the rich console
console = Console()

# Create a rotating file handler (max 5 MB per file, keep 5 backups)
file_handler = RotatingFileHandler(
    LOG_FILE, mode="a", maxBytes=5*1024*1024, backupCount=5, encoding="utf-8", delay=0
)
file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(file_formatter)
#file_handler.setLevel(logging.INFO)  # File logs INFO and above
file_handler.setLevel(logging.DEBUG)  # File logs DEBUG and above

# Create a console handler with Rich (no timestamps), only show WARNING+ 
console_handler = RichHandler(console=console, show_path=False, markup=True)
console_formatter = logging.Formatter("%(message)s")
console_handler.setFormatter(console_formatter)
console_handler.setLevel(logging.WARNING)  # Console logs WARNING and above

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.handlers.clear()
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

# Logger specifically for file (no propagation to root)
file_logger = logging.getLogger("file_logger")
file_logger.setLevel(logging.INFO)
file_logger.addHandler(file_handler)
file_logger.propagate = False  # Prevent messages from propagating to root

# Logger specifically for console (not used but kept for future extensions)
console_logger = logging.getLogger("console_logger")
console_logger.setLevel(logging.WARNING)
console_logger.addHandler(console_handler)
console_logger.propagate = False  # Prevent messages from propagating to root


def derive_key(master_password: str, salt: bytes) -> bytes:
    """Derive a key from the master password and salt."""
    if not isinstance(master_password, str):
        raise TypeError("master_password must be a string.")
    if not isinstance(salt, bytes):
        raise TypeError("salt must be bytes.")
    if not master_password:
        raise ValueError("master_password cannot be empty.")
    if not salt:
        raise ValueError("salt cannot be empty.")
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
        backend=default_backend()
    )
    return base64.urlsafe_b64encode(kdf.derive(master_password.encode()))

#def derive_key(master_password: str, salt: bytes) -> bytes:
#    """Derive a key from the master password and salt."""
#    kdf = PBKDF2HMAC(
#        algorithm=hashes.SHA256(),
#        length=32,
#        salt=salt,
#        iterations=100_000,
#        backend=default_backend()
#    )
#    return base64.urlsafe_b64encode(kdf.derive(master_password.encode()))


def encrypt_data(data: str, fernet: Fernet) -> str:
    """Encrypt data using Fernet."""
    return fernet.encrypt(data.encode()).decode()


def decrypt_data(data: str, fernet: Fernet) -> str:
    """Decrypt data using Fernet."""
    return fernet.decrypt(data.encode()).decode()


# Session Management Constants
SESSION_SERVICE_NAME = "colter_session"
SESSION_PASSWORD_USERNAME = "master_password"
SESSION_TIMESTAMP_USERNAME = "session_timestamp"
SESSION_DURATION = timedelta(minutes=30)


def create_session(master_password: str):
    """
    Create a session by storing the master password and current timestamp in the keyring.
    
    Args:
        master_password (str): The user's master password.
    """
    session_data = {
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    session_json = json.dumps(session_data)
    try:
        # Store master password
        keyring.set_password(SESSION_SERVICE_NAME, SESSION_PASSWORD_USERNAME, master_password)
        file_logger.debug("Master password set in keyring.")
    except keyring.errors.KeyringError as e:
        file_logger.error(f"Failed to set session password: {e}")
        console.print(f"[red]Failed to set session password: {e}[/red]")
        return  # Exit early since password couldn't be set
    
    try:
        # Store session timestamp
        keyring.set_password(SESSION_SERVICE_NAME, SESSION_TIMESTAMP_USERNAME, session_json)
        file_logger.debug("Session timestamp set in keyring.")
    except keyring.errors.KeyringError as e:
        file_logger.error(f"Failed to set session timestamp: {e}")
        console.print(f"[red]Failed to set session timestamp: {e}[/red]")
        # Optionally, decide whether to clear the password if timestamp fails


def check_session() -> Optional[str]:
    """
    Check if a valid session exists and retrieve the cached master password.
    
    Returns:
        Optional[str]: The cached master password if the session is valid; otherwise, None.
    """
    session_json = keyring.get_password(SESSION_SERVICE_NAME, SESSION_TIMESTAMP_USERNAME)
    if not session_json:
        file_logger.debug("No session timestamp found in keyring.")
        return None
    try:
        session_data = json.loads(session_json)
        session_time = datetime.fromisoformat(session_data["timestamp"])
        file_logger.debug(f"Retrieved session_time: {session_time}")
        # Ensure session_time is timezone-aware
        if session_time.tzinfo is None:
            file_logger.warning("Session time is naive. Assuming UTC.")
            session_time = session_time.replace(tzinfo=timezone.utc)
        current_time = datetime.now(timezone.utc)
        elapsed_time = current_time - session_time
        file_logger.debug(f"Elapsed time since session: {elapsed_time}")
        if elapsed_time < SESSION_DURATION:
            master_password = keyring.get_password(SESSION_SERVICE_NAME, SESSION_PASSWORD_USERNAME)
            if master_password:
                file_logger.debug("Valid session found.")
                return master_password
            else:
                file_logger.debug("Master password not found in keyring.")
                return None
        else:
            file_logger.debug("Session has expired.")
            clear_session()
            return None
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        file_logger.error(f"Error parsing session data: {e}")
        clear_session()
        return None



def clear_session():
    """
    Clear the cached session from the keyring.
    """
    try:
        keyring.delete_password(SESSION_SERVICE_NAME, SESSION_PASSWORD_USERNAME)
    except keyring.errors.PasswordDeleteError:
        pass  # Password was not set
    try:
        keyring.delete_password(SESSION_SERVICE_NAME, SESSION_TIMESTAMP_USERNAME)
    except keyring.errors.PasswordDeleteError:
        pass  # Timestamp was not set

