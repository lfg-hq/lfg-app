#!/usr/bin/env python3

import os
import sys
import django
import argparse

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


def create_or_restart_pod(project_id=None, conversation_id=None):
    """
    Create a new Kubernetes pod or restart an existing one.
    """
    print(f"Creating/restarting pod for project_id={project_id}, conversation_id={conversation_id}")
    
    # Resource limits for the pod
    resource_limits = {
        'memory': '200Mi',
        'cpu': '200m',
        'memory_requests': '100Mi',
        'cpu_requests': '100m'
    }
    
    # Create or restart pod
    success, pod = manage_kubernetes_pod(
        project_id=project_id,
        conversation_id=conversation_id,
        image="gitpod/workspace-full:latest",
        resource_limits=resource_limits
    )
    
    if success and pod:
        print("Pod created/restarted successfully!")
        print(f"Pod name: {pod.pod_name}")
        print(f"Namespace: {pod.namespace}")
        print(f"Status: {pod.status}")
        if pod.service_details and pod.service_details.get('access_url'):
            print(f"Access URL: {pod.service_details.get('access_url')}")
        return pod
    else:
        print("Failed to create/restart pod")
        return None


def execute_command(project_id=None, conversation_id=None, command=None):
    """
    Execute a command in a Kubernetes pod.
    """
    print(f"Executing command in pod for project_id={project_id}, conversation_id={conversation_id}")
    print(f"Command: {command}")
    
    # Execute command
    success, stdout, stderr = execute_command_in_pod(
        project_id=project_id,
        conversation_id=conversation_id,
        command=command
    )
    
    if success:
        print("Command executed successfully!")
        print(f"STDOUT: {stdout}")
        if stderr:
            print(f"STDERR: {stderr}")
        return stdout
    else:
        print("Failed to execute command")
        print(f"Error: {stderr}")
        return None


def remove_pod(project_id=None, conversation_id=None):
    """
    Delete a Kubernetes pod.
    """
    print(f"Deleting pod for project_id={project_id}, conversation_id={conversation_id}")
    
    # Delete pod
    success = delete_kubernetes_pod(
        project_id=project_id,
        conversation_id=conversation_id
    )
    
    if success:
        print("Pod deleted successfully!")
        return True
    else:
        print("Failed to delete pod")
        return False


def main():
    """
    Main function to demonstrate Kubernetes pod management.
    """
    parser = argparse.ArgumentParser(
        description="Kubernetes Pod Management Example",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Add arguments
    parser.add_argument("--project-id", help="Project ID", default=None)
    parser.add_argument("--conversation-id", help="Conversation ID", default=None)
    parser.add_argument("--action", choices=["create", "execute", "delete"], required=True,
                       help="Action to perform")
    parser.add_argument("--command", help="Command to execute (for execute action)", default=None)
    
    args = parser.parse_args()
    
    # Validate arguments
    if not (args.project_id or args.conversation_id):
        print("Error: Either --project-id or --conversation-id must be provided")
        sys.exit(1)
    
    if args.action == "execute" and not args.command:
        print("Error: --command must be provided for execute action")
        sys.exit(1)
    
    # Perform action
    if args.action == "create":
        create_or_restart_pod(args.project_id, args.conversation_id)
    elif args.action == "execute":
        execute_command(args.project_id, args.conversation_id, args.command)
    elif args.action == "delete":
        remove_pod(args.project_id, args.conversation_id)


if __name__ == "__main__":
    main() 