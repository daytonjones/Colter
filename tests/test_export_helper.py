import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from typing import Dict  # Ensures proper type hinting

# Adjust the system path to import the PyPITracker class
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _pypi_helper import PyPITracker

class TestPyPITracker(unittest.TestCase):
    def setUp(self):
        """
        Set up the test environment before each test method.
        """
        # Configuration with two packages: one existing and one non-existent
        self.config = {
            "pypi": {
                "packages": ["simply-useful", "non-existent-package"]
            }
        }
        # Mock logger and console to prevent actual logging during tests
        self.logger = MagicMock()
        self.console = MagicMock()
        # Initialize the PyPITracker instance with the mocked dependencies
        self.tracker = PyPITracker(config=self.config, logger=self.logger, console=self.console)

    @patch('pypistats.system')
    @patch('pypistats.python_minor')
    @patch('pypistats.python_major')
    @patch('pypistats.overall')
    @patch('pypistats.recent')
    def test_fetch_pypi_stats_success(self, mock_recent, mock_overall, mock_python_major, mock_python_minor, mock_system):
        """
        Test fetching PyPI stats successfully for an existing package.
        """
        # Mock API responses with valid JSON strings
        mock_recent.return_value = '{"data": {"last_day": 20, "last_month": 104, "last_week": 104}, "package": "simply-useful", "type": "recent_downloads"}'
        mock_overall.return_value = '{"data": [{"category": "with_mirrors", "downloads": 216}, {"category": "without_mirrors", "downloads": 104}], "package": "simply-useful", "type": "overall_downloads"}'
        mock_python_major.return_value = '{"data": [{"category": "3", "downloads": 15}, {"category": "null", "downloads": 89}], "package": "simply-useful", "type": "python_major_downloads"}'
        mock_python_minor.return_value = '{"data": [{"category": "3.10", "downloads": 11}, {"category": "3.11", "downloads": 1}, {"category": "3.12", "downloads": 2}, {"category": "3.8", "downloads": 1}, {"category": "null", "downloads": 89}], "package": "simply-useful", "type": "python_minor_downloads"}'
        mock_system.return_value = '{"data": [{"category": "Linux", "downloads": 15}, {"category": "null", "downloads": 89}], "package": "simply-useful", "type": "system_downloads"}'

        # Call the method under test
        stats = self.tracker.fetch_pypi_stats("simply-useful")
        
        # Debugging: Print the fetched stats
        print("Fetched Stats for 'simply-useful':", stats)
        
        # Assertions to verify that stats are correctly fetched and parsed
        self.assertIsNotNone(stats, "Stats should not be None for an existing package.")
        self.assertIn("recent", stats, "Stats should contain 'recent' data.")
        self.assertIn("overall", stats, "Stats should contain 'overall' data.")
        self.assertIn("python_major", stats, "Stats should contain 'python_major' data.")
        self.assertIn("python_minor", stats, "Stats should contain 'python_minor' data.")
        self.assertIn("system", stats, "Stats should contain 'system' data.")
        self.assertEqual(stats["recent"]["data"]["last_day"], 20, "Last day downloads should be 20.")

    @patch('pypistats.recent')
    def test_fetch_pypi_stats_json_decode_error(self, mock_recent):
        """
        Test handling of JSON decoding errors when fetching PyPI stats.
        """
        # Mock API response with invalid JSON
        mock_recent.return_value = "Invalid JSON"
        
        # Call the method under test
        stats = self.tracker.fetch_pypi_stats("simply-useful")
        
        # Debugging: Print the result
        print("Fetched Stats with JSON Decode Error:", stats)
        
        # Assertions to verify that stats are None due to JSON decode error
        self.assertIsNone(stats, "Stats should be None when JSON decoding fails.")
        # Verify that an error was logged
        self.logger.error.assert_called_with("JSON decoding failed for simply-useful: Expecting value: line 1 column 1 (char 0)")

    @patch('pypistats.system')
    @patch('pypistats.python_minor')
    @patch('pypistats.python_major')
    @patch('pypistats.overall')
    @patch('pypistats.recent')
    def test_fetch_pypi_stats_non_existent_package(self, mock_recent, mock_overall, mock_python_major, mock_python_minor, mock_system):
        """
        Test fetching PyPI stats for a non-existent package.
        """
        # Mock API responses indicating the package was not found
        mock_recent.return_value = '{"detail": "Not found."}'
        mock_overall.return_value = '{"detail": "Not found."}'
        mock_python_major.return_value = '{"detail": "Not found."}'
        mock_python_minor.return_value = '{"detail": "Not found."}'
        mock_system.return_value = '{"detail": "Not found."}'

        # Call the method under test
        stats = self.tracker.fetch_pypi_stats("non-existent-package")
        
        # Debugging: Print the fetched stats
        print("Fetched Stats for 'non-existent-package':", stats)
        
        # Assertions to verify that stats are not None but contain None data
        self.assertIsNotNone(stats, "Stats should not be None even if package is non-existent.")
        self.assertIn("recent", stats, "Stats should contain 'recent' key.")
        self.assertIn("overall", stats, "Stats should contain 'overall' key.")
        self.assertIn("python_major", stats, "Stats should contain 'python_major' key.")
        self.assertIn("python_minor", stats, "Stats should contain 'python_minor' key.")
        self.assertIn("system", stats, "Stats should contain 'system' key.")
        self.assertIsNone(stats["recent"].get("data"), "Recent data should be None for a non-existent package.")

    @patch('pypistats.system')
    @patch('pypistats.python_minor')
    @patch('pypistats.python_major')
    @patch('pypistats.overall')
    @patch('pypistats.recent')
    def test_fetch_package_version_success(self, mock_recent, mock_overall, mock_python_major, mock_python_minor, mock_system):
        """
        Test successfully fetching the version of an existing package.
        """
        with patch('requests.get') as mock_get:
            # Mock a successful HTTP response with version information
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "info": {
                    "version": "1.0.0"
                }
            }
            mock_get.return_value = mock_response

            # Call the method under test
            version = self.tracker.fetch_package_version("simply-useful")
            
            # Debugging: Print the fetched version
            print("Fetched Version for 'simply-useful':", version)
            
            # Assertions to verify the correct version is returned
            self.assertEqual(version, "1.0.0", "Version should be '1.0.0' for the existing package.")

    @patch('pypistats.system')
    @patch('pypistats.python_minor')
    @patch('pypistats.python_major')
    @patch('pypistats.overall')
    @patch('pypistats.recent')
    def test_fetch_package_version_failure(self, mock_recent, mock_overall, mock_python_major, mock_python_minor, mock_system):
        """
        Test handling of failure when fetching the version of a non-existent package.
        """
        with patch('requests.get') as mock_get:
            # Mock a failed HTTP response indicating the package was not found
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_response.text = "Not Found"
            mock_get.return_value = mock_response

            # Call the method under test
            version = self.tracker.fetch_package_version("non-existent-package")
            
            # Debugging: Print the fetched version
            print("Fetched Version for 'non-existent-package':", version)
            
            # Assertions to verify that None is returned on failure
            self.assertIsNone(version, "Version should be None when the package does not exist.")
            # Verify that an error was logged
            self.logger.error.assert_called_with("PyPI API Error 404: Not Found")

    @patch.object(PyPITracker, 'fetch_pypi_stats')
    @patch.object(PyPITracker, 'fetch_package_version')
    def test_check_packages(self, mock_fetch_version, mock_fetch_stats):
        """
        Test the check_packages method with both existing and non-existent packages.
        """
        # Setup mock returns
        mock_fetch_version.side_effect = ["1.0.0", None]  # First package exists, second does not
        mock_fetch_stats.side_effect = [
            {
                "recent": {"data": {"last_day": 20, "last_month": 104, "last_week": 104}},
                "overall": {"data": [{"category": "with_mirrors", "downloads": 216}, {"category": "without_mirrors", "downloads": 104}]},
                "python_major": {"data": [{"category": "3", "downloads": 15}, {"category": "null", "downloads": 89}]},
                "python_minor": {"data": [{"category": "3.10", "downloads": 11}, {"category": "3.11", "downloads": 1}, {"category": "3.12", "downloads": 2}, {"category": "3.8", "downloads": 1}, {"category": "null", "downloads": 89}]},
                "system": {"data": [{"category": "Linux", "downloads": 15}, {"category": "null", "downloads": 89}]}
            },
            None  # Second package failed to fetch stats
        ]

        # Call the method under test
        results = self.tracker.check_packages()

        # Debugging: Print the results
        print("Check Packages Results:", results)

        # Assertions for the first package (existing)
        self.assertIn("simply-useful", results, "Results should include 'simply-useful'.")
        self.assertEqual(results["simply-useful"]["version"], "1.0.0", "Version should be '1.0.0' for 'simply-useful'.")
        self.assertIsNotNone(results["simply-useful"]["stats"], "Stats should not be None for 'simply-useful'.")

        # Assertions for the second package (non-existent)
        self.assertIn("non-existent-package", results, "Results should include 'non-existent-package'.")
        self.assertEqual(results["non-existent-package"]["version"], "Error", "Version should be 'Error' for 'non-existent-package'.")
        self.assertIsNone(results["non-existent-package"]["stats"], "Stats should be None for 'non-existent-package'.")

        # Ensure fetch_package_version was called correctly
        self.assertEqual(mock_fetch_version.call_count, 2, "fetch_package_version should be called twice.")
        mock_fetch_version.assert_any_call("simply-useful")
        mock_fetch_version.assert_any_call("non-existent-package")
        
        # Ensure fetch_pypi_stats was called correctly
        self.assertEqual(mock_fetch_stats.call_count, 2, "fetch_pypi_stats should be called twice.")
        mock_fetch_stats.assert_any_call("simply-useful")
        mock_fetch_stats.assert_any_call("non-existent-package")

        # Additional Debugging: Check individual calls and their return values
        print("fetch_package_version calls:", mock_fetch_version.call_args_list)
        print("fetch_pypi_stats calls:", mock_fetch_stats.call_args_list)

if __name__ == '__main__':
    unittest.main()


