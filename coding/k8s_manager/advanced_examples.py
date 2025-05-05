#!/usr/bin/env python3

import os
import sys
import time
import django
import argparse
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LFG.settings')
django.setup()

# Import the Kubernetes management functions
from coding.k8s_manager import (
    manage_kubernetes_pod, 
    execute_command_in_pod, 
    delete_kubernetes_pod
)

def create_development_environment(project_id):
    """
    Create a complete development environment with various tools installed.
    
    Args:
        project_id (str): Project ID
    
    Returns:
        tuple: (success, pod, url)
    """
    logger.info(f"Creating development environment for project {project_id}")
    
    # Create a pod with more resources for development
    success, pod = manage_kubernetes_pod(
        project_id=project_id,
        image="gitpod/workspace-full:latest",
        resource_limits={
            'memory': '1Gi',
            'cpu': '500m',
            'memory_requests': '500Mi',
            'cpu_requests': '250m'
        }
    )
    
    if not success or not pod:
        logger.error("Failed to create pod")
        return False, None, None
    
    logger.info(f"Pod {pod.pod_name} created successfully in namespace {pod.namespace}")
    
    # Install development tools
    commands = [
        "apt-get update && apt-get install -y vim htop git curl",
        "python3 -m pip install --upgrade pip",
        "python3 -m pip install ipython pytest black flake8 mypy"
    ]
    
    for cmd in commands:
        logger.info(f"Running command: {cmd}")
        success, stdout, stderr = execute_command_in_pod(
            project_id=project_id,
            command=cmd
        )
        
        if not success:
            logger.warning(f"Command failed: {cmd}")
            logger.warning(f"Error: {stderr}")
    
    # Create a welcome message
    welcome_message = """
    # Welcome to your LFG Development Environment
    
    This environment has been pre-configured with:
    - Python development tools (pip, ipython, pytest, black, flake8, mypy)
    - Git and other utilities
    
    Your code is stored in the /workspace directory.
    
    Happy coding!
    """
    
    execute_command_in_pod(
        project_id=project_id,
        command=f"echo '{welcome_message}' > /workspace/README.md"
    )
    
    # Get access URL
    access_url = None
    if pod.service_details and pod.service_details.get('access_url'):
        access_url = pod.service_details.get('access_url')
        logger.info(f"Environment is accessible at: {access_url}")
    
    return True, pod, access_url


def clone_and_run_project(project_id, git_repo, branch=None, run_command=None):
    """
    Clone a Git repository and optionally run a command.
    
    Args:
        project_id (str): Project ID
        git_repo (str): Git repository URL
        branch (str, optional): Git branch to checkout
        run_command (str, optional): Command to run after cloning
    
    Returns:
        bool: Success or failure
    """
    logger.info(f"Cloning repository {git_repo} for project {project_id}")
    
    # Ensure pod is running
    success, pod = manage_kubernetes_pod(project_id=project_id)
    
    if not success or not pod:
        logger.error("Failed to create/ensure pod is running")
        return False
    
    # Clone the repository
    clone_cmd = f"git clone {git_repo} /workspace/repo"
    logger.info(f"Running command: {clone_cmd}")
    
    success, stdout, stderr = execute_command_in_pod(
        project_id=project_id,
        command=clone_cmd
    )
    
    if not success:
        logger.error(f"Failed to clone repository: {stderr}")
        return False
    
    # Checkout specific branch if requested
    if branch:
        checkout_cmd = f"cd /workspace/repo && git checkout {branch}"
        logger.info(f"Running command: {checkout_cmd}")
        
        success, stdout, stderr = execute_command_in_pod(
            project_id=project_id,
            command=checkout_cmd
        )
        
        if not success:
            logger.error(f"Failed to checkout branch {branch}: {stderr}")
            return False
    
    # Run command if provided
    if run_command:
        cmd = f"cd /workspace/repo && {run_command}"
        logger.info(f"Running command: {cmd}")
        
        success, stdout, stderr = execute_command_in_pod(
            project_id=project_id,
            command=cmd
        )
        
        if not success:
            logger.error(f"Failed to run command: {stderr}")
            return False
        
        logger.info(f"Command output: {stdout}")
    
    return True


def monitor_pod_logs(project_id, command, duration=60):
    """
    Run a command and continuously monitor its output for a specific duration.
    
    Args:
        project_id (str): Project ID
        command (str): Command to run and monitor
        duration (int): Monitoring duration in seconds
    
    Returns:
        bool: Success or failure
    """
    logger.info(f"Starting command monitoring for project {project_id}")
    logger.info(f"Command: {command}")
    logger.info(f"Monitoring for {duration} seconds")
    
    # Ensure pod is running
    success, pod = manage_kubernetes_pod(project_id=project_id)
    
    if not success or not pod:
        logger.error("Failed to create/ensure pod is running")
        return False
    
    # Start the background process
    cmd = f"cd /workspace && {command} > /tmp/command_output.log 2>&1 &"
    success, stdout, stderr = execute_command_in_pod(
        project_id=project_id,
        command=cmd
    )
    
    if not success:
        logger.error(f"Failed to start command: {stderr}")
        return False
    
    # Monitor logs for the specified duration
    start_time = time.time()
    end_time = start_time + duration
    
    while time.time() < end_time:
        # Check if the process is still running
        ps_cmd = "ps aux | grep -v grep | grep -F " + f'"{command}"'
        success, stdout, stderr = execute_command_in_pod(
            project_id=project_id,
            command=ps_cmd
        )
        
        if not success or not stdout.strip():
            logger.warning("Process appears to have stopped")
            break
        
        # Get the latest log output
        success, stdout, stderr = execute_command_in_pod(
            project_id=project_id,
            command="tail -n 20 /tmp/command_output.log"
        )
        
        if success and stdout:
            logger.info("Latest output:")
            for line in stdout.splitlines():
                logger.info(f"  | {line}")
        
        # Sleep for a short period
        time.sleep(5)
    
    logger.info("Monitoring completed")
    
    # Get the full log
    success, stdout, stderr = execute_command_in_pod(
        project_id=project_id,
        command="cat /tmp/command_output.log"
    )
    
    if success:
        logger.info("Full command output:")
        logger.info(stdout)
    
    return True


def main():
    """
    Main function for demonstrating advanced K8s pod management.
    """
    parser = argparse.ArgumentParser(
        description="Advanced Kubernetes Pod Management Examples",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Add arguments
    parser.add_argument("--project-id", required=True, help="Project ID")
    parser.add_argument("--example", choices=["dev-env", "git-clone", "monitor"], required=True,
                       help="Example to run")
    parser.add_argument("--git-repo", help="Git repository URL for git-clone example")
    parser.add_argument("--branch", help="Git branch for git-clone example")
    parser.add_argument("--run-command", help="Command to run after git clone")
    parser.add_argument("--monitor-command", help="Command to monitor")
    parser.add_argument("--duration", type=int, default=60, help="Monitoring duration in seconds")
    
    args = parser.parse_args()
    
    try:
        if args.example == "dev-env":
            create_development_environment(args.project_id)
        
        elif args.example == "git-clone":
            if not args.git_repo:
                logger.error("--git-repo is required for git-clone example")
                sys.exit(1)
            
            clone_and_run_project(
                args.project_id,
                args.git_repo,
                args.branch,
                args.run_command
            )
        
        elif args.example == "monitor":
            if not args.monitor_command:
                logger.error("--monitor-command is required for monitor example")
                sys.exit(1)
            
            monitor_pod_logs(
                args.project_id,
                args.monitor_command,
                args.duration
            )
    
    except KeyboardInterrupt:
        logger.info("Operation interrupted by user")
    except Exception as e:
        logger.error(f"Error: {str(e)}")
    finally:
        logger.info("Done")


if __name__ == "__main__":
    main() 