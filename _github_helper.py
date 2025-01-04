#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# _github_helper.py

"""
GitHub Helper Module for Colter.

This module provides the `GitHubTracker` class, which facilitates interaction with
the GitHub API to fetch repository data, issues, and related metrics. It also handles
sending email alerts for detected issues in repositories.
"""

from cachetools import cached, TTLCache
from email.mime.text import MIMEText
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
import requests
import smtplib
import logging
from typing import Dict, Any, List, Optional


# Custom Exception for GitHub API Errors
class GitHubAPIError(Exception):
    """Exception raised for GitHub API-related errors."""
    pass


class GitHubTracker:
    """
    A class responsible for tracking GitHub repositories and managing related metrics.

    The `GitHubTracker` interacts with the GitHub API to fetch repository details,
    branches, download counts, clone statistics, and issues. It also handles sending
    email alerts when issues are detected in repositories.

    Attributes:
        token (str): GitHub Personal Access Token for authentication.
        headers (Dict[str, str]): HTTP headers for API requests.
        smtp_config (Dict[str, Any]): SMTP configuration for sending emails.
        cache (TTLCache): Cache for storing API responses to reduce redundant requests.
        logger (logging.Logger): Logger instance for logging events and errors.
        console (Console): Rich console instance for user-friendly output.
    """

    def __init__(self, config: Dict[str, Any], logger: logging.Logger, console: Console):
        """
        Initialize the GitHubTracker with configuration, logger, and console.

        Sets up authentication headers, SMTP configuration, and initializes a cache
        for API responses.

        Args:
            config (Dict[str, Any]): Configuration dictionary containing GitHub and SMTP settings.
            logger (logging.Logger): Logger instance for logging events and errors.
            console (Console): Rich console instance for user-friendly output.
        """
        self.token = config["github"]["token"]  # Decrypted GitHub token
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.smtp_config = config.get("smtp", {})  # SMTP configuration for email alerts
        self.cache = TTLCache(maxsize=100, ttl=300)  # Cache for 5 minutes to store API responses
        self.logger = logger
        self.console = console

    @cached(cache=TTLCache(maxsize=100, ttl=300))
    def fetch_repos(self) -> List[Dict[str, Any]]:
        """
        Fetch the authenticated user's GitHub repositories.

        Sends a GET request to the GitHub API to retrieve the list of repositories
        associated with the authenticated user.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each representing a repository.

        Raises:
            GitHubAPIError: If the API request fails or returns an error status code.
        """
        url = "https://api.github.com/user/repos"
        self.logger.info(f"Connecting to GitHub API: {url}")
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                repos = response.json()
                self.logger.info("Successfully fetched repositories from GitHub.")
                return repos
            else:
                error = response.text
                self.logger.error(f"GitHub API Error {response.status_code}: {error}")
                raise GitHubAPIError(f"Failed to fetch repos: {response.status_code} {error}")
        except Exception as e:
            self.logger.error(f"GitHub API Exception: {e}")
            raise GitHubAPIError(f"An error occurred while fetching repositories: {e}") from e

    @cached(cache=TTLCache(maxsize=100, ttl=300))
    def fetch_branches_count(self, owner: str, repo_name: str) -> int:
        """
        Fetch the number of branches for a given repository.

        Sends a GET request to the GitHub API to retrieve branch information for the specified repository.

        Args:
            owner (str): The owner of the repository.
            repo_name (str): The name of the repository.

        Returns:
            int: The total number of branches in the repository.

        Raises:
            GitHubAPIError: If the API request fails or returns an error status code.
        """
        branches_url = f"https://api.github.com/repos/{owner}/{repo_name}/branches"
        try:
            response = requests.get(branches_url, headers=self.headers)
            if response.status_code == 200:
                branches = response.json()
                return len(branches)
            else:
                error = response.text
                self.logger.error(f"GitHub API Error {response.status_code}: {error}")
                raise GitHubAPIError(
                    f"Failed to fetch branches for {owner}/{repo_name}: {response.status_code} {error}"
                )
        except Exception as e:
            self.logger.error(f"GitHub API Exception: {e}")
            raise GitHubAPIError(
                f"An error occurred while fetching branches for {owner}/{repo_name}: {e}"
            ) from e

    @cached(cache=TTLCache(maxsize=100, ttl=300))
    def fetch_downloads_count(self, owner: str, repo_name: str) -> int:
        """
        Fetch the total downloads count for a given repository.

        Aggregates the download counts from all assets across all releases in the repository.

        Args:
            owner (str): The owner of the repository.
            repo_name (str): The name of the repository.

        Returns:
            int: The total number of downloads for the repository.

        Raises:
            GitHubAPIError: If the API request fails or returns an error status code.
        """
        releases_url = f"https://api.github.com/repos/{owner}/{repo_name}/releases"
        total_downloads = 0
        try:
            response = requests.get(releases_url, headers=self.headers)
            if response.status_code == 200:
                releases = response.json()
                for release in releases:
                    for asset in release.get("assets", []):
                        total_downloads += asset.get("download_count", 0)
                return total_downloads
            else:
                error = response.text
                self.logger.error(f"GitHub API Error {response.status_code}: {error}")
                raise GitHubAPIError(
                    f"Failed to fetch downloads for {owner}/{repo_name}: {response.status_code} {error}"
                )
        except Exception as e:
            self.logger.error(f"GitHub API Exception: {e}")
            raise GitHubAPIError(
                f"An error occurred while fetching downloads for {owner}/{repo_name}: {e}"
            ) from e

    @cached(cache=TTLCache(maxsize=100, ttl=300))
    def fetch_clone_count(self, owner: str, repo_name: str) -> (int, int):
        """
        Fetch the clone count for a given repository over the past 14 days.

        Retrieves both the total number of clones and the number of unique cloners.

        Args:
            owner (str): The owner of the repository.
            repo_name (str): The name of the repository.

        Returns:
            (int, int): A tuple containing the total clones and unique clones.

        Raises:
            GitHubAPIError: If the API request fails or returns an error status code.
        """
        clones_url = f"https://api.github.com/repos/{owner}/{repo_name}/traffic/clones"
        try:
            response = requests.get(clones_url, headers=self.headers)
            if response.status_code == 200:
                clones_data = response.json()
                total_clones = clones_data.get("count", 0)
                unique_clones = clones_data.get("uniques", 0)
                return total_clones, unique_clones
            else:
                error = response.text
                self.logger.error(f"GitHub API Error {response.status_code}: {error}")
                raise GitHubAPIError(
                    f"Failed to fetch clones for {owner}/{repo_name}: {response.status_code} {error}"
                )
        except Exception as e:
            self.logger.error(f"GitHub API Exception: {e}")
            raise GitHubAPIError(
                f"An error occurred while fetching clones for {owner}/{repo_name}: {e}"
            ) from e

    def send_email_alert(self, issues_by_repo: Dict[str, List[Dict[str, Any]]]):
        """
        Send an email alert for repositories with detected issues.

        Constructs and sends an email detailing the issues found in various repositories.
        Utilizes SMTP configuration for sending the email.

        Args:
            issues_by_repo (Dict[str, List[Dict[str, Any]]]): A dictionary mapping repository names
                to a list of issues detected within them.

        Returns:
            None

        Raises:
            None: Exceptions are caught and logged internally.
        """
        if not self.smtp_config:
            self.console.print("[red]Error:[/] SMTP configuration is missing. Cannot send email alerts.")
            self.logger.error("SMTP configuration is missing. Cannot send email alerts.")
            return

        try:
            subject = "GitHub Issues Detected"
            body = "Issues detected in the following repositories:\n\n"
            for repo, issues in issues_by_repo.items():
                body += f"Repository: {repo}\n"
                for issue in issues:
                    body += f" - {issue['title']}\n"
                body += "\n"
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = self.smtp_config["sender"]
            msg["To"] = self.smtp_config["recipient"]

            self.logger.info("Sending email alert.")
            self._send_email(msg)
            self.logger.info("Email alert sent successfully.")
        except Exception as e:
            self.logger.error(f"Failed to send email alert: {e}")
            self.console.print(f"[red]Error:[/] Failed to send email alert: {e}")

    def _send_email(self, msg: MIMEText):
        """
        Synchronously send an email using SMTP.

        Establishes a connection to the SMTP server, logs in, and sends the provided email message.

        Args:
            msg (MIMEText): The email message to be sent.

        Returns:
            None

        Raises:
            Exception: Propagates exceptions encountered during the email sending process.
        """
        try:
            with smtplib.SMTP(self.smtp_config["smtp_server"], int(self.smtp_config["smtp_port"])) as server:
                server.starttls()
                server.login(self.smtp_config["username"], self.smtp_config["password"])
                server.send_message(msg)
        except Exception as e:
            raise e

    def check_issues(
        self,
        test_email: bool = False,
        dry_run: bool = False
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Check for issues across all tracked repositories and handle alerts.

        This method performs the following steps:
        1. Fetches all repositories.
        2. Gathers repository-level data such as forks, branches, watchers, downloads, clones, and last push time.
        3. Detects issues in each repository.
        4. Displays issues in a formatted table.
        5. Sends email alerts if issues are found, unless in dry-run mode.

        Args:
            test_email (bool, optional): If True, injects a fake issue for testing email alerts.
                Defaults to False.
            dry_run (bool, optional): If True, simulates actions without performing exports or sending emails.
                Defaults to False.

        Returns:
            Dict[str, List[Dict[str, Any]]]: A dictionary mapping repository names to their respective issues.
        """
        self.logger.info("check_issues() has been invoked.")
        repos = self.fetch_repos()
        issues_by_repo = {}
        repo_stats = []

        # Temporary flag to inject fake issue for testing
        FAKE_ISSUE_INJECTION = test_email  # Controlled by parameter

        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
            issues_task = progress.add_task("[green]Fetching GitHub issues...", total=None)
            for repo in repos:
                repo_name = repo["name"]
                owner = repo["owner"]["login"]
                is_private = repo.get("private", False)

                # Log “fetching repo stats” and if it’s private
                self.logger.info(
                    f"Fetching repo stats for {owner}/{repo_name} (private={is_private})"
                )

                # Basic stats from the /user/repos response
                forks_count = repo.get("forks_count", 0)
                watchers_count = repo.get("watchers_count", 0)  # watchers ~ "followers"
                pushed_at = repo.get("pushed_at", "N/A")

                # Additional calls for more data
                try:
                    branches_count = self.fetch_branches_count(owner, repo_name)
                except GitHubAPIError:
                    branches_count = 0

                try:
                    downloads_count = self.fetch_downloads_count(owner, repo_name)
                except GitHubAPIError:
                    downloads_count = 0

                try:
                    total_clones, unique_clones = self.fetch_clone_count(owner, repo_name)
                except GitHubAPIError:
                    total_clones, unique_clones = 0, 0

                # Decide how to display the repo name in the final table
                if is_private:
                    display_repo_name = f"[bold red]{repo_name}[/]"
                else:
                    display_repo_name = f"[bold green]{repo_name}[/]"  # or remove bold if preferred

                # Store stats for the final “GitHub Repository Stats” table
                repo_stats.append(
                    (
                        display_repo_name,
                        forks_count,
                        branches_count,
                        watchers_count,
                        downloads_count,
                        total_clones,
                        unique_clones,
                        pushed_at,
                    )
                )

                # Now check for issues
                issues_url = repo["issues_url"].replace("{/number}", "")
                self.logger.info(f"Fetching issues for repository: {repo_name}")
                try:
                    response = requests.get(issues_url, headers=self.headers)
                    if response.status_code == 200:
                        issues = response.json()
                        if issues:
                            issues_by_repo[repo_name] = [{"title": issue["title"]} for issue in issues]
                    else:
                        error = response.text
                        self.logger.error(f"GitHub API Error {response.status_code}: {error}")
                except Exception as e:
                    self.logger.error(f"Error fetching issues for {repo_name}: {e}")

            progress.update(issues_task, completed=True)

        if FAKE_ISSUE_INJECTION and repos:
            test_repo = repos[0]["name"]  # Pick the first repo
            fake_issue = {"title": "This is a test issue for email alert."}
            if test_repo in issues_by_repo:
                issues_by_repo[test_repo].append(fake_issue)
            else:
                issues_by_repo[test_repo] = [fake_issue]
            self.logger.info(f"Injected fake issue into repository: {test_repo}")

        self.logger.info(f"Detailed GitHub issues: {issues_by_repo}")

        # Print table for any issues found
        if issues_by_repo:
            issues_table = Table(title="GitHub Issues Detected")
            issues_table.add_column("Repository Name", style="red")
            issues_table.add_column("Issue Title", style="blue")
            for repo, issues in issues_by_repo.items():
                for issue in issues:
                    issues_table.add_row(repo, issue["title"])
            self.console.print(issues_table)

            # Send email alert
            if not dry_run:
                self.send_email_alert(issues_by_repo)
        else:
            self.logger.info("No currently logged issues for any repositories.")

        # **Always** Print the “GitHub Repository Stats” table
        stats_table = Table(title="GitHub Repository Stats")
        stats_table.add_column("Repo Name", style="yellow")
        stats_table.add_column("Forks", style="cyan", justify="right")
        stats_table.add_column("Branches", style="magenta", justify="right")
        stats_table.add_column("Followers", style="green", justify="right")   # watchers_count
        stats_table.add_column("Downloads", style="blue", justify="right")
        stats_table.add_column("Total Clones", style="chartreuse1", justify="right")
        stats_table.add_column("Unique Clones", style="gold3", justify="right")
        stats_table.add_column("Last Push", style="white")

        # **Log the repo_stats count**
        self.logger.info(f"Total repositories processed: {len(repo_stats)}")

        for (
            repo_disp_name,
            forks,
            branches,
            watchers,
            downloads,
            total_clones,
            unique_clones,
            last_push,
        ) in repo_stats:
            stats_table.add_row(
                repo_disp_name,
                str(forks),
                str(branches),
                str(watchers),
                str(downloads),
                str(total_clones),
                str(unique_clones),
                str(last_push),
            )

        # Check if repo_stats is not empty before printing
        if repo_stats:
            self.console.print(stats_table)
        else:
            self.console.print("[yellow]No repositories found to display statistics.[/yellow]")

        # Add the legend below the stats table:
        legend_text = (
            "[bold red]Private[/bold red]  |  "
            "[bold green]Public[/bold green]\n\n"
        )
        self.console.print(legend_text, style="dim")

        return issues_by_repo  # Or return anything else you need

