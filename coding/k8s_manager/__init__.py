#!/usr/bin/env python3

import os
import logging
from django.conf import settings
from ..models import KubernetesPod
from .manage_pods import (
    manage_kubernetes_pod,
    execute_command_in_pod,
    delete_kubernetes_pod,
    create_ssh_client,
    execute_remote_command,
    get_k8s_server_settings
)

# Configure logging
logger = logging.getLogger(__name__)

def ensure_persistent_storage_directory():
    """
    Ensure that the persistent storage directory exists on the Kubernetes host.
    This function should be called during application startup.
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info("Checking persistent storage directory for Kubernetes volumes...")
        
        # Get SSH connection settings
        ssh_settings = get_k8s_server_settings()
        
        # Create SSH client
        client = create_ssh_client(
            host=ssh_settings.get('host'),
            port=ssh_settings.get('port'),
            username=ssh_settings.get('username'),
            key_file=ssh_settings.get('key_file'),
            key_string=ssh_settings.get('key_string'),
            key_passphrase=ssh_settings.get('key_passphrase')
        )
        
        if not client:
            logger.error("Failed to create SSH client to check persistent storage")
            logger.error(f"SSH settings: host={ssh_settings.get('host')}, port={ssh_settings.get('port')}, username={ssh_settings.get('username')}")
            logger.error(f"Check your .env file for K8S_SSH_* settings and ensure the SSH key is valid")
            return False
        
        try:
            # First check if /mnt/data exists
            logger.info("Checking if /mnt/data directory exists...")
            success, stdout, stderr = execute_remote_command(
                client, "ls -ld /mnt/data 2>/dev/null || echo 'Not found'"
            )
            
            if "Not found" in stdout:
                logger.warning("/mnt/data does not exist on the Kubernetes host")
                # Try to create the parent directory
                success, stdout, stderr = execute_remote_command(
                    client, "mkdir -p /mnt/data && chmod 755 /mnt/data"
                )
                
                if not success:
                    logger.error(f"Failed to create parent directory /mnt/data: {stderr}")
                    logger.error("You may need to manually create this directory on the Kubernetes host")
                    return False
                logger.info("Created parent directory /mnt/data")
            
            # Create the main persistent storage directory
            storage_dir = "/mnt/data/user-volumes"
            logger.info(f"Creating persistent storage directory: {storage_dir}")
            success, stdout, stderr = execute_remote_command(
                client, f"mkdir -p {storage_dir}"
            )
            
            if not success:
                logger.error(f"Failed to create persistent storage directory: {stderr}")
                return False
            
            # Set permissions
            logger.info(f"Setting permissions on {storage_dir}")
            success, stdout, stderr = execute_remote_command(
                client, f"chmod 777 {storage_dir}"
            )
            
            if not success:
                logger.error(f"Failed to set permissions on persistent storage directory: {stderr}")
                logger.warning("This may cause permission issues when pods try to write to volumes")
                # Continue anyway as it might work with existing permissions
            
            # Verify the directory exists and has correct permissions
            success, stdout, stderr = execute_remote_command(
                client, f"ls -ld {storage_dir}"
            )
            
            if success and stdout:
                logger.info(f"Persistent storage directory {storage_dir} is ready: {stdout.strip()}")
                return True
            else:
                logger.error(f"Failed to verify persistent storage directory: {stderr}")
                return False
        finally:
            client.close()
    except Exception as e:
        logger.error(f"Error ensuring persistent storage directory: {str(e)}")
        # Check if there's a connection error and provide more helpful message
        if "Connection refused" in str(e) or "No such file or directory" in str(e):
            logger.error("Connection to the Kubernetes server failed. Check your SSH connection settings in .env file.")
        return False

def test_persistent_volume_setup(namespace='test-pv'):
    """
    Test the persistent volume setup by creating a PV, PVC, and a test pod.
    This function can be used to diagnose issues with the Kubernetes persistent volume system.
    
    Args:
        namespace (str): Namespace to use for testing (default: 'test-pv')
        
    Returns:
        dict: Diagnostic information
    """
    logger.info(f"Running persistent volume diagnostic test in namespace {namespace}...")
    
    try:
        # Get SSH connection settings
        ssh_settings = get_k8s_server_settings()
        
        # Create SSH client
        client = create_ssh_client(
            host=ssh_settings.get('host'),
            port=ssh_settings.get('port'),
            username=ssh_settings.get('username'),
            key_file=ssh_settings.get('key_file'),
            key_string=ssh_settings.get('key_string'),
            key_passphrase=ssh_settings.get('key_passphrase')
        )
        
        if not client:
            logger.error("Failed to create SSH client for diagnostic test")
            return {"success": False, "error": "Failed to create SSH client", "stage": "initialization"}
        
        results = {
            "success": False,
            "stages": {},
            "errors": []
        }
        
        try:
            # Stage 1: Create test namespace
            stage = "namespace_creation"
            results["stages"][stage] = {"success": False}
            
            success, stdout, stderr = execute_remote_command(
                client, f"kubectl create namespace {namespace}"
            )
            
            if not success:
                results["stages"][stage]["error"] = stderr
                results["errors"].append(f"{stage}: {stderr}")
                return results
            
            results["stages"][stage]["success"] = True
            results["stages"][stage]["output"] = stdout
            
            # Stage 2: Create directory for volume
            stage = "directory_creation"
            results["stages"][stage] = {"success": False}
            
            success, stdout, stderr = execute_remote_command(
                client, f"mkdir -p /mnt/data/user-volumes/{namespace} && chmod 777 /mnt/data/user-volumes/{namespace}"
            )
            
            if not success:
                results["stages"][stage]["error"] = stderr
                results["errors"].append(f"{stage}: {stderr}")
                return results
            
            results["stages"][stage]["success"] = True
            
            # Stage 3: Create PV
            stage = "pv_creation"
            results["stages"][stage] = {"success": False}
            
            pv_yaml = f"""
apiVersion: v1
kind: PersistentVolume
metadata:
  name: {namespace}-pv
  labels:
    type: local
    pvname: {namespace}-pv
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
            
            success, stdout, stderr = execute_remote_command(
                client, f"cat > /tmp/{namespace}-pv.yaml << 'EOF'\n{pv_yaml}\nEOF"
            )
            
            if not success:
                results["stages"][stage]["error"] = stderr
                results["errors"].append(f"{stage} (creating file): {stderr}")
                return results
            
            success, stdout, stderr = execute_remote_command(
                client, f"kubectl apply -f /tmp/{namespace}-pv.yaml"
            )
            
            if not success:
                results["stages"][stage]["error"] = stderr
                results["errors"].append(f"{stage} (applying): {stderr}")
                return results
            
            results["stages"][stage]["success"] = True
            
            # Stage 4: Check PV Status
            stage = "pv_status"
            results["stages"][stage] = {"success": False}
            
            # Wait a bit for the PV to be created
            execute_remote_command(client, "sleep 3")
            
            success, stdout, stderr = execute_remote_command(
                client, f"kubectl get pv {namespace}-pv -o jsonpath='{{.status.phase}}'"
            )
            
            if not success:
                results["stages"][stage]["error"] = stderr
                results["errors"].append(f"{stage}: {stderr}")
                return results
            
            pv_status = stdout.strip()
            results["stages"][stage]["status"] = pv_status
            
            if pv_status != "Available":
                results["stages"][stage]["error"] = f"PV status is {pv_status}, expected Available"
                results["errors"].append(f"{stage}: PV status is {pv_status}, expected Available")
                # Continue anyway to see what happens
            else:
                results["stages"][stage]["success"] = True
            
            # Stage 5: Create PVC
            stage = "pvc_creation"
            results["stages"][stage] = {"success": False}
            
            pvc_yaml = f"""
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: {namespace}-pvc
  namespace: {namespace}
spec:
  storageClassName: manual
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
  volumeName: {namespace}-pv
"""
            
            success, stdout, stderr = execute_remote_command(
                client, f"cat > /tmp/{namespace}-pvc.yaml << 'EOF'\n{pvc_yaml}\nEOF"
            )
            
            if not success:
                results["stages"][stage]["error"] = stderr
                results["errors"].append(f"{stage} (creating file): {stderr}")
                return results
            
            success, stdout, stderr = execute_remote_command(
                client, f"kubectl apply -f /tmp/{namespace}-pvc.yaml"
            )
            
            if not success:
                results["stages"][stage]["error"] = stderr
                results["errors"].append(f"{stage} (applying): {stderr}")
                return results
            
            results["stages"][stage]["success"] = True
            
            # Stage 6: Check PVC Status
            stage = "pvc_status"
            results["stages"][stage] = {"success": False}
            
            # Wait a bit for the PVC to bind
            execute_remote_command(client, "sleep 5")
            
            success, stdout, stderr = execute_remote_command(
                client, f"kubectl get pvc {namespace}-pvc -n {namespace} -o jsonpath='{{.status.phase}}'"
            )
            
            if not success:
                results["stages"][stage]["error"] = stderr
                results["errors"].append(f"{stage}: {stderr}")
                return results
            
            pvc_status = stdout.strip()
            results["stages"][stage]["status"] = pvc_status
            
            if pvc_status != "Bound":
                results["stages"][stage]["error"] = f"PVC status is {pvc_status}, expected Bound"
                results["errors"].append(f"{stage}: PVC status is {pvc_status}, expected Bound")
                
                # Get detailed PVC information
                success, stdout, stderr = execute_remote_command(
                    client, f"kubectl describe pvc {namespace}-pvc -n {namespace}"
                )
                if success:
                    results["stages"][stage]["details"] = stdout
                
                # Continue anyway
            else:
                results["stages"][stage]["success"] = True
            
            # Stage 7: Create a test pod that uses the PVC
            stage = "pod_creation"
            results["stages"][stage] = {"success": False}
            
            pod_yaml = f"""
apiVersion: v1
kind: Pod
metadata:
  name: {namespace}-test-pod
  namespace: {namespace}
spec:
  containers:
  - name: busybox
    image: busybox
    command: ["sh", "-c", "echo 'Testing PV/PVC' > /data/test.txt && sleep 3600"]
    volumeMounts:
    - name: pv-storage
      mountPath: /data
  volumes:
  - name: pv-storage
    persistentVolumeClaim:
      claimName: {namespace}-pvc
"""
            
            success, stdout, stderr = execute_remote_command(
                client, f"cat > /tmp/{namespace}-pod.yaml << 'EOF'\n{pod_yaml}\nEOF"
            )
            
            if not success:
                results["stages"][stage]["error"] = stderr
                results["errors"].append(f"{stage} (creating file): {stderr}")
                return results
            
            success, stdout, stderr = execute_remote_command(
                client, f"kubectl apply -f /tmp/{namespace}-pod.yaml"
            )
            
            if not success:
                results["stages"][stage]["error"] = stderr
                results["errors"].append(f"{stage} (applying): {stderr}")
                return results
            
            results["stages"][stage]["success"] = True
            
            # Stage 8: Wait for Pod to be running and check status
            stage = "pod_status"
            results["stages"][stage] = {"success": False}
            
            # Wait for the pod to start
            execute_remote_command(client, "sleep 10")
            
            success, stdout, stderr = execute_remote_command(
                client, f"kubectl get pod {namespace}-test-pod -n {namespace} -o jsonpath='{{.status.phase}}'"
            )
            
            if not success:
                results["stages"][stage]["error"] = stderr
                results["errors"].append(f"{stage}: {stderr}")
                return results
            
            pod_status = stdout.strip()
            results["stages"][stage]["status"] = pod_status
            
            if pod_status != "Running":
                results["stages"][stage]["error"] = f"Pod status is {pod_status}, expected Running"
                results["errors"].append(f"{stage}: Pod status is {pod_status}, expected Running")
                
                # Get detailed pod information
                success, stdout, stderr = execute_remote_command(
                    client, f"kubectl describe pod {namespace}-test-pod -n {namespace}"
                )
                if success:
                    results["stages"][stage]["details"] = stdout
            else:
                results["stages"][stage]["success"] = True
            
            # Stage 9: Check if file was written to the volume
            stage = "file_writing"
            results["stages"][stage] = {"success": False}
            
            # Wait a bit for the file to be written
            execute_remote_command(client, "sleep 5")
            
            # Check if the file exists in the pod's volume
            success, stdout, stderr = execute_remote_command(
                client, f"kubectl exec {namespace}-test-pod -n {namespace} -- cat /data/test.txt"
            )
            
            if not success:
                results["stages"][stage]["error"] = stderr
                results["errors"].append(f"{stage} (in pod): {stderr}")
            else:
                results["stages"][stage]["pod_file"] = stdout.strip()
                
                # Check if the file also exists on the host
                success, stdout, stderr = execute_remote_command(
                    client, f"cat /mnt/data/user-volumes/{namespace}/test.txt"
                )
                
                if not success:
                    results["stages"][stage]["error"] = stderr
                    results["errors"].append(f"{stage} (on host): {stderr}")
                else:
                    results["stages"][stage]["host_file"] = stdout.strip()
                    results["stages"][stage]["success"] = True
            
            # Final cleanup (optional)
            execute_remote_command(
                client, f"kubectl delete pod {namespace}-test-pod -n {namespace}"
            )
            execute_remote_command(
                client, f"kubectl delete pvc {namespace}-pvc -n {namespace}"
            )
            execute_remote_command(
                client, f"kubectl delete pv {namespace}-pv"
            )
            execute_remote_command(
                client, f"kubectl delete namespace {namespace}"
            )
            
            # Set overall success based on all stages
            results["success"] = all(stage["success"] for stage in results["stages"].values())
            return results
            
        finally:
            client.close()
    except Exception as e:
        logger.error(f"Error in persistent volume diagnostic test: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "stage": "unknown"
        }

# Make functions available at the module level
__all__ = [
    'manage_kubernetes_pod',
    'execute_command_in_pod',
    'delete_kubernetes_pod',
    'ensure_persistent_storage_directory',
    'test_persistent_volume_setup'
] 