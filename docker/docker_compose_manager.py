"""
Docker Compose Project Manager

This script manages Docker Compose projects, allowing users to bring down or bring up containers as specified.
It processes a list of Docker Compose configurations, takes down or brings up containers, and prunes Docker images
to remove unused ones.

Usage:
    python docker_compose_manager.py

Dependencies:
    - Docker Desktop
    - PyYAML

Installation:
    Ensure you have Docker installed and running on your machine.
    Install the required Python package:
    pip install pyyaml

Description:
    - DockerComposeManager: A class to manage Docker Compose projects.
    - __init__: Initializes the manager with directory, compose file, and environment file.
    - run_docker_compose: Runs a Docker Compose command with the specified action and container name.
    - check_container_status: Checks if a Docker container exists and is running.
    - prune_docker_images: Prunes Docker images to remove unused ones.
    - process_docker_configs: Processes a list of Docker Compose configurations to take down or bring up containers.

Main Function:
    - Initializes DockerComposeManager instances for each Docker Compose configuration.
    - Takes down running containers.
    - Prunes unused Docker images.
    - Brings up containers as specified.

Example:
    python docker_compose_manager.py
"""

import subprocess
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import yaml

def setup_logging():
    """
    Set up logging with a rotating file handler.

    Returns:
    - None
    """
    # Get the full path of the script
    script_path = Path(__file__).resolve()
    script_directory = script_path.parent
    script_filename = script_path.stem

    log_file = script_directory / f"{script_filename}.log"
    handler = RotatingFileHandler(log_file, maxBytes=1024*1024, backupCount=5)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)

def rgb_color(r, g, b, text):
    """
    Generate ANSI escape sequences for RGB-like color formatting in terminal output.

    Parameters:
    - r (int): Red component (0-255).
    - g (int): Green component (0-255).
    - b (int): Blue component (0-255).
    - text (str): Text to be colored.

    Returns:
    - str: ANSI escape sequence for colored text.
    """
    return f"\033[38;2;{r};{g};{b}m{text}\033[0m"

class DockerComposeManager:
    """
    A class to manage Docker Compose projects, taking down or bringing up containers as specified.
    """

    def __init__(self, docker_dir, compose_file, env_file):
        """
        Initialize DockerComposeManager with directory, compose file, and environment file.

        Parameters:
        - docker_dir (Path): Directory containing the Docker Compose files.
        - compose_file (Path): Path to the Docker Compose YAML file.
        - env_file (Path): Path to the environment file.
        """
        self.docker_dir = Path(docker_dir)
        self.compose_file = self.docker_dir / compose_file
        self.env_file = self.docker_dir / env_file

    def run_docker_compose(self, action, container_name):
        """
        Run a Docker Compose command with the specified action and container name.

        Parameters:
        - action (str): Action to perform (e.g. "down", "up").
        - container_name (str): Name of the container.

        Returns:
        - bool: True if the command runs successfully, False otherwise.
        """
        cmd = [
            'docker', 'compose', '-f', str(self.compose_file),
            '--env-file', str(self.env_file), action
        ]

        if action == "up":
            cmd.extend(["-d", container_name])

        try:
            subprocess.run(cmd, stderr=subprocess.PIPE, check=True)
            logging.info(rgb_color(0, 255, 0, "Successfully %sed container %s"), action, container_name)
            return True
        except subprocess.CalledProcessError as e:
            logging.error(rgb_color(255, 0, 0, "Error %s while %sing container %s: %s"), e.returncode, action, container_name, e.stderr.decode('utf-8').strip())
            return False

    @staticmethod
    def check_container_status(container_name):
        """
        Check if a Docker container exists and is running.

        Parameters:
        - container_name (str): Name of the container.

        Returns:
        - bool: True if the container exists and is running, False otherwise.
        """
        cmd = ['docker', 'container', 'ls', '-a', '--format', '{{.Names}}', '--filter', f'name={container_name}']
        try:
            output = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            if output.stdout and output.stdout.decode('utf-8').strip() == container_name:
                return True
        except subprocess.CalledProcessError as e:
            logging.error(rgb_color(255, 0, 0, "Error %s while checking container status: %s"), e.returncode, e.stderr.decode('utf-8').strip())
        return False

    @staticmethod
    def prune_docker_images():
        """
        Run the Docker image prune command to remove unused images.

        Returns:
        - bool: True if the command runs successfully, False otherwise.
        """
        cmd = ['docker', 'image', 'prune', '-a', '-f']
        try:
            output = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            if output.stdout:
                logging.info(rgb_color(0, 255, 0, "%s"), output.stdout.decode('utf-8').strip())
            return True
        except subprocess.CalledProcessError as e:
            logging.error(rgb_color(255, 0, 0, "Error %s while pruning Docker images: %s"), e.returncode, e.stderr.decode('utf-8').strip())
            return False

def process_docker_configs(docker_configs, action):
    """
    Process a list of Docker Compose configurations, taking down or bringing up containers as specified.

    Parameters:
    - docker_configs (list): List of DockerComposeManager instances containing Docker Compose configuration details.
    - action (str): String indicating the action to perform ("down" or "up").

    Returns:
    - None
    """
    errors = False
    for config in docker_configs:
        try:
            with open(config.compose_file, 'r', encoding='utf-8') as file:
                compose_data = yaml.safe_load(file)
                for service in compose_data.get('services', {}):
                    container_name = service
                    if action == "down" and DockerComposeManager.check_container_status(container_name):
                        logging.info(rgb_color(255, 255, 0, "Taking down container %s..."), container_name)
                        if not config.run_docker_compose(action, container_name):
                            errors = True
                    elif action == "up":
                        logging.info(rgb_color(255, 255, 0, "Bringing up container %s..."), container_name)
                        if not config.run_docker_compose(action, container_name):
                            errors = True
        except FileNotFoundError:
            logging.error(rgb_color(255, 0, 0, "Compose file '%s' not found."), config.compose_file)
            errors = True
        except yaml.YAMLError as e:
            logging.error(rgb_color(255, 0, 0, "Error parsing YAML from the compose file: %s"), e)
            errors = True

    if errors:
        logging.error(rgb_color(255, 0, 0, "Error: One or more containers failed to %s."), action)
    else:
        logging.info(rgb_color(0, 255, 0, "All containers %s successfully."), action)

def load_config(config_file):
    """
    Load Docker Compose configurations from a YAML file.

    Parameters:
    - config_file (str): Path to the configuration YAML file.

    Returns:
    - list: A list of DockerComposeManager instances initialized with the configurations.
    """
    try:
        with open(config_file, 'r', encoding='utf-8') as file:
            config_data = yaml.safe_load(file)
    except FileNotFoundError:
        logging.error("Configuration file '%s' not found.", config_file)
        return []
    except yaml.YAMLError as e:
        logging.error("Error decoding YAML from the configuration file: %s", e)
        return []

    docker_configs = [
        DockerComposeManager(Path(config['docker_dir']), Path(config['compose_file']), Path(config['env_file']))
        for config in config_data.get('docker_configs', [])
    ]
    return docker_configs

def main():
    """
    Main entry point of the script. Processes Docker Compose projects, takes down running containers,
    prunes Docker images, and brings up containers.

    Returns:
    - None
    """
    setup_logging()

    start_time = datetime.now()
    logging.info(rgb_color(0, 255, 255, "Script started at: %s"), start_time.strftime('%Y-%m-%d %H:%M:%S'))

    docker_configs = load_config('/path/to/docker_compose_manager_config.json')

    # Use the standalone function to process Docker configurations
    process_docker_configs(docker_configs, "down")

    if not DockerComposeManager.prune_docker_images():
        logging.error(rgb_color(255, 0, 0, "Error: Failed to prune Docker images."))
    else:
        logging.info(rgb_color(0, 255, 0, "Docker images pruned successfully."))

    process_docker_configs(docker_configs, "up")

    end_time = datetime.now()
    logging.info(rgb_color(0, 255, 255, "Script finished at: %s"), end_time.strftime('%Y-%m-%d %H:%M:%S'))

    execution_time = end_time - start_time
    logging.info(rgb_color(201, 103, 28, "Total execution time: %s"), str(execution_time))

if __name__ == "__main__":
    main()
