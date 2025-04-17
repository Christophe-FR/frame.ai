# -*- coding: utf-8 -*-
import redis
import json
import base64
import numpy as np
import cv2
from PIL import Image
import io
import time
from typing import Dict, Any, Optional, List, Union
import uuid

# Redis configuration
REDIS_HOST = "localhost"
REDIS_PORT = 6379
TASK_QUEUE = "frame_interpolation_tasks"
RESULT_QUEUE = "frame_interpolation_results"

def encode_frame_to_base64(frame_rgb: np.ndarray) -> str:
    """Encode an RGB frame to base64."""
    try:
        _, buffer = cv2.imencode(".png", cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR))
        return base64.b64encode(buffer).decode("utf-8")
    except Exception as e:
        raise ValueError(f"Failed to encode frame: {str(e)}")

def submit_task(frame1_rgb: np.ndarray, frame2_rgb: np.ndarray, num_frames: int = 1, task_id: Optional[str] = None) -> str:
    """Submit a task to the Redis queue.
    
    Args:
        frame1_rgb: First RGB frame
        frame2_rgb: Second RGB frame
        num_frames: Number of frames to interpolate
        task_id: Optional task ID, will generate one if not provided
        
    Returns:
        str: The task ID
        
    Raises:
        redis.RedisError: If there's an error communicating with Redis
        ValueError: If frame encoding fails
    """
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)
        task_id = task_id or f"task_{uuid.uuid4()}"
        
        task_data = {
            "task_id": task_id,
            "image1": encode_frame_to_base64(frame1_rgb),
            "image2": encode_frame_to_base64(frame2_rgb),
            "num_frames": num_frames
        }
        r.rpush(TASK_QUEUE, json.dumps(task_data))
        return task_id
    except redis.RedisError as e:
        raise redis.RedisError(f"Failed to submit task to Redis: {str(e)}")

def retrieve_result(task_id: str, timeout: int = 60) -> Optional[Dict[str, Any]]:
    """Retrieve a result from the Redis queue for a specific task_id.
    
    Args:
        task_id: The task ID to retrieve results for
        timeout: Maximum time to wait for results in seconds
        
    Returns:
        Optional[Dict[str, Any]]: The result dictionary if found, None if timeout
        
    Raises:
        redis.RedisError: If there's an error communicating with Redis
    """
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)
        start_time = time.time()
        while time.time() - start_time < timeout:
            result = r.blpop(RESULT_QUEUE, timeout=1)
            if result is None:
                continue
                
            _, result_json = result
            if result_json:
                result_data = json.loads(result_json)
                if result_data.get("task_id") == task_id:
                    return result_data
        return None
    except redis.RedisError as e:
        raise redis.RedisError(f"Failed to retrieve result from Redis: {str(e)}")

def save_frames(result: dict, prefix: str = "interpolated") -> List[str]:
    """Save all interpolated frames to disk.
    
    Args:
        result: The result dictionary containing interpolated frames
        prefix: Prefix for saved frame filenames
        
    Returns:
        List[str]: List of paths to saved frames
        
    Raises:
        ValueError: If result doesn't contain interpolated frames
    """
    if "interpolated_frames" not in result:
        raise ValueError("Result does not contain interpolated frames")
        
    saved_paths = []
    for i, frame_b64 in enumerate(result["interpolated_frames"]):
        path = f"{prefix}_frame_{i+1}.png"
        try:
            with open(path, "wb") as f:
                f.write(base64.b64decode(frame_b64))
            saved_paths.append(path)
        except Exception as e:
            raise ValueError(f"Failed to save frame {i+1}: {str(e)}")
    return saved_paths

def load_and_resize_frame(frame_path: str, max_dim: int = 512) -> np.ndarray:
    """Load and resize frame while maintaining aspect ratio.
    
    Args:
        frame_path: Path to the frame image
        max_dim: Maximum dimension (width or height)
        
    Returns:
        np.ndarray: Resized frame in BGR format
        
    Raises:
        FileNotFoundError: If frame cannot be loaded
        ValueError: If frame is invalid
    """
    frame = cv2.imread(frame_path)
    if frame is None:
        raise FileNotFoundError(f"Could not load {frame_path}")
    
    # Calculate scaling factor
    h, w = frame.shape[:2]
    scale = min(max_dim/h, max_dim/w)
    
    # Resize
    return cv2.resize(frame, (int(w*scale), int(h*scale)))

def clear_queues() -> None:
    """Clear both Redis queues.
    
    Raises:
        redis.RedisError: If there's an error communicating with Redis
    """
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)
        r.delete(TASK_QUEUE, RESULT_QUEUE)
    except redis.RedisError as e:
        raise redis.RedisError(f"Failed to clear Redis queues: {str(e)}")

if __name__ == "__main__":
    # Test the functionality
    try:
        # Load and resize frames
        frame1_bgr = load_and_resize_frame("frame_17848.jpg")
        frame2_bgr = load_and_resize_frame("frame_17850.jpg")
        
        # Convert to RGB
        frame1_rgb = cv2.cvtColor(frame1_bgr, cv2.COLOR_BGR2RGB)
        frame2_rgb = cv2.cvtColor(frame2_bgr, cv2.COLOR_BGR2RGB)
        
        # Submit task for 2 interpolated frames
        task_id = submit_task(frame1_rgb, frame2_rgb, num_frames=2)
        print(f"Submitted task with ID: {task_id}")
        
        # Retrieve and save results
        result = retrieve_result(task_id)
        if result:
            saved_paths = save_frames(result)
            print(f"Saved frames: {saved_paths}")
        else:
            print("No results received within timeout")
            
    except Exception as e:
        print(f"Error: {str(e)}")