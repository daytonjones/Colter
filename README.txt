Colter is a robust GitHub and PyPI tracker designed to monitor repositories and packages, providing insightful metrics and exporting them to InfluxDB and Prometheus. Named after John Colter, a renowned tracker from the Lewis and Clark Expedition, Colter ensures you stay updated with the latest developments in your projects and dependencies.

Features
GitHub Tracking: Monitor your GitHub repositories for issues, forks, branches, followers, and more.
PyPI Tracking: Keep track of your PyPI packages' download statistics and overall performance.
Export Capabilities: Seamlessly export metrics to InfluxDB for time-series analysis and Prometheus for monitoring.
Session Caching: Securely cache user authentication for 30 minutes to enhance user experience without compromising security.
Daemon Mode: Run Colter as a background service, executing tasks at regular intervals.
Verbose Logging: Gain insights into Colter's operations with adjustable logging levels.
Secure Password Handling: Utilize robust encryption and secure storage for managing master passwords.

Installation

Prerequisites
Python 3.8+
pip (Python package installer)

Steps
Clone the Repository:

   git clone https://github.com/daytonjones/colter.git
   cd colter
Create a Virtual Environment (Optional but Recommended):

   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
Install Dependencies:

   
   pip install -r requirements.txt
Set Up Configuration:

   Generate the default configuration file.

   
   python colter.py --generate-config

   You'll be prompted to enter a master password. This password is crucial for encrypting and decrypting your configuration data - keeping passwords and API tokens secure on disk.

Configuration

Colter uses a YAML configuration file located at /.colterconfig.yaml. This file contains settings for GitHub tracking, PyPI tracking, SMTP settings, InfluxDB, and Prometheus integrations.

Sample Configuration

github:
  token: <encrypted token string>
pypi:
  packages:
simply-useful
requests
influxdb:
  url: http://influx.somedomain.com:8086
  org: MONITOR
  bucket: ProjectTracker
  token: <encrypted token string>
prometheus:
  gateway: http://prometheus.somedomain.com:9091
  job: ProjectTracker
smtp:
  smtpserver: smtp.gmail.com
  smtpport: '587'
  username: yourusername@gmail.com
  password: <encrypted password>
  sender: user@nowhere.org
  recipient: recipient@somedomain.com

Note: Sensitive information like tokens should be handled securely. Colter encrypts the configuration using your master password.

Usage

Authentication

Colter employs a session caching mechanism to enhance user experience. When you run Colter:
First Run:
You'll be prompted to enter your master password.
Colter encrypts and caches this password securely for 30 minutes.
Subsequent Runs Within 30 Minutes:
Colter uses the cached session.
No need to re-enter the master password.
After 30 Minutes:
The session expires.
You'll be prompted to enter the master password again.
Logout:
Use the --logout flag to manually clear the cached session.

Commands and Arguments


usage: colter.py [-g] [-t {github,pypi,all}] [-o {influx,prometheus} ...] [--test-email] [-v] [--dry-run] [--schedule SCHEDULE] [-h] [--logout]

Colter: A GitHub and PyPI Tracker with Export Capabilities

optional arguments:
g, --generate-config  Generate or update the configuration file.
t {github,pypi,all}, --type {github,pypi,all}
                        Specify the tracking type.
o {influx,prometheus} ..., --output {influx,prometheus} ...
                        Specify the output format(s) for metrics.
-test-email           Inject fake issue to test email alerts.
v, --verbose          Increase output verbosity.
-dry-run              Simulate actions without performing exports or sending emails.
-schedule SCHEDULE    Run the script in daemon mode, executing every X minutes.
h, --help             Show this help message and exit.
-logout               Clear the cached session and logout.

Examples
Run Colter Normally:

   
   python colter.py
Specify Tracking Type and Output:

   
   python colter.py -t github -o influx prometheus
Enable Verbose Logging:

   
   python colter.py --verbose
Run in Daemon Mode (Every 15 Minutes):

   
   python colter.py --schedule 15
Simulate Actions Without Executing:

   
   python colter.py --dry-run
Logout and Clear Cached Session:

   
   python colter.py --logout

Daemon Mode

Run Colter as a background service that executes tasks at specified intervals.


python colter.py --schedule 30

This command runs Colter every 30 minutes, automating data collection and export processes.

Session Management

Colter securely caches user authentication for 30 minutes using the OS keyring service via the keyring library. This mechanism enhances user experience by reducing the frequency of password prompts without compromising security.

How It Works
Session Creation:
After successful authentication, Colter stores the master password and a timestamp in the system keyring.
Session Validation:
On subsequent runs, Colter checks if a valid session exists (i.e., within the last 30 minutes).
If valid, it uses the cached master password.
If expired or absent, it prompts for the master password again.
Logout:
Use the --logout flag to manually clear the cached session.

Security Considerations
Secure Storage: The master password is stored securely using the system's keyring service, ensuring it isn't exposed in plaintext.
Session Expiration: Sessions expire after 30 minutes, balancing convenience and security.
Manual Logout: Users can clear sessions at any time to prevent unauthorized access.

Export Options

Colter supports exporting metrics to InfluxDB and Prometheus, enabling comprehensive monitoring and analysis.

InfluxDB

InfluxDB is a time-series database ideal for storing and querying large volumes of metrics data.

Configuration:

Ensure your InfluxDB settings are correctly specified in the configuration file.  Colter will correctly format the metrics for InfluxDB2, using Flux (not compatible with Influx V1 query language).  So you will need a bucket and API key with permissions to write to it.

Exported Metrics:
GitHub:
Forks
Branches
Followers
Downloads
Last Push
PyPI:
Recent Downloads (Day, Week, Month)
Overall Downloads

Prometheus

Prometheus is a powerful monitoring and alerting toolkit widely used for system and application monitoring.

Configuration:

Ensure your Prometheus gateway settings are correctly specified in the configuration file.

prometheus:
  gateway: http://localhost:9091
  job: pypiexporter

Exported Metrics:
GitHub:
Forks
Branches
Followers
Downloads
Last Push
PyPI:
Overall Downloads

Testing

Colter includes a comprehensive test suite to ensure reliability and stability. To run the tests:


pytest tests/

All tests should pass, indicating that the core functionalities are working as expected.

Logging

Colter employs robust logging mechanisms to track its operations and assist in debugging.
Log Files:
Located at /colter.log.
Utilizes a rotating file handler (5 MB per file, 5 backups).
Console Logging:
Warnings and above are displayed in the console using Rich for enhanced readability.
Verbose Mode:
Enable verbose logging with the --verbose flag to capture debug-level logs.

Contributing

Contributions are welcome! If you'd like to contribute to Colter, please follow these steps:
Fork the Repository:

   Click the "Fork" button at the top right of the repository page.
Clone Your Fork:

   
   git clone https://github.com/daytonjones/colter.git
   cd colter
Create a New Branch:

   
   git checkout -b feature/YourFeatureName
Make Your Changes and Commit:

   
   git commit -m "Add your feature"
Push to Your Fork:

   
   git push origin feature/YourFeatureName
Create a Pull Request:

   Navigate to your fork on GitHub and click "Compare & pull request."

Reporting Issues

If you encounter any bugs or have suggestions for improvements, please open an issue in the  section.

License

Distributed under the .

Contact
Project Link: 
Email: jones.dayton@gmail.com
--
