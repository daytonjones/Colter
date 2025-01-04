# Colter

<div align="center">
    <img src="https://github.com/daytonjones/colter/blob/main/assets/colter.png?raw=true" alt="Colter Logo">
</div>


**Colter** is a robust GitHub and PyPI tracker designed to monitor repositories and packages, providing insightful metrics and exporting them to InfluxDB and Prometheus. Named after John Colter, a renowned tracker from the Lewis and Clark Expedition, Colter ensures you stay updated with the latest developments in your projects and dependencies.

<div align="center">
    <img src="https://github.com/daytonjones/colter/blob/main/assets/feature_overview.png?raw=true" alt="Colter Logo">
</div>


## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
  - [Authentication](#authentication)
  - [Commands and Arguments](#commands-and-arguments)
  - [Daemon Mode](#daemon-mode)
  - [Logout](#logout)
- [Session Management](#session-management)
- [Export Options](#export-options)
  - [InfluxDB](#influxdb)
  - [Prometheus](#prometheus)
- [Testing](#testing)
- [Logging](#logging)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)

## Features

- **GitHub Tracking:** Monitor your GitHub repositories for issues, forks, branches, followers, and more.
- **PyPI Tracking:** Keep track of your PyPI packages' download statistics and overall performance.
- **Export Capabilities:** Seamlessly export metrics to InfluxDB for time-series analysis and Prometheus for monitoring.
- **Session Caching:** Securely cache user authentication for 30 minutes to enhance user experience without compromising security.
- **Daemon Mode:** Run Colter as a background service, executing tasks at regular intervals.
- **Verbose Logging:** Gain insights into Colter's operations with adjustable logging levels.
- **Secure Password Handling:** Utilize robust encryption and secure storage for managing master passwords.

## Installation

### Prerequisites

- **Python 3.8+**
- **pip** (Python package installer)

### Steps

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/daytonjones/colter.git
   cd colter
   ```

2. **Create a Virtual Environment (Optional but Recommended):**

   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Set Up Configuration:**

   Generate the default configuration file.

   ```bash
   python colter.py --generate-config
   ```

   You'll be prompted to enter a master password. This password is crucial for encrypting and decrypting your configuration data - keeping passwords and API tokens secure on disk.

## Configuration

Colter uses a YAML configuration file located at `~/.colter_config.yaml`. This file contains settings for GitHub tracking, PyPI tracking, SMTP settings, InfluxDB, and Prometheus integrations.

### Sample Configuration

```yaml
github:
  token: <encrypted token string>
pypi:
  packages:
  - simply-useful
  - requests
influxdb:
  url: http://influx.somedomain.com:8086
  org: MONITOR
  bucket: ProjectTracker
  token: <encrypted token string>
prometheus:
  gateway: http://prometheus.somedomain.com:9091
  job: ProjectTracker
smtp:
  smtp_server: smtp.gmail.com
  smtp_port: '587'
  username: yourusername@gmail.com
  password: <encrypted password>
  sender: user@nowhere.org
  recipient: recipient@somedomain.com

```

**Note:** Sensitive information like tokens should be handled securely. Colter encrypts the configuration using your master password.

## Usage

### Authentication

Colter employs a session caching mechanism to enhance user experience. When you run Colter:

1. **First Run:**
   - You'll be prompted to enter your master password.
   - Colter encrypts and caches this password securely for 30 minutes.

2. **Subsequent Runs Within 30 Minutes:**
   - Colter uses the cached session.
   - No need to re-enter the master password.

3. **After 30 Minutes:**
   - The session expires.
   - You'll be prompted to enter the master password again.

4. **Logout:**
   - Use the `--logout` flag to manually clear the cached session.

### Commands and Arguments

```bash
usage: colter.py [-g] [-t {github,pypi,all}] [-o {influx,prometheus} ...] [--test-email] [-v] [--dry-run] [--schedule SCHEDULE] [-h] [--logout]

Colter: A GitHub and PyPI Tracker with Export Capabilities

optional arguments:
  -g, --generate-config  Generate or update the configuration file.
  -t {github,pypi,all}, --type {github,pypi,all}
                        Specify the tracking type.
  -o {influx,prometheus} ..., --output {influx,prometheus} ...
                        Specify the output format(s) for metrics.
  --test-email           Inject fake issue to test email alerts.
  -v, --verbose          Increase output verbosity.
  --dry-run              Simulate actions without performing exports or sending emails.
  --schedule SCHEDULE    Run the script in daemon mode, executing every X minutes.
  -h, --help             Show this help message and exit.
  --logout               Clear the cached session and logout.
```

### Examples

1. **Run Colter Normally:**

   ```bash
   python colter.py
   ```

2. **Specify Tracking Type and Output:**

   ```bash
   python colter.py -t github -o influx prometheus
   ```

3. **Enable Verbose Logging:**

   ```bash
   python colter.py --verbose
   ```

4. **Run in Daemon Mode (Every 15 Minutes):**

   ```bash
   python colter.py --schedule 15
   ```

5. **Simulate Actions Without Executing:**

   ```bash
   python colter.py --dry-run
   ```

6. **Logout and Clear Cached Session:**

   ```bash
   python colter.py --logout
   ```

### Daemon Mode

Run Colter as a background service that executes tasks at specified intervals.

```bash
python colter.py --schedule 30
```

This command runs Colter every 30 minutes, automating data collection and export processes.

## Session Management

Colter securely caches user authentication for 30 minutes using the OS keyring service via the `keyring` library. This mechanism enhances user experience by reducing the frequency of password prompts without compromising security.

### How It Works

1. **Session Creation:**
   - After successful authentication, Colter stores the master password and a timestamp in the system keyring.

2. **Session Validation:**
   - On subsequent runs, Colter checks if a valid session exists (i.e., within the last 30 minutes).
   - If valid, it uses the cached master password.
   - If expired or absent, it prompts for the master password again.

3. **Logout:**
   - Use the `--logout` flag to manually clear the cached session.

### Security Considerations

- **Secure Storage:** The master password is stored securely using the system's keyring service, ensuring it isn't exposed in plaintext.
- **Session Expiration:** Sessions expire after 30 minutes, balancing convenience and security.
- **Manual Logout:** Users can clear sessions at any time to prevent unauthorized access.

## Export Options

Colter supports exporting metrics to **InfluxDB** and **Prometheus**, enabling comprehensive monitoring and analysis.

### InfluxDB

**InfluxDB** is a time-series database ideal for storing and querying large volumes of metrics data.

**Configuration:**

Ensure your InfluxDB settings are correctly specified in the configuration file.  Colter will correctly format the metrics for InfluxDB2, using Flux (not compatible with Influx V1 query language).  So you will need a bucket and API key with permissions to write to it.

**Exported Metrics:**

- **GitHub:**
  - Forks
  - Branches
  - Followers
  - Downloads
  - Last Push

- **PyPI:**
  - Recent Downloads (Day, Week, Month)
  - Overall Downloads

### Prometheus

**Prometheus** is a powerful monitoring and alerting toolkit widely used for system and application monitoring.

**Configuration:**

Ensure your Prometheus gateway settings are correctly specified in the configuration file.

```yaml
prometheus:
  gateway: http://localhost:9091
  job: pypi_exporter
```

**Exported Metrics:**

- **GitHub:**
  - Forks
  - Branches
  - Followers
  - Downloads
  - Last Push

- **PyPI:**
  - Overall Downloads

## Testing

Colter includes a comprehensive test suite to ensure reliability and stability. To run the tests:

```bash
pytest tests/
```

All tests should pass, indicating that the core functionalities are working as expected.

## Logging

Colter employs robust logging mechanisms to track its operations and assist in debugging.

- **Log Files:**
  - Located at `~/colter.log`.
  - Utilizes a rotating file handler (5 MB per file, 5 backups).

- **Console Logging:**
  - Warnings and above are displayed in the console using Rich for enhanced readability.

- **Verbose Mode:**
  - Enable verbose logging with the `--verbose` flag to capture debug-level logs.

## Contributing

Contributions are welcome! If you'd like to contribute to Colter, please follow these steps:

1. **Fork the Repository:**

   Click the "Fork" button at the top right of the repository page.

2. **Clone Your Fork:**

   ```bash
   git clone https://github.com/daytonjones/colter.git
   cd colter
   ```

3. **Create a New Branch:**

   ```bash
   git checkout -b feature/YourFeatureName
   ```

4. **Make Your Changes and Commit:**

   ```bash
   git commit -m "Add your feature"
   ```

5. **Push to Your Fork:**

   ```bash
   git push origin feature/YourFeatureName
   ```

6. **Create a Pull Request:**

   Navigate to your fork on GitHub and click "Compare & pull request."

### Reporting Issues

If you encounter any bugs or have suggestions for improvements, please open an issue in the [Issues](https://github.com/daytonjones/colter/issues) section.

## License

Distributed under the [MIT License](LICENSE).

## Contact

- **Project Link:** [https://github.com/daytonjones/colter](https://github.com/daytonjones/colter)
- **Email:** jones.dayton@gmail.com

---



