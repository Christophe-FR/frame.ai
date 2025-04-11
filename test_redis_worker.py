# -*- coding: utf-8 -*-
import redis
import json
import base64
import numpy as np
import cv2
from PIL import Image
import io

# Redis configuration (must match the worker script)
REDIS_HOST = "localhost"  # or "redis" if using Docker service name
REDIS_PORT = 6379
TASK_QUEUE = "frame_interpolation_tasks"
RESULT_QUEUE = "frame_interpolation_results"

def encode_frame_to_base64(frame_rgb: np.ndarray) -> str:
    """Encode an RGB frame (numpy array) to base64."""
    # Convert numpy array to bytes (OpenCV expects BGR for encoding)
    _, buffer = cv2.imencode(".png", cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR))
    return base64.b64encode(buffer).decode("utf-8")

def submit_task(frame1_rgb: np.ndarray, frame2_rgb: np.ndarray, time: float = 0.5, task_id: str = "test_task"):
    """Submit a task to the Redis queue."""
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)
    
    # Encode frames to base64
    frame1_b64 = encode_frame_to_base64(frame1_rgb)
    frame2_b64 = encode_frame_to_base64(frame2_rgb)
    
    # Prepare task data
    task_data = {
        "task_id": task_id,
        "image1": frame1_b64,
        "image2": frame2_b64,
        "time": time,
    }
    
    # Push to the task queue
    r.rpush(TASK_QUEUE, json.dumps(task_data))
    print(f"Submitted task: {task_id}")

def retrieve_result(timeout: int = 100) -> dict:
    """Retrieve a result from the Redis queue."""
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)
    
    # Blocking pop from the result queue
    _, result_json = r.blpop(RESULT_QUEUE, timeout=timeout)
    if result_json:
        result = json.loads(result_json)
        print(f"Retrieved result for task: {result['task_id']}")
        return result
    else:
        print("No result retrieved within the timeout period.")
        return None

def save_base64_image(base64_str: str, output_path: str):
    """Save a base64-encoded image to a file."""
    image_data = base64.b64decode(base64_str)
    image = Image.open(io.BytesIO(image_data))
    image.save(output_path)
    print(f"Saved interpolated frame to: {output_path}")

if __name__ == "__main__":
    # Load frames from image files (replace with your actual file paths)
    frame1_path = "frame_17848.jpg"  # Example path
    frame2_path = "frame_17850.jpg"  # Example path
    
    # Read frames using OpenCV (BGR format)
    frame1_bgr = cv2.imread(frame1_path)
    frame2_bgr = cv2.imread(frame2_path)
    
    if frame1_bgr is not None and frame2_bgr is not None:
        # Convert BGR to RGB (matching your frontend)
        frame1_rgb = cv2.cvtColor(frame1_bgr, cv2.COLOR_BGR2RGB)
        frame2_rgb = cv2.cvtColor(frame2_bgr, cv2.COLOR_BGR2RGB)
        
        # Submit a task
        submit_task(frame1_rgb, frame2_rgb, time=0.5, task_id="test_1")
        
        # Retrieve the result (blocking call)
        result = retrieve_result()
        
        if result:
            # Save the interpolated frame
            save_base64_image(result["interpolated_frame"], "interpolated_frame.png")
    else:
        print("Failed to load one or both frames. Check file paths.")