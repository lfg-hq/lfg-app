#!/usr/bin/env python3

import os
import re
import time
import uuid
import json
import logging
import paramiko
from django.conf import settings
from ..models import KubernetesPod, KubernetesPortMapping

# Configure logging
logger = logging.getLogger(__name__)

# K8s server SSH connection settings
# These would ideally be in settings.py, but we're fetching them from there
def get_k8s_server_settings():
    """
    Get Kubernetes server settings from Django settings.
    
    Returns:
        dict: Dictionary with host, port, username, key_file, key_string, and key_passphrase.
    """
    try:
        # Attempt to get settings from Django settings
        k8s_settings = {
            'host': getattr(settings, 'K8S_SSH_HOST', '127.0.0.1'),
            'port': int(getattr(settings, 'K8S_SSH_PORT', 22)),
            'username': getattr(settings, 'K8S_SSH_USERNAME', 'root'),
            'key_file': getattr(settings, 'K8S_SSH_KEY_FILE', os.path.expanduser('~/.ssh/id_rsa')),
            'key_string': getattr(settings, 'K8S_SSH_KEY_STRING', None),
            'key_passphrase': getattr(settings, 'K8S_SSH_KEY_PASSPHRASE', None),
        }
        return k8s_settings
    except Exception as e:
        logger.error(f"Error getting K8s server settings: {str(e)}")
        # Fallback to defaults
        return {
            'host': '127.0.0.1',
            'port': 22,
            'username': 'root',
            'key_file': os.path.expanduser('~/.ssh/id_rsa'),
            'key_string': None,
            'key_passphrase': None,
        }


def create_ssh_client(host=None, port=None, username=None, key_file=None, key_string=None, key_passphrase=None):
    """
    Create an SSH client connection to the Kubernetes server.
    
    Args:
        host (str): SSH host
        port (int): SSH port
        username (str): SSH username
        key_file (str): Path to SSH private key file
        key_string (str): SSH private key as a string
        key_passphrase (str): Passphrase for SSH private key
        
    Returns:
        paramiko.SSHClient: Connected SSH client or None if connection fails
    """
    # Get settings if not provided
    if not all([host, port, username]) or (not key_file and not key_string):
        k8s_settings = get_k8s_server_settings()
        host = host or k8s_settings['host']
        port = port or k8s_settings['port']
        username = username or k8s_settings['username']
        key_file = key_file or k8s_settings['key_file']
        key_string = key_string or k8s_settings['key_string']
        key_passphrase = key_passphrase or k8s_settings['key_passphrase']
        
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # If key_string is provided, use it instead of key_file
        if key_string:
            try:
                # Use StringIO to create a file-like object from the key string
                from io import StringIO
                key_file_obj = StringIO(key_string)
                
                # Create a private key object
                if key_passphrase:
                    pkey = paramiko.RSAKey.from_private_key(key_file_obj, password=key_passphrase)
                else:
                    pkey = paramiko.RSAKey.from_private_key(key_file_obj)
                
                logger.info(f"Connecting to {username}@{host}:{port} using key string")
                client.connect(
                    hostname=host, 
                    port=port, 
                    username=username, 
                    pkey=pkey
                )
            except Exception as e:
                logger.error(f"Error connecting with key string: {str(e)}")
                # Fall back to key file if it exists
                if key_file and os.path.exists(key_file):
                    logger.info(f"Falling back to key file: {key_file}")
                    client.connect(
                        hostname=host, 
                        port=port, 
                        username=username, 
                        key_filename=key_file,
                        passphrase=key_passphrase
                    )
                else:
                    raise
        else:
            # Use key file
            logger.info(f"Connecting to {username}@{host}:{port} using key: {key_file}")
            client.connect(
                hostname=host, 
                port=port, 
                username=username, 
                key_filename=key_file,
                passphrase=key_passphrase
            )
        
        logger.info("SSH connection established successfully!")
        return client
    except Exception as e:
        logger.error(f"Error connecting to {host}: {str(e)}")
        return None


def execute_remote_command(client, command):
    """
    Execute a command on the remote server and return the output.
    
    Args:
        client (paramiko.SSHClient): SSH client
        command (str): Command to execute
        
    Returns:
        tuple: (success, stdout, stderr)
    """
    logger.info(f"Executing remote command: {command}")
    
    try:
        stdin, stdout, stderr = client.exec_command(command)
        exit_status = stdout.channel.recv_exit_status()
        
        stdout_str = stdout.read().decode('utf-8')
        stderr_str = stderr.read().decode('utf-8')
        
        if stdout_str:
            logger.debug(f"STDOUT: {stdout_str}")
        if stderr_str:
            logger.debug(f"STDERR: {stderr_str}")
            
        if exit_status != 0:
            logger.warning(f"Command failed with exit status {exit_status}")
            return False, stdout_str, stderr_str
            
        return True, stdout_str, stderr_str
    except Exception as e:
        logger.error(f"Error executing command: {str(e)}")
        return False, "", str(e)


def generate_namespace(project_id=None, conversation_id=None):
    """
    Generate a unique namespace based on project_id or conversation_id.
    
    Args:
        project_id (str): Project ID
        conversation_id (str): Conversation ID
        
    Returns:
        str: Unique namespace name
    """
    if project_id:
        # Use project ID as base for namespace
        namespace_base = f"proj-{project_id}"
    elif conversation_id:
        # Use conversation ID as base for namespace
        namespace_base = f"conv-{conversation_id}"
    else:
        # Generate a random namespace if neither is provided
        namespace_base = f"lfg-{uuid.uuid4().hex[:8]}"
    
    # Clean namespace: lowercase, replace special chars with dashes
    namespace = re.sub(r'[^a-z0-9-]', '-', namespace_base.lower())
    
    # Ensure it's valid (starts with letter, only contains letters, numbers, and dashes)
    if not re.match(r'^[a-z]', namespace):
        namespace = f"ns-{namespace}"
    
    # Truncate if too long (Kubernetes has a 63 character limit)
    if len(namespace) > 60:
        namespace = namespace[:60]
    
    return namespace


def check_pod_status(client, namespace, pod_name=None):
    """
    Check the status of a pod in the given namespace.
    
    Args:
        client (paramiko.SSHClient): SSH client
        namespace (str): Kubernetes namespace
        pod_name (str, optional): Specific pod name to check
        
    Returns:
        tuple: (exists, running, pod_details)
    """
    try:
        # Create namespace if it doesn't exist
        execute_remote_command(
            client, f"kubectl get namespace {namespace} || kubectl create namespace {namespace}"
        )
        
        # Fetch all pods in the namespace with a single command
        # We'll filter them programmatically instead of using multiple kubectl calls
        success, stdout, stderr = execute_remote_command(
            client, f"kubectl get pods -n {namespace} -o json"
        )
        
        if success:
            try:
                pod_data = json.loads(stdout)
                pods = pod_data.get('items', [])
                
                if not pods:
                    logger.info(f"No pods found in namespace {namespace}")
                    return False, False, {}
                
                # First try to find pods with the app label
                labeled_pods = [p for p in pods if p.get('metadata', {}).get('labels', {}).get('app') == namespace]
                
                # Then try to find the specific pod if requested
                specific_pod = None
                if pod_name:
                    specific_pod = next((p for p in pods if p.get('metadata', {}).get('name') == pod_name), None)
                
                # Decide which pod to use based on priorities:
                # 1. Specifically requested pod by name
                # 2. Pod with matching app label
                # 3. Any pod in the namespace
                pod = None
                if specific_pod:
                    pod = specific_pod
                    actual_pod_name = pod_name
                    logger.info(f"Using specifically requested pod: {pod_name}")
                elif labeled_pods:
                    pod = labeled_pods[0]
                    actual_pod_name = pod.get('metadata', {}).get('name', '')
                    logger.info(f"Found pod with app={namespace} label: {actual_pod_name}")
                else:
                    pod = pods[0]
                    actual_pod_name = pod.get('metadata', {}).get('name', '')
                    logger.info(f"Using first available pod in namespace: {actual_pod_name}")
                
                # Check pod phase
                phase = pod.get('status', {}).get('phase', '')
                if phase.lower() != 'running':
                    logger.info(f"Pod {actual_pod_name} phase is {phase}, not Running")
                    return True, False, pod
                
                # Check if all containers are ready
                container_statuses = pod.get('status', {}).get('containerStatuses', [])
                all_containers_ready = True
                
                for container in container_statuses:
                    if not container.get('ready', False):
                        container_name = container.get('name', 'unknown')
                        state = container.get('state', {})
                        reason = "unknown"
                        
                        # Check for container state reasons
                        if 'waiting' in state:
                            reason = state['waiting'].get('reason', 'waiting')
                        elif 'terminated' in state:
                            reason = state['terminated'].get('reason', 'terminated')
                        
                        logger.warning(f"Container {container_name} in pod {actual_pod_name} is not ready. State: {reason}")
                        all_containers_ready = False
                
                # Only consider pod running if phase is Running AND all containers are ready
                return True, phase.lower() == 'running' and all_containers_ready, pod
                
            except json.JSONDecodeError:
                logger.error(f"Failed to parse pod JSON data: {stdout}")
        
        return False, False, {}
    except Exception as e:
        logger.error(f"Error checking pod status: {str(e)}")
        return False, False, {}


def create_kubernetes_pod(client, namespace, image="gitpod/workspace-full:latest", resource_limits=None):
    """
    Create a Kubernetes pod in the given namespace.
    
    Args:
        client (paramiko.SSHClient): SSH client
        namespace (str): Kubernetes namespace
        image (str): Docker image to use
        resource_limits (dict): Resource limits for the pod
        
    Returns:
        tuple: (success, pod_name, service_details)
    """
    pod_name = f"{namespace}-pod"
    service_name = f"{namespace}-service"
    pv_name = f"{namespace}-pv"
    pvc_name = f"{namespace}-pvc"
    
    # Log what we're creating
    logger.info(f"Creating pod with the following specifications:")
    logger.info(f"  Namespace: {namespace}")
    logger.info(f"  Pod name: {pod_name}")
    logger.info(f"  Image: {image}")
    logger.info(f"  Resource limits: {resource_limits}")
    
    # Default resource limits if not provided
    if not resource_limits:
        resource_limits = {
            'memory': '100Mi',
            'cpu': '100m',
            'memory_requests': '50Mi',
            'cpu_requests': '50m'
        }
    
    # Clean up any existing resources completely
    logger.info(f"Performing complete cleanup for namespace {namespace}...")
    
    # Delete deployments and pods first
    execute_remote_command(
        client, f"kubectl delete deployment {namespace}-dep -n {namespace} 2>/dev/null || true"
    )
    execute_remote_command(
        client, f"kubectl delete service {service_name} -n {namespace} 2>/dev/null || true"
    )
    execute_remote_command(
        client, f"kubectl delete pod --all -n {namespace} 2>/dev/null || true"
    )
    
    # Delete PVC
    logger.info(f"Deleting PVC {pvc_name} if it exists...")
    execute_remote_command(
        client, f"kubectl delete pvc {pvc_name} -n {namespace} 2>/dev/null || true"
    )
    
    # Wait for PVC to be fully deleted
    logger.info("Waiting for PVC deletion to complete...")
    execute_remote_command(client, "sleep 3")
    
    # Check if PV exists
    logger.info(f"Checking status of PV {pv_name}...")
    success, stdout, stderr = execute_remote_command(
        client, f"kubectl get pv {pv_name} -o jsonpath='{{.status.phase}}' 2>/dev/null || echo 'NotFound'"
    )
    
    pv_status = stdout.strip()
    logger.info(f"PV {pv_name} status: {pv_status}")
    
    # If PV exists and is in Released/Failed state, delete it
    if pv_status != "NotFound" and pv_status != "Available":
        logger.info(f"PV {pv_name} is in {pv_status} state. Deleting it...")
        execute_remote_command(
            client, f"kubectl delete pv {pv_name} --force --grace-period=0 2>/dev/null || true"
        )
        
        # If deletion fails, try patching finalizers
        execute_remote_command(
            client, f"kubectl patch pv {pv_name} -p '{{\"metadata\":{{\"finalizers\":null}}}}' 2>/dev/null || true"
        )
        
        # Try deleting again
        execute_remote_command(
            client, f"kubectl delete pv {pv_name} --force --grace-period=0 2>/dev/null || true"
        )
        
        # Wait for deletion to complete
        logger.info("Waiting for PV deletion to complete...")
        execute_remote_command(client, "sleep 3")
    
    # Create namespace
    logger.info(f"Creating or verifying namespace {namespace}...")
    success, stdout, stderr = execute_remote_command(
        client, f"kubectl get namespace {namespace} || kubectl create namespace {namespace}"
    )
    
    if not success:
        logger.error(f"Failed to create namespace {namespace}: {stderr}")
        return False, None, {}
    
    # Create directory structure for volume on host and ensure proper permissions
    logger.info(f"Creating host directory for persistent volume at /mnt/data/user-volumes/{namespace}...")
    
    # Create directory
    success, stdout, stderr = execute_remote_command(
        client, f"mkdir -p /mnt/data/user-volumes/{namespace}"
    )
    
    if not success:
        logger.error(f"Failed to create directory for volume: {stderr}")
        return False, None, {}
    
    # Set proper permissions on directory
    success, stdout, stderr = execute_remote_command(
        client, f"chmod 777 /mnt/data/user-volumes/{namespace}"
    )
    
    if not success:
        logger.error(f"Failed to set permissions on volume directory: {stderr}")
        # Continue anyway, might work with existing permissions
    
    # Create a test file to verify write access
    success, stdout, stderr = execute_remote_command(
        client, f"echo 'This is a test file to verify write access.' > /mnt/data/user-volumes/{namespace}/test_access.txt"
    )
    
    if not success:
        logger.warning(f"Failed to create test file in volume directory: {stderr}")
        logger.warning("This may indicate a permission issue with the host directory")
    
    # Create PersistentVolume
    pv_yaml = f"""
apiVersion: v1
kind: PersistentVolume
metadata:
  name: {pv_name}
  labels:
    type: local
    pvname: {pv_name}
spec:
  storageClassName: manual
  capacity:
    storage: 1Gi
  accessModes:
    - ReadWriteOnce
  hostPath:
    path: "/mnt/data/user-volumes/{namespace}"
  persistentVolumeReclaimPolicy: Retain
"""
    
    # Apply the PV
    logger.info(f"Creating PersistentVolume {pv_name}...")
    success, stdout, stderr = execute_remote_command(
        client, f"cat > /tmp/{namespace}-pv.yaml << 'EOF'\n{pv_yaml}\nEOF"
    )
    if not success:
        logger.error(f"Failed to create PV file: {stderr}")
        return False, None, {}
    
    success, stdout, stderr = execute_remote_command(
        client, f"kubectl apply -f /tmp/{namespace}-pv.yaml"
    )
    if not success:
        logger.error(f"Failed to apply PV: {stderr}")
        return False, None, {}
    
    # Wait for the PV to be fully created and Available
    logger.info("Waiting for PersistentVolume to be available...")
    for i in range(5):  # Try for up to 15 seconds
        execute_remote_command(client, "sleep 3")
        
        success, stdout, stderr = execute_remote_command(
            client, f"kubectl get pv {pv_name} -o jsonpath='{{.status.phase}}'"
        )
        
        if success and stdout.strip() == "Available":
            logger.info("PersistentVolume is now Available")
            break
        
        logger.info(f"PV not yet available, waiting... (status: {stdout.strip() if success else 'unknown'})")
    
    # Check PV status one final time
    success, stdout, stderr = execute_remote_command(
        client, f"kubectl get pv {pv_name} -o jsonpath='{{.status.phase}}'"
    )
    
    if not success or (success and stdout.strip() != "Available"):
        pv_status = stdout.strip() if success else "unknown"
        logger.error(f"PersistentVolume status is {pv_status}, expected Available")
        logger.error("Troubleshooting the PV...")
        
        # Get more information about the PV
        execute_remote_command(
            client, f"kubectl describe pv {pv_name}"
        )
        
        # Continue anyway, might work
    
    # Create PersistentVolumeClaim
    pvc_yaml = f"""
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: {pvc_name}
  namespace: {namespace}
spec:
  storageClassName: manual
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
  volumeName: {pv_name}
"""
    
    # Apply the PVC
    logger.info(f"Creating PersistentVolumeClaim {pvc_name}...")
    success, stdout, stderr = execute_remote_command(
        client, f"cat > /tmp/{namespace}-pvc.yaml << 'EOF'\n{pvc_yaml}\nEOF"
    )
    if not success:
        logger.error(f"Failed to create PVC file: {stderr}")
        return False, None, {}
    
    success, stdout, stderr = execute_remote_command(
        client, f"kubectl apply -f /tmp/{namespace}-pvc.yaml"
    )
    if not success:
        logger.error(f"Failed to apply PVC: {stderr}")
        return False, None, {}
    
    # Wait for PVC to bind to PV
    logger.info("Waiting for PersistentVolumeClaim to bind...")
    bound = False
    for i in range(10):  # Try for up to 30 seconds
        success, stdout, stderr = execute_remote_command(
            client, f"kubectl get pvc {pvc_name} -n {namespace} -o jsonpath='{{.status.phase}}'"
        )
        
        if success and stdout.strip() == "Bound":
            logger.info("PersistentVolumeClaim successfully bound to PersistentVolume")
            bound = True
            break
        
        logger.info(f"PVC not yet bound, waiting... (status: {stdout.strip() if success else 'unknown'})")
        execute_remote_command(client, "sleep 3")
    
    # If PVC didn't bind, check for errors
    if not bound:
        logger.error("PVC failed to bind to PV after multiple attempts")
        
        # Get detailed information about PVC and PV
        logger.info("Gathering diagnostic information...")
        execute_remote_command(
            client, f"kubectl describe pvc {pvc_name} -n {namespace}"
        )
        execute_remote_command(
            client, f"kubectl describe pv {pv_name}"
        )
        
        # Let's try creating a simple pod without a volume as a sanity check
        logger.info("Attempting to create a test pod without volume...")
        test_pod_yaml = f"""
apiVersion: v1
kind: Pod
metadata:
  name: {namespace}-test
  namespace: {namespace}
spec:
  containers:
  - name: test-container
    image: busybox
    command: ["sh", "-c", "echo 'Test pod is running' && sleep 3600"]
"""
        
        execute_remote_command(
            client, f"cat > /tmp/{namespace}-test-pod.yaml << 'EOF'\n{test_pod_yaml}\nEOF"
        )
        execute_remote_command(
            client, f"kubectl apply -f /tmp/{namespace}-test-pod.yaml"
        )
        
        # Wait a moment for the pod to start
        execute_remote_command(client, "sleep 5")
        
        # Check if the test pod is running
        success, stdout, stderr = execute_remote_command(
            client, f"kubectl get pod {namespace}-test -n {namespace} -o jsonpath='{{.status.phase}}'"
        )
        
        if success and stdout.strip() == "Running":
            logger.info("Test pod is running, suggesting the issue is specific to the volume")
        else:
            logger.info(f"Test pod is not running (status: {stdout.strip() if success else 'unknown'}), suggesting a broader issue")
        
        # Clean up the test pod
        execute_remote_command(
            client, f"kubectl delete pod {namespace}-test -n {namespace} --force --grace-period=0"
        )
        
        # Continue anyway, but unlikely to succeed
    
    # Apply the Deployment
    logger.info(f"Creating Deployment for namespace {namespace}...")
    deployment_yaml = f"""
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {namespace}-dep
  namespace: {namespace}
  labels:
    app: {namespace}
    component: workspace
spec:
  replicas: 1
  selector:
    matchLabels:
      app: {namespace}
  template:
    metadata:
      labels:
        app: {namespace}
        component: workspace
    spec:
      containers:
      - name: dev-environment
        image: {image}
        command: ["sleep", "infinity"]
        resources:
          limits:
            memory: "{resource_limits.get('memory', '100Mi')}"
            cpu: "{resource_limits.get('cpu', '100m')}"
          requests:
            memory: "{resource_limits.get('memory_requests', '50Mi')}"
            cpu: "{resource_limits.get('cpu_requests', '50m')}"
        volumeMounts:
        - name: user-data
          mountPath: /workspace
      - name: ttyd
        image: tsl0922/ttyd:latest
        command: ["/usr/bin/ttyd"]
        args: ["--port", "7681", "--interface", "0.0.0.0", "--credential", "user:password", "--writable", "/bin/sh"]
        ports:
        - containerPort: 7681
          name: ttyd
          protocol: TCP
        volumeMounts:
        - name: user-data
          mountPath: /workspace
      - name: filebrowser
        image: filebrowser/filebrowser:latest
        command: ["/filebrowser"]
        args: ["--noauth", "--address", "0.0.0.0", "--port", "8080", "--root", "/workspace"]
        ports:
        - containerPort: 8080
          name: filebrowser
          protocol: TCP
        volumeMounts:
        - name: user-data
          mountPath: /workspace
      volumes:
      - name: user-data
        persistentVolumeClaim:
          claimName: {pvc_name}
"""
    
    success, stdout, stderr = execute_remote_command(
        client, f"cat > /tmp/{namespace}-deployment.yaml << 'EOF'\n{deployment_yaml}\nEOF"
    )
    if not success:
        logger.error(f"Failed to create deployment file: {stderr}")
        return False, None, {}
    
    success, stdout, stderr = execute_remote_command(
        client, f"kubectl apply -f /tmp/{namespace}-deployment.yaml"
    )
    if not success:
        logger.error(f"Failed to apply deployment: {stderr}")
        # Show detailed error information
        execute_remote_command(
            client, f"kubectl get pvc {pvc_name} -n {namespace} -o yaml"
        )
        execute_remote_command(
            client, f"kubectl get pv {pv_name} -o yaml"
        )
        return False, None, {}
    
    # Validate that the deployment was created with the correct ttyd configuration
    logger.info("Verifying ttyd container configuration in the deployment...")
    deployment_name = f"{namespace}-dep"
    success, stdout, stderr = execute_remote_command(
        client, f"kubectl get deployment {deployment_name} -n {namespace} -o json"
    )
    
    if success and stdout:
        try:
            import json
            deployment_json = json.loads(stdout)
            
            # Find the ttyd container in the template spec
            ttyd_container = None
            for container in deployment_json.get('spec', {}).get('template', {}).get('spec', {}).get('containers', []):
                if container.get('name') == 'ttyd':
                    ttyd_container = container
                    break
            
            if ttyd_container:
                # Check if command and args are set correctly
                if 'command' not in ttyd_container or '/usr/bin/ttyd' not in " ".join(ttyd_container.get('command', [])):
                    logger.warning("ttyd container missing command or has incorrect command, fixing...")
                    
                    # Patch the deployment to add the correct command and args
                    patch_json = {
                        "spec": {
                            "template": {
                                "spec": {
                                    "containers": [
                                        {
                                            "name": "ttyd",
                                            "command": ["/usr/bin/ttyd"],
                                            "args": ["--port", "7681", "--interface", "0.0.0.0", "--credential", "user:password", "/bin/sh"]
                                        }
                                    ]
                                }
                            }
                        }
                    }
                    
                    patch_cmd = f"kubectl patch deployment {deployment_name} -n {namespace} --type=strategic --patch '{json.dumps(patch_json)}'"
                    success, stdout, stderr = execute_remote_command(client, patch_cmd)
                    
                    if success:
                        logger.info("Successfully patched ttyd container configuration")
                        
                        # Wait for the deployment to apply changes
                        logger.info("Waiting for deployment rollout to complete after patching...")
                        execute_remote_command(client, f"kubectl rollout status deployment/{deployment_name} -n {namespace} --timeout=60s")
                        
                        # Since we patched the deployment, we should refresh running status
                        exists_in_k8s, running_in_k8s, pod_details = check_pod_status(client, namespace, pod_name)
                        logger.info(f"After patching: pod exists={exists_in_k8s}, running={running_in_k8s}")
                    else:
                        logger.error(f"Failed to patch existing ttyd container: {stderr}")
                else:
                    logger.info("ttyd container has correct command configuration")
                    
                if 'args' not in ttyd_container or not any('--credential' in arg for arg in ttyd_container.get('args', [])):
                    logger.warning("ttyd container missing args or has incorrect args, this may cause login issues")
                else:
                    logger.info("ttyd container has correct args configuration")
            else:
                logger.error("Could not find ttyd container in existing deployment spec")
        except Exception as e:
            logger.error(f"Error validating existing ttyd configuration: {str(e)}")
    else:
        logger.warning("Could not validate ttyd container configuration")
    
    # Apply the Service
    service_yaml = f"""
apiVersion: v1
kind: Service
metadata:
  name: {service_name}
  namespace: {namespace}
  labels:
    app: {namespace}
    component: ttyd-service
spec:
  type: NodePort
  ports:
  - port: 8080
    targetPort: 8080
    name: http
  - port: 7681
    targetPort: 7681
    name: ttyd
    protocol: TCP
  - port: 8090
    targetPort: 8080
    name: filebrowser
    protocol: TCP
  selector:
    app: {namespace}
"""
    
    success, stdout, stderr = execute_remote_command(
        client, f"cat > /tmp/{namespace}-service.yaml << 'EOF'\n{service_yaml}\nEOF"
    )
    if not success:
        logger.error("Failed to create service file")
        return False, None, {}
    
    success, stdout, stderr = execute_remote_command(
        client, f"kubectl apply -f /tmp/{namespace}-service.yaml"
    )
    if not success:
        logger.error("Failed to apply service")
        return False, None, {}
    
    # Wait for pod to be running
    actual_pod_name = None
    service_details = {}
    
    for attempt in range(6):  # Try for up to 1 minute
        logger.info(f"Checking pod status (attempt {attempt+1}/6)...")
        
        success, stdout, stderr = execute_remote_command(
            client,
            f"kubectl get pods -n {namespace} -l app={namespace} -o jsonpath='{{.items[0].metadata.name}}'"
        )
        
        if success and stdout:
            actual_pod_name = stdout.strip()
            logger.info(f"Found pod: {actual_pod_name}")
            
            # Check if pod phase is Running
            success, stdout, stderr = execute_remote_command(
                client,
                f"kubectl get pod {actual_pod_name} -n {namespace} -o jsonpath='{{.status.phase}}'"
            )
            
            if success and stdout.strip() == "Running":
                logger.info("Pod phase is Running, checking container readiness...")
                
                # Also check if all containers are ready
                success, stdout, stderr = execute_remote_command(
                    client,
                    f"kubectl get pod {actual_pod_name} -n {namespace} -o jsonpath='{{.status.containerStatuses[*].ready}}'"
                )
                
                if success and stdout:
                    # The output is a space-separated list of boolean values, one for each container
                    container_ready_states = stdout.strip().split()
                    all_ready = all(state == "true" for state in container_ready_states)
                    
                    if not all_ready:
                        logger.warning(f"Not all containers are ready: {stdout} - waiting for all containers to be ready...")
                        
                        # Get more detailed information about container status
                        execute_remote_command(
                            client,
                            f"kubectl get pod {actual_pod_name} -n {namespace} -o jsonpath='{{.status.containerStatuses}}'"
                        )
                        
                        # Continue to the next attempt
                        execute_remote_command(client, "sleep 10")
                        continue
                
                logger.info("All containers in pod are ready")
                
                # Get HTTP nodePort
                success, stdout, stderr = execute_remote_command(
                    client,
                    f"kubectl get service {service_name} -n {namespace} -o jsonpath='{{.spec.ports[?(@.name==\"http\")].nodePort}}'"
                )
                
                http_port = stdout.strip() if success and stdout else None
                
                # Get ttyd nodePort
                success, stdout, stderr = execute_remote_command(
                    client, f"kubectl get service {service_name} -n {namespace} -o jsonpath='{{.spec.ports[?(@.name==\"ttyd\")].nodePort}}'"
                )
                
                ttyd_port = stdout.strip() if success and stdout else None
                logger.info(f"Retrieved ttyd nodePort: {ttyd_port}")
                
                # If we couldn't get the ttyd port, try again with a different approach
                if not ttyd_port:
                    logger.warning("Could not get ttyd port with jsonpath, trying alternative method")
                    success, stdout, stderr = execute_remote_command(
                        client, f"kubectl get service {service_name} -n {namespace} -o yaml | grep -A 3 'name: ttyd' | grep nodePort | awk '{{print $2}}'"
                    )
                    ttyd_port = stdout.strip() if success and stdout else None
                    logger.info(f"Alternative method ttyd nodePort: {ttyd_port}")
                    
                    # If still no ttyd port, try one more method
                    if not ttyd_port:
                        success, stdout, stderr = execute_remote_command(
                            client, f"kubectl get service {service_name} -n {namespace} -o json | grep -A 10 '\"name\": \"ttyd\"' | grep nodePort"
                        )
                        # Parse the JSON nodePort value
                        if success and stdout:
                            import re
                            port_match = re.search(r'"nodePort":\s*(\d+)', stdout)
                            if port_match:
                                ttyd_port = port_match.group(1)
                                logger.info(f"Final attempt ttyd nodePort: {ttyd_port}")
                
                # Get node IP
                success, stdout, stderr = execute_remote_command(
                    client,
                    "kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type==\"InternalIP\")].address}'"
                )
                
                node_ip = stdout.strip() if success and stdout else "localhost"
                
                # Create service details with ttyd info
                service_details = {
                    "nodePort": http_port,
                    "ttydPort": ttyd_port,
                    "nodeIP": node_ip,
                    "url": f"http://{node_ip}:{http_port}" if http_port else None,
                    "ttydUrl": f"http://{node_ip}:{ttyd_port}" if ttyd_port else None
                }
                
                # Get filebrowser nodePort
                success, stdout, stderr = execute_remote_command(
                    client, f"kubectl get service {service_name} -n {namespace} -o jsonpath='{{.spec.ports[?(@.name==\"filebrowser\")].nodePort}}'"
                )
                
                filebrowser_port = stdout.strip() if success and stdout else None
                logger.info(f"Retrieved filebrowser nodePort: {filebrowser_port}")
                
                # If we couldn't get the filebrowser port, try again with a different approach
                if not filebrowser_port:
                    logger.warning("Could not get filebrowser port with jsonpath, trying alternative method")
                    success, stdout, stderr = execute_remote_command(
                        client, f"kubectl get service {service_name} -n {namespace} -o yaml | grep -A 3 'name: filebrowser' | grep nodePort | awk '{{print $2}}'"
                    )
                    filebrowser_port = stdout.strip() if success and stdout else None
                    logger.info(f"Alternative method filebrowser nodePort: {filebrowser_port}")
                    
                    # If still no filebrowser port, try one more method
                    if not filebrowser_port:
                        success, stdout, stderr = execute_remote_command(
                            client, f"kubectl get service {service_name} -n {namespace} -o json | grep -A 10 '\"name\": \"filebrowser\"' | grep nodePort"
                        )
                        # Parse the JSON nodePort value
                        if success and stdout:
                            import re
                            port_match = re.search(r'"nodePort":\s*(\d+)', stdout)
                            if port_match:
                                filebrowser_port = port_match.group(1)
                                logger.info(f"Final attempt filebrowser nodePort: {filebrowser_port}")
                
                # Add filebrowser info to service details
                if filebrowser_port:
                    service_details["filebrowserPort"] = filebrowser_port
                    service_details["filebrowserUrl"] = f"http://{node_ip}:{filebrowser_port}"
                
                logger.info(f"Service details: {service_details}")
                
                # Verify the ttydUrl is set
                if not service_details.get("ttydUrl"):
                    logger.warning("ttydUrl is not set in service_details")
                    
                    # Dump detailed info about the service for debugging
                    execute_remote_command(
                        client, f"kubectl get service {service_name} -n {namespace} -o yaml"
                    )
                
                # Clean up temporary files
                execute_remote_command(
                    client, f"rm -f /tmp/{namespace}-*.yaml"
                )
                
                return True, actual_pod_name, service_details
            
            logger.info(f"Pod status: {stdout.strip() if success else 'unknown'}, waiting...")
        else:
            logger.info("Pod not found yet, waiting...")
        
        # Wait before checking again
        execute_remote_command(client, "sleep 10")
    
    # If we get here, the pod didn't reach Running state
    logger.error("Pod didn't reach Running state. Checking pod events...")
    
    # Get detailed information about the pod
    if actual_pod_name:
        execute_remote_command(
            client, f"kubectl describe pod {actual_pod_name} -n {namespace}"
        )
        
        # Check pod logs if available
        execute_remote_command(
            client, f"kubectl logs {actual_pod_name} -n {namespace} 2>/dev/null || echo 'No logs available'"
        )
    
    # Check for events in the namespace
    execute_remote_command(
        client, f"kubectl get events -n {namespace} --sort-by='.lastTimestamp'"
    )
    
    # Check for any pod status
    execute_remote_command(
        client, f"kubectl get pods -n {namespace} -o wide"
    )
    
    # Check node status
    execute_remote_command(
        client, "kubectl get nodes"
    )
    
    # Check if there are any resource issues on the node
    execute_remote_command(
        client, "kubectl describe nodes | grep -A 5 'Allocated resources'"
    )
    
    # Clean up temporary files
    execute_remote_command(
        client, f"rm -f /tmp/{namespace}-*.yaml"
    )
    
    logger.error(f"Failed to create pod in namespace {namespace}")
    return False, None, {}


def get_kubernetes_access_config():
    """
    Get Kubernetes API access configuration from the environment.
    
    Returns:
        dict: Dictionary with cluster_host, kubeconfig, and token information
    """
    access_config = {
        'cluster_host': None,
        'kubeconfig': None,
        'token': None
    }
    
    try:
        # Try to load kubeconfig
        kube_config_path = os.environ.get('KUBECONFIG') or os.path.expanduser('~/.kube/config')
        if os.path.exists(kube_config_path):
            logger.info(f"Loading kubeconfig from {kube_config_path}")
            try:
                import yaml
                with open(kube_config_path, 'r') as f:
                    kubeconfig = yaml.safe_load(f)
                    
                # Extract current context info
                current_context = kubeconfig.get('current-context')
                
                # Find the cluster info
                if current_context:
                    for context in kubeconfig.get('contexts', []):
                        if context.get('name') == current_context:
                            cluster_name = context.get('context', {}).get('cluster')
                            if cluster_name:
                                for cluster in kubeconfig.get('clusters', []):
                                    if cluster.get('name') == cluster_name:
                                        access_config['cluster_host'] = cluster.get('cluster', {}).get('server')
                                        break
                            break
                
                # Store the full kubeconfig for direct use
                access_config['kubeconfig'] = kubeconfig
                
                # Try to extract a token
                for user in kubeconfig.get('users', []):
                    user_data = user.get('user', {})
                    if user_data.get('token'):
                        access_config['token'] = user_data.get('token')
                        break
                
                logger.info(f"Extracted Kubernetes cluster_host: {access_config['cluster_host']}")
                return access_config
            except Exception as e:
                logger.error(f"Error loading kubeconfig: {str(e)}")
        
        # Try to load from environment variables as fallback
        if os.environ.get('KUBERNETES_SERVICE_HOST'):
            access_config['cluster_host'] = f"https://{os.environ.get('KUBERNETES_SERVICE_HOST')}:{os.environ.get('KUBERNETES_SERVICE_PORT')}"
            
            # Try to load token from service account
            token_path = '/var/run/secrets/kubernetes.io/serviceaccount/token'
            if os.path.exists(token_path):
                with open(token_path, 'r') as f:
                    access_config['token'] = f.read().strip()
                
            logger.info(f"Using in-cluster Kubernetes config: {access_config['cluster_host']}")
            return access_config
        
        # If all else fails, try using direct connection details from SSH
        logger.warning("No standard Kubernetes config found, will use direct SSH connection to pod")
        return access_config
        
    except Exception as e:
        logger.exception(f"Error getting Kubernetes access config: {str(e)}")
        return access_config


def manage_kubernetes_pod(project_id=None, conversation_id=None, image="gitpod/workspace-full:latest", resource_limits=None):
    """
    Create or manage a Kubernetes pod for a project or conversation.
    
    Args:
        project_id (str): Project ID (optional)
        conversation_id (str): Conversation ID (optional)
        image (str): Docker image to use (default: "gitpod/workspace-full:latest")
        resource_limits (dict): Resource limits to apply to the pod (optional)
        
    Returns:
        tuple: (success, pod, error_message)
    """
    if not (project_id or conversation_id):
        logger.error("Either project_id or conversation_id must be provided")
        return False, None, "Either project_id or conversation_id must be provided"
    
    try:
        # Get Kubernetes API access configuration
        k8s_access_config = get_kubernetes_access_config()
        logger.info(f"Got Kubernetes access config with cluster_host: {k8s_access_config.get('cluster_host')}")
        
        # Get SSH connection to Kubernetes server
        client = create_ssh_client()
        if not client:
            logger.error("Failed to create SSH client")
            return False, None, "Failed to create SSH connection to Kubernetes server"
        
        try:
            # Check if pod already exists
            # First check if we have a record in the database
            pod = None
            if project_id:
                pod = KubernetesPod.objects.filter(project_id=project_id).first()
            elif conversation_id:
                pod = KubernetesPod.objects.filter(conversation_id=conversation_id).first()
            
            # Generate a unique namespace for this project/conversation
            namespace = generate_namespace(project_id, conversation_id)
            expected_pod_name = f"{namespace}-pod"
            deployment_name = f"{namespace}-dep"
            
            # First check if there's a deployment in the namespace
            deployment_exists = check_deployment_exists(client, namespace, deployment_name)
            logger.info(f"Deployment check: exists={deployment_exists}")
            
            # If a deployment exists, check if pods are running
            # Don't specify pod_name here - we want to find any pod in the namespace
            exists_in_k8s, running_in_k8s, pod_details = check_pod_status(client, namespace)
            
            # If we found pod details, get the actual pod name
            actual_pod_name = None
            if pod_details:
                actual_pod_name = pod_details.get('metadata', {}).get('name', '')
                logger.info(f"Found pod in K8s: {actual_pod_name}, running={running_in_k8s}")
            else:
                logger.info(f"No pod found in K8s for namespace {namespace}")
            
            # We have four cases to handle:
            # 1. Pod exists in DB and is running in K8s -> Just update DB record with actual pod name
            # 2. Pod exists in DB but not running in K8s -> Start or recreate pod
            # 3. Pod doesn't exist in DB but exists in K8s -> Create DB record for existing pod
            # 4. Pod doesn't exist anywhere -> Create new pod and DB record
            
            # Case 3: Pod exists in K8s but not in DB - create DB record
            if (exists_in_k8s or deployment_exists) and not pod:
                logger.info(f"Resources exist in Kubernetes but not in database. Creating database record.")
                
                # If we found pod details, use them
                if pod_details:
                    containers = pod_details.get('spec', {}).get('containers', [{}])
                    actual_image = containers[0].get('image', image) if containers else image
                else:
                    # Otherwise use default values
                    actual_image = image
                
                # Ensure actual_image is never None or empty, use default if needed
                if not actual_image:
                    logger.warning(f"No image found for existing pod, using default image: {image}")
                    actual_image = image
                
                logger.info(f"Creating pod record with image: {actual_image}")
                
                pod = KubernetesPod(
                    project_id=project_id,
                    conversation_id=conversation_id,
                    namespace=namespace,
                    pod_name=actual_pod_name or expected_pod_name,
                    image=actual_image,
                    status='running' if running_in_k8s else 'created',
                    resource_limits=resource_limits,
                    ssh_connection_details=get_k8s_server_settings(),
                    # Add Kubernetes API access details
                    cluster_host=k8s_access_config.get('cluster_host'),
                    kubeconfig=k8s_access_config.get('kubeconfig'),
                    token=k8s_access_config.get('token')
                )
                
                # If the pod is running, get service details
                if running_in_k8s:
                    success, _, service_details = get_pod_service_details(client, namespace, actual_pod_name)
                    if success and service_details:
                        pod.service_details = service_details
                
                pod.save()
                
                # Create port mapping records for the pod
                service_name = f"{namespace}-service"
                create_port_mappings(pod, service_details if 'service_details' in locals() else {}, service_name)
                
                logger.info(f"Created database record for existing Kubernetes pod {pod.pod_name}")
                
                if running_in_k8s:
                    return True, pod, None
            
            # Case 1: Pod exists in both DB and K8s and is running
            if pod and exists_in_k8s and running_in_k8s:
                logger.info(f"Pod {pod.pod_name} is already running in namespace {pod.namespace}")
                
                # Update pod name in database if it doesn't match actual pod name in K8s
                # This is important if the pod was created by a deployment with a different name format
                if actual_pod_name and pod.pod_name != actual_pod_name:
                    logger.info(f"Updating pod name in database from {pod.pod_name} to {actual_pod_name}")
                    pod.pod_name = actual_pod_name
                
                # Update status if needed
                if pod.status != 'running':
                    pod.mark_as_running()
                
                # Update Kubernetes API access details
                if k8s_access_config.get('cluster_host'):
                    pod.cluster_host = k8s_access_config.get('cluster_host')
                if k8s_access_config.get('kubeconfig'):
                    pod.kubeconfig = k8s_access_config.get('kubeconfig')
                if k8s_access_config.get('token'):
                    pod.token = k8s_access_config.get('token')
                else:
                    # Get token for the default service account in the pod's namespace if not provided
                    try:
                        success, stdout, stderr = execute_remote_command(
                            client, f"kubectl -n {pod.namespace} get secret $(kubectl -n {pod.namespace} get serviceaccount default -o jsonpath='{{.secrets[0].name}}') -o jsonpath='{{.data.token}}' | base64 --decode"
                        )
                        
                        if success and stdout:
                            token = stdout.strip()
                            pod.token = token
                            logger.info("Retrieved token for default service account")
                    except Exception as e:
                        logger.warning(f"Failed to get token for pod: {str(e)}")
                
                # Verify ttyd container configuration
                logger.info("Verifying ttyd container configuration for existing deployment...")
                success, stdout, stderr = execute_remote_command(
                    client, f"kubectl get deployment {deployment_name} -n {namespace} -o json"
                )
                
                if success and stdout:
                    try:
                        import json
                        deployment_json = json.loads(stdout)
                        
                        # Find the ttyd container in the template spec
                        ttyd_container = None
                        for container in deployment_json.get('spec', {}).get('template', {}).get('spec', {}).get('containers', []):
                            if container.get('name') == 'ttyd':
                                ttyd_container = container
                                break
                        
                        if ttyd_container:
                            needs_patch = False
                            
                            # Check if command is correctly set
                            if 'command' not in ttyd_container or '/usr/bin/ttyd' not in " ".join(ttyd_container.get('command', [])):
                                logger.warning("Existing ttyd container missing command or has incorrect command, needs patching")
                                needs_patch = True
                            
                            # Check if args are correctly set
                            if 'args' not in ttyd_container or not any('--credential' in arg for arg in ttyd_container.get('args', [])):
                                logger.warning("Existing ttyd container missing args or has incorrect args, needs patching")
                                needs_patch = True
                            
                            if needs_patch:
                                logger.info("Patching existing deployment with correct ttyd configuration")
                                patch_json = {
                                    "spec": {
                                        "template": {
                                            "spec": {
                                                "containers": [
                                                    {
                                                        "name": "ttyd",
                                                        "command": ["/usr/bin/ttyd"],
                                                        "args": ["--port", "7681", "--interface", "0.0.0.0", "--credential", "user:password", "/bin/sh"]
                                                    }
                                                ]
                                            }
                                        }
                                    }
                                }
                                
                                patch_cmd = f"kubectl patch deployment {deployment_name} -n {namespace} --type=strategic --patch '{json.dumps(patch_json)}'"
                                success, stdout, stderr = execute_remote_command(client, patch_cmd)
                                
                                if success:
                                    logger.info("Successfully patched existing ttyd container configuration")
                                    
                                    # Wait for the deployment to apply changes
                                    logger.info("Waiting for deployment rollout to complete after patching...")
                                    execute_remote_command(client, f"kubectl rollout status deployment/{deployment_name} -n {namespace} --timeout=60s")
                                    
                                    # Since we patched the deployment, we should refresh running status
                                    exists_in_k8s, running_in_k8s, pod_details = check_pod_status(client, namespace)
                                    if pod_details:
                                        actual_pod_name = pod_details.get('metadata', {}).get('name', '')
                                        # Update pod name in database if it has changed
                                        if actual_pod_name and pod.pod_name != actual_pod_name:
                                            logger.info(f"Updating pod name after rollout from {pod.pod_name} to {actual_pod_name}")
                                            pod.pod_name = actual_pod_name
                                    
                                    logger.info(f"After patching: pod exists={exists_in_k8s}, running={running_in_k8s}")
                                else:
                                    logger.error(f"Failed to patch existing ttyd container: {stderr}")
                            else:
                                logger.info("Existing ttyd container has correct configuration")
                        else:
                            logger.error("Could not find ttyd container in existing deployment spec")
                    except Exception as e:
                        logger.error(f"Error validating existing ttyd configuration: {str(e)}")
                else:
                    logger.warning("Could not validate existing ttyd container configuration")
                
                # Update SSH connection details
                pod.ssh_connection_details = get_k8s_server_settings()
                
                # Refresh service details - use actual pod name we found in K8s
                success, _, service_details = get_pod_service_details(client, namespace, pod.pod_name)
                if success and service_details:
                    pod.service_details = service_details
                
                pod.save()
                
                # Create port mapping records for the pod
                service_name = f"{namespace}-service"
                create_port_mappings(pod, service_details if 'service_details' in locals() else {}, service_name)
                
                logger.info(f"Updated pod {pod.pod_name} with latest access details")
                return True, pod, None
            
            # Case 2: Pod exists in DB but not running in K8s - try to start existing pod
            if pod and exists_in_k8s and not running_in_k8s:
                logger.info(f"Pod {pod.pod_name} exists but is not running. Attempting to start it.")
                
                # Try to start the existing pod
                pod_started = start_kubernetes_pod(client, pod.namespace, pod.pod_name)
                
                if pod_started:
                    logger.info(f"Successfully started pod {pod.pod_name}")
                    
                    # Check for actual pod name after restart
                    exists_in_k8s, running_in_k8s, pod_details = check_pod_status(client, namespace)
                    if pod_details:
                        actual_pod_name = pod_details.get('metadata', {}).get('name', '')
                        # Update pod name in database if it has changed
                        if actual_pod_name and pod.pod_name != actual_pod_name:
                            logger.info(f"Updating pod name after restart from {pod.pod_name} to {actual_pod_name}")
                            pod.pod_name = actual_pod_name
                    
                    # Update pod status
                    pod.mark_as_running()
                    
                    # Update service details
                    success, _, service_details = get_pod_service_details(client, pod.namespace, pod.pod_name)
                    
                    if success and service_details:
                        pod.service_details = service_details
                    
                    pod.save()
                    return True, pod, None
            
            # Case 4 or fallback from Case 2: Need to create or recreate pod
            logger.info(f"Creating or recreating pod in namespace {namespace}")
            
            # Preserve the pod's original image and resource limits if they exist
            if pod and pod.image:
                image = pod.image
                logger.info(f"Using existing pod image for creation/recreation: {image}")
            
            if pod and pod.resource_limits:
                resource_limits = pod.resource_limits
                logger.info(f"Using existing pod resource limits for creation/recreation")
            
            # Create the pod in Kubernetes
            success, actual_pod_name, service_details = create_kubernetes_pod(client, namespace, image, resource_limits)
            
            if not success:
                logger.error(f"Failed to create pod: {actual_pod_name}")
                if pod:
                    pod.mark_as_error()
                return False, pod, f"Failed to create pod: {actual_pod_name}"
            
            # If pod doesn't exist in database yet, create it now
            if not pod:
                logger.info(f"Creating new pod record in database for {actual_pod_name}")
                pod = KubernetesPod(
                    project_id=project_id,
                    conversation_id=conversation_id,
                    namespace=namespace,
                    pod_name=actual_pod_name or expected_pod_name,
                    image=image,
                    status='created',
                    resource_limits=resource_limits,
                    ssh_connection_details=get_k8s_server_settings(),
                    # Add Kubernetes API access details
                    cluster_host=k8s_access_config.get('cluster_host'),
                    kubeconfig=k8s_access_config.get('kubeconfig'),
                    token=k8s_access_config.get('token')
                )
            
            # Update pod record with actual pod name from K8s
            pod.pod_name = actual_pod_name or pod.pod_name
            pod.namespace = namespace
            pod.service_details = service_details or {}
            pod.mark_as_running()
            
            # Get token for the default service account in the pod's namespace if not already set
            if not pod.token:
                try:
                    logger.info("Attempting to get token for service account")
                    success, stdout, stderr = execute_remote_command(
                        client, f"kubectl -n {pod.namespace} get secret $(kubectl -n {pod.namespace} get serviceaccount default -o jsonpath='{{.secrets[0].name}}') -o jsonpath='{{.data.token}}' | base64 --decode"
                    )
                    
                    if success and stdout:
                        token = stdout.strip()
                        pod.token = token
                        logger.info("Successfully retrieved token")
                except Exception as e:
                    logger.warning(f"Failed to get token for service account: {str(e)}")
            
            # If we don't have a cluster_host yet, get it from kubectl config
            if not pod.cluster_host:
                try:
                    logger.info("Attempting to get cluster host from kubectl config")
                    success, stdout, stderr = execute_remote_command(
                        client, "kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}'"
                    )
                    
                    if success and stdout:
                        cluster_host = stdout.strip()
                        pod.cluster_host = cluster_host
                        logger.info(f"Successfully retrieved cluster host: {cluster_host}")
                except Exception as e:
                    logger.warning(f"Failed to get cluster host: {str(e)}")
            
            # Ensure SSH connection details are set for fallback
            if not pod.ssh_connection_details:
                pod.ssh_connection_details = get_k8s_server_settings()
            
            # Save the pod record
            pod.save()
            
            # Create port mapping records for the pod
            service_name = f"{namespace}-service"
            create_port_mappings(pod, service_details, service_name)
            
            logger.info(f"Pod {pod.pod_name} created successfully in namespace {namespace}")
            logger.info(f"Pod has cluster_host: {pod.cluster_host or 'Not set'}, token: {'Set' if pod.token else 'Not set'}")
            return True, pod, None
        finally:
            client.close()
    except Exception as e:
        logger.exception(f"Error creating or managing Kubernetes pod: {str(e)}")
        
        # Check specifically for integrity errors related to image field
        if 'IntegrityError' in str(e) and 'coding_kubernetespod.image' in str(e):
            logger.error("The error is due to missing image field. This happens when creating a pod record for an existing K8s pod.")
            logger.error(f"Debug info - image: {image}, project_id: {project_id}, conversation_id: {conversation_id}")
        
        # Update pod status if we have a pod
        if 'pod' in locals() and pod:
            pod.mark_as_error()
        
        return False, None, f"Error: {str(e)}"


def execute_command_in_pod(project_id=None, conversation_id=None, command=None):
    """
    Execute a command in a Kubernetes pod.
    
    Args:
        project_id (str): Project ID (optional)
        conversation_id (str): Conversation ID (optional)
        command (str): Command to execute
        
    Returns:
        tuple: (success, stdout, stderr)
    """
    if not (project_id or conversation_id):
        logger.error("Either project_id or conversation_id must be provided")
        return False, "", "Either project_id or conversation_id must be provided"
    
    if not command:
        logger.error("Command must be provided")
        return False, "", "Command must be provided"
    
    try:
        # Get pod details from database
        pod = None
        if project_id:
            pod = KubernetesPod.objects.filter(project_id=project_id).first()
        elif conversation_id:
            pod = KubernetesPod.objects.filter(conversation_id=conversation_id).first()
        
        if not pod:
            logger.error(f"No pod found for project_id={project_id} or conversation_id={conversation_id}")
            return False, "", "No pod found. You need to create a pod first."
        
        # Get SSH connection
        ssh_connection_details = pod.ssh_connection_details
        
        # Create SSH client
        client = None
        if ssh_connection_details:
            client = create_ssh_client(
                host=ssh_connection_details.get('host'),
                port=ssh_connection_details.get('port'),
                username=ssh_connection_details.get('username'),
                key_file=ssh_connection_details.get('key_file'),
                key_string=ssh_connection_details.get('key_string'),
                key_passphrase=ssh_connection_details.get('key_passphrase')
            )
        else:
            client = create_ssh_client()
        
        if not client:
            logger.error("Failed to create SSH client")
            return False, "", "Failed to create SSH connection to Kubernetes server"
        
        try:
            # Check if pod is running - but don't specify pod name to get any pod with app label
            exists, running, pod_details = check_pod_status(client, pod.namespace)
            
            # If we found a pod but it's not the one in our database, update our record
            actual_pod_name = pod.pod_name
            if exists and pod_details:
                found_pod_name = pod_details.get('metadata', {}).get('name', '')
                if found_pod_name and found_pod_name != pod.pod_name:
                    logger.info(f"Found different pod name in K8s ({found_pod_name}) than in database ({pod.pod_name})")
                    actual_pod_name = found_pod_name
                    
                    # Update database record with actual pod name
                    pod.pod_name = actual_pod_name
                    pod.save(update_fields=['pod_name'])
                    logger.info(f"Updated pod name in database to {actual_pod_name}")
            
            if not exists:
                logger.error(f"No pod found in namespace {pod.namespace}")
                return False, "", f"No pod found in namespace {pod.namespace}"
            
            if not running:
                logger.error(f"Pod exists in namespace {pod.namespace} but is not running")
                return False, "", f"Pod exists in namespace {pod.namespace} but is not running"
            
            # Execute command in pod using the actual pod name (from K8s)
            k8s_command = f"kubectl exec -n {pod.namespace} {actual_pod_name} -- {command}"
            success, stdout, stderr = execute_remote_command(client, k8s_command)
            
            return success, stdout, stderr
        finally:
            client.close()
    except Exception as e:
        logger.error(f"Error executing command in pod: {str(e)}")
        return False, "", f"Error: {str(e)}"


def delete_kubernetes_pod(project_id=None, conversation_id=None, preserve_data=True):
    """
    Delete a Kubernetes pod.
    
    Args:
        project_id (str): Project ID (optional)
        conversation_id (str): Conversation ID (optional)
        preserve_data (bool): Whether to preserve the PersistentVolume for user data (default: True)
        
    Returns:
        bool: Success or failure
    """
    if not (project_id or conversation_id):
        logger.error("Either project_id or conversation_id must be provided")
        return False
    
    try:
        # Get pod details from database
        pod = None
        if project_id:
            pod = KubernetesPod.objects.filter(project_id=project_id).first()
        elif conversation_id:
            pod = KubernetesPod.objects.filter(conversation_id=conversation_id).first()
        
        if not pod:
            logger.error(f"No pod found for project_id={project_id} or conversation_id={conversation_id}")
            return True  # No pod to delete, so technically success
        
        # Get SSH connection
        ssh_connection_details = pod.ssh_connection_details
        
        # Create SSH client
        client = None
        if ssh_connection_details:
            client = create_ssh_client(
                host=ssh_connection_details.get('host'),
                port=ssh_connection_details.get('port'),
                username=ssh_connection_details.get('username'),
                key_file=ssh_connection_details.get('key_file'),
                key_string=ssh_connection_details.get('key_string'),
                key_passphrase=ssh_connection_details.get('key_passphrase')
            )
        else:
            client = create_ssh_client()
        
        if not client:
            logger.error("Failed to create SSH client")
            return False
        
        try:
            namespace = pod.namespace
            pv_name = f"{namespace}-pv"
            pvc_name = f"{namespace}-pvc"
            
            # Delete deployments, services and pods
            logger.info(f"Deleting deployments in namespace {namespace}...")
            execute_remote_command(
                client, f"kubectl delete deployment --all -n {namespace}"
            )
            
            logger.info(f"Deleting services in namespace {namespace}...")
            execute_remote_command(
                client, f"kubectl delete service --all -n {namespace}"
            )
            
            logger.info(f"Deleting pods in namespace {namespace}...")
            execute_remote_command(
                client, f"kubectl delete pod --all -n {namespace}"
            )
            
            if not preserve_data:
                # If we're not preserving data, delete PVCs and PVs as well
                logger.info(f"Removing all user data for {namespace}...")
                
                # First check if the PVC exists and delete it
                logger.info(f"Checking if PVC {pvc_name} exists...")
                success, stdout, stderr = execute_remote_command(
                    client, f"kubectl get pvc {pvc_name} -n {namespace} 2>/dev/null || echo 'not found'"
                )
                
                if "not found" not in stdout:
                    logger.info(f"Deleting PVC {pvc_name}...")
                    success, stdout, stderr = execute_remote_command(
                        client, f"kubectl delete pvc {pvc_name} -n {namespace}"
                    )
                    if not success:
                        logger.warning(f"Failed to delete PVC {pvc_name}: {stderr}")
                
                # Wait for PVC to be deleted before deleting PV
                logger.info(f"Waiting for PVC to be fully deleted...")
                execute_remote_command(client, "sleep 5")
                
                # Check if the PV exists and delete it
                logger.info(f"Checking if PV {pv_name} exists...")
                success, stdout, stderr = execute_remote_command(
                    client, f"kubectl get pv {pv_name} 2>/dev/null || echo 'not found'"
                )
                
                if "not found" not in stdout:
                    logger.info(f"Deleting PV {pv_name}...")
                    success, stdout, stderr = execute_remote_command(
                        client, f"kubectl delete pv {pv_name}"
                    )
                    if not success:
                        logger.warning(f"Failed to delete PV {pv_name}: {stderr}")
                        
                        # Try to patch the PV to force deletion if it's stuck
                        logger.info("Attempting to patch PV finalizers to force deletion...")
                        execute_remote_command(
                            client, f"kubectl patch pv {pv_name} -p '{{\"metadata\":{{\"finalizers\":null}}}}'"
                        )
                        
                        # Try to delete again
                        execute_remote_command(
                            client, f"kubectl delete pv {pv_name} --force --grace-period=0"
                        )
                
                # Delete the namespace itself
                logger.info(f"Deleting namespace {namespace}...")
                success, stdout, stderr = execute_remote_command(
                    client, f"kubectl delete namespace {namespace}"
                )
                
                # Optionally delete the data directory on the host
                logger.info(f"Removing data directory /mnt/data/user-volumes/{namespace} on host...")
                execute_remote_command(
                    client, f"rm -rf /mnt/data/user-volumes/{namespace}"
                )
                
                success = True
            else:
                # If preserving data, just stop the pod but keep the namespace, PVC, and PV
                logger.info(f"Preserving PV and PVC for namespace {namespace} to retain user data")
                success = True
            
            # Mark pod as stopped in database
            pod.mark_as_stopped()
            
            return success
        finally:
            client.close()
    except Exception as e:
        logger.error(f"Error deleting Kubernetes pod: {str(e)}")
        return False


def start_kubernetes_pod(client, namespace, pod_name):
    """
    Start a Kubernetes pod that exists but is not running.
    
    Args:
        client (paramiko.SSHClient): SSH client
        namespace (str): Kubernetes namespace
        pod_name (str): The name of the pod to start
        
    Returns:
        bool: True if the pod was started successfully, False otherwise
    """
    logger.info(f"Attempting to start pod {pod_name} in namespace {namespace}")
    
    # First check if any pod with the app label exists and is running
    success, stdout, stderr = execute_remote_command(
        client, f"kubectl get pods -n {namespace} -l app={namespace} -o jsonpath='{{.items[*].metadata.name}}'"
    )
    
    if success and stdout:
        pod_names = stdout.strip().split()
        logger.info(f"Found {len(pod_names)} pods with app={namespace} label: {pod_names}")
        
        # Check if any of these pods are running
        for found_pod in pod_names:
            success, stdout, stderr = execute_remote_command(
                client, f"kubectl get pod {found_pod} -n {namespace} -o jsonpath='{{.status.phase}}'"
            )
            
            if success and stdout.strip() == 'Running':
                logger.info(f"Pod {found_pod} is already running")
                return True
    
    # Check if the specific pod exists
    success, stdout, stderr = execute_remote_command(
        client, f"kubectl get pod {pod_name} -n {namespace} -o jsonpath='{{.status.phase}}' 2>/dev/null || echo 'NotFound'"
    )
    
    pod_status = stdout.strip()
    logger.info(f"Pod {pod_name} current status: {pod_status}")
    
    if pod_status == 'NotFound':
        logger.info(f"Pod {pod_name} not found in namespace {namespace}, will check if deployment exists")
        
        # Check if a deployment exists that should create this pod
        deployment_name = f"{namespace}-dep"
        success, stdout, stderr = execute_remote_command(
            client, f"kubectl get deployment {deployment_name} -n {namespace} 2>/dev/null || echo 'NotFound'"
        )
        
        if 'NotFound' in stdout:
            logger.error(f"No deployment found in namespace {namespace} to create pods")
            return False
        
        logger.info(f"Deployment exists, will scale it to force pod recreation")
        
        # Scale down and up to force pod recreation
        execute_remote_command(
            client, f"kubectl scale deployment {deployment_name} -n {namespace} --replicas=0"
        )
        
        # Wait for pods to be terminated
        logger.info("Waiting for pods to be terminated...")
        execute_remote_command(client, "sleep 3")
        
        # Scale back up
        execute_remote_command(
            client, f"kubectl scale deployment {deployment_name} -n {namespace} --replicas=1"
        )
    elif pod_status == 'Running':
        logger.info(f"Pod {pod_name} is already running")
        return True
    else:
        # If pod exists but is not running, try to restart it
        logger.info(f"Deleting non-running pod {pod_name} so it can be recreated by deployment")
        execute_remote_command(
            client, f"kubectl delete pod {pod_name} -n {namespace} --grace-period=0 --force"
        )
        
        # Wait for the pod to be deleted
        logger.info("Waiting for pod deletion to complete...")
        for i in range(5):  # Wait up to 15 seconds
            success, stdout, stderr = execute_remote_command(
                client, f"kubectl get pod {pod_name} -n {namespace} 2>/dev/null || echo 'NotFound'"
            )
            
            if 'NotFound' in stdout:
                logger.info(f"Pod {pod_name} has been deleted")
                break
                
            logger.info("Pod still exists, waiting...")
            execute_remote_command(client, "sleep 3")
    
    # Wait for a new pod to be created and become ready
    logger.info("Waiting for pod to be created and started...")
    new_pod_running = False
    
    for i in range(10):  # Wait up to 60 seconds for the pod to start
        # Find any pod in the namespace with the app label
        success, stdout, stderr = execute_remote_command(
            client, f"kubectl get pods -n {namespace} -l app={namespace} -o jsonpath='{{.items[0].metadata.name}}'"
        )
        
        if success and stdout:
            new_pod_name = stdout.strip()
            logger.info(f"Found pod: {new_pod_name}")
            
            # Check if the pod is running
            success, stdout, stderr = execute_remote_command(
                client, f"kubectl get pod {new_pod_name} -n {namespace} -o jsonpath='{{.status.phase}}'"
            )
            
            if success and stdout.strip() == 'Running':
                logger.info(f"Pod {new_pod_name} phase is Running, checking container readiness...")
                
                # Check if all containers are ready
                success, stdout, stderr = execute_remote_command(
                    client, f"kubectl get pod {new_pod_name} -n {namespace} -o jsonpath='{{.status.containerStatuses[*].ready}}'"
                )
                
                if success and stdout:
                    # The output is a space-separated list of boolean values for each container
                    container_ready_states = stdout.strip().split()
                    all_ready = all(state == "true" for state in container_ready_states)
                    
                    if not all_ready:
                        logger.warning(f"Not all containers in pod {new_pod_name} are ready: {stdout}")
                        
                        # Get more detailed information about container status
                        execute_remote_command(
                            client, f"kubectl get pod {new_pod_name} -n {namespace} -o jsonpath='{{.status.containerStatuses}}'"
                        )
                        
                        # Continue to the next attempt
                        execute_remote_command(client, "sleep 6")
                        continue
                
                logger.info(f"Pod {new_pod_name} is now running with all containers ready")
                new_pod_running = True
                break
        
        logger.info("No pod found yet, waiting for deployment to create one...")
        
        execute_remote_command(client, "sleep 6")
    
    if not new_pod_running:
        logger.error(f"Failed to start pod in namespace {namespace} after multiple attempts")
        
        # Let's check the deployment events for debugging
        deployment_name = f"{namespace}-dep"
        execute_remote_command(
            client, f"kubectl describe deployment {deployment_name} -n {namespace}"
        )
        
        # Check events in the namespace
        execute_remote_command(
            client, f"kubectl get events -n {namespace} --sort-by=.lastTimestamp"
        )
    
    return new_pod_running


def get_pod_service_details(client, namespace, pod_name=None):
    """
    Get service details for a running pod.
    
    Args:
        client (paramiko.SSHClient): SSH client
        namespace (str): Kubernetes namespace
        pod_name (str, optional): Name of the pod
        
    Returns:
        tuple: (success, pod_name, service_details)
    """
    logger.info(f"Getting service details for namespace {namespace}" + (f", pod {pod_name}" if pod_name else ""))
    
    service_name = f"{namespace}-service"
    
    # If no pod name specified, try to find any pod in the namespace
    if not pod_name:
        success, stdout, stderr = execute_remote_command(
            client, f"kubectl get pods -n {namespace} -l app={namespace} -o jsonpath='{{.items[0].metadata.name}}'"
        )
        
        if success and stdout:
            pod_name = stdout.strip()
            logger.info(f"Found pod: {pod_name}")
        else:
            # Try to find any pod in the namespace as fallback
            success, stdout, stderr = execute_remote_command(
                client, f"kubectl get pods -n {namespace} -o jsonpath='{{.items[0].metadata.name}}'"
            )
            
            if success and stdout:
                pod_name = stdout.strip()
                logger.info(f"Found pod using fallback: {pod_name}")
            else:
                logger.error(f"No pods found in namespace {namespace}")
                return False, None, {}
    
    # Check if pod exists
    success, stdout, stderr = execute_remote_command(
        client, f"kubectl get pod {pod_name} -n {namespace} -o jsonpath='{{.status.phase}}' 2>/dev/null || echo 'NotFound'"
    )
    
    if not success or 'NotFound' in stdout:
        logger.warning(f"Pod {pod_name} not found in namespace {namespace}, trying to find any pod")
        
        # Try to find any pod in the namespace
        success, stdout, stderr = execute_remote_command(
            client, f"kubectl get pods -n {namespace} -l app={namespace} -o jsonpath='{{.items[0].metadata.name}}'"
        )
        
        if success and stdout:
            pod_name = stdout.strip()
            logger.info(f"Found alternative pod: {pod_name}")
        else:
            logger.error(f"No pods found with app={namespace} label")
            return False, None, {}
    
    # Check if pod is running
    success, stdout, stderr = execute_remote_command(
        client, f"kubectl get pod {pod_name} -n {namespace} -o jsonpath='{{.status.phase}}'"
    )
    
    if not success or stdout.strip() != 'Running':
        logger.error(f"Pod {pod_name} is not running (status: {stdout.strip() if success else 'unknown'}), cannot get service details")
        return False, pod_name, {}
    
    # Get HTTP nodePort
    success, stdout, stderr = execute_remote_command(
        client, f"kubectl get service {service_name} -n {namespace} -o jsonpath='{{.spec.ports[?(@.name==\"http\")].nodePort}}'"
    )
    
    http_port = stdout.strip() if success and stdout else None
    
    # Get ttyd nodePort
    success, stdout, stderr = execute_remote_command(
        client, f"kubectl get service {service_name} -n {namespace} -o jsonpath='{{.spec.ports[?(@.name==\"ttyd\")].nodePort}}'"
    )
    
    ttyd_port = stdout.strip() if success and stdout else None
    logger.info(f"Retrieved ttyd nodePort: {ttyd_port}")
    
    # If we couldn't get the ttyd port, try again with a different approach
    if not ttyd_port:
        logger.warning("Could not get ttyd port with jsonpath, trying alternative method")
        success, stdout, stderr = execute_remote_command(
            client, f"kubectl get service {service_name} -n {namespace} -o yaml | grep -A 3 'name: ttyd' | grep nodePort | awk '{{print $2}}'"
        )
        ttyd_port = stdout.strip() if success and stdout else None
        logger.info(f"Alternative method ttyd nodePort: {ttyd_port}")
        
        # If still no ttyd port, try one more method
        if not ttyd_port:
            success, stdout, stderr = execute_remote_command(
                client, f"kubectl get service {service_name} -n {namespace} -o json | grep -A 10 '\"name\": \"ttyd\"' | grep nodePort"
            )
            # Parse the JSON nodePort value
            if success and stdout:
                import re
                port_match = re.search(r'"nodePort":\s*(\d+)', stdout)
                if port_match:
                    ttyd_port = port_match.group(1)
                    logger.info(f"Final attempt ttyd nodePort: {ttyd_port}")
    
    # Get filebrowser nodePort
    success, stdout, stderr = execute_remote_command(
        client, f"kubectl get service {service_name} -n {namespace} -o jsonpath='{{.spec.ports[?(@.name==\"filebrowser\")].nodePort}}'"
    )
    
    filebrowser_port = stdout.strip() if success and stdout else None
    logger.info(f"Retrieved filebrowser nodePort: {filebrowser_port}")
    
    # If we couldn't get the filebrowser port, try again with a different approach
    if not filebrowser_port:
        logger.warning("Could not get filebrowser port with jsonpath, trying alternative method")
        success, stdout, stderr = execute_remote_command(
            client, f"kubectl get service {service_name} -n {namespace} -o yaml | grep -A 3 'name: filebrowser' | grep nodePort | awk '{{print $2}}'"
        )
        filebrowser_port = stdout.strip() if success and stdout else None
        logger.info(f"Alternative method filebrowser nodePort: {filebrowser_port}")
        
        # If still no filebrowser port, try one more method
        if not filebrowser_port:
            success, stdout, stderr = execute_remote_command(
                client, f"kubectl get service {service_name} -n {namespace} -o json | grep -A 10 '\"name\": \"filebrowser\"' | grep nodePort"
            )
            # Parse the JSON nodePort value
            if success and stdout:
                import re
                port_match = re.search(r'"nodePort":\s*(\d+)', stdout)
                if port_match:
                    filebrowser_port = port_match.group(1)
                    logger.info(f"Final attempt filebrowser nodePort: {filebrowser_port}")
    
    # Get node IP
    success, stdout, stderr = execute_remote_command(
        client,
        "kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type==\"InternalIP\")].address}'"
    )
    
    node_ip = stdout.strip() if success and stdout else "localhost"
    
    # Create service details with ttyd and filebrowser info
    service_details = {
        "nodePort": http_port,
        "ttydPort": ttyd_port,
        "nodeIP": node_ip,
        "url": f"http://{node_ip}:{http_port}" if http_port else None,
        "ttydUrl": f"http://{node_ip}:{ttyd_port}" if ttyd_port else None
    }
    
    # Add filebrowser details if available
    if filebrowser_port:
        service_details["filebrowserPort"] = filebrowser_port
        service_details["filebrowserUrl"] = f"http://{node_ip}:{filebrowser_port}"
    
    logger.info(f"Service details for namespace {namespace}: {service_details}")
    
    # Verify the ttydUrl is set
    if not service_details.get("ttydUrl"):
        logger.warning(f"ttydUrl is not set in service_details for namespace {namespace}")
        
        # Dump detailed info about the service for debugging
        execute_remote_command(
            client, f"kubectl get service {service_name} -n {namespace} -o yaml"
        )
        
        return False, pod_name, service_details
    
    return True, pod_name, service_details


def check_deployment_exists(client, namespace, deployment_name=None):
    """
    Check if a deployment exists in the namespace.
    
    Args:
        client (paramiko.SSHClient): SSH client
        namespace (str): Kubernetes namespace
        deployment_name (str, optional): Specific deployment name to check
        
    Returns:
        bool: True if deployment exists, False otherwise
    """
    try:
        # Create namespace if it doesn't exist
        logger.info(f"Checking if namespace {namespace} exists")
        create_ns, create_stdout, create_stderr = execute_remote_command(
            client, f"kubectl get namespace {namespace} || kubectl create namespace {namespace}"
        )
        
        if not create_ns:
            logger.warning(f"Failed to get/create namespace {namespace}: {create_stderr}")
        
        # Get deployment info
        if deployment_name:
            # Check specific deployment
            logger.info(f"Checking if deployment {deployment_name} exists in namespace {namespace}")
            success, stdout, stderr = execute_remote_command(
                client, f"kubectl get deployment {deployment_name} -n {namespace} 2>/dev/null || echo 'NotFound'"
            )
        else:
            # Get any deployment in namespace
            logger.info(f"Checking for any deployments in namespace {namespace}")
            success, stdout, stderr = execute_remote_command(
                client, f"kubectl get deployments -n {namespace} -o name 2>/dev/null || echo 'NotFound'"
            )
        
        if not success:
            logger.warning(f"Command failed when checking deployments: {stderr}")
            return False
            
        exists = stdout.strip() != '' and 'NotFound' not in stdout
        logger.info(f"Deployment {'exists' if exists else 'does not exist'} in namespace {namespace}")
        return exists
    except Exception as e:
        logger.error(f"Error checking deployment status: {str(e)}")
        return False


def create_port_mappings(pod, service_details, service_name=None):
    """
    Create port mapping records for a pod.
    
    Args:
        pod (KubernetesPod): The pod object
        service_details (dict): Service details including port information
        service_name (str, optional): Name of the service, defaults to "{namespace}-service" if not provided
    """
    # If service_name is not provided, generate a default one
    if service_name is None and pod and pod.namespace:
        service_name = f"{pod.namespace}-service"
    
    # Create port mapping for ttyd
    if service_details.get('ttydPort'):
        KubernetesPortMapping.objects.update_or_create(
            pod=pod,
            container_name='ttyd',
            container_port=7681,
            defaults={
                'service_port': 7681,
                'node_port': service_details.get('ttydPort'),
                'protocol': 'TCP',
                'service_name': service_name,
                'description': 'Terminal access via ttyd'
            }
        )
    
    # Create port mapping for filebrowser
    if service_details.get('filebrowserPort'):
        KubernetesPortMapping.objects.update_or_create(
            pod=pod,
            container_name='filebrowser',
            container_port=8080,
            defaults={
                'service_port': 8090,
                'node_port': service_details.get('filebrowserPort'),
                'protocol': 'TCP',
                'service_name': service_name,
                'description': 'File browser for workspace'
            }
        )
