#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# _export_helper.py

"""
Export Helper Module for Colter.

This module provides the `DataExporter` class, which facilitates exporting
collected metrics from GitHub and PyPI trackers to InfluxDB and Prometheus.
It handles the creation of data points, batching, retry mechanisms, and
ensures secure and reliable data transmission to the configured endpoints.
"""

from contextlib import contextmanager
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway
from rich.console import Console
from simply_useful import retry, timeit
from typing import Dict, Any, List, Optional
import logging


class DataExporter:
    """
    A class responsible for exporting data to InfluxDB and Prometheus.

    The `DataExporter` handles the creation of InfluxDB points, batching of data,
    and exporting to both InfluxDB and Prometheus based on the provided configuration.

    Attributes:
        influx_config (Optional[Dict[str, Any]]): Configuration for InfluxDB export.
        prometheus_config (Optional[Dict[str, Any]]): Configuration for Prometheus export.
        logger (logging.Logger): Logger instance for logging events and errors.
        console (Console): Rich console instance for user-friendly output.
        outputs (List[str]): List of output formats to export data to.
        influx_client (Optional[InfluxDBClient]): InfluxDB client instance.
        write_api (Optional[WriteApi]): InfluxDB Write API instance.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        logger: logging.Logger,
        console: Console,
        outputs: Optional[List[str]] = None
    ):
        """
        Initialize the DataExporter with configurations for InfluxDB and Prometheus.

        This constructor sets up the necessary clients for InfluxDB and prepares
        for Prometheus exports based on the provided configurations.

        Args:
            config (Dict[str, Any]): The configuration dictionary containing
                InfluxDB and Prometheus settings.
            logger (logging.Logger): Logger instance for logging events and errors.
            console (Console): Rich console instance for user-friendly output.
            outputs (Optional[List[str]]): List of output formats to export data to.
                Supported options are "influx" and "prometheus". Defaults to an empty list.

        Raises:
            None
        """
        self.influx_config = config.get("influxdb")
        self.prometheus_config = config.get("prometheus")
        self.logger = logger
        self.console = console
        self.outputs = outputs or []

        # Initialize InfluxDB client if configuration exists
        if self.influx_config:
            try:
                self.influx_client = InfluxDBClient(
                    url=self.influx_config["url"],
                    token=self.influx_config["token"],
                    org=self.influx_config["org"]
                )
                self.write_api = self.influx_client.write_api(write_options=SYNCHRONOUS)
                self.logger.info("InfluxDB client initialized successfully.")
            except Exception as e:
                self.logger.error(f"Failed to initialize InfluxDB client: {e}")
                self.influx_client = None
                self.write_api = None
        else:
            self.influx_client = None
            self.write_api = None

    def __enter__(self):
        """
        Enter the runtime context related to this object.

        Returns:
            DataExporter: The instance itself.
        """
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Exit the runtime context and perform cleanup.

        Ensures that the InfluxDB client is properly closed upon exiting the context.

        Args:
            exc_type (Type[BaseException] or None): Exception type, if any.
            exc_value (BaseException or None): Exception value, if any.
            traceback (TracebackType or None): Traceback, if any.
        """
        self.close_influx_client()

    def close_influx_client(self):
        """
        Close the InfluxDB client.

        Safely closes the InfluxDB client to release resources. Logs the closure status.

        Args:
            None

        Returns:
            None
        """
        if self.influx_client:
            try:
                self.influx_client.close()
                self.logger.info("InfluxDB client closed successfully.")
            except Exception as e:
                self.logger.error(f"Error closing InfluxDB client: {e}")
            finally:
                self.influx_client = None  # Remove reference
                self.write_api = None  # Remove reference

    def create_influx_point(
        self,
        measurement: str,
        tags: Dict[str, str],
        fields: Dict[str, Any]
    ) -> Point:
        """
        Create an InfluxDB Point object with the specified measurement, tags, and fields.

        This method constructs a data point for InfluxDB, ensuring that numeric fields
        are correctly typed and non-numeric fields are converted to strings.

        Args:
            measurement (str): The measurement name for the data point.
            tags (Dict[str, str]): A dictionary of tag key-value pairs.
            fields (Dict[str, Any]): A dictionary of field key-value pairs.

        Returns:
            Point: An InfluxDB Point object ready for export.
        """
        point = Point(measurement)
        for tag_key, tag_value in tags.items():
            point = point.tag(tag_key, tag_value)
        for field_key, field_value in fields.items():
            if isinstance(field_value, (int, float)):
                point = point.field(field_key, field_value)
            else:
                point = point.field(field_key, str(field_value))
        # Debug log for the point
        self.logger.debug(f"Created InfluxDB Point: {point.to_line_protocol()}")
        return point

    @timeit
    @retry(max_retries=3, backoff=2.0)
    def export_to_influx_batch(self, points: List[Point]) -> bool:
        """
        Export a batch of data points to InfluxDB.

        This method writes a batch of InfluxDB Points to the configured bucket and organization.
        It employs a retry mechanism to handle transient failures.

        Args:
            points (List[Point]): A list of InfluxDB Point objects to be exported.

        Returns:
            bool: True if the export is successful, False otherwise.

        Raises:
            Exception: Propagates exceptions encountered during the export process.
        """
        if not self.influx_config or not self.write_api:
            self.logger.error("InfluxDB configuration is missing. Skipping export.")
            return False  # Indicate failure
        try:
            self.write_api.write(
                bucket=self.influx_config["bucket"],
                org=self.influx_config["org"],
                record=points
            )
            self.logger.info(
                f"Batch data exported to InfluxDB successfully: {len(points)} points."
            )
            return True
        except Exception as e:
            self.logger.error(f"Failed to export batch data to InfluxDB: {e}")
            raise e  # Raise exception to be caught in process_batches

    def process_batches(self, batches: List[List[Point]]) -> (int, int):
        """
        Process multiple batches of data and provide a summary after execution.

        Iterates through each batch, attempting to export them to InfluxDB.
        Keeps track of successful and failed exports, providing a consolidated summary.

        Args:
            batches (List[List[Point]]): A list of batches, where each batch is a list of InfluxDB Point objects.

        Returns:
            (int, int): A tuple containing the count of successful exports and failed exports, respectively.
        """
        success_count = 0
        failure_count = 0

        if not batches:
            self.console.print("[yellow]No data points available for export to InfluxDB.[/yellow]")
            self.logger.warning("No batches to process for InfluxDB export.")
            return success_count, failure_count

        self.console.print("[blue]Preparing to export batches to InfluxDB...[/blue]")
        self.logger.info("Starting batch export to InfluxDB.")

        for idx, batch in enumerate(batches, start=1):
            try:
                self.export_to_influx_batch(batch)
                success_count += 1
                self.logger.debug(f"Batch {idx} exported successfully.")
            except Exception:
                failure_count += 1
                self.logger.debug(f"Batch {idx} failed to export.")

        # Provide a consolidated summary
        if failure_count > 0:
            self.console.print(
                f"[red]Batch processing completed with {failure_count} failures and {success_count} successes.[/red]"
            )
            self.logger.warning(
                f"Batch processing completed with {failure_count} failures and {success_count} successes."
            )
        else:
            self.console.print(
                f"[green]Success: All {success_count} InfluxDB batches exported successfully.[/green]"
            )
            self.logger.info(
                f"All {success_count} InfluxDB batches exported successfully."
            )

        return success_count, failure_count

    @timeit
    @retry(max_retries=3, backoff=2.0)
    def export_to_prometheus(
        self,
        metric_name: str,
        value: Any,
        labels: Optional[Dict[str, str]] = None
    ):
        """
        Export a single metric to Prometheus.

        This method creates a Prometheus gauge metric with the specified name, value, and labels,
        then pushes it to the configured Prometheus Pushgateway. It employs a retry mechanism
        to handle transient failures.

        Args:
            metric_name (str): The name of the Prometheus metric to export.
            value (Any): The value of the metric. Typically numeric.
            labels (Optional[Dict[str, str]]): A dictionary of labels associated with the metric.
                Defaults to None.

        Returns:
            None

        Raises:
            Exception: Propagates exceptions encountered during the export process.
        """
        if "prometheus" not in self.outputs:
            return  # Skip Prometheus export entirely if not requested

        if not self.prometheus_config:
            self.logger.error("Prometheus configuration is missing. Skipping export.")
            return
        try:
            self.logger.debug(
                f"Exporting data to Prometheus: {metric_name}, value={value}, labels={labels}"
            )
            registry = CollectorRegistry()
            gauge = Gauge(
                metric_name,
                "Metric exported to Prometheus",
                labels.keys() if labels else [],
                registry=registry
            )
            if labels:
                gauge.labels(**labels).set(value)
            else:
                gauge.set(value)
            push_to_gateway(
                self.prometheus_config["gateway"],
                job=self.prometheus_config["job"],
                registry=registry
            )
            self.logger.info(f"Data exported to Prometheus successfully: {metric_name}")
        except Exception as e:
            self.logger.error(f"Failed to export {metric_name} to Prometheus: {e}")
            raise e

