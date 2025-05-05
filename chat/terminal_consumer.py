import json
import asyncio
import logging
import subprocess
import os
import threading
import paramiko
import io
from urllib.parse import parse_qs
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.conf import settings

logger = logging.getLogger(__name__)

class TerminalConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.process = None
        self.ssh_client = None
        self.shell_channel = None
        self.stop_event = asyncio.Event()
        
        # Accept the WebSocket connection
        await self.accept()
        
        # Parse query parameters
        query_string = self.scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        
        # Check if we need to connect to a pod or just use local terminal
        self.project_id = query_params.get('projectId', [None])[0]
        self.pod_id = query_params.get('podId', [None])[0]
        
        # Connect to a pod's terminal or create a local terminal
        if self.project_id and self.pod_id:
            await self.create_pod_terminal()
        else:
            await self.create_local_terminal()
    
    async def create_local_terminal(self):
        """Create a local terminal process."""
        try:
            # Determine the shell to use based on the OS
            shell = os.environ.get('SHELL', '/bin/bash')
            
            # Set environment variables for proper terminal behavior
            env = os.environ.copy()
            env['TERM'] = 'xterm-256color'
            env['COLORTERM'] = 'truecolor'
            
            # Start the terminal process
            # Using shell=True to ensure proper shell features
            self.process = await asyncio.create_subprocess_shell(
                shell,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            logger.info(f"Started local terminal process with PID: {self.process.pid}")
            
            # Start reading output in the background
            asyncio.create_task(self.read_output())
            
            # Send initial connection message
            await self.send(text_data=json.dumps({
                'type': 'terminal.connected',
                'message': 'Connected to local terminal'
            }))
            
        except Exception as e:
            logger.error(f"Error creating local terminal: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'terminal.error',
                'message': f"Failed to create terminal: {str(e)}"
            }))
            await self.close()
    
    async def create_pod_terminal(self):
        """Create a terminal connection to a Kubernetes pod."""
        try:
            # Here you would implement pod connection logic
            # For example, get pod details from database
            # This is just a placeholder since we don't have the actual pod model
            
            # Example of how you might implement this with SSH and kubectl
            # Assuming you have a KubernetesPod model or similar
            """
            pod = await sync_to_async(lambda: KubernetesPod.objects.filter(
                project_id=self.project_id, 
                id=self.pod_id
            ).first())()
            
            if not pod:
                await self.send(text_data=json.dumps({
                    'type': 'terminal.error',
                    'message': 'Pod not found'
                }))
                await self.close()
                return
                
            # Create SSH client
            self.ssh_client = self.create_ssh_client(
                host=pod.ssh_connection_details.get('host'),
                port=pod.ssh_connection_details.get('port'),
                username=pod.ssh_connection_details.get('username'),
                key_file=pod.ssh_connection_details.get('key_file'),
                key_string=pod.ssh_connection_details.get('key_string'),
                key_passphrase=pod.ssh_connection_details.get('key_passphrase')
            )
            
            # Create a shell session
            self.shell_channel = self.ssh_client.invoke_shell()
            
            # Send kubectl command to exec into the pod
            k8s_command = f"kubectl exec -n {pod.namespace} {pod.pod_name} -it -- /bin/bash"
            self.shell_channel.send(k8s_command + "\n")
            
            # Start reading output in the background
            asyncio.create_task(self.read_ssh_output())
            """
            
            # For now, let's just send a message that pod connection is not implemented
            await self.send(text_data=json.dumps({
                'type': 'terminal.connected',
                'message': 'Pod terminal connection is not implemented yet.'
            }))
            
            # Fall back to local terminal for demonstration
            await self.create_local_terminal()
            
        except Exception as e:
            logger.error(f"Error creating pod terminal: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'terminal.error',
                'message': f"Failed to create pod terminal: {str(e)}"
            }))
            await self.close()
    
    def create_ssh_client(self, host, port, username, key_file=None, key_string=None, key_passphrase=None):
        """Create an SSH client for connecting to a remote server."""
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Load private key
            if key_file:
                private_key = paramiko.RSAKey.from_private_key_file(key_file, password=key_passphrase)
            elif key_string:
                private_key = paramiko.RSAKey.from_private_key(
                    file_obj=io.StringIO(key_string),
                    password=key_passphrase
                )
            else:
                private_key = None
            
            # Connect to SSH server
            client.connect(
                hostname=host,
                port=port,
                username=username,
                pkey=private_key
            )
            
            return client
        except Exception as e:
            logger.error(f"Error creating SSH client: {str(e)}")
            return None
    
    async def read_output(self):
        """Read output from the local terminal process."""
        try:
            while not self.stop_event.is_set() and self.process:
                # Read from stdout
                line = await self.process.stdout.read(4096)
                if line:
                    await self.send(text_data=line.decode('utf-8', errors='replace'))
                
                # Read from stderr
                line_err = await self.process.stderr.read(4096)
                if line_err:
                    await self.send(text_data=line_err.decode('utf-8', errors='replace'))
                
                # Small delay to prevent CPU hogging
                await asyncio.sleep(0.01)
        except Exception as e:
            logger.error(f"Error reading terminal output: {str(e)}")
    
    async def read_ssh_output(self):
        """Read output from the SSH shell channel."""
        try:
            while not self.stop_event.is_set() and self.shell_channel:
                if self.shell_channel.recv_ready():
                    data = self.shell_channel.recv(4096).decode('utf-8', errors='replace')
                    await self.send(text_data=data)
                
                # Small delay to prevent CPU hogging
                await asyncio.sleep(0.01)
        except Exception as e:
            logger.error(f"Error reading SSH output: {str(e)}")
    
    async def receive(self, text_data):
        """Receive input from the client and send it to the terminal."""
        try:
            # Log received data for debugging
            logger.debug(f"Received data: {repr(text_data)}")
            
            # Send input to the appropriate terminal
            if self.process:
                # Send to local process
                self.process.stdin.write(text_data.encode('utf-8'))
                await self.process.stdin.drain()
                logger.debug("Data sent to process stdin")
            elif self.shell_channel:
                # Send to SSH shell
                self.shell_channel.send(text_data)
                logger.debug("Data sent to SSH channel")
            else:
                logger.warning("No process or SSH channel available to send input to")
                await self.send(text_data=json.dumps({
                    'type': 'terminal.error',
                    'message': 'Terminal process is not available'
                }))
        except Exception as e:
            logger.error(f"Error sending input to terminal: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'terminal.error',
                'message': f"Failed to send input: {str(e)}"
            }))
    
    async def disconnect(self, close_code):
        """Clean up resources when the WebSocket connection is closed."""
        # Set stop event to terminate output reading tasks
        self.stop_event.set()
        
        # Close the local process if it exists
        if self.process:
            try:
                self.process.terminate()
                await self.process.wait()
            except:
                pass
        
        # Close SSH connection if it exists
        if self.shell_channel:
            try:
                self.shell_channel.close()
            except:
                pass
        
        if self.ssh_client:
            try:
                self.ssh_client.close()
            except:
                pass 