"""
Docker Compose Project Manager

This script manages Docker Compose projects, allowing users to bring down or bring up containers as specified.
It processes a list of Docker Compose configurations, takes down or brings up containers, and prunes Docker images
to remove unused ones.

Usage:
    python docker_compose_manager.py

Dependencies:
    - docker desktop
    - pyyaml
Pip:
    Make sure your pip is updated
    python.exe -m pip install --upgrade pip

Windows:
    If warning on a Windows machine perform the following
    WARNING: The scripts pip.exe, pip3.12.exe and pip3.exe are installed in 'C:\\Users\\<user_name>\\AppData\\Roaming\\Python\\Python312\\Scripts' which is not on PATH.
    Consider adding this directory to PATH or, if you prefer to suppress this warning, use --no-warn-script-location.

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

import time
from datetime import datetime
import subprocess
import os
import yaml

# ANSI color escape sequences for RGB-like colors
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

        :param docker_dir: Directory containing the Docker Compose files
        :param compose_file: Name of the Docker Compose YAML file
        :param env_file: Name of the environment file
        """
        self.docker_dir = docker_dir
        self.compose_file = compose_file
        self.env_file = env_file

    def run_docker_compose(self, action, container_name):
        """
        Run a Docker Compose command with the specified action and container name.

        :param action: Action to perform (e.g. "down", "up")
        :param container_name: Name of the container
        :return: True if the command runs successfully, False otherwise
        """
        yaml_file = os.path.join(self.docker_dir, self.compose_file)
        env_file_path = os.path.join(self.docker_dir, self.env_file)
        cmd = ['docker', 'compose', '-f', os.path.normpath(yaml_file), '--env-file', os.path.normpath(env_file_path), action]
        if action == "up":
            cmd.append("-d")
        cmd.append(container_name)

        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(rgb_color(255, 0, 0, f"Error {e.returncode} while {action}ing container {container_name}")) # rgb(255, 0, 0)
            return False
        return True

    @staticmethod
    def check_container_status(container_name):
        """
        Check if a Docker container exists and is running.

        :param container_name: Name of the container
        :return: True if the container exists and is running, False otherwise
        """
        cmd = ['docker', 'container', 'ls', '-a', '--format', '{{.Names}}', '--filter', f'name={container_name}']
        try:
            output = subprocess.run(cmd, stdout=subprocess.PIPE, check=True)
            if output.stdout is not None:
                if output.stdout.decode('utf-8').strip() == container_name:
                    return True
        except subprocess.CalledProcessError as e:
            print(rgb_color(255, 0, 0, f"Error {e.returncode} while checking container status: {e.stderr.decode('utf-8').strip()}")) # rgb(255, 0, 0)
        return False

    @staticmethod
    def prune_docker_images():
        """
        Run the Docker image prune command to remove unused images.

        :return: True if the command runs successfully, False otherwise
        """
        cmd = ['docker', 'image', 'prune', '-a', '-f']
        try:
            output = subprocess.run(cmd, stdout=subprocess.PIPE, check=True)
            if output.stdout is not None:
                print(rgb_color(0, 255, 0, f"{output.stdout.decode('utf-8').strip()}")) # rgb(0, 255, 0)
        except subprocess.CalledProcessError as e:
            print(rgb_color(255, 0, 0, f"Error {e.returncode} while pruning Docker images: {e.stderr.decode('utf-8').strip()}")) # rgb(255, 0, 0)
            return False
        return True

    def process_docker_configs(self, docker_configs, action):
        """
        Process a list of Docker Compose configurations, taking down or bringing up containers as specified.

        :param docker_configs: List of DockerComposeManager instances containing Docker Compose configuration details
        :param action: String indicating the action to perform ("down" or "up")
        :return: None
        """
        errors = False
        for config in docker_configs:
            with open(os.path.join(config.docker_dir, config.compose_file), 'r', encoding='utf-8') as file:
                compose_data = yaml.safe_load(file)
                for service, _ in compose_data.get('services', {}).items():
                    container_name = service
                    if action == "down" and self.check_container_status(container_name):
                        print(rgb_color(255, 255, 0, f"  Taking down container {container_name}...")) # rgb(255, 255, 0)
                        if not config.run_docker_compose(action, container_name):
                            errors = True
                    elif action == "up":
                        print(rgb_color(255, 255, 0, f"  Bringing up container {container_name}...")) # rgb(255, 255, 0)
                        if not config.run_docker_compose(action, container_name):
                            errors = True
        if errors:
            print(rgb_color(255, 0, 0, f"Error: One or more containers failed to {action}.")) # rgb(255, 0, 0)
        else:
            print(rgb_color(0, 255, 0, f"All containers {action} successfully.")) # rgb(0, 255, 0)

def main():
    """
    Main entry point of the script. Processes Docker Compose projects, takes down running containers,
    prunes Docker images, and brings up containers.

    :return: None
    """
    start_time = time.time()
    start_timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))
    print(rgb_color(0, 255, 255, f"Script started at {start_timestamp}...")) # rgb(0, 255, 255)

    docker_configs = [
        DockerComposeManager("<path/to/docker/directory/01>", "<docker_compose_filename_01.yml>", "<docker_compose_environment_filename_01.env>"),
        DockerComposeManager("<path/to/docker/directory/02>", "<docker_compose_filename_02.yml>", "<docker_compose_environment_filename_02.env>"),
        DockerComposeManager("<path/to/docker/directory/03>", "<docker_compose_filename_03.yml>", "<docker_compose_environment_filename_03.env>")
    ]

    manager = DockerComposeManager(None, None, None)
    manager.process_docker_configs(docker_configs, "down")
    if not DockerComposeManager.prune_docker_images():
        print(rgb_color(255, 0, 0, "Error: Failed to prune Docker images.")) # rgb(255, 0, 0)
    else:
        print(rgb_color(0, 255, 0, "Docker images pruned successfully.")) # rgb(0, 255, 0)
    manager.process_docker_configs(docker_configs, "up")

    # Get the end time
    end_time = datetime.now()
    print(rgb_color(0, 255, 255, f"Script finished at: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")) # rgb(0, 255, 255)

    # Calculate and print the execution time
    execution_time = end_time - start_time
    print(rgb_color(201, 103, 28, f"Total execution time: {str(execution_time)}")) # rgb(201, 103, 28)

if __name__ == "__main__":
    main()
