# LFG Kubernetes Pod Management

A simple and flexible system for creating and managing Kubernetes pods for LFG projects and conversations.

## Quick Start

### 1. Installation

The system is built into the LFG project. Make sure you have the required packages:

```bash
pip install -r requirements.txt
```

### 2. Configuration

Configure your Kubernetes host in the `.env` file:

```
K8S_SSH_HOST=178.156.174.242
K8S_SSH_PORT=22
K8S_SSH_USERNAME=root
K8S_SSH_KEY_FILE=~/.ssh/id_rsa
```

### 3. Usage Examples

#### Create a Pod for a Project

```python
from coding.k8s_manager import manage_kubernetes_pod

success, pod = manage_kubernetes_pod(
    project_id="my-project-123",
    image="gitpod/workspace-full:latest"
)

if success:
    print(f"Pod running at: {pod.service_details.get('access_url')}")
```

#### Execute Commands in the Pod

```python
from coding.k8s_manager import execute_command_in_pod

success, stdout, stderr = execute_command_in_pod(
    project_id="my-project-123",
    command="git clone https://github.com/user/repo.git /workspace/repo"
)

success, stdout, stderr = execute_command_in_pod(
    project_id="my-project-123",
    command="cd /workspace/repo && python app.py"
)
```

#### Delete the Pod

```python
from coding.k8s_manager import delete_kubernetes_pod

# Delete pod but preserve user data (default behavior)
delete_kubernetes_pod(project_id="my-project-123")

# Delete pod and all associated data
delete_kubernetes_pod(project_id="my-project-123", preserve_data=False)
```

### 4. Command Line Tools

You can also use the command line script:

```bash
# Create a pod
python coding/k8s_manager.py/example_usage.py --project-id=my-project-123 --action=create

# Run a command
python coding/k8s_manager.py/example_usage.py --project-id=my-project-123 --action=execute --command="ls -la /workspace"

# Delete a pod
python coding/k8s_manager.py/example_usage.py --project-id=my-project-123 --action=delete
```

## Key Features

- Create and manage Kubernetes pods remotely via SSH
- Associate pods with projects or conversations
- Execute commands in pods
- Automatic namespace generation
- Database persistence of pod details
- Resource limits control
- Automatic pod status management
- **Persistent user data across pod restarts and deletions**

## Persistent Storage

Each user (identified by project_id or conversation_id) is assigned a persistent volume that preserves their data even when pods are deleted or restarted. This ensures that:

1. Users can resume their work exactly where they left off
2. Files and data persist between sessions
3. Pod restarts due to errors or maintenance don't cause data loss

The persistent volumes are stored on the host machine at `/mnt/data/user-volumes/{namespace}` and are mounted at `/workspace` inside the pod. The system uses Kubernetes PersistentVolumes and PersistentVolumeClaims to manage this storage.

When a pod is deleted using `delete_kubernetes_pod()`, the user data is preserved by default. You can specify `preserve_data=False` to completely remove all user data.

## How It Works

1. The system connects to the Kubernetes host via SSH
2. It creates a namespace, PersistentVolume, PersistentVolumeClaim, deployment, and service for each pod
3. Pods are tracked in the database with their project or conversation ID
4. The system checks for existing pods before creating new ones
5. All pod operations are securely executed via SSH + kubectl
6. User data is stored persistently in dedicated volumes

## Common Issues

- **SSH Connection Failures**: Check that your SSH key is valid and the host is accessible
- **Pod Creation Failures**: Verify that the Kubernetes host has sufficient resources
- **Command Execution Failures**: Ensure that the pod is running before executing commands
- **Storage Issues**: Make sure the host machine has enough disk space at `/mnt/data/user-volumes/`
- **Permission Problems**: Verify that the volume directories have appropriate permissions (777)

For more detailed documentation, see [coding/k8s_manager.py/README.md](coding/k8s_manager.py/README.md). 