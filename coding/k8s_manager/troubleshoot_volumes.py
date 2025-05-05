#!/usr/bin/env python3

import os
import sys
import time
import argparse
import subprocess
import random
import string
import json

def run_command(command, shell=True):
    """Run a shell command and return output and status"""
    try:
        result = subprocess.run(
            command,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)

def generate_random_name(prefix="test", length=6):
    """Generate a random name for resources"""
    suffix = ''.join(random.choice(string.ascii_lowercase) for _ in range(length))
    return f"{prefix}-{suffix}"

def wait_for_resource(resource_type, name, namespace=None, field="status.phase", expected_value=None, timeout=30):
    """Wait for a Kubernetes resource to reach a specific state"""
    namespace_arg = f"-n {namespace}" if namespace else ""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        cmd = f"kubectl get {resource_type} {name} {namespace_arg} -o jsonpath='{{.{field}}}'"
        code, stdout, stderr = run_command(cmd)
        
        if code == 0:
            current_value = stdout.strip()
            print(f"{resource_type} {name} {field}: {current_value}")
            
            if expected_value is None or current_value == expected_value:
                return True, current_value
        
        print(f"Waiting for {resource_type} {name}... ({int(timeout - (time.time() - start_time))}s remaining)")
        time.sleep(3)
    
    return False, ""

def test_volume_creation(test_name, host_path_base="/mnt/data/test-volumes"):
    """Test the creation and binding of a PV and PVC"""
    results = {
        "test_name": test_name,
        "success": False,
        "steps": {},
        "cleanup_status": "not_attempted"
    }
    
    # Create host path
    host_path = f"{host_path_base}/{test_name}"
    print(f"Creating host path: {host_path}")
    
    code, stdout, stderr = run_command(f"mkdir -p {host_path} && chmod 777 {host_path}")
    results["steps"]["create_host_path"] = {
        "success": code == 0,
        "output": stdout,
        "error": stderr
    }
    
    if code != 0:
        print(f"Failed to create host path: {stderr}")
        return results
    
    # Create test content
    test_content = f"Test data created at {time.time()}"
    code, stdout, stderr = run_command(f"echo '{test_content}' > {host_path}/test-file.txt")
    results["steps"]["create_test_file"] = {
        "success": code == 0,
        "output": stdout,
        "error": stderr
    }
    
    # Create namespace
    print(f"Creating namespace: {test_name}")
    code, stdout, stderr = run_command(f"kubectl create namespace {test_name}")
    results["steps"]["create_namespace"] = {
        "success": code == 0,
        "output": stdout,
        "error": stderr
    }
    
    if code != 0 and "AlreadyExists" not in stderr:
        print(f"Failed to create namespace: {stderr}")
        return results
    
    # Create PV
    pv_name = f"{test_name}-pv"
    pv_yaml = f"""
apiVersion: v1
kind: PersistentVolume
metadata:
  name: {pv_name}
  labels:
    type: local
    test: {test_name}
spec:
  storageClassName: manual
  capacity:
    storage: 500Mi
  accessModes:
    - ReadWriteOnce
  hostPath:
    path: {host_path}
  persistentVolumeReclaimPolicy: Delete
"""
    
    print(f"Creating PersistentVolume: {pv_name}")
    with open(f"/tmp/{pv_name}.yaml", "w") as f:
        f.write(pv_yaml)
    
    code, stdout, stderr = run_command(f"kubectl apply -f /tmp/{pv_name}.yaml")
    results["steps"]["create_pv"] = {
        "success": code == 0,
        "output": stdout,
        "error": stderr
    }
    
    if code != 0:
        print(f"Failed to create PV: {stderr}")
        cleanup(test_name, results)
        return results
    
    # Wait for PV to be available
    print("Waiting for PV to be available...")
    success, value = wait_for_resource("pv", pv_name, field="status.phase", expected_value="Available")
    results["steps"]["wait_for_pv"] = {
        "success": success,
        "value": value
    }
    
    if not success:
        print("PV did not become Available within the timeout period")
        code, stdout, stderr = run_command(f"kubectl describe pv {pv_name}")
        results["steps"]["describe_pv"] = {
            "output": stdout,
            "error": stderr
        }
        cleanup(test_name, results)
        return results
    
    # Create PVC
    pvc_name = f"{test_name}-pvc"
    pvc_yaml = f"""
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: {pvc_name}
  namespace: {test_name}
spec:
  storageClassName: manual
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 500Mi
  volumeName: {pv_name}
"""
    
    print(f"Creating PersistentVolumeClaim: {pvc_name}")
    with open(f"/tmp/{pvc_name}.yaml", "w") as f:
        f.write(pvc_yaml)
    
    code, stdout, stderr = run_command(f"kubectl apply -f /tmp/{pvc_name}.yaml")
    results["steps"]["create_pvc"] = {
        "success": code == 0,
        "output": stdout,
        "error": stderr
    }
    
    if code != 0:
        print(f"Failed to create PVC: {stderr}")
        cleanup(test_name, results)
        return results
    
    # Wait for PVC to be bound
    print("Waiting for PVC to be bound...")
    success, value = wait_for_resource("pvc", pvc_name, namespace=test_name, field="status.phase", expected_value="Bound")
    results["steps"]["wait_for_pvc"] = {
        "success": success,
        "value": value
    }
    
    if not success:
        print("PVC did not become Bound within the timeout period")
        code, stdout, stderr = run_command(f"kubectl describe pvc {pvc_name} -n {test_name}")
        results["steps"]["describe_pvc"] = {
            "output": stdout,
            "error": stderr
        }
        cleanup(test_name, results)
        return results
    
    # Create a test pod that uses the PVC
    pod_name = f"{test_name}-pod"
    pod_yaml = f"""
apiVersion: v1
kind: Pod
metadata:
  name: {pod_name}
  namespace: {test_name}
spec:
  containers:
  - name: busybox
    image: busybox
    command: ["sh", "-c", "echo 'Test from pod' > /data/pod-file.txt && cat /data/test-file.txt && sleep 3600"]
    volumeMounts:
    - name: test-volume
      mountPath: /data
  volumes:
  - name: test-volume
    persistentVolumeClaim:
      claimName: {pvc_name}
"""
    
    print(f"Creating Pod: {pod_name}")
    with open(f"/tmp/{pod_name}.yaml", "w") as f:
        f.write(pod_yaml)
    
    code, stdout, stderr = run_command(f"kubectl apply -f /tmp/{pod_name}.yaml")
    results["steps"]["create_pod"] = {
        "success": code == 0,
        "output": stdout,
        "error": stderr
    }
    
    if code != 0:
        print(f"Failed to create Pod: {stderr}")
        cleanup(test_name, results)
        return results
    
    # Wait for pod to be running
    print("Waiting for Pod to be running...")
    success, value = wait_for_resource("pod", pod_name, namespace=test_name, field="status.phase", expected_value="Running", timeout=60)
    results["steps"]["wait_for_pod"] = {
        "success": success,
        "value": value
    }
    
    if not success:
        print("Pod did not become Running within the timeout period")
        code, stdout, stderr = run_command(f"kubectl describe pod {pod_name} -n {test_name}")
        results["steps"]["describe_pod"] = {
            "output": stdout,
            "error": stderr
        }
        cleanup(test_name, results)
        return results
    
    # Wait a bit for the container to run its commands
    time.sleep(5)
    
    # Verify that the pod can read the test file
    print("Checking if pod can read the test file...")
    code, stdout, stderr = run_command(f"kubectl logs {pod_name} -n {test_name}")
    results["steps"]["pod_logs"] = {
        "success": code == 0,
        "output": stdout,
        "error": stderr
    }
    
    if test_content in stdout:
        print("SUCCESS: Pod can read the test file from the volume")
        results["steps"]["pod_read_test"] = {
            "success": True,
            "output": "Pod can read the test file from the volume"
        }
    else:
        print("FAILURE: Pod cannot read the test file from the volume")
        results["steps"]["pod_read_test"] = {
            "success": False,
            "output": "Pod cannot read the test file from the volume"
        }
    
    # Verify that the pod can write to the volume
    print("Checking if pod can write to the volume...")
    code, stdout, stderr = run_command(f"ls -la {host_path}")
    results["steps"]["host_dir_content"] = {
        "success": code == 0,
        "output": stdout,
        "error": stderr
    }
    
    if "pod-file.txt" in stdout:
        print("SUCCESS: Pod can write to the volume")
        results["steps"]["pod_write_test"] = {
            "success": True,
            "output": "Pod can write to the volume"
        }
    else:
        print("FAILURE: Pod cannot write to the volume")
        results["steps"]["pod_write_test"] = {
            "success": False,
            "output": "Pod cannot write to the volume"
        }
    
    # Overall test success
    results["success"] = (
        results["steps"].get("wait_for_pv", {}).get("success", False) and
        results["steps"].get("wait_for_pvc", {}).get("success", False) and
        results["steps"].get("wait_for_pod", {}).get("success", False) and
        results["steps"].get("pod_read_test", {}).get("success", False) and
        results["steps"].get("pod_write_test", {}).get("success", False)
    )
    
    # Clean up
    cleanup(test_name, results)
    
    return results

def cleanup(test_name, results):
    """Clean up all created resources"""
    print(f"\nCleaning up resources for test: {test_name}")
    
    # Delete pod
    code, stdout, stderr = run_command(f"kubectl delete pod {test_name}-pod -n {test_name} --grace-period=0 --force 2>/dev/null || true")
    
    # Delete PVC
    code, stdout, stderr = run_command(f"kubectl delete pvc {test_name}-pvc -n {test_name} 2>/dev/null || true")
    
    # Delete PV
    code, stdout, stderr = run_command(f"kubectl delete pv {test_name}-pv 2>/dev/null || true")
    
    # Delete namespace
    code, stdout, stderr = run_command(f"kubectl delete namespace {test_name} 2>/dev/null || true")
    
    # Delete temporary YAML files
    run_command(f"rm -f /tmp/{test_name}-*.yaml 2>/dev/null || true")
    
    # Optional: Delete host path
    run_command(f"rm -rf /mnt/data/test-volumes/{test_name} 2>/dev/null || true")
    
    results["cleanup_status"] = "completed"
    print("Cleanup completed")

def check_k8s_connectivity():
    """Check if kubectl can connect to the cluster"""
    code, stdout, stderr = run_command("kubectl cluster-info")
    if code != 0:
        print(f"Error connecting to Kubernetes cluster: {stderr}")
        return False
    
    print("Successfully connected to Kubernetes cluster:")
    print(stdout)
    return True

def check_storage_provider():
    """Check what storage providers are available in the cluster"""
    code, stdout, stderr = run_command("kubectl get storageclass")
    if code != 0:
        print(f"Error getting storage classes: {stderr}")
        return False
    
    print("Available storage classes:")
    print(stdout)
    return True

def main():
    parser = argparse.ArgumentParser(description="Diagnose Kubernetes Persistent Volume issues")
    parser.add_argument("--name", default="", help="Name for test resources (default: auto-generated)")
    parser.add_argument("--host-path", default="/mnt/data/test-volumes", help="Base host path for test volumes")
    parser.add_argument("--output", default="console", choices=["console", "json"], help="Output format")
    parser.add_argument("--output-file", help="Output file for JSON results")
    
    args = parser.parse_args()
    
    print("==== Kubernetes Persistent Volume Diagnostic Tool ====")
    
    # Check kubectl connectivity
    if not check_k8s_connectivity():
        return 1
    
    # Check storage providers
    check_storage_provider()
    
    # Generate test name if not provided
    test_name = args.name if args.name else generate_random_name("pvtest")
    
    print(f"\nRunning diagnostic test with name: {test_name}")
    
    # Run the test
    results = test_volume_creation(test_name, args.host_path)
    
    # Output results
    if args.output == "json":
        if args.output_file:
            with open(args.output_file, "w") as f:
                json.dump(results, f, indent=2)
            print(f"Results written to {args.output_file}")
        else:
            print(json.dumps(results, indent=2))
    else:
        print("\n==== Test Results ====")
        print(f"Overall Success: {'Yes' if results['success'] else 'No'}")
        print("\nTest Steps:")
        for step, details in results["steps"].items():
            status = "✅ Success" if details.get("success", False) else "❌ Failed"
            print(f"  {step}: {status}")
        
        print("\nRecommendations:")
        if not results["success"]:
            if not results["steps"].get("create_host_path", {}).get("success", False):
                print("- Check permissions on the host system for creating directories")
                print(f"- Ensure the directory path {args.host_path} exists and is writable")
            
            if not results["steps"].get("wait_for_pv", {}).get("success", False):
                print("- Check if there are any existing PVs with the same name")
                print("- Verify that the hostPath is correctly configured in the cluster")
            
            if not results["steps"].get("wait_for_pvc", {}).get("success", False):
                print("- Ensure the PV and PVC have matching accessModes and storage sizes")
                print("- Check that the storageClassName matches between PV and PVC")
            
            if not results["steps"].get("wait_for_pod", {}).get("success", False):
                print("- Check if the pod has permission to use the PVC")
                print("- Verify if the node has enough resources to schedule the pod")
            
            if not results["steps"].get("pod_read_test", {}).get("success", False) or \
               not results["steps"].get("pod_write_test", {}).get("success", False):
                print("- Check if the pod has the correct permissions to read/write to the volume")
                print("- Verify that the host directory has the proper ownership and permissions")
        else:
            print("- Your Kubernetes persistent volume setup is working correctly!")
            print("- You can use the same configuration approach for your application")
    
    return 0 if results["success"] else 1

if __name__ == "__main__":
    sys.exit(main()) 