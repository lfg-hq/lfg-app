# Kubernetes Pod File Management for Monaco Editor

This guide shows how to use the new Kubernetes API endpoints to edit files in Kubernetes pods directly from the Monaco editor.

## API Endpoints

All Kubernetes-specific API endpoints are prefixed with `/coding/k8s/` to distinguish them from the Docker-based endpoints.

### 1. Get File Tree

**Endpoint:** `/coding/k8s/get_file_tree/`

**Method:** POST

**Parameters:**
- `project_id` or `conversation_id`: Identifier for the pod
- `directory` (optional): Base directory to list files from (defaults to `/workspace`)

**Response:**
```json
{
  "files": [
    {
      "name": "folder1",
      "type": "directory",
      "path": "folder1",
      "children": [
        {
          "name": "file1.txt",
          "type": "file",
          "path": "folder1/file1.txt"
        }
      ]
    },
    {
      "name": "file2.txt",
      "type": "file",
      "path": "file2.txt"
    }
  ],
  "pod_info": {
    "namespace": "proj-123",
    "pod_name": "proj-123-pod",
    "status": "running"
  }
}
```

### 2. Get File Content

**Endpoint:** `/coding/k8s/get_file_content/`

**Method:** POST

**Parameters:**
- `project_id` or `conversation_id`: Identifier for the pod
- `path`: Path to the file (relative to `/workspace` or absolute)

**Response:**
```json
{
  "content": "File content here..."
}
```

### 3. Save File Content

**Endpoint:** `/coding/k8s/save_file/`

**Method:** POST

**Parameters:**
- `project_id` or `conversation_id`: Identifier for the pod
- `path`: Path to save the file (relative to `/workspace` or absolute)
- `content`: File content

**Response:**
```json
{
  "status": "success"
}
```

### 4. Create Folder

**Endpoint:** `/coding/k8s/create_folder/`

**Method:** POST

**Parameters:**
- `project_id` or `conversation_id`: Identifier for the pod
- `path`: Path for the new folder (relative to `/workspace` or absolute)

**Response:**
```json
{
  "status": "success"
}
```

### 5. Delete Item

**Endpoint:** `/coding/k8s/delete_item/`

**Method:** POST

**Parameters:**
- `project_id` or `conversation_id`: Identifier for the pod
- `path`: Path to the item to delete (relative to `/workspace` or absolute)
- `is_directory` (optional): Boolean indicating if the item is a directory (defaults to false)

**Response:**
```json
{
  "status": "success"
}
```

### 6. Rename Item

**Endpoint:** `/coding/k8s/rename_item/`

**Method:** POST

**Parameters:**
- `project_id` or `conversation_id`: Identifier for the pod
- `old_path`: Current path of the item (relative to `/workspace` or absolute)
- `new_path`: New path for the item (relative to `/workspace` or absolute)

**Response:**
```json
{
  "status": "success"
}
```

### 7. Get Pod Info

**Endpoint:** `/coding/k8s/get_pod_info/`

**Method:** POST

**Parameters:**
- `project_id` or `conversation_id`: Identifier for the pod

**Response:**
```json
{
  "pod_id": 1,
  "pod_name": "proj-123-pod",
  "namespace": "proj-123",
  "status": "running",
  "image": "gitpod/workspace-full:latest",
  "service_details": {
    "node_port": "30123",
    "server_ip": "178.156.174.242",
    "access_url": "http://178.156.174.242:30123"
  }
}
```

### 8. Execute Command

**Endpoint:** `/coding/k8s/execute_command/`

**Method:** POST

**Parameters:**
- `project_id` or `conversation_id`: Identifier for the pod
- `command`: Command to execute

**Response:**
```json
{
  "success": true,
  "stdout": "Command output...",
  "stderr": ""
}
```

## Monaco Editor Integration

To integrate these APIs with your Monaco editor, you'll need to modify your client-side JavaScript. Here's an example:

```javascript
// Example function to load a file from Kubernetes pod
async function loadFileFromK8s(projectId, filePath) {
  try {
    const response = await fetch('/coding/k8s/get_file_content/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        project_id: projectId,
        path: filePath,
      }),
    });
    
    const data = await response.json();
    
    if (response.ok) {
      // Update Monaco editor with file content
      monaco.editor.getModels()[0].setValue(data.content);
    } else {
      console.error('Error loading file:', data.error);
    }
  } catch (error) {
    console.error('Error:', error);
  }
}

// Example function to save a file to Kubernetes pod
async function saveFileToK8s(projectId, filePath, content) {
  try {
    const response = await fetch('/coding/k8s/save_file/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        project_id: projectId,
        path: filePath,
        content: content,
      }),
    });
    
    const data = await response.json();
    
    if (response.ok) {
      console.log('File saved successfully');
    } else {
      console.error('Error saving file:', data.error);
    }
  } catch (error) {
    console.error('Error:', error);
  }
}
```

## Modified Editor Interface

To add Kubernetes support to your existing Monaco editor UI:

1. Add a toggle switch to select between Docker and Kubernetes environments
2. Modify your file explorer component to use the appropriate API endpoints based on the selected environment
3. Update all file operations (load, save, create, delete, rename) to use the Kubernetes APIs when Kubernetes is selected

Example toggle implementation:

```html
<div class="environment-toggle">
  <label>
    <input type="checkbox" id="k8s-toggle" onchange="toggleEnvironment()">
    Use Kubernetes
  </label>
</div>

<script>
let useK8s = false;

function toggleEnvironment() {
  useK8s = document.getElementById('k8s-toggle').checked;
  
  // Refresh file tree with appropriate API
  if (useK8s) {
    loadK8sFileTree(currentProjectId);
  } else {
    loadDockerFileTree(currentProjectId);
  }
}

// Load file tree from Kubernetes or Docker based on toggle
function loadFileTree(projectId) {
  if (useK8s) {
    loadK8sFileTree(projectId);
  } else {
    loadDockerFileTree(projectId);
  }
}
</script>
```

## Testing Your Integration

1. Start a Kubernetes pod using the `manage_kubernetes_pod` function
2. Access your Monaco editor with the appropriate project_id
3. Toggle to Kubernetes mode
4. Test file operations (view, edit, save, create, delete)

Remember that all operations are performed directly on the Kubernetes pod, so any changes are immediate and persist as long as the pod exists.

## Common Issues

1. **Pod not running**: If you see "Failed to start Kubernetes pod" errors, check that your Kubernetes server is accessible and properly configured.

2. **Permission issues**: Make sure the user running commands in the pod has appropriate permissions for the directories you're accessing.

3. **Path problems**: Double check that paths are correctly formatted. Remember that relative paths are resolved against `/workspace`.

4. **Content encoding**: When saving files with special characters, make sure the content is properly encoded both on the client and server side. 