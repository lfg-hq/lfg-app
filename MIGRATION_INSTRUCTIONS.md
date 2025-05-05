# Kubernetes WebSocket Terminal Migration

This document provides instructions for transitioning from SSH-based terminal connection to direct WebSocket connection for improved performance and reliability.

## Changes Overview

1. Direct WebSocket connection to Kubernetes pods
2. Fallback to SSH if WebSocket connection fails
3. Support for kubeconfig, token-based, and in-cluster authentication methods
4. Improved error handling and user feedback

## Installation Steps

1. Install required dependencies:
   ```
   pip install kubernetes>=18.0.0 paramiko>=2.10.0
   ```

2. Apply database migrations to add new fields to the KubernetesPod model:
   ```
   python manage.py migrate coding
   ```

3. Ensure proper configuration:
   - Make sure your Kubernetes cluster is accessible either through:
     a. A kubeconfig file (default location or specified in KUBECONFIG env var)
     b. Direct access with cluster_host and token values in the database
     c. In-cluster configuration (if running inside Kubernetes)

## Benefits

1. Better performance: Reduced latency by eliminating SSH hop
2. More reliable connections: Direct WebSocket connection to the Kubernetes API
3. Simplified architecture: No need for SSH access to Kubernetes server
4. Graceful fallback: Falls back to SSH connection if WebSocket connection fails

## Fallback Mechanism

The new terminal connection system will try to connect to pods in this order:

1. Direct Kubernetes WebSocket connection using:
   - Default kubeconfig (from KUBECONFIG env var or ~/.kube/config)
   - KubernetesPod.kubeconfig field (if available)
   - KubernetesPod.token and KubernetesPod.cluster_host fields (if available)
   - In-cluster configuration (if running inside Kubernetes)

2. If all WebSocket connection attempts fail, it will automatically fall back to SSH connection using:
   - SSH connection details from the pod record
   - Running kubectl exec through the SSH connection

This ensures backwards compatibility and reliability even if the WebSocket connection cannot be established.

## Troubleshooting

If you experience issues with the terminal connection:

1. Verify that your KubernetesPod records have the necessary fields populated:
   - For WebSocket: cluster_host, kubeconfig, or token
   - For SSH fallback: ssh_connection_details

2. Ensure the service account has the required permissions:
   - For WebSocket: ability to exec into pods
   - For SSH: proper SSH key access and kubectl capabilities

3. Check the logs for specific error messages:
   - Look for "Error setting up Kubernetes WebSocket connection" for WebSocket issues
   - Look for "Falling back to SSH connection to pod" for fallback activation
   - Look for "Error in SSH fallback method" for SSH fallback failures

4. Update existing pod records with new fields:
   You can use this script to update existing KubernetesPod records with Kubernetes API access details:

   ```python
   from coding.models import KubernetesPod
   from coding.k8s_manager.manage_pods import get_kubernetes_access_config
   
   def update_pods_with_k8s_config():
       pods = KubernetesPod.objects.all()
       k8s_config = get_kubernetes_access_config()
       
       for pod in pods:
           pod.cluster_host = k8s_config.get('cluster_host', '')
           if k8s_config.get('kubeconfig'):
               pod.kubeconfig = k8s_config.get('kubeconfig')
           if k8s_config.get('token'):
               pod.token = k8s_config.get('token')
           pod.save()
           
       print(f"Updated {pods.count()} pod records with Kubernetes access configuration")
   
   # Run the function
   update_pods_with_k8s_config()
   ```

## Testing

Test the terminal connection by:

1. Applying database migrations
2. Installing dependencies
3. Ensuring at least one authentication method is properly configured
4. Connecting to the terminal in the web interface 