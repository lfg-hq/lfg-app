#!/usr/bin/env python
"""
Test script for Kubernetes file management APIs
This script tests all the Kubernetes API endpoints for Monaco editor integration
"""

import requests
import json
import argparse
import sys
import time


class KubernetesAPITester:
    def __init__(self, base_url, project_id=None, conversation_id=None, verbose=False):
        self.base_url = base_url.rstrip('/')
        self.project_id = project_id
        self.conversation_id = conversation_id
        self.verbose = verbose
        
        if not project_id and not conversation_id:
            print("Error: Either project_id or conversation_id must be provided")
            sys.exit(1)
        
        self.identifier = {"project_id": project_id} if project_id else {"conversation_id": conversation_id}
        self.test_file_path = "/workspace/test_api_file.txt"
        self.test_folder_path = "/workspace/test_api_folder"
        self.test_file_content = "This is a test file created by the API tester\nLine 2\nLine 3"

    def log(self, message):
        if self.verbose:
            print(message)

    def make_request(self, endpoint, data):
        """Make a POST request to the API endpoint"""
        url = f"{self.base_url}/coding/k8s/{endpoint}/"
        headers = {"Content-Type": "application/json"}
        payload = {**self.identifier, **data}
        
        self.log(f"REQUEST to {endpoint}: {json.dumps(payload, indent=2)}")
        
        response = requests.post(url, json=payload, headers=headers)
        
        try:
            response_data = response.json()
            self.log(f"RESPONSE from {endpoint}: {json.dumps(response_data, indent=2)}")
        except:
            self.log(f"RESPONSE from {endpoint} (not JSON): {response.text}")
            response_data = {"status": "error", "message": response.text}
        
        return response.status_code, response_data

    def test_get_pod_info(self):
        print("\n--- Testing get_pod_info API ---")
        status_code, response = self.make_request("get_pod_info", {})
        
        if status_code == 200 and response.get("status") == "running":
            print("✅ Pod info API test passed")
            return True
        else:
            print("❌ Pod info API test failed")
            print(f"Status code: {status_code}")
            print(f"Response: {json.dumps(response, indent=2)}")
            return False

    def test_get_file_tree(self):
        print("\n--- Testing get_file_tree API ---")
        status_code, response = self.make_request("get_file_tree", {"directory": "/workspace"})
        
        if status_code == 200 and "files" in response:
            print("✅ Get file tree API test passed")
            return True
        else:
            print("❌ Get file tree API test failed")
            print(f"Status code: {status_code}")
            print(f"Response: {json.dumps(response, indent=2)}")
            return False

    def test_create_folder(self):
        print("\n--- Testing create_folder API ---")
        status_code, response = self.make_request("create_folder", {"path": self.test_folder_path})
        
        if status_code == 200 and response.get("status") == "success":
            print("✅ Create folder API test passed")
            return True
        else:
            print("❌ Create folder API test failed")
            print(f"Status code: {status_code}")
            print(f"Response: {json.dumps(response, indent=2)}")
            return False

    def test_save_file(self):
        print("\n--- Testing save_file API ---")
        status_code, response = self.make_request("save_file", {
            "path": self.test_file_path,
            "content": self.test_file_content
        })
        
        if status_code == 200 and response.get("status") == "success":
            print("✅ Save file API test passed")
            return True
        else:
            print("❌ Save file API test failed")
            print(f"Status code: {status_code}")
            print(f"Response: {json.dumps(response, indent=2)}")
            return False

    def test_get_file_content(self):
        print("\n--- Testing get_file_content API ---")
        status_code, response = self.make_request("get_file_content", {"path": self.test_file_path})
        
        if status_code == 200 and response.get("content") == self.test_file_content:
            print("✅ Get file content API test passed")
            return True
        else:
            print("❌ Get file content API test failed")
            print(f"Status code: {status_code}")
            print(f"Response: {json.dumps(response, indent=2)}")
            return False

    def test_rename_item(self):
        print("\n--- Testing rename_item API ---")
        new_path = f"{self.test_file_path}.renamed"
        status_code, response = self.make_request("rename_item", {
            "old_path": self.test_file_path,
            "new_path": new_path
        })
        
        if status_code == 200 and response.get("status") == "success":
            # Set current path to the renamed path for later tests
            self.test_file_path = new_path
            print("✅ Rename item API test passed")
            return True
        else:
            print("❌ Rename item API test failed")
            print(f"Status code: {status_code}")
            print(f"Response: {json.dumps(response, indent=2)}")
            return False

    def test_execute_command(self):
        print("\n--- Testing execute_command API ---")
        status_code, response = self.make_request("execute_command", {
            "command": f"ls -la {self.test_folder_path}"
        })
        
        if status_code == 200 and response.get("success"):
            print("✅ Execute command API test passed")
            return True
        else:
            print("❌ Execute command API test failed")
            print(f"Status code: {status_code}")
            print(f"Response: {json.dumps(response, indent=2)}")
            return False

    def test_delete_item(self):
        print("\n--- Testing delete_item API (file) ---")
        status_code, response = self.make_request("delete_item", {
            "path": self.test_file_path,
            "is_directory": False
        })
        
        if status_code == 200 and response.get("status") == "success":
            print("✅ Delete file API test passed")
            
            print("\n--- Testing delete_item API (folder) ---")
            status_code, response = self.make_request("delete_item", {
                "path": self.test_folder_path,
                "is_directory": True
            })
            
            if status_code == 200 and response.get("status") == "success":
                print("✅ Delete folder API test passed")
                return True
            else:
                print("❌ Delete folder API test failed")
                print(f"Status code: {status_code}")
                print(f"Response: {json.dumps(response, indent=2)}")
                return False
        else:
            print("❌ Delete file API test failed")
            print(f"Status code: {status_code}")
            print(f"Response: {json.dumps(response, indent=2)}")
            return False

    def run_all_tests(self):
        print(f"Testing Kubernetes APIs at {self.base_url}")
        print(f"Using {'project_id: ' + self.project_id if self.project_id else 'conversation_id: ' + self.conversation_id}")
        
        # Test pod info first to make sure we have a running pod
        if not self.test_get_pod_info():
            print("\n❌ Pod is not running. Cannot continue with tests.")
            return False
        
        # Run all the tests in a reasonable order
        test_functions = [
            self.test_get_file_tree,
            self.test_create_folder,
            self.test_save_file,
            self.test_get_file_content,
            self.test_rename_item,
            self.test_execute_command,
            self.test_delete_item
        ]
        
        results = []
        for test_func in test_functions:
            results.append(test_func())
            time.sleep(0.5)  # Small delay between tests
        
        success_count = results.count(True)
        total_count = len(results)
        
        print("\n--- Test Summary ---")
        print(f"Tests passed: {success_count}/{total_count}")
        
        if success_count == total_count:
            print("\n✅ All tests passed! Your Kubernetes APIs are working correctly.")
            return True
        else:
            print(f"\n❌ {total_count - success_count} tests failed. Please check the logs above.")
            return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Kubernetes APIs for Monaco editor")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base URL of the application")
    parser.add_argument("--project-id", help="Project ID to use for testing")
    parser.add_argument("--conversation-id", help="Conversation ID to use for testing")
    parser.add_argument("--verbose", action="store_true", help="Show detailed request/response information")
    
    args = parser.parse_args()
    
    tester = KubernetesAPITester(
        base_url=args.base_url,
        project_id=args.project_id,
        conversation_id=args.conversation_id,
        verbose=args.verbose
    )
    
    tester.run_all_tests() 