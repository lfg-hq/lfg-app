from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import os
import json
import subprocess
import git
import shutil
from coding.models import DockerSandbox, KubernetesPod
from django.db.models import Q
from .docker.docker_utils import get_sandbox_by_project_id
from coding.k8s_manager import manage_kubernetes_pod, execute_command_in_pod, delete_kubernetes_pod
import time
import logging

logger = logging.getLogger(__name__)

def editor(request):
    """
    Main view for the Monaco Editor interface
    """
    project_id = request.GET.get('project_id')
    conversation_id = request.GET.get('conversation_id')
    
    # If neither project_id nor conversation_id provided, show a message
    if not project_id and not conversation_id:
        return render(request, 'coding/editor.html', {
            'no_context': True,
            'message': 'Please provide either project_id or conversation_id as a URL parameter.'
        })
    
    # Create context with project or conversation data
    context = {
        # Pass both IDs directly to the template
        'project_id': project_id,
        'conversation_id': conversation_id
    }
    
    return render(request, 'coding/editor.html', context)

@csrf_exempt
def get_file_tree(request):
    """
    API endpoint to get the file structure
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        project_id = data.get('project_id')
        conversation_id = data.get('conversation_id')
        
        # Build query to find matching sandbox
        query = Q(status='running')
        if project_id:
            query &= Q(project_id=project_id)
        elif conversation_id:
            query &= Q(conversation_id=conversation_id)
        else:
            return JsonResponse({'error': 'Either project_id or conversation_id must be provided'}, status=400)
        
        # Get the sandbox record
        sandbox = DockerSandbox.objects.filter(query).first()
        if not sandbox or not sandbox.code_dir:
            return JsonResponse({'error': 'No active sandbox found for the given project or conversation'}, status=404)
        
        # Use the code_dir from the sandbox
        base_path = sandbox.code_dir
    else:
        return JsonResponse({'error': 'POST request expected'}, status=400)
    
    def get_directory_structure(path):
        tree = []
        # Sort so that directories come first, then files, each alphabetically (case‑insensitive)
        entries = sorted(os.listdir(path), key=lambda name: (not os.path.isdir(os.path.join(path, name)), name.lower()))
        for item in entries:
            item_path = os.path.join(path, item)
            if item.startswith('.'):  # Skip hidden files
                continue
            if os.path.isfile(item_path):
                tree.append({
                    'name': item,
                    'type': 'file',
                    'path': os.path.relpath(item_path, base_path)
                })
            elif os.path.isdir(item_path):
                tree.append({
                    'name': item,
                    'type': 'directory',
                    'children': get_directory_structure(item_path),
                    'path': os.path.relpath(item_path, base_path)
                })
        return tree

    try:
        file_tree = get_directory_structure(base_path)
        return JsonResponse({'files': file_tree})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def get_file_content(request):
    """
    API endpoint to get file content
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        file_path = data.get('path')
        project_id = data.get('project_id')
        conversation_id = data.get('conversation_id')
        
        # Build query to find matching sandbox
        query = Q(status='running')
        if project_id:
            query &= Q(project_id=project_id)
        elif conversation_id:
            query &= Q(conversation_id=conversation_id)
        else:
            return JsonResponse({'error': 'Either project_id or conversation_id must be provided'}, status=400)
        
        # Get the sandbox record
        sandbox = DockerSandbox.objects.filter(query).first()
        if not sandbox or not sandbox.code_dir:
            return JsonResponse({'error': 'No active sandbox found for the given project or conversation'}, status=404)
        
        # Use the code_dir from the sandbox
        base_path = sandbox.code_dir
        full_path = os.path.join(base_path, file_path)
        
        try:
            with open(full_path, 'r') as file:
                content = file.read()
            return JsonResponse({'content': content})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'POST request expected'}, status=400)

@csrf_exempt
def save_file(request):
    """
    API endpoint to save file content
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        file_path = data.get('path')
        content = data.get('content')
        project_id = data.get('project_id')
        conversation_id = data.get('conversation_id')
        
        # Build query to find matching sandbox
        query = Q(status='running')
        if project_id:
            query &= Q(project_id=project_id)
        elif conversation_id:
            query &= Q(conversation_id=conversation_id)
        else:
            return JsonResponse({'error': 'Either project_id or conversation_id must be provided'}, status=400)
        
        # Get the sandbox record
        sandbox = DockerSandbox.objects.filter(query).first()
        if not sandbox or not sandbox.code_dir:
            return JsonResponse({'error': 'No active sandbox found for the given project or conversation'}, status=404)
        
        # Use the code_dir from the sandbox
        base_path = sandbox.code_dir
        full_path = os.path.join(base_path, file_path)
        
        try:
            # Make sure directory exists
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            with open(full_path, 'w') as file:
                file.write(content)
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'POST request expected'}, status=400)

@csrf_exempt
def execute_command(request):
    """
    API endpoint to execute terminal commands
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        command = data.get('command')
        project_id = data.get('project_id')
        conversation_id = data.get('conversation_id')
        
        # Build query to find matching sandbox
        query = Q(status='running')
        if project_id:
            query &= Q(project_id=project_id)
        elif conversation_id:
            query &= Q(conversation_id=conversation_id)
        else:
            return JsonResponse({'error': 'Either project_id or conversation_id must be provided'}, status=400)
        
        # Get the sandbox record
        sandbox = DockerSandbox.objects.filter(query).first()
        if not sandbox or not sandbox.code_dir:
            return JsonResponse({'error': 'No active sandbox found for the given project or conversation'}, status=404)
        
        # Use the code_dir from the sandbox as the working directory
        working_dir = sandbox.code_dir
        
        try:
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=working_dir
            )
            stdout, stderr = process.communicate()
            return JsonResponse({
                'stdout': stdout,
                'stderr': stderr,
                'returncode': process.returncode
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'POST request expected'}, status=400)

@csrf_exempt
def create_folder(request):
    """
    API endpoint to create a new folder
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        folder_path = data.get('path')
        project_id = data.get('project_id')
        conversation_id = data.get('conversation_id')
        
        # Build query to find matching sandbox
        query = Q(status='running')
        if project_id:
            query &= Q(project_id=project_id)
        elif conversation_id:
            query &= Q(conversation_id=conversation_id)
        else:
            return JsonResponse({'error': 'Either project_id or conversation_id must be provided'}, status=400)
        
        # Get the sandbox record
        sandbox = DockerSandbox.objects.filter(query).first()
        if not sandbox or not sandbox.code_dir:
            return JsonResponse({'error': 'No active sandbox found for the given project or conversation'}, status=404)
        
        # Use the code_dir from the sandbox
        base_path = sandbox.code_dir
        full_path = os.path.join(base_path, folder_path)
        
        try:
            os.makedirs(full_path, exist_ok=True)
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'POST request expected'}, status=400)

@csrf_exempt
def delete_item(request):
    """
    API endpoint to delete a file or folder
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        path = data.get('path')
        is_directory = data.get('is_directory', False)
        project_id = data.get('project_id')
        conversation_id = data.get('conversation_id')
        
        # Build query to find matching sandbox
        query = Q(status='running')
        if project_id:
            query &= Q(project_id=project_id)
        elif conversation_id:
            query &= Q(conversation_id=conversation_id)
        else:
            return JsonResponse({'error': 'Either project_id or conversation_id must be provided'}, status=400)
        
        # Get the sandbox record
        sandbox = DockerSandbox.objects.filter(query).first()
        if not sandbox or not sandbox.code_dir:
            return JsonResponse({'error': 'No active sandbox found for the given project or conversation'}, status=404)
        
        # Use the code_dir from the sandbox
        base_path = sandbox.code_dir
        full_path = os.path.join(base_path, path)
        
        try:
            if is_directory:
                shutil.rmtree(full_path)
            else:
                os.remove(full_path)
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'POST request expected'}, status=400)

@csrf_exempt
def rename_item(request):
    """
    API endpoint to rename a file or folder
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        old_path = data.get('old_path')
        new_path = data.get('new_path')
        project_id = data.get('project_id')
        conversation_id = data.get('conversation_id')
        
        # Build query to find matching sandbox
        query = Q(status='running')
        if project_id:
            query &= Q(project_id=project_id)
        elif conversation_id:
            query &= Q(conversation_id=conversation_id)
        else:
            return JsonResponse({'error': 'Either project_id or conversation_id must be provided'}, status=400)
        
        # Get the sandbox record
        sandbox = DockerSandbox.objects.filter(query).first()
        if not sandbox or not sandbox.code_dir:
            return JsonResponse({'error': 'No active sandbox found for the given project or conversation'}, status=404)
        
        # Use the code_dir from the sandbox
        base_path = sandbox.code_dir
        full_old_path = os.path.join(base_path, old_path)
        full_new_path = os.path.join(base_path, new_path)
        
        try:
            # Ensure parent directory of new path exists
            os.makedirs(os.path.dirname(full_new_path), exist_ok=True)
            
            os.rename(full_old_path, full_new_path)
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'POST request expected'}, status=400)

@csrf_exempt
def get_sandbox_info(request):
    """
    API endpoint to get information about a sandbox, including its port
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        project_id = data.get('project_id')
        conversation_id = data.get('conversation_id')
        
        # Build query to find matching sandbox
        query = Q(status='running')
        if project_id:
            query &= Q(project_id=project_id)
        elif conversation_id:
            query &= Q(conversation_id=conversation_id)
        else:
            return JsonResponse({'error': 'Either project_id or conversation_id must be provided'}, status=400)
        
        # Get the sandbox record
        sandbox = DockerSandbox.objects.filter(query).first()
        if not sandbox:
            return JsonResponse({'error': 'No active sandbox found for the given project or conversation'}, status=404)
        
        # Get port mappings for this sandbox
        port_mappings = []
        
        # Add the main port from the sandbox model if it exists
        if sandbox.port is not None:
            port_mappings.append({
                'container_port': 8000,  # Default web server port
                'host_port': sandbox.port,
                'is_primary': True
            })
            
        # Add all port mappings from the related DockerPortMapping model
        for mapping in sandbox.port_mappings.all():
            # Check if this mapping is already included
            if not any(pm.get('host_port') == mapping.host_port for pm in port_mappings):
                port_mappings.append({
                    'container_port': mapping.container_port,
                    'host_port': mapping.host_port,
                    'is_primary': False
                })
        
        # If we have no port mappings but sandbox is running, add a default one
        # This is a fallback for older sandboxes that might not have explicit mappings
        if not port_mappings and sandbox.status == 'running':
            # Try to get port from Docker directly using the docker_utils module
            try:
                sandbox_info = get_sandbox_by_project_id(project_id or "")
                if sandbox_info and sandbox_info.get('port'):
                    port_mappings.append({
                        'container_port': 8000,
                        'host_port': sandbox_info['port'],
                        'is_primary': True
                    })
            except Exception as e:
                print(f"Error getting sandbox info from Docker: {e}")
        
        # Return sandbox information including port
        return JsonResponse({
            'sandbox_id': sandbox.id,
            'status': sandbox.status,
            'port': sandbox.port,  # Include the main port directly for backward compatibility
            'port_mappings': port_mappings
        })
    
    return JsonResponse({'error': 'POST request expected'}, status=400)

@csrf_exempt
def get_k8s_file_tree(request):
    """
    API endpoint to get the file structure from a Kubernetes pod
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        project_id = data.get('project_id')
        conversation_id = data.get('conversation_id')
        directory = data.get('directory', '/workspace')  # Default to /workspace
        
        # Validate input
        if not (project_id or conversation_id):
            return JsonResponse({'error': 'Either project_id or conversation_id must be provided'}, status=400)
        
        try:
            # Get the pod from the database
            query = Q()
            if project_id:
                query &= Q(project_id=str(project_id))
            elif conversation_id:
                query &= Q(conversation_id=str(conversation_id))
            
            pod = KubernetesPod.objects.filter(query).first()
            
            if not pod or pod.status != 'running':
                # Try to create/start the pod if it doesn't exist or isn't running
                success, pod, error_message = manage_kubernetes_pod(
                    project_id=project_id,
                    conversation_id=conversation_id
                )
                
                if not success or not pod:
                    return JsonResponse({
                        'error': 'Failed to start Kubernetes pod',
                        'debug_info': {
                            'project_id': project_id,
                            'conversation_id': conversation_id,
                            'pod_exists': pod is not None,
                            'error_message': error_message
                        }
                    }, status=500)
            
            # Execute 'find' command to get file structure
            success, stdout, stderr = execute_command_in_pod(
                project_id=project_id,
                conversation_id=conversation_id,
                command=f"find {directory} -type f -o -type d | sort"
            )
            
            if not success:
                return JsonResponse({'error': f'Failed to list files: {stderr}'}, status=500)
            
            # Parse the output into a tree structure
            file_tree = []
            base_path = directory.rstrip('/')
            paths = stdout.strip().split('\n')
            
            # Create a dictionary for directories
            dirs = {}
            
            for path in paths:
                # Skip empty paths
                if not path:
                    continue
                    
                # Check if it's a file or directory
                success, is_dir_stdout, _ = execute_command_in_pod(
                    project_id=project_id,
                    conversation_id=conversation_id,
                    command=f"[ -d '{path}' ] && echo 'true' || echo 'false'"
                )
                
                is_dir = is_dir_stdout.strip() == 'true'
                
                # Get relative path
                rel_path = os.path.relpath(path, base_path)
                if rel_path == '.':
                    continue
                
                # Split path into components
                parts = rel_path.split('/')
                current = file_tree
                
                # Build tree structure
                for i, part in enumerate(parts[:-1]):
                    # Skip current directory
                    if part == '.':
                        continue
                        
                    # Find or create directory in current level
                    dir_path = '/'.join(parts[:i+1])
                    full_path = f"{base_path}/{dir_path}"
                    
                    if full_path not in dirs:
                        dir_node = {
                            'name': part,
                            'type': 'directory',
                            'path': dir_path,
                            'children': []
                        }
                        dirs[full_path] = dir_node
                        
                        # Add to parent
                        if i == 0:
                            current.append(dir_node)
                        else:
                            parent_path = '/'.join(parts[:i])
                            full_parent_path = f"{base_path}/{parent_path}"
                            if full_parent_path in dirs:
                                dirs[full_parent_path]['children'].append(dir_node)
                    
                    current = dirs[full_path]['children']
                
                # Add leaf node (file or empty directory)
                leaf_name = parts[-1]
                leaf_path = rel_path
                full_leaf_path = f"{base_path}/{leaf_path}"
                
                if is_dir:
                    if full_leaf_path not in dirs:
                        dir_node = {
                            'name': leaf_name,
                            'type': 'directory',
                            'path': leaf_path,
                            'children': []
                        }
                        dirs[full_leaf_path] = dir_node
                        
                        # Add to parent
                        if len(parts) == 1:
                            file_tree.append(dir_node)
                        else:
                            parent_path = '/'.join(parts[:-1])
                            full_parent_path = f"{base_path}/{parent_path}"
                            if full_parent_path in dirs:
                                dirs[full_parent_path]['children'].append(dir_node)
                else:
                    file_node = {
                        'name': leaf_name,
                        'type': 'file',
                        'path': leaf_path
                    }
                    
                    # Add to parent
                    if len(parts) == 1:
                        file_tree.append(file_node)
                    else:
                        parent_path = '/'.join(parts[:-1])
                        full_parent_path = f"{base_path}/{parent_path}"
                        if full_parent_path in dirs:
                            dirs[full_parent_path]['children'].append(file_node)
            
            return JsonResponse({
                'files': file_tree,
                'pod_info': {
                    'namespace': pod.namespace,
                    'pod_name': pod.pod_name,
                    'status': pod.status
                }
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'POST request expected'}, status=400)

@csrf_exempt
def get_k8s_file_content(request):
    """
    API endpoint to get file content from a Kubernetes pod
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        project_id = data.get('project_id')
        conversation_id = data.get('conversation_id')
        file_path = data.get('path')
        
        # Validate input
        if not (project_id or conversation_id):
            return JsonResponse({'error': 'Either project_id or conversation_id must be provided'}, status=400)
        
        if not file_path:
            return JsonResponse({'error': 'File path must be provided'}, status=400)
        
        try:
            # Ensure the pod is running
            success, pod, error_message = manage_kubernetes_pod(
                project_id=project_id,
                conversation_id=conversation_id
            )
            
            if not success or not pod:
                return JsonResponse({
                    'error': 'Failed to start Kubernetes pod',
                    'debug_info': {
                        'project_id': project_id,
                        'conversation_id': conversation_id,
                        'pod_exists': pod is not None,
                        'error_message': error_message
                    }
                }, status=500)
            
            # Get absolute path
            abs_path = file_path
            if not file_path.startswith('/'):
                abs_path = f"/workspace/{file_path}"
            
            # Check if file exists
            success, exists_stdout, _ = execute_command_in_pod(
                project_id=project_id,
                conversation_id=conversation_id,
                command=f"[ -f '{abs_path}' ] && echo 'true' || echo 'false'"
            )
            
            if not success or exists_stdout.strip() != 'true':
                return JsonResponse({'error': f'File not found: {file_path}'}, status=404)
            
            # Cat the file content
            success, stdout, stderr = execute_command_in_pod(
                project_id=project_id,
                conversation_id=conversation_id,
                command=f"cat '{abs_path}'"
            )
            
            if not success:
                return JsonResponse({'error': f'Failed to read file: {stderr}'}, status=500)
            
            return JsonResponse({'content': stdout})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'POST request expected'}, status=400)

@csrf_exempt
def save_k8s_file(request):
    """
    API endpoint to save file content to a Kubernetes pod
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        project_id = data.get('project_id')
        conversation_id = data.get('conversation_id')
        file_path = data.get('path')
        content = data.get('content')
        
        # Validate input
        if not (project_id or conversation_id):
            return JsonResponse({'error': 'Either project_id or conversation_id must be provided'}, status=400)
        
        if not file_path:
            return JsonResponse({'error': 'File path must be provided'}, status=400)
        
        try:
            # Ensure the pod is running
            success, pod, error_message = manage_kubernetes_pod(
                project_id=project_id,
                conversation_id=conversation_id
            )
            
            if not success or not pod:
                return JsonResponse({
                    'error': 'Failed to start Kubernetes pod',
                    'debug_info': {
                        'project_id': project_id,
                        'conversation_id': conversation_id,
                        'pod_exists': pod is not None,
                        'error_message': error_message
                    }
                }, status=500)
            
            # Get absolute path
            abs_path = file_path
            if not file_path.startswith('/'):
                abs_path = f"/workspace/{file_path}"
            
            # Create directory if needed
            dir_path = os.path.dirname(abs_path)
            success, _, stderr = execute_command_in_pod(
                project_id=project_id,
                conversation_id=conversation_id,
                command=f"mkdir -p '{dir_path}'"
            )
            
            if not success:
                return JsonResponse({'error': f'Failed to create directory: {stderr}'}, status=500)
            
            # Write content to a temporary file, then move it to the target location
            # This handles special characters in the content better
            temp_file = f"/tmp/{os.path.basename(abs_path)}.{int(time.time())}"
            success, _, stderr = execute_command_in_pod(
                project_id=project_id,
                conversation_id=conversation_id,
                command=f"cat > {temp_file} << 'EOL'\n{content}\nEOL"
            )
            
            if not success:
                return JsonResponse({'error': f'Failed to write file: {stderr}'}, status=500)
            
            # Move the temp file to the target location
            success, _, stderr = execute_command_in_pod(
                project_id=project_id,
                conversation_id=conversation_id,
                command=f"mv {temp_file} '{abs_path}'"
            )
            
            if not success:
                return JsonResponse({'error': f'Failed to save file: {stderr}'}, status=500)
            
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'POST request expected'}, status=400)

@csrf_exempt
def k8s_create_folder(request):
    """
    API endpoint to create a new folder in a Kubernetes pod
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        project_id = data.get('project_id')
        conversation_id = data.get('conversation_id')
        folder_path = data.get('path')
        
        # Validate input
        if not (project_id or conversation_id):
            return JsonResponse({'error': 'Either project_id or conversation_id must be provided'}, status=400)
        
        if not folder_path:
            return JsonResponse({'error': 'Folder path must be provided'}, status=400)
        
        try:
            # Ensure the pod is running
            success, pod, error_message = manage_kubernetes_pod(
                project_id=project_id,
                conversation_id=conversation_id
            )
            
            if not success or not pod:
                return JsonResponse({
                    'error': 'Failed to start Kubernetes pod',
                    'debug_info': {
                        'project_id': project_id,
                        'conversation_id': conversation_id,
                        'pod_exists': pod is not None,
                        'error_message': error_message
                    }
                }, status=500)
            
            # Get absolute path
            abs_path = folder_path
            if not folder_path.startswith('/'):
                abs_path = f"/workspace/{folder_path}"
            
            # Create directory
            success, _, stderr = execute_command_in_pod(
                project_id=project_id,
                conversation_id=conversation_id,
                command=f"mkdir -p '{abs_path}'"
            )
            
            if not success:
                return JsonResponse({'error': f'Failed to create directory: {stderr}'}, status=500)
            
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'POST request expected'}, status=400)

@csrf_exempt
def k8s_delete_item(request):
    """
    API endpoint to delete a file or folder in a Kubernetes pod
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        project_id = data.get('project_id')
        conversation_id = data.get('conversation_id')
        path = data.get('path')
        is_directory = data.get('is_directory', False)
        
        # Validate input
        if not (project_id or conversation_id):
            return JsonResponse({'error': 'Either project_id or conversation_id must be provided'}, status=400)
        
        if not path:
            return JsonResponse({'error': 'Path must be provided'}, status=400)
        
        try:
            # Ensure the pod is running
            success, pod, error_message = manage_kubernetes_pod(
                project_id=project_id,
                conversation_id=conversation_id
            )
            
            if not success or not pod:
                return JsonResponse({
                    'error': 'Failed to start Kubernetes pod',
                    'debug_info': {
                        'project_id': project_id,
                        'conversation_id': conversation_id,
                        'pod_exists': pod is not None,
                        'error_message': error_message
                    }
                }, status=500)
            
            # Get absolute path
            abs_path = path
            if not path.startswith('/'):
                abs_path = f"/workspace/{path}"
            
            # Delete item
            if is_directory:
                success, _, stderr = execute_command_in_pod(
                    project_id=project_id,
                    conversation_id=conversation_id,
                    command=f"rm -rf '{abs_path}'"
                )
            else:
                success, _, stderr = execute_command_in_pod(
                    project_id=project_id,
                    conversation_id=conversation_id,
                    command=f"rm '{abs_path}'"
                )
            
            if not success:
                return JsonResponse({'error': f'Failed to delete item: {stderr}'}, status=500)
            
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'POST request expected'}, status=400)

@csrf_exempt
def k8s_rename_item(request):
    """
    API endpoint to rename a file or folder in a Kubernetes pod
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        project_id = data.get('project_id')
        conversation_id = data.get('conversation_id')
        old_path = data.get('old_path')
        new_path = data.get('new_path')
        
        # Validate input
        if not (project_id or conversation_id):
            return JsonResponse({'error': 'Either project_id or conversation_id must be provided'}, status=400)
        
        if not old_path or not new_path:
            return JsonResponse({'error': 'Both old_path and new_path must be provided'}, status=400)
        
        try:
            # Ensure the pod is running
            success, pod, error_message = manage_kubernetes_pod(
                project_id=project_id,
                conversation_id=conversation_id
            )
            
            if not success or not pod:
                return JsonResponse({
                    'error': 'Failed to start Kubernetes pod',
                    'debug_info': {
                        'project_id': project_id,
                        'conversation_id': conversation_id,
                        'pod_exists': pod is not None,
                        'error_message': error_message
                    }
                }, status=500)
            
            # Get absolute paths
            abs_old_path = old_path
            if not old_path.startswith('/'):
                abs_old_path = f"/workspace/{old_path}"
                
            abs_new_path = new_path
            if not new_path.startswith('/'):
                abs_new_path = f"/workspace/{new_path}"
            
            # Create parent directory if needed
            dir_path = os.path.dirname(abs_new_path)
            success, _, stderr = execute_command_in_pod(
                project_id=project_id,
                conversation_id=conversation_id,
                command=f"mkdir -p '{dir_path}'"
            )
            
            if not success:
                return JsonResponse({'error': f'Failed to create directory: {stderr}'}, status=500)
            
            # Rename item
            success, _, stderr = execute_command_in_pod(
                project_id=project_id,
                conversation_id=conversation_id,
                command=f"mv '{abs_old_path}' '{abs_new_path}'"
            )
            
            if not success:
                return JsonResponse({'error': f'Failed to rename item: {stderr}'}, status=500)
            
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'POST request expected'}, status=400)

@csrf_exempt
def get_k8s_pod_info(request):
    """
    API endpoint to get information about a Kubernetes pod
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        project_id = data.get('project_id')
        conversation_id = data.get('conversation_id')
        
        # Validate input
        if not (project_id or conversation_id):
            return JsonResponse({'error': 'Either project_id or conversation_id must be provided'}, status=400)
        
        try:
            # Check DB for pod info first
            query = Q()
            if project_id:
                query &= Q(project_id=str(project_id))
            elif conversation_id:
                query &= Q(conversation_id=str(conversation_id))
            
            pod = KubernetesPod.objects.filter(query).first()
            
            # Define variables to track what's happening
            pod_existed = pod is not None
            pod_was_running = pod and pod.status == 'running'
            
            logger.info(f"Starting get_k8s_pod_info: db_record_exists={pod_existed}, was_running={pod_was_running}")
            
            # IMPORTANT OPTIMIZATION: If pod is in DB and marked as running, and has valid service details,
            # we can skip the expensive K8s checks and management operations
            if pod_existed and pod_was_running and pod.service_details and 'ttydUrl' in pod.service_details:
                logger.info(f"Using existing pod info from database for {pod.pod_name} - skipping K8s operations")
                
                # Return pod info directly from DB
                pod_info = {
                    'pod_id': pod.id,
                    'pod_name': pod.pod_name,
                    'namespace': pod.namespace,
                    'status': pod.status,
                    'image': pod.image,
                    'service_details': pod.service_details,
                    'ttydUrl': pod.service_details.get('ttydUrl'),
                    'from_cache': True
                }
                
                # Add debug info
                pod_info['debug_info'] = {
                    'has_service_details': bool(pod.service_details),
                    'service_details_keys': list(pod.service_details.keys()) if pod.service_details else [],
                    'pod_existed': pod_existed,
                    'pod_was_running': pod_was_running,
                    'pod_name': pod.pod_name,
                    'pod_namespace': pod.namespace,
                    'skipped_k8s_check': True
                }
                
                return JsonResponse(pod_info)
            
            # Only perform expensive K8s operations if necessary
            # Ensure a pod is available and running - will check for existing resources first
            success, pod, error_message = manage_kubernetes_pod(
                project_id=project_id,
                conversation_id=conversation_id,
                image=pod.image if pod and pod.image else "gitpod/workspace-full:latest",
                resource_limits=pod.resource_limits if pod and pod.resource_limits else None
            )
            
            if not success or not pod:
                return JsonResponse({
                    'error': 'Failed to ensure Kubernetes pod is running',
                    'debug_info': {
                        'project_id': project_id,
                        'conversation_id': conversation_id,
                        'pod_exists': pod is not None,
                        'error_message': error_message
                    }
                }, status=500)
            
            # Verify the pod is now running
            if pod.status != 'running':
                logger.error(f"Pod {pod.pod_name} is still not running after creation/start attempts")
                return JsonResponse({
                    'error': 'Pod is not running after creation/start attempts',
                    'debug_info': {
                        'pod_name': pod.pod_name,
                        'status': pod.status,
                        'existed_before': pod_existed,
                        'was_running_before': pod_was_running
                    }
                }, status=500)
            
            # Extract pod info
            pod_info = {
                'pod_id': pod.id,
                'pod_name': pod.pod_name,
                'namespace': pod.namespace,
                'status': pod.status,
                'image': pod.image,
                'from_cache': False
            }
            
            # Add service details if available
            if pod.service_details:
                # Log details about service_details for debugging
                logger.info(f"Pod service_details: {pod.service_details}")
                
                # Add full service_details to response for debugging
                pod_info['service_details'] = pod.service_details
                
                # Check for ttydUrl and directly expose it at the top level for easy access
                if 'ttydUrl' in pod.service_details and pod.service_details.get('ttydUrl'):
                    # Add ttydUrl directly to the response object for easier access in the frontend
                    pod_info['ttydUrl'] = pod.service_details.get('ttydUrl')
                else:
                    # No ttydUrl found, check if ttydPort exists
                    ttyd_port = pod.service_details.get('ttydPort')
                    node_ip = pod.service_details.get('nodeIP')
                    
                    if ttyd_port and node_ip:
                        # We have the ttyd port and node IP, but no direct URL - create it
                        ttyd_url = f"http://{node_ip}:{ttyd_port}"
                        pod_info['ttydUrl'] = ttyd_url
                        
                        # Also update the database record for next time
                        pod.service_details['ttydUrl'] = ttyd_url
                        pod.save(update_fields=['service_details'])
                        
                        logger.info(f"Created and saved missing ttydUrl: {ttyd_url}")
                    else:
                        # Log the missing information
                        logger.warning(f"Missing ttydPort ({ttyd_port}) or nodeIP ({node_ip}) for pod {pod.pod_name}")
                        pod_info['warning'] = 'Missing ttyd connection information'
            else:
                pod_info['warning'] = 'No service details available'
                
            # Add debug info
            pod_info['debug_info'] = {
                'has_service_details': bool(pod.service_details),
                'service_details_keys': list(pod.service_details.keys()) if pod.service_details else [],
                'pod_existed': pod_existed,
                'pod_was_running': pod_was_running,
                'pod_name': pod.pod_name,
                'pod_namespace': pod.namespace
            }
                
            return JsonResponse(pod_info)
        except Exception as e:
            logger.exception(f"Error in get_k8s_pod_info: {str(e)}")
            return JsonResponse({
                'error': str(e),
                'debug_info': {
                    'project_id': project_id,
                    'conversation_id': conversation_id,
                    'exception_type': type(e).__name__
                }
            }, status=500)
    
    return JsonResponse({'error': 'POST request expected'}, status=400)

@csrf_exempt
def k8s_execute_command(request):
    """
    API endpoint to execute a command in a Kubernetes pod
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        project_id = data.get('project_id')
        conversation_id = data.get('conversation_id')
        command = data.get('command')
        
        # Validate input
        if not (project_id or conversation_id):
            return JsonResponse({'error': 'Either project_id or conversation_id must be provided'}, status=400)
        
        if not command:
            return JsonResponse({'error': 'Command must be provided'}, status=400)
        
        try:
            # Ensure the pod is running
            success, pod, error_message = manage_kubernetes_pod(
                project_id=project_id,
                conversation_id=conversation_id
            )
            
            if not success or not pod:
                return JsonResponse({
                    'error': 'Failed to start Kubernetes pod',
                    'debug_info': {
                        'project_id': project_id,
                        'conversation_id': conversation_id,
                        'pod_exists': pod is not None,
                        'error_message': error_message
                    }
                }, status=500)
            
            # Execute command
            success, stdout, stderr = execute_command_in_pod(
                project_id=project_id,
                conversation_id=conversation_id,
                command=command
            )
            
            return JsonResponse({
                'success': success,
                'stdout': stdout,
                'stderr': stderr
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'POST request expected'}, status=400)
