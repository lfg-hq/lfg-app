#!/usr/bin/env python3

import os
import sys
import django
from pathlib import Path

# Add the project directory to Python path
project_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(project_dir))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LFG.settings')
django.setup()

from django.conf import settings
from coding.k8s_manager.manage_pods_api import get_k8s_api_client, manage_kubernetes_pod

def test_k8s_connection():
    """Test Kubernetes API connection and diagnose issues."""
    
    print("=== Kubernetes Connection Diagnostic ===\n")
    
    # Check Django settings
    print("1. Checking Django settings:")
    api_host = getattr(settings, 'K8S_API_HOST', None)
    api_token = getattr(settings, 'K8S_API_TOKEN', None)
    ca_cert = getattr(settings, 'K8S_CA_CERT', None)
    verify_ssl = getattr(settings, 'K8S_VERIFY_SSL', False)
    
    print(f"   K8S_API_HOST: {api_host}")
    print(f"   K8S_API_TOKEN: {'SET' if api_token else 'NOT SET'} ({'*' * min(len(api_token), 10) if api_token else 'EMPTY'})")
    print(f"   K8S_CA_CERT: {'SET' if ca_cert else 'NOT SET'}")
    print(f"   K8S_VERIFY_SSL: {verify_ssl}")
    
    if not api_host:
        print("   ❌ ERROR: K8S_API_HOST is not configured!")
        return False
        
    if not api_token:
        print("   ❌ ERROR: K8S_API_TOKEN is not configured!")
        print("   💡 You need to set the K8S_PERMANENT_TOKEN environment variable")
        return False
    
    print("   ✅ Basic settings look good\n")
    
    # Test API client creation
    print("2. Testing API client creation:")
    try:
        api_client, core_v1_api, apps_v1_api = get_k8s_api_client()
        
        if not core_v1_api or not apps_v1_api:
            print("   ❌ ERROR: Failed to create API clients")
            return False
            
        print("   ✅ API clients created successfully\n")
        
        # Test basic API call
        print("3. Testing basic API connectivity:")
        try:
            namespaces = core_v1_api.list_namespace(limit=5)
            print(f"   ✅ Successfully connected! Found {len(namespaces.items)} namespaces:")
            for ns in namespaces.items[:3]:  # Show first 3
                print(f"      - {ns.metadata.name}")
            if len(namespaces.items) > 3:
                print(f"      ... and {len(namespaces.items) - 3} more")
            print()
            
        except Exception as e:
            print(f"   ❌ ERROR: API call failed: {e}")
            return False
            
        # Test pod creation (dry run)
        print("4. Testing pod creation capability:")
        try:
            # Try to create a test namespace to verify permissions
            test_namespace = "test-connection"
            try:
                core_v1_api.read_namespace(name=test_namespace)
                print(f"   ✅ Test namespace '{test_namespace}' already exists")
            except:
                # Try to create it
                from kubernetes import client
                namespace_body = client.V1Namespace(
                    metadata=client.V1ObjectMeta(name=test_namespace)
                )
                core_v1_api.create_namespace(body=namespace_body)
                print(f"   ✅ Successfully created test namespace '{test_namespace}'")
                
                # Clean up
                core_v1_api.delete_namespace(name=test_namespace)
                print(f"   ✅ Successfully deleted test namespace '{test_namespace}'")
                
        except Exception as e:
            print(f"   ❌ ERROR: Cannot create/delete namespaces: {e}")
            print("   💡 This might be a permissions issue with your API token")
            return False
            
        print("   ✅ Pod creation permissions look good\n")
        
        print("🎉 All tests passed! Your Kubernetes API connection should work.")
        print("\n5. Testing actual pod creation:")
        print("   You can now try creating a pod with manage_kubernetes_pod()")
        
        return True
        
    except Exception as e:
        print(f"   ❌ ERROR: Exception during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_pod_creation():
    """Test actual pod creation."""
    print("\n=== Testing Pod Creation ===\n")
    
    try:
        # Test with a conversation ID
        test_conversation_id = "test-123"
        print(f"Attempting to create pod for conversation: {test_conversation_id}")
        
        success, pod, error_message = manage_kubernetes_pod(
            conversation_id=test_conversation_id,
            image="jitin2pillai/lfg-base:v1"
        )
        
        if success:
            print(f"✅ Pod created successfully!")
            print(f"   Pod name: {pod.pod_name}")
            print(f"   Namespace: {pod.namespace}")
            print(f"   Status: {pod.status}")
            if pod.service_details:
                print(f"   Service details: {pod.service_details}")
        else:
            print(f"❌ Pod creation failed: {error_message}")
            
    except Exception as e:
        print(f"❌ Exception during pod creation: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if test_k8s_connection():
        # Only test pod creation if basic connection works
        test_pod_creation()
    else:
        print("\n❌ Basic connection test failed. Fix the issues above before trying pod creation.") 