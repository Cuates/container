"""
Docker Compose Manager & Firewall Auditor

This script orchestrates container lifecycle operations and validates firewall conditions
for Docker environments. It includes:

- Docker Compose controls (`up`, `down`, pruning, network setup)
- Firewall auditing with PowerShell integration for:
    • Active network profile detection
    • Docker backend rule enforcement
    • Port 80/443 inbound rule checks
- Modular configuration loading from YAML
- Structured logging with rotating log files
- Runtime diagnostics including Docker daemon availability

Designed for Windows platforms running Docker and PowerShell.

Usage:
    python docker_compose_manager.py

Dependencies:
    - Docker Desktop
    - PyYAML
    - tqdm
    - alive-progress

Installation:
    Ensure you have Docker installed and running on your machine.
    Install the required Python package:
        - pip install PyYAML
        - pip install alive-progress
        - pip install tqdm
"""
import platform
import subprocess
import json
import time
from datetime import datetime, timedelta
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple, Callable, Optional
import re
import sys
import yaml
from yaml import YAMLError
from alive_progress import alive_it
from tqdm import tqdm

REQUIRED_PORTS = [80, 443]

FIREWALL_PROFILE_MAP = {
    "1": "Domain",
    "2": "Private",
    "3": "Domain,Private",
    "4": "Public",
    "5": "Domain,Public",
    "6": "Private,Public",
    "7": "Domain,Private,Public"
}

def setup_logging() -> None:
    """
    Configure console + file logging with custom formatting.

    Console: colorized output using RGB
    File: plaintext logs with timestamp and level
    """
    script_path = Path(__file__).resolve()
    log_file = script_path.parent / f"{script_path.stem}.log"

    # File logger
    file_handler = RotatingFileHandler(log_file, maxBytes=1024 * 1024, backupCount=5, encoding="utf-8")
    file_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(file_format)

    # Console logger with custom RGB wrapper
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(message)s"))  # raw text; color added by apply_log_color()

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # script_path = Path(__file__).resolve()
    # log_file = script_path.parent / f"{script_path.stem}.log"

    # handler = RotatingFileHandler(log_file, maxBytes=1024*1024, backupCount=5, encoding='utf-8')
    # formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    # handler.setFormatter(formatter)

    # logger = logging.getLogger()
    # logger.addHandler(handler)
    # logger.setLevel(logging.INFO)
    # # logger.setLevel(logging.DEBUG)

def rgb_color(r: int, g: int, b: int, text: str) -> str:
    """
    Format terminal output using ANSI escape sequences for RGB color text.

    Args:
        r (int): Red component (0-255)
        g (int): Green component (0-255)
        b (int): Blue component (0-255)
        text (str): The text to colorize

    Returns:
        str: The color-formatted string for console display
    """
    return f"\033[38;2;{r};{g};{b}m{text}\033[0m"

class DockerComposeManager:
    """
    Manages a single Docker Compose stack by wrapping Docker commands and project state.

    Attributes:
        docker_dir (Path): Root path of the Compose setup.
        compose_file (Path): Path to the Docker Compose YAML file.
        env_file (Path): Path to the .env file used with Compose.
    """
    def __init__(self, docker_dir: Path, compose_file: Path, env_file: Path):
        """
        Initialize a DockerComposeManager instance.

        Args:
            docker_dir (Path): Base directory for Compose configs.
            compose_file (Path): Relative path to compose YAML.
            env_file (Path): Relative path to .env file.
        """
        self.docker_dir = Path(docker_dir)
        self.compose_file = self.docker_dir / compose_file
        self.env_file = self.docker_dir / env_file

    def run_docker_compose(self, action: str, container_name: str) -> bool:
        """
        Run a docker compose action (up/down) for a specific container.

        Args:
            action (str): Either "up" or "down".
            container_name (str): The name of the service container to target.

        Returns:
            bool: True if the command succeeded, False otherwise.
        """
        cmd = [
            'docker', 'compose', '-f', str(self.compose_file),
            '--env-file', str(self.env_file), action
        ]
        if action == "up":
            cmd.extend(["-d", container_name])
        try:
            subprocess.run(cmd, stderr=subprocess.PIPE, check=True)
            logging.info("Successfully %sed container %s", action, container_name)
            return True
        except subprocess.CalledProcessError as e:
            logging.error("Error %s while %sing container %s: %s", e.returncode, action, container_name, e.stderr.strip())
            return False

    @staticmethod
    def check_container_status(container_name: str) -> bool:
        """
        Check if a container with the given name is currently present.

        Args:
            container_name (str): Docker container name.

        Returns:
            bool: True if the container is present, False otherwise.
        """
        cmd = ['docker', 'container', 'ls', '-a', '--format', '{{.Names}}', '--filter', f'name={container_name}']
        try:
            output = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            return output.stdout.strip() == container_name
        except subprocess.CalledProcessError as e:
            logging.error("Error %s checking container status: %s", e.returncode, e.stderr.strip())
            return False

    @staticmethod
    def prune_docker_images() -> bool:
        """
        Prune all unused Docker images to reclaim space.

        Returns:
            bool: True if prune succeeded, False otherwise.
        """
        try:
            result = run_command_with_spinner("Pruning Docker images", ["docker", "image", "prune", "-a", "-f"])

            if result:
                return True
            return False
        except subprocess.CalledProcessError as e:
            logging.error("Error %s while pruning Docker images: %s", e.returncode, e.stderr.strip())
            return False

    @staticmethod
    def ensure_docker_network(network_name: str) -> bool:
        """
        Ensure that a Docker internal network exists; create it if not.

        Args:
            network_name (str): Name of the Docker network.

        Returns:
            bool: True if it exists or is successfully created; False if creation failed.
        """
        try:
            networks = subprocess.run(
                ['docker', 'network', 'ls', '--format', '{{.Name}}'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
            )
            if network_name in networks.stdout.decode('utf-8').splitlines():
                logging.info("Docker network '%s' already exists.", network_name)
                return True

            sys.stdout.write("\n")
            _, _ = with_spinner_and_timer(
                f"Creating Docker network: {network_name}",
                lambda: subprocess.run(
                    ['docker', 'network', 'create', '--driver', 'bridge', network_name],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
                )
            )

            logging.info("Docker network '%s' created successfully.", network_name)
            return True

        except subprocess.CalledProcessError as e:
            msg = e.stderr.decode('utf-8').strip() if e.stderr else str(e)
            logging.error("Error ensuring network '%s': %s", network_name, msg)
            return False

def process_docker_configs(docker_configs: List[DockerComposeManager], action: str) -> None:
    """
    Perform Docker Compose actions ('up' or 'down') across multiple configurations.

    Displays:
        - Colored progress bar if multiple services
        - Spinner + per-container timing if single service
        - Summarized results with timing at the end

    Args:
        docker_configs (List[DockerComposeManager]): Compose manager instances.
        action (str): Either 'up' or 'down' to control container lifecycles.
    """
    errors = False
    all_timings: List[Tuple[str, float, bool]] = []
    total_start = datetime.now()

    for docker_config in docker_configs:
        try:
            with open(docker_config.compose_file, 'r', encoding='utf-8') as file:
                compose_data = yaml.safe_load(file)

            services = list(compose_data.get('services', {}))
            service_count = len(services)

            if service_count > 1:
                for service_name in tqdm(
                    services,
                    desc=f"{action.upper()} {docker_config.compose_file.name}",
                    unit="service",
                    colour="cyan"
                ):
                    sys.stdout.write("\n")
                    logging.info("%s %s...", "Taking down" if action == "down" else "Bringing up", service_name)

                    start = time.time()
                    success = container_task(docker_config, service_name, action)
                    duration = round(time.time() - start, 2)
                    all_timings.append((service_name, duration, success))

                    readable = format_time_delta(timedelta(seconds=duration))

                    logging.info("⏱️ %s completed in %s", service_name, readable)
                    if not success:
                        errors = True

            elif service_count == 1:
                service_name = services[0]
                sys.stdout.write("\n")
                logging.info("%s %s...", "Taking down" if action == "down" else "Bringing up", service_name)

                title = f"{action.capitalize()} {service_name}"
                success, duration = run_container_task_with_spinner(title, docker_config, service_name, action)

                all_timings.append((service_name, duration, success))
                readable = format_time_delta(timedelta(seconds=duration))
                logging.info("⏱️ %s completed in %s", service_name, readable)

                if not success:
                    errors = True

            else:
                logging.warning("No services found in %s", docker_config.compose_file.name)
        except FileNotFoundError as fnf:
            logging.error("Missing file: %s", fnf)
            errors = True
        except YAMLError as ye:
            logging.error("YAML parsing error in %s: %s", docker_config.compose_file, ye)
            errors = True
        except ValueError as ve:
            logging.error("Data validation error: %s", ve)
            errors = True
        except subprocess.SubprocessError as se:
            logging.error("Docker subprocess error: %s", se)
            errors = True

    total_elapsed = datetime.now() - total_start
    logging.info("🚀 Total container operation time: %s", format_time_delta(total_elapsed))

    # 📊 Show end-of-run dashboard
    if all_timings:
        logging.info("📊 Container Timing Summary:")
        for name, duration, success in sorted(all_timings, key=lambda x: x[1], reverse=True):
            status = "✅" if success else "❌"

            readable = format_time_delta(timedelta(seconds=duration))

            logging.info(" %s %-20s %s", status, name, readable)

    if errors:
        logging.error("⚠️ Errors occurred during '%s' operations.", action)
    else:
        logging.info("✅ All containers '%s'ed successfully.", action)

def container_task(docker_cfg: DockerComposeManager, svc_name: str, action: str) -> bool:
    """
    Task runner for a single Docker service action.

    Args:
        docker_cfg (DockerComposeManager): Compose manager instance.
        svc_name (str): Name of the service container.
        action (str): Docker action ('up' or 'down').

    Returns:
        bool: True if command succeeded or skipped; False if failed.
    """
    if action == "up" or DockerComposeManager.check_container_status(svc_name):
        return docker_cfg.run_docker_compose(action, svc_name)
    return True

def load_config(config_file: str) -> List[DockerComposeManager]:
    """
    Load external YAML configuration that defines Docker projects to manage.

    Args:
        config_file (str): Path to the YAML configuration file.

    Returns:
        List[DockerComposeManager]: Initialized list of managers for each project.
    """
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        return [
            DockerComposeManager(Path(cfg['docker_dir']), Path(cfg['compose_file']), Path(cfg['env_file']))
            for cfg in config_data.get('docker_configs', [])
        ]
    except FileNotFoundError:
        logging.error("Config file not found: %s", config_file)
        return []
    except PermissionError:
        logging.error("Permission denied when accessing: %s", config_file)
        return []
    except yaml.YAMLError as e:
        logging.error("Error parsing YAML from config file: %s", e)
        return []

def check_docker_running() -> bool:
    """
    Check if the Docker daemon is active by running `docker info`.

    Returns:
        bool: True if Docker is responsive; False otherwise.
    """
    try:
        result = run_command_with_spinner("Checking Docker daemon", ["docker", "info"])

        if result:
            logging.info("Docker daemon is active.")
            return True

        logging.error("Docker is not running or unresponsive.")
        return False
    except subprocess.CalledProcessError as e:
        stderr_msg = e.stderr.strip() if e.stderr else str(e)
        logging.error("Docker is not running or not responding: %s", stderr_msg)
        return False
    except FileNotFoundError:
        logging.error("Docker command not found. Is Docker installed and on your system PATH?")
        return False

def parse_firewall_profiles(profiles: list) -> Dict[str, bool]:
    """
    Extract enabled status for Public and Private firewall profiles.

    Args:
        profiles: List of profile dictionaries from PowerShell output.

    Returns:
        Dict[str, bool]: Profile name → Enabled (True/False)
    """
    return {p["Name"]: p["Enabled"].lower() == "true" for p in profiles}

def extract_profiles_from_rules(rules: list) -> Set[str]:
    """
    Extract unique profile names from a list of rules.

    Args:
        rules: List of firewall rules with profile strings.

    Returns:
        Set[str]: All unique profiles from all rules.
    """
    profile_set = set()
    for rule in rules:
        for p in rule.get("Profile", "").split(","):
            profile_set.add(p.strip())
    return profile_set

def check_required_ports_exist(port_rules: list) -> Dict[int, Dict[str, Any]]:
    """
    Evaluate firewall rules for required ports.

    Args:
        port_rules: List of parsed port-related firewall rules.

    Returns:
        Dict[int, Dict[str, Any]]: Details for each required port.
    """
    # 🌐 Port rule analysis
    port_evaluation = {}

    for port in REQUIRED_PORTS:
        try:
            result = {
                "found": False,
                "enabled": False,
                "action": "",
                "all_profiles": False,
                "matched_rules": [],
                "profiles": set()
            }

            for rule in port_rules:
                raw_port = rule.get("LocalPort")

                # Handle both string and object case
                ports = []
                if isinstance(raw_port, dict) and "value" in raw_port:
                    ports = raw_port["value"]
                elif isinstance(raw_port, str):
                    ports = [raw_port]

                if str(port) not in ports:
                    continue  # This rule doesn't match the port we care about

                result["found"] = True
                result["matched_rules"].append(rule.get("DisplayName", rule.get("Name", "Unnamed")))

                if rule.get("Enabled", "").lower() == "true":
                    result["enabled"] = True

                action = rule.get("Action", "").strip().lower()
                if action in {"allow", "block"}:
                    result["action"] = action.capitalize()
                elif result["action"] == "":
                    result["action"] = "Unknown"

                profiles_set = {p.strip() for p in rule.get("Profile", "").split(",")}
                result["profiles"].update(profiles_set)

                if {"Domain", "Private", "Public"}.issubset(profiles_set) or "Any" in profiles_set:
                    result["all_profiles"] = True

            port_evaluation[port] = result
        except (TypeError, ValueError):
            continue
    return port_evaluation

def evaluate_firewall_conditions(
    data: Dict[str, Any],
    enforce_active_profile: bool,
    enforce_docker_backend: bool,
    enforce_ports: bool
) -> bool:
    """
    Orchestrates modular evaluation of firewall conditions.

    Args:
        data (Dict[str, Any]): Parsed JSON output from PowerShell.
        enforce_active_profile (bool): Enforce that the active network profile is enabled.
        enforce_docker_backend (bool): Check Docker backend rule scope for Public and Private profiles.
        enforce_ports (bool): Check inbound TCP port rules for ports 80 and 443.

    Returns:
        bool: True if all enabled checks pass without blocked rules; False otherwise.
    """
    raw_profile = data.get("ActiveProfile", "")
    active_profile = str(raw_profile).capitalize() if isinstance(raw_profile, (str, int)) else ""

    profiles_ok = evaluate_active_profile(data, active_profile) if enforce_active_profile else True
    docker_ok, has_blocked = evaluate_docker_rules(data) if enforce_docker_backend else (True, False)
    ports_ok = evaluate_port_rules(data) if enforce_ports else True

    return all([profiles_ok, docker_ok, ports_ok]) and not has_blocked

def evaluate_active_profile(data: Dict[str, Any], active_profile: str) -> bool:
    """
    Validates whether the currently active firewall profile is enabled.

    Args:
        data (Dict[str, Any]): Parsed JSON containing firewall profile states.
        active_profile (str): Normalized profile name ("Public", "Private", "Domain").

    Returns:
        bool: True if the active profile is enabled; False if disabled or missing.
    """
    profiles = parse_firewall_profiles(data.get("Profiles", []))
    status = profiles.get(active_profile, False)

    logging.info("[NETWORK] Active Network Profile: %s", active_profile)
    logging.info("  %s: %s", active_profile, "✅ Enabled" if status else "❌ Disabled")

    return status

def evaluate_docker_rules(data: Dict[str, Any]) -> Tuple[bool, bool]:
    """
    Evaluates Docker backend firewall rules across Public and Private profiles.

    Args:
        data (Dict[str, Any]): Parsed JSON containing Docker firewall rules.

    Returns:
        Tuple[bool, bool]:
            - bool: True if all profiles contain at least one enabled 'Allow' rule.
            - bool: True if any enabled 'Block' rule exists; used for failure detection.
    """
    allowed = {}
    blocked = {}

    for rule in data.get("DockerRules", []):
        if rule.get("Enabled", "").lower() != "true":
            continue
        action = rule.get("Action", "").lower()
        if action not in {"allow", "block"}:
            continue

        raw_name = rule.get("Name", "")
        profile = rule.get("Profile", "").strip().capitalize()
        display_base = rule.get("DisplayName", "Docker Desktop Backend")
        conn_match = re.match(r"^(.*?)(?:\{.*|\s*C:\\.*)?$", raw_name)
        conn_type = conn_match.group(1).strip() if conn_match else ""
        label = f"{display_base} {conn_type}"

        (allowed if action == "allow" else blocked).setdefault(profile, []).append(label)

    docker_ok = all(profile in allowed and allowed[profile] for profile in ("Public", "Private"))
    has_blocked = any(blocked.get(profile) for profile in ("Public", "Private"))

    logging.info("[FIREWALL] Docker Backend Rule Scope:")
    for profile in ("Public", "Private"):
        if allowed.get(profile):
            logging.info("  %s: ✅ Allow", profile)
            for rule in allowed[profile]:
                logging.info("    → %s", rule)
        if blocked.get(profile):
            logging.info("  %s: 🚫 Block", profile)
            for rule in blocked[profile]:
                logging.info("    → %s", rule)
        if not allowed.get(profile) and not blocked.get(profile):
            logging.info("  %s: ❌ No Rules Found", profile)

    return docker_ok, has_blocked

def evaluate_port_rules(data: Dict[str, Any]) -> bool:
    """
    Assesses inbound TCP firewall rules for ports 80 and 443.

    Args:
        data (Dict[str, Any]): Parsed JSON containing port rule metadata.

    Returns:
        bool: True if both ports are allowed, enabled, and scoped to all profiles; False otherwise.
    """
    ports = check_required_ports_exist(data.get("PortRules", []))

    logging.info("[FIREWALL] Inbound Port Rules:")
    for port, status in ports.items():
        icon = "✅" if all((
            status["found"],
            status["enabled"],
            status["action"] == "Allow",
            status["all_profiles"]
        )) else "❌"

        logging.info("  Port %s: %s", port, icon)
        logging.info("    Enabled: %s", "Yes" if status["enabled"] else "No")
        logging.info("    Action: %s", status["action"])
        if status["all_profiles"]:
            logging.info("    Applies to Profiles: All")
        else:
            p_str = ",".join(status["profiles"]) if status["profiles"] else "None"
            logging.info("    Applies to Profile(s): %s", p_str)
        matched = ", ".join(status["matched_rules"]) if status["matched_rules"] else "None"
        logging.info("    Matched Rules: %s", matched)

    return all(
        status["found"] and
        status["enabled"] and
        status["action"] == "Allow" and
        status["all_profiles"]
        for status in ports.values()
    )

def check_docker_firewall(
    enforce_docker_backend: bool = True,
    enforce_ports: bool = True,
    enforce_active_profile: bool = True
) -> bool:
    """
    Extract and evaluate Windows Firewall metadata using PowerShell.

    Execution is conditional based on provided enforcement flags:
        - Active network profile state
        - Docker backend firewall rules
        - Inbound TCP ports (80/443)

    Returns:
        bool: True if all enforced rules are valid; False otherwise.
    """

    if platform.system() != "Windows":
        logging.info("[INFO] Skipping firewall check: not running on Windows.")
        return True

    # 🔍 Build PowerShell blocks conditionally
    ps_blocks = [
        # Shared function always included
        r"""
        function Convert-FirewallProfile {
            param([int]$Profile)
            switch ($Profile) {
                1 { return "Domain" }
                2 { return "Private" }
                3 { return "Domain,Private" }
                4 { return "Public" }
                5 { return "Domain,Public" }
                6 { return "Private,Public" }
                7 { return "Domain,Private,Public" }
                0 { return "Any" }
                default { return "Unspecified" }
            }
        }
        """
    ]

    # 🌐 Active network profile detection
    if enforce_active_profile:
        ps_blocks.append(r"""
        $rawProfile = (Get-NetConnectionProfile | Select-Object -First 1).NetworkCategory
        $activeProfile = switch ($rawProfile) {
            "Public"              { "Public" }
            "Private"             { "Private" }
            "DomainAuthenticated" { "Domain" }
            0                     { "Public" }
            1                     { "Private" }
            2                     { "Domain" }
            default               { "Unspecified" }
        }

        $profiles = Get-NetFirewallProfile | ForEach-Object {
            [PSCustomObject]@{
                Name    = [string]$_.Name
                Enabled = [string]$_.Enabled
            }
        }
        """)

    if enforce_docker_backend:
        ps_blocks.append(r"""
        $dockerRules = Get-NetFirewallRule -Direction Inbound |
            Where-Object {
                ($_ | Get-NetFirewallApplicationFilter).Program -like "*com.docker.backend.exe"
            } | ForEach-Object {
                [PSCustomObject]@{
                    Name        = [string]$_.Name
                    DisplayName = [string]$_.DisplayName
                    Enabled     = [string]$_.Enabled
                    Action      = [string]$_.Action
                    Profile     = Convert-FirewallProfile -Profile $_.Profile
                }
            }
        """)

    if enforce_ports:
        ps_blocks.append(r"""
        $portRules = @()
        $inboundRules = Get-NetFirewallRule -Direction Inbound | Where-Object {
            $_.Name -match "^\{.*\}$" -or $_.Group -eq $null
        }
        foreach ($rule in $inboundRules) {
            $portFilters = $rule | Get-NetFirewallPortFilter
            foreach ($portFilter in $portFilters) {
                if ($portFilter.Protocol -eq "TCP" -and ($portFilter.LocalPort -eq 80 -or $portFilter.LocalPort -eq 443)) {
                    $decodedProfile = Convert-FirewallProfile -Profile $rule.Profile
                    $portRules += [PSCustomObject]@{
                        Name        = [string]$rule.Name
                        DisplayName = [string]$rule.DisplayName
                        Enabled     = [string]$rule.Enabled
                        Action      = [string]$rule.Action
                        Profile     = $decodedProfile
                        Protocol    = [string]$portFilter.Protocol
                        LocalPort   = [string]$portFilter.LocalPort
                    }
                }
            }
        }
        """)

    # 🧩 Final JSON Output Block
    output_parts = []
    if enforce_active_profile:
        output_parts.append("ActiveProfile = $activeProfile")
        output_parts.append("Profiles = $profiles")
    if enforce_docker_backend:
        output_parts.append("DockerRules = $dockerRules")
    if enforce_ports:
        output_parts.append("PortRules = $portRules")

    # If nothing is requested, skip execution entirely
    if not output_parts:
        logging.info("[NETWORK/FIREWALL] Skipping network/firewall PowerShell execution — no checks enabled.")
        return True

    ps_script = "\n".join(ps_blocks) + "\n" + "[PSCustomObject]@{\n    " + "\n    ".join(output_parts) + "\n} | ConvertTo-Json -Depth 3"

    logging.info("[NETWORK/FIREWALL] Extracting network/firewall metadata...")

    try:
        result, duration = run_command_with_spinner("Extracting network/firewall metadata", ["powershell", "-Command", ps_script])
        if not result:
            return False

        readable = format_time_delta(timedelta(seconds=duration))

        logging.info("Network/Firewall metadata extracted in %s", readable)

        data = json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        msg = e.stderr.strip() if e.stderr else str(e)
        logging.error("[FIREWALL] ❌ PowerShell execution failed: %s", msg)
        return False
    except json.JSONDecodeError as e:
        logging.error("[FIREWALL] ❌ Failed to parse firewall output as JSON: %s", e)
        return False

    return evaluate_firewall_conditions(
        data=data,
        enforce_active_profile=enforce_active_profile,
        enforce_docker_backend=enforce_docker_backend,
        enforce_ports=enforce_ports
    )

@staticmethod
def format_time_delta(td: timedelta) -> str:
    """
    Format a timedelta object into a human-readable string.

    Args:
        td (timedelta): The timedelta object to format.

    Returns:
        str: A human-readable string representation of the time delta.
    """
    years, remainder = divmod(td.days, 365)
    months, days = divmod(remainder, 30)
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = td.microseconds // 1000

    parts = []
    if years > 0:
        parts.append(f"{years} year{'s' if years > 1 else ''}")
    if months > 0:
        parts.append(f"{months} month{'s' if months > 1 else ''}")
    if days > 0:
        parts.append(f"{days} day{'s' if days > 1 else ''}")
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours > 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes > 1 else ''}")

    no_larger_units = all(x == 0 for x in (years, months, days, hours, minutes))
    if seconds > 0 or no_larger_units:
        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
    if milliseconds > 0:
        parts.append(f"{milliseconds} millisecond{'s' if milliseconds != 1 else ''}")

    return ", ".join(parts)

def with_spinner_and_timer(title: str, func: Callable[[], Any]) -> Tuple[Any, float]:
    """
    Run a callable function with a live spinner and timing feedback.

    Args:
        title (str): Spinner label shown to the user.
        func (Callable): A callable that returns a result.

    Returns:
        Tuple: (result of the function, elapsed time in seconds)
    """
    start = time.time()

    for _ in alive_it(range(1), title=title, spinner="dots_waves"):
        result = func()

    elapsed = round(time.time() - start, 2)
    readable = format_time_delta(timedelta(seconds=elapsed))

    logging.info("⏱️ Elapsed time for '%s': %s", title, readable)

    return result, elapsed

def run_command_with_spinner(
    description: str,
    command: List[str],
    log_output: bool = False
) -> Tuple[Optional[subprocess.CompletedProcess], float]:
    """
    Execute a subprocess command with a live spinner and optional log classification.

    Args:
        description (str): Spinner label shown to the user.
        command (List[str]): Subprocess command list.
        log_output (bool): Whether to log stdout/stderr lines with classified colors.

    Returns:
        Tuple: (CompletedProcess result, elapsed time in seconds), or (None, 0.0) if failed.
    """
    try:
        result, duration = with_spinner_and_timer(description, lambda: subprocess.run(
            command, capture_output=True, text=True, check=True
        ))

        if log_output:
            for line in result.stdout.strip().splitlines():
                severity = classify_log_severity(line)
                colorized = apply_log_color(severity, line)
                timestamp = datetime.now().strftime("%H:%M:%S")

                # ✅ Console color
                print(f"[{timestamp}] {colorized}")

                # ✅ File log (plaintext)
                logging.info(line)

            if result.stderr:
                for line in result.stderr.strip().splitlines():
                    severity = classify_log_severity(line)
                    colorized = apply_log_color(severity, line)
                    timestamp = datetime.now().strftime("%H:%M:%S")

                    print(f"[{timestamp}] {colorized}")
                    logging.warning(line)

        return result, duration
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else str(e)
        colored_error = apply_log_color("ERROR", error_msg)
        logging.error("%s failed: %s", description, colored_error)
        return None, 0.0

def run_container_task_with_spinner(
    title: str,
    docker_cfg: DockerComposeManager,
    svc_name: str,
    action: str
) -> Tuple[bool, float]:
    """
    Run a container task using a spinner and return result with elapsed time.

    Returns:
        Tuple: (success status, elapsed time in seconds)
    """
    def task_runner():
        return container_task(docker_cfg, svc_name, action)

    result, duration = with_spinner_and_timer(title, task_runner)
    return result, duration

def classify_log_severity(line: str) -> str:
    """
    Classify log line severity based on keywords.

    Args:
        line (str): Line to evaluate.

    Returns:
        str: "INFO", "WARNING", or "ERROR"
    """
    lowered = line.lower()

    if "docker" in lowered and ("failed" in lowered or "error" in lowered):
        return "DOCKER_ERROR"
    if "firewall" in lowered and ("deny" in lowered or "block" in lowered):
        return "FIREWALL_BLOCK"

    if "error" in lowered or "exception" in lowered or "failed" in lowered:
        return "ERROR"
    if "warn" in lowered or "deprecated" in lowered:
        return "WARNING"
    return "INFO"

def apply_log_color(category: str, text: str) -> str:
    """
    Apply RGB coloring to log lines based on severity.

    Args:
        category (str): Severity level.
        text (str): Original message.

    Returns:
        str: Colorized string for console output.
    """
    colors = {
        "INFO": (173, 255, 47),
        "WARNING": (255, 215, 0),
        "ERROR": (255, 69, 0),
        "DOCKER_ERROR": (70, 130, 180),
        "FIREWALL_BLOCK": (255, 99, 71),
    }
    r, g, b = colors.get(category, (255, 255, 255))
    return rgb_color(r, g, b, text)

def main() -> None:
    """
    Entry point for the Docker Compose management and firewall audit script.

    Workflow:
        - Initializes logging
        - Verifies Docker daemon status
        - Checks active network profile, firewall rules, and Docker network
        - Executes container down/up operations based on configuration
        - Logs total execution time and outcomes
    """
    setup_logging()
    logging.info("Starting Docker management script...")
    start_datetime = datetime.now()
    logging.info("Script started at: %s", start_datetime.strftime("%Y-%m-%d %H:%M:%S"))

    docker_ready = check_docker_running()
    if docker_ready:
        network_firewall_ok = check_docker_firewall(
            enforce_active_profile=False,
            enforce_docker_backend=False,
            enforce_ports=False
        ) # Adjust these flags as needed True or False

        docker_network_name = "<docker-network-name>"  # 🔁 Replace with your actual internal Docker network
        docker_network_ok = DockerComposeManager.ensure_docker_network(docker_network_name)

        if network_firewall_ok and docker_network_ok:

            docker_configs = load_config('<path/to/docker_compose_manager_config.json>')

            process_docker_configs(docker_configs, "down")

            if not DockerComposeManager.prune_docker_images():
                logging.error("Error: Failed to prune Docker images.")
            else:
                logging.info("Docker images pruned successfully.")

            process_docker_configs(docker_configs, "up")
        else:
            logging.warning("Pre-checks failed. Skipping Docker operations.")

    end_datetime = datetime.now()
    logging.info("Script finished at: %s", end_datetime.strftime("%Y-%m-%d %H:%M:%S"))
    logging.info("Total execution time: %s", format_time_delta(end_datetime - start_datetime))

if __name__ == "__main__":
    main()
