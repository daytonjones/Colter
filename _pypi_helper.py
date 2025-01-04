#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# _pypi_helper.py

"""
PyPI Helper Module for Colter.

This module provides the `PyPITracker` class, which facilitates interaction with
the PyPI API to fetch package statistics and versions. It processes download
metrics across different categories such as Python major/minor versions and systems,
and presents the data in a structured format using Rich tables.
"""

from cachetools import cached, TTLCache
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from simply_useful import format_number  # Importing format_number
from typing import Dict, Any, List, Optional
import json
import logging
import pypistats
import requests


class PyPITracker:
    """
    A class responsible for tracking PyPI packages and retrieving their statistics.

    The `PyPITracker` interacts with the PyPI API to fetch the latest version of
    packages and detailed download statistics. It processes and formats this data
    for display and export purposes.

    Attributes:
        packages (List[str]): A list of PyPI package names to track.
        cache (TTLCache): Cache for storing API responses to reduce redundant requests.
        logger (logging.Logger): Logger instance for logging events and errors.
        console (Console): Rich console instance for user-friendly output.
    """

    def __init__(self, config: Dict[str, Any], logger: logging.Logger, console: Console):
        """
        Initialize the PyPITracker with configuration, logger, and console.

        Sets up the list of packages to track and initializes a cache for API responses.

        Args:
            config (Dict[str, Any]): Configuration dictionary containing PyPI settings.
            logger (logging.Logger): Logger instance for logging events and errors.
            console (Console): Rich console instance for user-friendly output.
        """
        self.packages = config["pypi"]["packages"]
        self.cache = TTLCache(maxsize=100, ttl=300)  # Cache for 5 minutes
        self.logger = logger
        self.console = console

    @cached(cache=TTLCache(maxsize=100, ttl=300))
    def fetch_package_version(self, package: str) -> Optional[str]:
        """
        Fetch the latest version of a PyPI package.

        Sends a GET request to the PyPI API to retrieve the latest version information
        for the specified package.

        Args:
            package (str): The name of the PyPI package.

        Returns:
            Optional[str]: The latest version of the package if successful, otherwise None.

        Raises:
            None: Exceptions are caught and logged internally.
        """
        url = f"https://pypi.org/pypi/{package}/json"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                return data["info"]["version"]
            else:
                error = response.text
                self.logger.error(f"PyPI API Error {response.status_code}: {error}")
                return None
        except Exception as e:
            self.logger.error(f"Exception fetching PyPI package {package}: {e}")
            return None

    def fetch_pypi_stats(self, package: str) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed PyPI statistics using pypistats.

        Utilizes the `pypistats` library to retrieve various download metrics for the specified package,
        including recent, overall, Python major/minor version, and system downloads.

        Args:
            package (str): The name of the PyPI package.

        Returns:
            Optional[Dict[str, Any]]: A dictionary containing detailed statistics if successful,
            otherwise None.

        Raises:
            None: Exceptions are caught and logged internally.
        """
        try:
            recent = pypistats.recent(package, format="json")
            overall = pypistats.overall(package, format="json")
            python_major = pypistats.python_major(package, format="json")
            python_minor = pypistats.python_minor(package, format="json")
            system = pypistats.system(package, format="json")

            # Parse JSON strings into dictionaries
            recent_dict = json.loads(recent)
            overall_dict = json.loads(overall)
            python_major_dict = json.loads(python_major)
            python_minor_dict = json.loads(python_minor)
            system_dict = json.loads(system)

            stats = {
                "recent": recent_dict,
                "overall": overall_dict,
                "python_major": python_major_dict,
                "python_minor": python_minor_dict,
                "system": system_dict
            }

            self.logger.info(f"Fetched pypistats for package: {package}")
            return stats
        except json.JSONDecodeError as je:
            self.logger.error(f"JSON decoding failed for {package}: {je}")
            return None
        except Exception as e:
            self.logger.error(f"Failed to fetch pypistats for {package}: {e}")
            return None

    def check_packages(self, dry_run: bool = False) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Check PyPI packages and display their statistics.

        Iterates through the list of configured PyPI packages, fetches their latest versions
        and download statistics, and presents the data in a formatted Rich table. Optionally,
        it can perform a dry run where actions are simulated without actual exports or notifications.

        Args:
            dry_run (bool, optional): If True, simulates actions without performing exports or sending emails.
                Defaults to False.

        Returns:
            Dict[str, Optional[Dict[str, Any]]]: A dictionary mapping package names to their respective statistics.
        """
        results = {}
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
            task = progress.add_task("[green]Checking PyPI packages...", total=len(self.packages))
            for pkg in self.packages:
                pkg_clean = pkg.strip()
                if not pkg_clean:
                    progress.advance(task)
                    continue
                self.logger.info(f"Checking PyPI package: {pkg_clean}")
                version = self.fetch_package_version(pkg_clean)
                if version is None:
                    version = "Error"
                stats = self.fetch_pypi_stats(pkg_clean)
                results[pkg_clean] = {
                    "version": version,
                    "stats": stats  # stats is now a dict or None
                }
                progress.advance(task)

        # Consolidate data for all packages
        consolidated_data = []
        for package, data in results.items():
            version = data["version"] if data["version"] else "Error"
            stats = data["stats"]
            if stats:
                # Recent Downloads
                recent_day = format_number(stats.get("recent", {}).get("data", {}).get("last_day", 0))
                # recent_week = format_number(stats.get("recent", {}).get("data", {}).get("last_week", 0))  # Removed

                # Overall Downloads
                overall_downloads = format_number(
                    sum(item.get("downloads", 0) for item in stats.get("overall", {}).get("data", []))
                )

                # Python Major Downloads
                python_major = stats.get("python_major", {}).get("data", [])
                # Remove "Python " prefix and sort by downloads descending
                python_major_sorted = sorted(
                    python_major,
                    key=lambda x: x.get("downloads", 0),
                    reverse=True
                )
                python_major_downloads = "\n".join([
                    f"{item.get('category', 'N/A')}: {format_number(item.get('downloads', 0))}"
                    for item in python_major_sorted
                ])

                # Python Minor Downloads
                python_minor = stats.get("python_minor", {}).get("data", [])
                # Optionally sort Python Minor Downloads if needed
                python_minor_sorted = sorted(
                    python_minor,
                    key=lambda x: x.get("downloads", 0),
                    reverse=True
                )
                python_minor_downloads = "\n".join([
                    f"{item.get('category', 'N/A')}: {format_number(item.get('downloads', 0))}"
                    for item in python_minor_sorted
                ])

                # System Downloads
                system = stats.get("system", {}).get("data", [])
                # Remove "Python " prefix and sort by downloads descending
                system_sorted = sorted(
                    system,
                    key=lambda x: x.get("downloads", 0),
                    reverse=True
                )
                system_downloads = "\n".join([
                    f"{item.get('category', 'N/A')}: {format_number(item.get('downloads', 0))}"
                    for item in system_sorted
                ])

                consolidated_data.append({
                    "Package": package,
                    "Version": version,
                    # "Recent Downloads (Day)": recent_day,  # Removed from display
                    # "Recent Downloads (Week)": recent_week,  # Removed from display
                    "Recent Downloads (Month)": format_number(
                        stats.get("recent", {}).get("data", {}).get("last_month", 0)
                    ),
                    "Overall Downloads": overall_downloads,
                    "Python Major Downloads": python_major_downloads,
                    "Python Minor Downloads": python_minor_downloads,
                    "System Downloads": system_downloads
                })
            else:
                consolidated_data.append({
                    "Package": package,
                    "Version": version,
                    # "Recent Downloads (Day)": "N/A",  # Removed from display
                    # "Recent Downloads (Week)": "N/A",  # Removed from display
                    "Recent Downloads (Month)": "N/A",
                    "Overall Downloads": "N/A",
                    "Python Major Downloads": "N/A",
                    "Python Minor Downloads": "N/A",
                    "System Downloads": "N/A"
                })

        # Create a single consolidated table
        table = Table(title="PyPI Packages Statistics", show_lines=True)

        # Define columns with overflow where necessary
        table.add_column("Package", style="cyan", no_wrap=True)
        table.add_column("Version", style="magenta")
        # Removed "Recent Downloads (Day)" and "Recent Downloads (Week)"
        table.add_column("Recent Downloads (Month)", style="green")
        table.add_column("Overall Downloads", style="blue")
        table.add_column("Python Major Downloads", style="yellow", overflow="fold")
        table.add_column("Python Minor Downloads", style="yellow", overflow="fold")
        table.add_column("System Downloads", style="red", overflow="fold")

        # Populate the table
        for data in consolidated_data:
            table.add_row(
                data["Package"],
                data["Version"],
                data["Recent Downloads (Month)"],
                data["Overall Downloads"],
                data["Python Major Downloads"],
                data["Python Minor Downloads"],
                data["System Downloads"]
            )

        # Display the table
        self.console.print(table)

        return results

