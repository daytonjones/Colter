#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Colter: A GitHub and PyPI Tracker with Export Capabilities.

Named after John Colter, a tracker for the Lewis and Clark Expedition, this script
monitors GitHub repositories and PyPI packages, fetching various metrics and exporting
them to InfluxDB and Prometheus. It supports daemon mode for scheduled executions and
provides comprehensive logging and error handling.
"""

from _config_helper import ConfigLoader, print_custom_help
from _export_helper import DataExporter
from _github_helper import GitHubTracker
from _pypi_helper import PyPITracker
from _utilities import (
    file_logger,
    console,
    create_session,
    check_session,
    clear_session
)
from datetime import datetime, timedelta, timezone
from rich.console import Console
from rich.prompt import Prompt
from simply_useful import clear_term, timeit
import argparse
import json
import keyring
import logging
import schedule
import sys
import time
from pathlib import Path

# Constants for session management
SESSION_SERVICE_NAME = "colter_session"
SESSION_PASSWORD_USERNAME = "session_password"
SESSION_TIMESTAMP_USERNAME = "session_timestamp"
SESSION_DURATION = timedelta(minutes=30)

# Define the configuration file path
CONFIG_PATH = Path.home() / ".colter_config.yaml"


@timeit
def main():
    """
    The main entry point for the Colter script.

    Handles argument parsing, session management, configuration loading,
    initialization of trackers and exporters, and execution of tasks
    either in normal or daemon mode based on user inputs.

    Exits gracefully upon user interruption or critical errors.
    """
    # Argument Parsing
    parser = argparse.ArgumentParser(
        description="Colter: A GitHub and PyPI Tracker with Export Capabilities",
        add_help=False  # Disable default help to implement custom help
    )
    # Define known arguments
    parser.add_argument(
        "-g",
        "--generate-config",
        action="store_true",
        help="Generate or update the configuration file."
    )
    parser.add_argument(
        "-t",
        "--type",
        choices=["github", "pypi", "all"],
        default="all",
        help="Specify the tracking type."
    )
    parser.add_argument(
        "-o",
        "--output",
        nargs='*',
        choices=["influx", "prometheus"],
        default=[],
        help="Specify the output format(s) for metrics."
    )
    parser.add_argument(
        "--test-email",
        action="store_true",
        help="Inject fake issue to test email alerts."
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Increase output verbosity."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate actions without performing exports or sending emails."
    )
    parser.add_argument(
        "--schedule",
        type=int,
        help="Run the script in daemon mode, executing every X minutes."
    )
    parser.add_argument(
        "-h",
        "--help",
        action="store_true",
        help="Show this help message and exit."
    )
    parser.add_argument(
        "--logout",
        action="store_true",
        help="Clear the cached session and logout."
    )
    
    args, unknown = parser.parse_known_args()

    # Handle logout
    if args.logout:
        clear_session()
        console.print("[green]Session cleared. You will be prompted for the master password next time.[/green]")
        file_logger.info("User logged out and session cleared.")
        sys.exit(0)

    # Display custom help if requested
    if args.help:
        print_custom_help()
        sys.exit(0)

    # Handle verbosity
    if args.verbose:
        file_logger.setLevel(logging.DEBUG)
        file_logger.debug("Verbose mode enabled.")

    file_logger.info(
        f"Colter started with options: type={args.type}, output={args.output}, "
        f"test_email={args.test_email}, dry_run={args.dry_run}, schedule={args.schedule}"
    )

    # Check for a valid cached session
    master_password = check_session()
    if master_password:
        file_logger.info("Using cached authentication session.")
        # Retrieve session timestamp from keyring
        session_json = keyring.get_password(SESSION_SERVICE_NAME, SESSION_TIMESTAMP_USERNAME)
        if session_json:
            try:
                session_data = json.loads(session_json)
                session_time = datetime.fromisoformat(session_data["timestamp"])
                
                # Ensure session_time is timezone-aware
                if session_time.tzinfo is None:
                    session_time = session_time.replace(tzinfo=timezone.utc)
                
                current_time = datetime.now(timezone.utc)
                elapsed_time = current_time - session_time
                remaining_time = SESSION_DURATION - elapsed_time
                remaining_minutes = int(remaining_time.total_seconds() / 60)
                # Ensure remaining_minutes is non-negative
                remaining_minutes = max(remaining_minutes, 0)
                console.print(
                    f"[green]Authenticated using cached session. (Valid for another {remaining_minutes} minutes)[/green]"
                )
                file_logger.debug(f"Session valid for another {remaining_minutes} minutes.")
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                console.print("[red]Error parsing session data. Prompting for master password.[/red]")
                file_logger.error(f"Error parsing session data: {e}")
                clear_session()
                master_password = Prompt.ask("Enter your master password", password=True)
                # Proceed to load configuration below
        else:
            # Handle missing session data
            console.print("[red]Session data not found. Prompting for master password.[/red]")
            file_logger.error("Session timestamp not found in keyring.")
            master_password = Prompt.ask("Enter your master password", password=True)
            # Proceed to load configuration below

        # If master_password was reset due to errors, proceed to load config
        if master_password:
            if args.generate_config:
                console.print(
                    "[red]Cannot generate config without a valid master password. Please logout and try again.[/red]"
                )
                file_logger.error("Attempted to generate config using invalid cached session.")
                sys.exit(1)
            else:
                config = ConfigLoader.load_config(master_password)
                if not config:
                    console.print("[red]Failed to load configuration using cached session. Aborting.[/red]")
                    file_logger.error("Failed to load configuration using cached session.")
                    clear_session()
                    sys.exit(1)
                file_logger.info("Configuration loaded successfully using cached session.")
    else:
        # Prompt for master password
        master_password = Prompt.ask("Enter your master password", password=True)
        # Attempt to load configuration with the entered password
        if args.generate_config:
            ConfigLoader.generate_default_config(master_password)
            config = ConfigLoader.load_config(master_password)
            if not config:
                console.print("[red]Could not create/update config; aborting.[/red]")
                file_logger.error("Failed to create/update configuration.")
                sys.exit(1)
            file_logger.info("Configuration generated successfully.")
        else:
            config = ConfigLoader.load_config(master_password)
            if not config:
                console.print("[red]Failed to load configuration. Aborting.[/red]")
                file_logger.error("Failed to load configuration.")
                sys.exit(1)
            file_logger.info("Configuration loaded successfully.")
        # Create a new session since authentication was successful
        create_session(master_password)

    # Initialize Trackers based on configuration
    github_tracker = GitHubTracker(config=config, logger=file_logger, console=console) if "github" in config else None
    pypi_tracker = PyPITracker(config=config, logger=file_logger, console=console) if "pypi" in config else None

    # Check for missing output configurations
    missing_outputs = []
    if args.output:
        for output in args.output:
            if output == "influx" and not config.get("influxdb"):
                missing_outputs.append("influxdb")
            if output == "prometheus" and not config.get("prometheus"):
                missing_outputs.append("prometheus")

    # Handle missing configurations
    if missing_outputs:
        console.print(f"[red]Warning:[/] The following configurations are missing: {', '.join(missing_outputs)}.")
        add_now = Prompt.ask("Add missing configurations now?", choices=["yes", "no"], default="no") == "yes"
        if add_now:
            ConfigLoader.generate_default_config(master_password)
            config = ConfigLoader.load_config(master_password)
            # Re-initialize trackers based on new config
            github_tracker = GitHubTracker(config=config, logger=file_logger, console=console) if "github" in config else None
            pypi_tracker = PyPITracker(config=config, logger=file_logger, console=console) if "pypi" in config else None
            # Re-initialize exporters after regenerating config
            if args.output:
                data_exporter = DataExporter(config=config, logger=file_logger, console=console, outputs=args.output)
            # Re-check for missing outputs after regeneration
            still_missing = []
            for output in args.output:
                if output == "influx" and not config.get("influxdb"):
                    still_missing.append("influxdb")
                if output == "prometheus" and not config.get("prometheus"):
                    still_missing.append("prometheus")
            if still_missing:
                console.print(f"[red]Error:[/] Failed to add configurations for: {', '.join(still_missing)}. Skipping these exports.")
                file_logger.error(f"Failed to add configurations for: {', '.join(still_missing)}. Skipping these exports.")
                # Remove missing outputs from args.output to skip them
                args.output = [output for output in args.output if output not in still_missing]
        else:
            console.print("Skipping exports for missing configurations.")

    # Initialize DataExporter within a context manager if outputs are specified
    if args.output:
        with DataExporter(config=config, logger=file_logger, console=console, outputs=args.output) as data_exporter:
            if args.schedule:
                # Define daemon mode as a nested function to access config and master_password
                def run_tasks_daemon_mode():
                    """
                    Execute tasks in daemon mode with dynamic configuration reloading.

                    Monitors the configuration file for changes and reloads it on-the-fly.
                    Schedules tasks to run at user-specified intervals.
                    """
                    last_config_mtime = CONFIG_PATH.stat().st_mtime if CONFIG_PATH.exists() else None

                    def job():
                        """
                        Job to be scheduled for periodic execution.

                        Checks for configuration changes, reloads if necessary, and runs tasks.
                        """
                        nonlocal last_config_mtime, config, github_tracker, pypi_tracker, data_exporter

                        # Check if the config file was modified
                        try:
                            current_mtime = CONFIG_PATH.stat().st_mtime
                        except FileNotFoundError:
                            console.print(f"[red]Configuration file {CONFIG_PATH} not found. Skipping job.[/red]")
                            file_logger.error(f"Configuration file {CONFIG_PATH} not found. Skipping job.")
                            return

                        if current_mtime != last_config_mtime:
                            console.print("[yellow]Configuration file has changed. Reloading config.[/yellow]")
                            file_logger.info("Configuration file changed; reloading config.")
                            last_config_mtime = current_mtime

                            # Reload the configuration
                            new_config = ConfigLoader.load_config(master_password)
                            if not new_config:
                                console.print("[red]Failed to reload configuration. Exiting daemon mode.[/red]")
                                file_logger.error("Failed to reload configuration.")
                                sys.exit(1)

                            # Reinitialize trackers and exporter
                            config = new_config
                            github_tracker = GitHubTracker(config=config, logger=file_logger, console=console) if "github" in config else None
                            pypi_tracker = PyPITracker(config=config, logger=file_logger, console=console) if "pypi" in config else None
                            if args.output:
                                # No need to close manually; __exit__ handles it
                                data_exporter = DataExporter(config=config, logger=file_logger, console=console, outputs=args.output)
                                # Note: In a real-world scenario, consider restructuring to handle multiple instances or use a more sophisticated exporter management.

                            console.print("[green]Configuration reloaded successfully.[/green]")
                            file_logger.info("Configuration reloaded and components reinitialized successfully.")

                        # Run tasks
                        run_tasks(args, github_tracker, pypi_tracker, data_exporter)

                    # Schedule the job
                    schedule.every(args.schedule).minutes.do(job)
                    console.print(f"[blue]Daemon mode enabled. Running every {args.schedule} minutes.[/blue]")
                    file_logger.info(f"Daemon mode enabled. Running every {args.schedule} minutes.")

                    # Run the first job immediately
                    job()

                    try:
                        while True:
                            schedule.run_pending()
                            time.sleep(1)
                    except KeyboardInterrupt:
                        console.print("\n[red]Colter interrupted by user. Exiting...[/red]")
                    except Exception as e:
                        file_logger.error(f"Unexpected error in daemon mode: {e}", exc_info=True)
                        console.print(f"[red]Unexpected error in daemon mode: {e}[/red]")
                    finally:
                        # No manual closure needed; context manager handles it
                        file_logger.debug("Daemon mode terminated.")

                # Start daemon mode
                run_tasks_daemon_mode()
            else:
                try:
                    run_tasks(args, github_tracker, pypi_tracker, data_exporter)
                except KeyboardInterrupt:
                    console.print("\n[red]Colter interrupted by user. Exiting...[/red]")
                except Exception as e:
                    # Catch any unexpected exceptions and log them
                    file_logger.error(f"Unexpected error: {e}", exc_info=True)
                    console.print(f"[red]Unexpected error occurred: {e}[/red]")
    else:
        # If no outputs are specified
        if args.schedule:
            # Initialize data_exporter as None to ensure it's defined
            data_exporter = None

            # Define daemon mode as a nested function to access config and master_password
            def run_tasks_daemon_mode():
                """
                Execute tasks in daemon mode without data export.

                Monitors the configuration file for changes and reloads it on-the-fly.
                Schedules tasks to run at user-specified intervals.
                """
                last_config_mtime = CONFIG_PATH.stat().st_mtime if CONFIG_PATH.exists() else None

                def job():
                    """
                    Job to be scheduled for periodic execution.

                    Checks for configuration changes, reloads if necessary, and runs tasks.
                    """
                    nonlocal last_config_mtime, config, github_tracker, pypi_tracker, data_exporter

                    # Check if the config file was modified
                    try:
                        current_mtime = CONFIG_PATH.stat().st_mtime
                    except FileNotFoundError:
                        console.print(f"[red]Configuration file {CONFIG_PATH} not found. Skipping job.[/red]")
                        file_logger.error(f"Configuration file {CONFIG_PATH} not found. Skipping job.")
                        return

                    if current_mtime != last_config_mtime:
                        console.print("[yellow]Configuration file has changed. Reloading config.[/yellow]")
                        file_logger.info("Configuration file changed; reloading config.")
                        last_config_mtime = current_mtime

                        # Reload the configuration
                        new_config = ConfigLoader.load_config(master_password)
                        if not new_config:
                            console.print("[red]Failed to reload configuration. Exiting daemon mode.[/red]")
                            file_logger.error("Failed to reload configuration.")
                            sys.exit(1)

                        # Reinitialize trackers
                        config = new_config
                        github_tracker = GitHubTracker(config=config, logger=file_logger, console=console) if "github" in config else None
                        pypi_tracker = PyPITracker(config=config, logger=file_logger, console=console) if "pypi" in config else None

                        console.print("[green]Configuration reloaded successfully.[/green]")
                        file_logger.info("Configuration reloaded and components reinitialized successfully.")

                    # Run tasks
                    run_tasks(args, github_tracker, pypi_tracker, data_exporter=None)

                # Schedule the job
                schedule.every(args.schedule).minutes.do(job)
                console.print(f"[blue]Daemon mode enabled. Running every {args.schedule} minutes.[/blue]")
                file_logger.info(f"Daemon mode enabled. Running every {args.schedule} minutes.")

                # Run the first job immediately
                job()

                try:
                    while True:
                        schedule.run_pending()
                        time.sleep(1)
                except KeyboardInterrupt:
                    console.print("\n[red]Colter interrupted by user. Exiting...[/red]")
                except Exception as e:
                    file_logger.error(f"Unexpected error in daemon mode: {e}", exc_info=True)
                    console.print(f"[red]Unexpected error in daemon mode: {e}[/red]")
                finally:
                    # No manual closure needed
                    file_logger.debug("Daemon mode terminated.")

            # Start daemon mode
            run_tasks_daemon_mode()
        else:
            try:
                run_tasks(args, github_tracker, pypi_tracker, data_exporter=None)
            except KeyboardInterrupt:
                console.print("\n[red]Colter interrupted by user. Exiting...[/red]")
            except Exception as e:
                # Catch any unexpected exceptions and log them
                file_logger.error(f"Unexpected error: {e}", exc_info=True)
                console.print(f"[red]Unexpected error occurred: {e}[/red]")

    logging.shutdown()


def run_tasks(args, github_tracker, pypi_tracker, data_exporter):
    """
    Execute tracking and export tasks based on user-specified arguments.

    This function processes only the requested outputs and data types,
    fetching data from GitHub and PyPI trackers and exporting them
    using the DataExporter.

    Args:
        args (argparse.Namespace): Parsed command-line arguments.
        github_tracker (GitHubTracker or None): Instance for tracking GitHub repositories.
        pypi_tracker (PyPITracker or None): Instance for tracking PyPI packages.
        data_exporter (DataExporter or None): Instance for exporting data.
    """
    # Initialize variables for data
    issues_by_repo = {}
    packages_info = {}

    # Process GitHub data if requested
    if args.type in ["github", "all"] and github_tracker:
        try:
            issues_by_repo = github_tracker.check_issues(
                test_email=args.test_email and not args.dry_run,
                dry_run=args.dry_run
            )
        except Exception as e:
            file_logger.error(f"Error processing GitHub data: {e}")
            console.print(f"[red]Error processing GitHub data: {e}[/red]")

    # Process PyPI data if requested
    if args.type in ["pypi", "all"] and pypi_tracker:
        try:
            packages_info = pypi_tracker.check_packages(dry_run=args.dry_run)
        except Exception as e:
            file_logger.error(f"Error processing PyPI data: {e}")
            console.print(f"[red]Error processing PyPI data: {e}[/red]")

    # Handle data export if outputs are specified
    if not args.dry_run and data_exporter:
        # Process InfluxDB export
        if "influx" in args.output:
            process_influx_export(args, data_exporter, github_tracker, issues_by_repo, packages_info)

        # Process Prometheus export
        if "prometheus" in args.output:
            process_prometheus_export(args, data_exporter, github_tracker, issues_by_repo, packages_info)


def process_influx_export(args, data_exporter, github_tracker, issues_by_repo, packages_info):
    """
    Collect and export data to InfluxDB.

    This function gathers metrics from GitHub and PyPI trackers based on the
    specified tracking type and exports the collected data points to InfluxDB
    using the DataExporter.

    Args:
        args (argparse.Namespace): Parsed command-line arguments.
        data_exporter (DataExporter): Instance for exporting data.
        github_tracker (GitHubTracker or None): Instance for tracking GitHub repositories.
        issues_by_repo (dict): Dictionary of repositories with their issues.
        packages_info (dict): Dictionary of PyPI packages with their statistics.
    """
    measurement_github = "github_repo_stats"
    measurement_pypi = "pypi_package_stats"
    points = []

    # Collect GitHub data for InfluxDB
    if args.type in ["github", "all"] and github_tracker:
        repos = github_tracker.fetch_repos()
        if not repos:
            console.print("[yellow]No GitHub repositories found for export.[/yellow]")
            file_logger.warning("No GitHub repositories found for export.")
        else:
            file_logger.info(f"Fetched {len(repos)} repositories from GitHub.")
            for repo in repos:
                tags = {
                    "repo": repo["name"],
                    "owner": repo["owner"]["login"],
                    "private": str(repo.get("private", False)).lower()
                }
                fields = {
                    "forks": repo.get("forks_count", 0),
                    "branches": github_tracker.fetch_branches_count(repo["owner"]["login"], repo["name"]),
                    "followers": repo.get("watchers_count", 0),
                    "downloads": github_tracker.fetch_downloads_count(repo["owner"]["login"], repo["name"]),
                    "last_push": repo.get("pushed_at", "N/A")
                }
                point = data_exporter.create_influx_point(measurement_github, tags, fields)
                points.append(point)

    # Collect PyPI data for InfluxDB
    if args.type in ["pypi", "all"] and packages_info:
        file_logger.info(f"Processing {len(packages_info)} PyPI packages for export.")
        for package, data in packages_info.items():
            stats = data.get("stats")
            if stats:
                tags = {"package": package}
                fields = {
                    "recent_downloads_day": stats.get("recent", {}).get("data", {}).get("last_day", 0),
                    "recent_downloads_week": stats.get("recent", {}).get("data", {}).get("last_week", 0),
                    "recent_downloads_month": stats.get("recent", {}).get("data", {}).get("last_month", 0),
                    "overall_downloads": sum(item.get("downloads", 0) for item in stats.get("overall", {}).get("data", [])),
                    "python_major_downloads": sum(item.get("downloads", 0) for item in stats.get("python_major", {}).get("data", [])),
                    "python_minor_downloads": sum(item.get("downloads", 0) for item in stats.get("python_minor", {}).get("data", [])),
                    "system_downloads": sum(item.get("downloads", 0) for item in stats.get("system", {}).get("data", [])),
                }
                point = data_exporter.create_influx_point(measurement_pypi, tags, fields)
                points.append(point)

    # Log the collected points
    if points:
        file_logger.debug(f"Total points collected for InfluxDB export: {len(points)}")
        for idx, point in enumerate(points, start=1):
            file_logger.debug(f"Point {idx}: {point.to_line_protocol()}")
    else:
        file_logger.debug("No data points collected for InfluxDB export.")

    # Export data if points are available
    if points:
        batch_size = 10
        batches = [points[i:i + batch_size] for i in range(0, len(points), batch_size)]
        success, fail = data_exporter.process_batches(batches)
        if fail > 0:
            console.print(f"[red]Error: {fail} InfluxDB batches failed to export.[/red]")
            file_logger.error(f"{fail} InfluxDB batches failed to export.")
    else:
        console.print("[yellow]No data points available for export to InfluxDB.[/yellow]")
        # Only log debug to avoid cluttering the console
        file_logger.debug("No data points were created for InfluxDB export.")


def process_prometheus_export(args, data_exporter, github_tracker, issues_by_repo, packages_info):
    """
    Collect and export data to Prometheus.

    This function gathers metrics from GitHub and PyPI trackers based on the
    specified tracking type and exports the collected metrics to Prometheus
    using the DataExporter.

    Args:
        args (argparse.Namespace): Parsed command-line arguments.
        data_exporter (DataExporter): Instance for exporting data.
        github_tracker (GitHubTracker or None): Instance for tracking GitHub repositories.
        issues_by_repo (dict): Dictionary of repositories with their issues.
        packages_info (dict): Dictionary of PyPI packages with their statistics.
    """
    # Collect and export GitHub data to Prometheus
    if "prometheus" in args.output and (args.type in ["github", "all"]) and github_tracker:
        repos = github_tracker.fetch_repos()
        for repo in repos:
            repo_name = repo["name"]
            stats = {
                "forks": repo.get("forks_count", 0),
                "branches": github_tracker.fetch_branches_count(repo["owner"]["login"], repo_name),
                "followers": repo.get("watchers_count", 0),
                "downloads": github_tracker.fetch_downloads_count(repo["owner"]["login"], repo_name),
                "last_push": repo.get("pushed_at", "N/A")
            }
            for metric, value in stats.items():
                if metric == "last_push":
                    if value != "N/A":
                        try:
                            # Convert ISO timestamp to UNIX timestamp
                            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                            unix_time = int(dt.timestamp())
                            data_exporter.export_to_prometheus(
                                f"github_repo_{metric}",
                                unix_time,
                                labels={"repo": repo_name}
                            )
                        except ValueError:
                            # Handle invalid timestamp format
                            file_logger.warning(f"Invalid timestamp format for last_push in repo {repo_name}: {value}")
                            continue
                else:
                    data_exporter.export_to_prometheus(
                        f"github_repo_{metric}",
                        value,
                        labels={"repo": repo_name}
                    )

    # Collect and export PyPI data to Prometheus
    if "prometheus" in args.output and (args.type in ["pypi", "all"]) and packages_info:
        for package, data in packages_info.items():
            stats = data.get("stats")
            if stats:
                # Overall Downloads
                metric_name = f"pypi_{package}_downloads"
                overall_downloads = stats.get("overall_downloads", 0)
                data_exporter.export_to_prometheus(
                    metric_name,
                    overall_downloads,
                    labels={"package": package}
                )

                # Python Major Downloads
                python_major_downloads = sum(
                    item.get("downloads", 0) for item in stats.get("python_major", {}).get("data", [])
                )
                metric_name_major = f"pypi_{package}_python_major_downloads"
                data_exporter.export_to_prometheus(
                    metric_name_major,
                    python_major_downloads,
                    labels={"package": package}
                )

                # Python Minor Downloads
                python_minor_downloads = sum(
                    item.get("downloads", 0) for item in stats.get("python_minor", {}).get("data", [])
                )
                metric_name_minor = f"pypi_{package}_python_minor_downloads"
                data_exporter.export_to_prometheus(
                    metric_name_minor,
                    python_minor_downloads,
                    labels={"package": package}
                )

                # System Downloads
                system_downloads = sum(
                    item.get("downloads", 0) for item in stats.get("system", {}).get("data", [])
                )
                metric_name_system = f"pypi_{package}_system_downloads"
                data_exporter.export_to_prometheus(
                    metric_name_system,
                    system_downloads,
                    labels={"package": package}
                )


if __name__ == "__main__":
    clear_term()
    main()

