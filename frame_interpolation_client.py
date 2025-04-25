import redis
import json
import uuid
import yaml
import numpy as np
import cv2
from typing import List
from frame_codec import encode_frame_to_base64, decode_base64_to_frame
import time
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configuration
with open("config.yaml", 'r') as f:
    cfg = yaml.safe_load(f)

class FrameInterpolationClient:
    """Client for sending frame interpolation tasks to the server."""
    
    def __init__(self, host: str = cfg['redis']['host'], port: int = cfg['redis']['port'], 
                 task_queue: str = cfg['queues']['task'], result_queue: str = cfg['queues']['result']):
        """Initialize frame interpolation client.
        
        Args:
            host: Redis host address
            port: Redis port number
            task_queue: Redis queue name for tasks
            result_queue: Redis queue name for results
        """
        self.r = redis.Redis(host=host, port=port)
        self.task_queue = task_queue
        self.result_queue = result_queue

    def send_task(self, frame1: np.ndarray, frame2: np.ndarray, 
                 num_frames: int = 1) -> str:
        """Send a frame interpolation task to the server.
        
        Args:
            frame1: First frame as numpy array
            frame2: Second frame as numpy array
            num_frames: Number of in-between frames to generate
            
        Returns:
            Task ID
        """
        task_id = str(uuid.uuid4())
            
        # Encode frames to base64
        frame1_b64 = encode_frame_to_base64(frame1)
        frame2_b64 = encode_frame_to_base64(frame2)
        
        # Create task data
        task_data = {
            "task_id": task_id,
            "frame1": frame1_b64,
            "frame2": frame2_b64,
            "num_frames": num_frames
        }
        
        # Send task to Redis queue
        self.r.lpush(self.task_queue, json.dumps(task_data))
        logger.info(f"Sent task {task_id}")
        
        return task_id

    def get_result(self, task_id: str, timeout: int = 30) -> List[np.ndarray]:
        """Get the result for a specific task.
        
        Args:
            task_id: Task ID to get result for
            timeout: Timeout in seconds
            
        Returns:
            List of interpolated frames
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            # Check Redis for result
            result_data = self.r.get(f"{self.result_queue}:{task_id}")
            if result_data:
                result = json.loads(result_data)
                if 'error' in result and result['error']:
                    raise Exception(f"Task failed: {result['error']}")
                if 'frames' in result and result['frames']:
                    logger.info(f"Retrieved result {task_id}")
                    return [decode_base64_to_frame(frame_b64) for frame_b64 in result['frames']]
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
        try:
            task_id = self.send_task(frame1, frame2, num_frames)
            return self.get_result(task_id, timeout)
        except Exception as e:
            logger.error(f"Error in process_frames: {str(e)}")
            raise

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
        frames = interpolation_client.process_frames(frame1_rgb, frame2_rgb, num_frames=1)
        print("Successfully received interpolated frames!")
        
        # Save the interpolated frame
        cv2.imwrite("test_interpolated_frame.png", 
                   cv2.cvtColor(frames[0], cv2.COLOR_RGB2BGR))
        print("Saved interpolated frame to test_interpolated_frame.png")
            
    except Exception as e:
        logger.error(f"Test error: {str(e)}") 