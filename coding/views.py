from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import os
import json
import subprocess
import git
import shutil
from coding.models import DockerSandbox
from django.db.models import Q
from .docker.docker_utils import get_sandbox_by_project_id

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
    
    return render(request, 'coding/editor.html')

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
