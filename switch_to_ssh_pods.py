#!/usr/bin/env python3

"""
Quick script to switch from API-based to SSH-based Kubernetes pod management.
Run this if you're having issues with the API approach and want to fall back to SSH.
"""

import os
from pathlib import Path

def switch_to_ssh():
    """Switch the imports in views.py to use SSH-based pod management."""
    
    views_file = Path("coding/views.py")
    
    if not views_file.exists():
        print("❌ coding/views.py not found!")
        return False
    
    # Read the current file
    with open(views_file, 'r') as f:
        content = f.read()
    
    # Replace the import line
    old_import = "from coding.k8s_manager.manage_pods_api import manage_kubernetes_pod, execute_command_in_pod, delete_kubernetes_pod"
    new_import = "from coding.k8s_manager.manage_pods import manage_kubernetes_pod, execute_command_in_pod, delete_kubernetes_pod"
    
    if old_import in content:
        content = content.replace(old_import, new_import)
        
        # Write back to file
        with open(views_file, 'w') as f:
            f.write(content)
        
        print("✅ Successfully switched to SSH-based pod management!")
        print("   Updated import in coding/views.py")
        print("   The system will now use SSH + kubectl commands instead of direct API calls")
        print("\n💡 Make sure your SSH connection settings are correct in settings.py:")
        print("   - K8S_SSH_HOST")
        print("   - K8S_SSH_USERNAME") 
        print("   - K8S_SSH_KEY_STRING or K8S_SSH_KEY_FILE")
        return True
    else:
        print("⚠️  Import line not found or already using SSH-based approach")
        print(f"   Looking for: {old_import}")
        return False

def switch_to_api():
    """Switch the imports in views.py to use API-based pod management."""
    
    views_file = Path("coding/views.py")
    
    if not views_file.exists():
        print("❌ coding/views.py not found!")
        return False
    
    # Read the current file
    with open(views_file, 'r') as f:
        content = f.read()
    
    # Replace the import line
    old_import = "from coding.k8s_manager.manage_pods import manage_kubernetes_pod, execute_command_in_pod, delete_kubernetes_pod"
    new_import = "from coding.k8s_manager.manage_pods_api import manage_kubernetes_pod, execute_command_in_pod, delete_kubernetes_pod"
    
    if old_import in content:
        content = content.replace(old_import, new_import)
        
        # Write back to file
        with open(views_file, 'w') as f:
            f.write(content)
        
        print("✅ Successfully switched to API-based pod management!")
        print("   Updated import in coding/views.py")
        print("   The system will now use direct Kubernetes API calls")
        print("\n💡 Make sure your API connection settings are correct in settings.py:")
        print("   - K8S_API_HOST")
        print("   - K8S_API_TOKEN")
        return True
    else:
        print("⚠️  Import line not found or already using API-based approach")
        print(f"   Looking for: {old_import}")
        return False

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2 or sys.argv[1] not in ['ssh', 'api']:
        print("Usage: python switch_to_ssh_pods.py [ssh|api]")
        print("  ssh - Switch to SSH-based pod management")
        print("  api - Switch to API-based pod management")
        sys.exit(1)
    
    mode = sys.argv[1]
    
    if mode == 'ssh':
        switch_to_ssh()
    elif mode == 'api':
        switch_to_api() 