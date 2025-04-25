import redis
import json
import uuid
import yaml
import numpy as np
import cv2
from typing import Dict, Any, List, Optional
from datetime import datetime
from frame_codec import encode_frame_to_base64, decode_base64_to_frame
import time

# Load configuration
with open("config.yaml", 'r') as f:
    config = yaml.safe_load(f)

class FrameInterpolationClient:
    """Client for sending frame interpolation tasks to the server."""
    
    def __init__(self, host: str = config['redis']['host'], port: int = config['redis']['port']):
        """Initialize frame interpolation client.
        
        Args:
            host: Redis host address
            port: Redis port number
        """
        self.r = redis.Redis(host=host, port=port)
        self.task_queue = config['queues']['task']
        self.result_queue = config['queues']['result']
        self._active_tasks = {}  # Track active tasks

    def send_task(self, frame1: np.ndarray, frame2: np.ndarray, 
                 num_frames: int = 1, task_id: str = None) -> str:
        """Send a frame interpolation task to the server.
        
        Args:
            frame1: First frame as numpy array
            frame2: Second frame as numpy array
            num_frames: Number of in-between frames to generate
            task_id: Optional task ID (will generate one if not provided)
            
        Returns:
            Task ID
        """
        if task_id is None:
            task_id = str(uuid.uuid4())
            
        # Encode frames to base64
        frame1_b64 = encode_frame_to_base64(frame1)
        frame2_b64 = encode_frame_to_base64(frame2)
        
        # Create task data
        task_data = {
            "task_id": task_id,
            "image1": frame1_b64,
            "image2": frame2_b64,
            "num_frames": num_frames,
            "submitted_at": datetime.utcnow().isoformat()
        }
        
        # Send task to Redis queue
        self.r.lpush(self.task_queue, json.dumps(task_data))
        
        # Track the task
        self._active_tasks[task_id] = {
            'status': 'PENDING',
            'submitted_at': task_data['submitted_at']
        }
        
        return task_id

    def get_result(self, task_id: str, timeout: int = 30) -> List[np.ndarray]:
        """Get the result for a specific task.
        
        Args:
            task_id: Task ID to get result for
            timeout: Timeout in seconds
            
        Returns:
            List of interpolated frames
        """
        if task_id not in self._active_tasks:
            raise ValueError(f"Task {task_id} not found")
            
        start_time = time.time()
        while time.time() - start_time < timeout:
            # Check Redis for result
            result_data = self.r.get(f"{self.result_queue}:{task_id}")
            if result_data:
                result = json.loads(result_data)
                if result.get('status') == 'SUCCESS':
                    # Update task status
                    self._active_tasks[task_id]['status'] = 'SUCCESS'
                    self._active_tasks[task_id]['updated_at'] = datetime.utcnow().isoformat()
                    
                    # Decode frames from base64
                    return [decode_base64_to_frame(frame_b64) for frame_b64 in result['frames']]
                elif result.get('status') == 'FAILURE':
                    # Update task status with error
                    self._active_tasks[task_id]['status'] = 'FAILURE'
                    self._active_tasks[task_id]['updated_at'] = datetime.utcnow().isoformat()
                    self._active_tasks[task_id]['error'] = result.get('error', 'Unknown error')
                    raise Exception(f"Task failed: {result.get('error', 'Unknown error')}")
            
            # Update task status
            self._active_tasks[task_id]['status'] = 'STARTED'
            self._active_tasks[task_id]['updated_at'] = datetime.utcnow().isoformat()
            time.sleep(0.1)
            
        raise TimeoutError(f"Task {task_id} still running")

    def process_frames(self, frame1: np.ndarray, frame2: np.ndarray, 
                      num_frames: int = 1, timeout: int = 30) -> List[np.ndarray]:
        """Submit a task and wait for its result.
        
        Args:
            frame1: First frame (RGB numpy array)
            frame2: Second frame (RGB numpy array)
            num_frames: Number of frames to interpolate between frame1 and frame2
            timeout: Maximum time to wait for results in seconds
            
        Returns:
            List of interpolated frames
        """
        task_id = self.send_task(frame1, frame2, num_frames)
        return self.get_result(task_id, timeout)

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get the status of a specific task.
        
        Args:
            task_id: Task ID to check
            
        Returns:
            Dictionary containing task status information
        """
        if task_id not in self._active_tasks:
            raise ValueError(f"Task {task_id} not found")
            
        task_info = self._active_tasks[task_id]
        
        status_info = {
            'id': task_id,
            'status': task_info['status'],
            'submitted_at': task_info['submitted_at']
        }
        
        if 'updated_at' in task_info:
            status_info['updated_at'] = task_info['updated_at']
            
        if 'error' in task_info:
            status_info['error'] = task_info['error']
            
        return status_info

    def list_jobs(self) -> List[Dict[str, Any]]:
        """List all jobs tracked by this client.
        
        Returns:
            List of dictionaries containing job information
        """
        jobs = []
        for task_id, task_info in self._active_tasks.items():
            job_info = self.get_task_status(task_id)
            jobs.append(job_info)
        return jobs

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task.
        
        Args:
            task_id: Task ID to cancel
            
        Returns:
            True if task was cancelled, False otherwise
        """
        if task_id not in self._active_tasks:
            return False
            
        # Mark task as cancelled in Redis
        self.r.set(f"{self.result_queue}:{task_id}", json.dumps({
            'status': 'REVOKED',
            'task_id': task_id
        }))
        
        # Update task status
        self._active_tasks[task_id]['status'] = 'REVOKED'
        self._active_tasks[task_id]['updated_at'] = datetime.utcnow().isoformat()
        
        return True

if __name__ == "__main__":
    # Test the frame interpolation client with a simple example
    try:
        # Load test frames
        frame1 = cv2.imread("frame_17848.jpg")
        frame2 = cv2.imread("frame_17850.jpg")
        
        if frame1 is None or frame2 is None:
            raise FileNotFoundError("Could not load test images")
            
        # Convert to RGB
        frame1_rgb = cv2.cvtColor(frame1, cv2.COLOR_BGR2RGB)
        frame2_rgb = cv2.cvtColor(frame2, cv2.COLOR_BGR2RGB)
        
        # Initialize interpolation client
        interpolation_client = FrameInterpolationClient()
        
        print("Submitting test task...")
        task_id = interpolation_client.send_task(frame1_rgb, frame2_rgb, num_frames=1)
        print(f"Task submitted with ID: {task_id}")
        
        # Monitor task status
        while True:
            status = interpolation_client.get_task_status(task_id)
            print(f"Task status: {status['status']}")
            if status['status'] in ['SUCCESS', 'FAILURE', 'REVOKED']:
                break
            time.sleep(1)
            
        if status['status'] == 'SUCCESS':
            frames = interpolation_client.get_result(task_id)
            print("Successfully received interpolated frames!")
            # Save the interpolated frame
            cv2.imwrite("test_interpolated_frame.png", 
                       cv2.cvtColor(frames[0], cv2.COLOR_RGB2BGR))
            print("Saved interpolated frame to test_interpolated_frame.png")
        else:
            print(f"Task failed: {status.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"Test error: {e}") 