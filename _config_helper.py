#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# _config_helper.py

"""
Configuration Helper Module for Colter.

This module provides functionalities to load, generate, and manage the configuration
file for the Colter application. It ensures that sensitive information is securely
handled through encryption and decryption mechanisms.
"""

from typing import Dict, Any, Optional
import yaml
import os
from simply_useful import timeit
from rich.prompt import Prompt
from cryptography.fernet import Fernet
from _utilities import (
    CONFIG_PATH,
    SALT_FILE,
    derive_key,
    encrypt_data,
    decrypt_data,
    file_logger,
    console
)
from pathlib import Path


class ConfigError(Exception):
    """Exception raised for configuration-related errors."""
    pass


class ConfigLoader:
    """
    A class responsible for loading and generating the configuration file.

    Attributes:
        key (bytes): Encryption key derived from the master password.
    """

    def __init__(self):
        """
        Initialize the ConfigLoader with no encryption key.
        """
        self.key = None  # Encryption key derived from master password

    @staticmethod
    @timeit
    def load_config(master_password: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Load the configuration file from the user's home directory.

        If the configuration file does not exist, it initiates the configuration
        generation process.

        Args:
            master_password (Optional[str]): The master password for decrypting
                sensitive configuration fields. If None and the config does not exist,
                the user will be prompted.

        Returns:
            Optional[Dict[str, Any]]: The loaded configuration as a dictionary if successful,
            otherwise None.

        Raises:
            ConfigError: If the salt file is missing.
        """
        if not CONFIG_PATH.exists():
            # Automatically initiate config generation
            console.print(f"[yellow]Configuration file not found at: {CONFIG_PATH}.[/]")
            console.print("[yellow]Starting configuration setup...[/yellow]")
            ConfigLoader.generate_default_config(master_password)
            # After generation, proceed to load the config
            if CONFIG_PATH.exists():
                try:
                    return ConfigLoader._load(master_password)
                except ConfigError as ce:
                    file_logger.error(f"Configuration Error: {ce}")
                    console.print(f"[red]Configuration Error:[/] {ce}")
                    return None
                except Exception as e:
                    file_logger.error(f"Failed to load configuration file: {e}")
                    console.print(f"[red]Error:[/] Failed to load configuration file: {e}")
                    return None
            else:
                console.print("[red]Failed to create configuration file. Aborting.[/red]")
                return None
        else:
            # Check if salt file exists
            if not SALT_FILE.exists():
                console.print("[red]Salt file missing. Cannot derive encryption key.[/red]")
                raise ConfigError("Salt file missing. Cannot derive encryption key.")
            try:
                return ConfigLoader._load(master_password)
            except ConfigError as ce:
                file_logger.error(f"Configuration Error: {ce}")
                console.print(f"[red]Configuration Error:[/] {ce}")
                return None
            except Exception as e:
                file_logger.error(f"Failed to load configuration file: {e}")
                console.print(f"[red]Error:[/] Failed to load configuration file: {e}")
                return None

    @staticmethod
    @timeit
    def _load(master_password: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Helper function to load existing configuration from disk.

        This function decrypts sensitive fields using the provided master password.

        Args:
            master_password (Optional[str]): The master password for decrypting
                sensitive configuration fields.

        Returns:
            Optional[Dict[str, Any]]: The decrypted configuration as a dictionary if successful,
            otherwise None.

        Raises:
            ConfigError: If the master password is not provided.
            yaml.YAMLError: If there's an error parsing the YAML configuration.
            cryptography.fernet.InvalidToken: If decryption fails due to an invalid key or corrupted data.
            Exception: For any other unforeseen errors.
        """
        file_logger.info(f"Loading configuration from: {CONFIG_PATH}")
        with CONFIG_PATH.open("r") as f:
            config = yaml.safe_load(f)

        with SALT_FILE.open("rb") as sf:
            salt = sf.read()

        # Check if master_password is provided
        if not master_password:
            raise ConfigError("Master password not provided.")

        # Derive key
        key = derive_key(master_password, salt)
        fernet = Fernet(key)

        # Decrypt sensitive fields
        encrypted_fields = {
            "github": ["token"],
            "smtp": ["password"],
            "influxdb": ["token"],
            "prometheus": []  # Assuming no sensitive fields here
        }

        for section, fields in encrypted_fields.items():
            if section in config:
                for field in fields:
                    if field in config[section]:
                        encrypted_data = config[section][field]
                        decrypted_data = decrypt_data(encrypted_data, fernet)
                        config[section][field] = decrypted_data

        return config

    @staticmethod
    @timeit
    def generate_default_config(master_password: Optional[str]):
        """
        Prompt the user to create or update the configuration file.

        This function guides the user through the process of setting up the
        configuration by adding missing sections and encrypting sensitive fields.

        Args:
            master_password (Optional[str]): The master password for encrypting
                sensitive configuration fields.

        Notes:
            - If the salt file does not exist, it is generated and stored securely.
            - Existing configuration sections are loaded and updated as needed.
            - Sensitive fields like API tokens and SMTP passwords are encrypted.
        """
        if not master_password:
            raise ValueError("Master password cannot be empty.")

        console.print("[yellow]Generating/updating configuration file...[/]")
        # Ensure master_password is provided

        # Load salt if it exists, else generate a new one
        if not SALT_FILE.exists():
            salt = os.urandom(16)
            try:
                with SALT_FILE.open("wb") as sf:
                    sf.write(salt)
                SALT_FILE.chmod(0o600)  # Restrict permissions
                file_logger.info("Salt file created.")
            except Exception as e:
                file_logger.error(f"Failed to write salt file: {e}")
                console.print(f"[red]Error:[/] Failed to write salt file: {e}")
                return
        else:
            # Load existing salt
            try:
                with SALT_FILE.open("rb") as sf:
                    salt = sf.read()
                file_logger.info("Salt file loaded.")
            except Exception as e:
                file_logger.error(f"Failed to read salt file: {e}")
                console.print(f"[red]Error:[/] Failed to read salt file: {e}")
                return

        # Derive key
        try:
            key = derive_key(master_password, salt)
            fernet = Fernet(key)
            file_logger.info("Encryption key derived successfully.")
        except Exception as e:
            file_logger.error(f"Failed to derive encryption key: {e}")
            console.print(f"[red]Error:[/] Failed to derive encryption key: {e}")
            return

        # Load existing config if it exists
        if CONFIG_PATH.exists():
            try:
                with CONFIG_PATH.open("r") as f:
                    existing_config = yaml.safe_load(f) or {}
                file_logger.info("Existing configuration loaded for updating.")
            except Exception as e:
                file_logger.error(f"Failed to read existing configuration: {e}")
                console.print(f"[red]Error:[/] Failed to read existing configuration: {e}")
                return
        else:
            existing_config = {}
            file_logger.info("No existing configuration found. Creating new configuration.")

        # Determine which sections are missing
        sections = ["github", "pypi", "influxdb", "prometheus"]
        missing_sections = [section for section in sections if section not in existing_config]

        if not missing_sections:
            console.print("[green]All configuration sections are already present. No updates needed.[/green]")
            return

        # Prompt the user to add missing sections
        include_sections = []
        console.print("[cyan]The following configuration sections are missing and can be added:[/cyan]")
        for section in missing_sections:
            include = Prompt.ask(f"Do you want to configure {section}?", choices=["yes", "no"], default="yes") == "yes"
            if include:
                include_sections.append(section)

        if not include_sections:
            console.print("[yellow]No new configuration sections selected. Exiting configuration setup.[/yellow]")
            return

        # Add configurations for the selected sections
        for section in include_sections:
            if section == "github":
                github_token = Prompt.ask("Enter your GitHub Personal Access Token", password=True)
                encrypted_github_token = encrypt_data(github_token, fernet)
                existing_config["github"] = {"token": encrypted_github_token}

            elif section == "pypi":
                packages_input = Prompt.ask(
                    "Enter the PyPI packages to track (comma-separated)", default=""
                )
                packages = [pkg.strip() for pkg in packages_input.split(",") if pkg.strip()]
                existing_config["pypi"] = {"packages": packages}

            elif section == "influxdb":
                influx_url = Prompt.ask("Enter the InfluxDB URL (e.g., http://localhost:8086)")
                influx_org = Prompt.ask("Enter the InfluxDB organization name")
                influx_bucket = Prompt.ask("Enter the InfluxDB bucket name")
                influx_token = Prompt.ask("Enter your InfluxDB token", password=True)
                encrypted_influx_token = encrypt_data(influx_token, fernet)
                existing_config["influxdb"] = {
                    "url": influx_url,
                    "org": influx_org,
                    "bucket": influx_bucket,
                    "token": encrypted_influx_token
                }

            elif section == "prometheus":
                prometheus_gateway = Prompt.ask("Enter the Prometheus Pushgateway URL (e.g., http://localhost:9091)")
                prometheus_job = Prompt.ask("Enter the Prometheus job name")
                existing_config["prometheus"] = {
                    "gateway": prometheus_gateway,
                    "job": prometheus_job
                }

        # SMTP Configuration (if GitHub is configured and SMTP is missing)
        if ("github" in include_sections or "github" in existing_config) and "smtp" not in existing_config:
            configure_smtp = Prompt.ask(
                "Do you want to configure SMTP settings for email alerts?",
                choices=["yes", "no"],
                default="yes"
            ) == "yes"
            if configure_smtp:
                smtp_server = Prompt.ask("Enter your SMTP server (e.g., smtp.gmail.com)")
                smtp_port = Prompt.ask("Enter your SMTP port", default="587")
                smtp_username = Prompt.ask("Enter your SMTP username (full email address, e.g., your_email@some.domain)")
                smtp_password = Prompt.ask("Enter your SMTP password", password=True)
                encrypted_smtp_password = encrypt_data(smtp_password, fernet)
                smtp_sender = Prompt.ask("Enter the sender email address")
                smtp_recipient = Prompt.ask("Enter the recipient email address")
                existing_config["smtp"] = {
                    "smtp_server": smtp_server,
                    "smtp_port": smtp_port,
                    "username": smtp_username,
                    "password": encrypted_smtp_password,
                    "sender": smtp_sender,
                    "recipient": smtp_recipient
                }

        # Write the updated config back to file
        try:
            with CONFIG_PATH.open("w") as f:
                # Use default_flow_style=False for better readability
                yaml.safe_dump(existing_config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
            # Set file permissions to 0600 (read and write for owner only)
            CONFIG_PATH.chmod(0o600)
            console.print(f"[green]Configuration updated successfully at: {CONFIG_PATH}[/]")
            file_logger.info(f"Configuration updated: {CONFIG_PATH}")
        except Exception as e:
            file_logger.error(f"Failed to write configuration file: {e}")
            console.print(f"[red]Error:[/] Failed to write configuration file: {e}")


def print_custom_help():
    """
    Print a custom, colorful help message using Rich.

    This function displays detailed usage instructions, options, and examples
    for the Colter script in a visually appealing format.
    """
    help_text = """
[colter.py] - GitHub and PyPI Tracker with InfluxDB and Prometheus Integration

[bold yellow]Usage:[/bold yellow]
    python colter.py [options]

[bold yellow]Options:[/bold yellow]
    [bold cyan]-g, --generate-config[/bold cyan]
        Generate or update the configuration file.
        If the configuration file is missing, it will be created.
        Existing configurations will be retained, and only missing sections will be prompted for.

    [bold cyan]-t, --type[/bold cyan] [italic](github | pypi | all)[/italic] [bold yellow]default: all[/bold yellow]
        Specify the tracking type.
        - [bold cyan]github[/bold cyan]: Track GitHub repositories.
        - [bold cyan]pypi[/bold cyan]: Track PyPI packages.
        - [bold cyan]all[/bold cyan]: Track both GitHub repositories and PyPI packages.

    [bold cyan]-o, --output[/bold cyan] [italic](influx | prometheus)[/italic]
        Specify the output format(s) for metrics.
        You can specify multiple outputs separated by spaces.
        - [bold cyan]influx[/bold cyan]: Export metrics to InfluxDB.
        - [bold cyan]prometheus[/bold cyan]: Export metrics to Prometheus.

    [bold cyan]--test-email[/bold cyan]
        Inject a fake issue to test email alerts.

    [bold cyan]-v, --verbose[/bold cyan]
        Increase output verbosity. Enables DEBUG level logging.

    [bold cyan]--dry-run[/bold cyan]
        Simulate actions without performing exports or sending emails.

    [bold cyan]--schedule[/bold cyan] [italic]minutes[/italic]
        Run the script in daemon mode, executing every X minutes.

    [bold cyan]-h, --help[/bold cyan]
        Display this help message.

[bold cyan]--logout[/bold cyan]
    Clear the cached session and logout.

[bold yellow]Configuration Encryption:[/bold yellow]
    The configuration file (~/.colter_config.yaml) stores sensitive information such as API tokens and SMTP passwords.
    These fields are encrypted using a master password to ensure security.
    **Important:** Remember your master password, as it is required to decrypt the configuration.
    If you forget the master password, you will need to regenerate the configuration file, which may require re-entering all credentials.

[bold yellow]Setting Up InfluxDB:[/bold yellow]
    1. [bold cyan]Create an InfluxDB Account:[/bold cyan]
        - Sign up at [underline]https://influxdata.com/[/underline] if you don't have an account.
    2. [bold cyan]Create an Organization:[/bold cyan]
        - Navigate to the InfluxDB UI and create an organization.
    3. [bold cyan]Create a Bucket:[/bold cyan]
        - Create a bucket where your metrics will be stored.
    4. [bold cyan]Generate an API Token:[/bold cyan]
        - Go to the API Tokens section and generate a token with write permissions for your bucket.

[bold yellow]Setting Up Prometheus:[/bold yellow]
    1. [bold cyan]Install Prometheus Pushgateway:[/bold cyan]
        - Download and run the Pushgateway from [underline]https://prometheus.io/docs/practices/pushing/#the-pushgateway[/underline].
    2. [bold cyan]Configure Job Name:[/bold cyan]
        - Decide on a job name (e.g., "ColterTracker") to identify metrics pushed by this script.
    3. [bold cyan]Ensure Network Accessibility:[/bold cyan]
        - Make sure the Pushgateway is accessible from the machine running this script.

[bold yellow]Examples:[/bold yellow]
    - [italic]Track all and export to InfluxDB and Prometheus:[/italic]
        python colter.py --type all --output influx prometheus

    - [italic]Generate or update the configuration file:[/italic]
        python colter.py --generate-config

    - [italic]Run in daemon mode every 60 minutes with verbose logging:[/italic]
        python colter.py --schedule 60 --verbose

    - [italic]Check PyPI packages without exporting data:[/italic]
        python colter.py --type pypi

[bold yellow]Notes:[/bold yellow]
    - Ensure that your InfluxDB and Prometheus configurations are correctly set up in the configuration file.
    - The master password is crucial for decrypting your configuration. Keep it secure and memorable.
    - For further assistance, refer to the documentation or contact support.
    """
    console.print(help_text)

