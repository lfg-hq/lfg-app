#!/usr/bin/env python3

import os
import sys
import json
import logging
import argparse
import django

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the parent directory to the Python path
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(parent_dir)

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LFG.settings')
django.setup()

# Import the test function
from coding.k8s_manager import test_persistent_volume_setup

def main():
    parser = argparse.ArgumentParser(description='Test Kubernetes persistent volume setup')
    parser.add_argument('--namespace', default='test-pv', help='Namespace for testing (default: test-pv)')
    parser.add_argument('--output', default='console', choices=['console', 'json'], help='Output format (default: console)')
    parser.add_argument('--output-file', help='Output file path (if json format is selected)')

    args = parser.parse_args()

    print(f"Running persistent volume diagnostic test in namespace {args.namespace}...")
    results = test_persistent_volume_setup(namespace=args.namespace)
    
    if args.output == 'json':
        if args.output_file:
            with open(args.output_file, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"Results written to {args.output_file}")
        else:
            print(json.dumps(results, indent=2))
    else:
        # Console output
        print("\n==== PERSISTENT VOLUME DIAGNOSTIC RESULTS ====")
        print(f"Overall success: {'✅ YES' if results.get('success', False) else '❌ NO'}")
        
        if results.get('error'):
            print(f"\nError: {results['error']}")
        
        if 'stages' in results:
            print("\nStages:")
            for stage_name, stage_data in results['stages'].items():
                status = '✅' if stage_data.get('success', False) else '❌'
                print(f"{status} {stage_name}")
                
                if not stage_data.get('success', False) and 'error' in stage_data:
                    print(f"   Error: {stage_data['error']}")
                
                if 'status' in stage_data:
                    print(f"   Status: {stage_data['status']}")
        
        if results.get('errors'):
            print("\nError summary:")
            for i, error in enumerate(results['errors'], 1):
                print(f"{i}. {error}")
                
        print("\nRecommendations:")
        if not results.get('success', False):
            if 'error' in results and 'Connection refused' in results['error']:
                print("- Check your SSH connection settings in .env")
                print("- Verify that the K8S_SSH_HOST is correct and accessible")
                print("- Make sure the SSH key is valid and has proper permissions")
            
            if 'stages' in results:
                if not results['stages'].get('directory_creation', {}).get('success', False):
                    print("- Create the directory /mnt/data on the Kubernetes host manually")
                    print("  Run: mkdir -p /mnt/data/user-volumes && chmod 777 /mnt/data/user-volumes")
                
                if not results['stages'].get('pv_status', {}).get('success', False):
                    print("- Check for existing PersistentVolumes with conflicting names")
                    print("  Run: kubectl get pv")
                
                if not results['stages'].get('pvc_status', {}).get('success', False):
                    print("- Verify that the PersistentVolume and PersistentVolumeClaim have matching storage class names")
                    print("- Check that volume name in PVC matches the PV name")
                
                if not results['stages'].get('pod_status', {}).get('success', False):
                    print("- Check that the pod can access the PVC")
                    print("- Verify that the pod has the correct permissions to write to the volume")
        else:
            print("- Your Kubernetes persistent volume setup is working correctly!")
            print("- You can now use PersistentVolumes for user data in your pods")

if __name__ == "__main__":
    main() 