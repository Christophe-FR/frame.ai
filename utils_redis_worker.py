# -*- coding: utf-8 -*-
import redis
import json
import base64
import numpy as np
import cv2
from PIL import Image
import io
import time
from typing import Dict, Any, Optional
import uuid

# Redis configuration
REDIS_HOST = "localhost"
REDIS_PORT = 6379
TASK_QUEUE = "frame_interpolation_tasks"
RESULT_QUEUE = "frame_interpolation_results"

def encode_frame_to_base64(frame_rgb: np.ndarray) -> str:
    """Encode an RGB frame to base64."""
    _, buffer = cv2.imencode(".png", cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR))
    return base64.b64encode(buffer).decode("utf-8")

def submit_task(frame1_rgb: np.ndarray, frame2_rgb: np.ndarray, num_frames: int = 1, task_id: Optional[str] = None) -> str:
    """Submit a task to the Redis queue."""
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

def retrieve_result(task_id: str, timeout: int = 60) -> Optional[Dict[str, Any]]:
    """Retrieve a result from the Redis queue for a specific task_id."""
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)
    start_time = time.time()
    while time.time() - start_time < timeout:
        _, result_json = r.blpop(RESULT_QUEUE, timeout=1)
        if result_json:
            result = json.loads(result_json)
            if result.get("task_id") == task_id:
                return result
    return None

def save_frames(result: dict, prefix: str = "interpolated"):
    """Save all interpolated frames."""
    for i, frame_b64 in enumerate(result["interpolated_frames"]):
        path = f"{prefix}_frame_{i+1}.png"
        with open(path, "wb") as f:
            f.write(base64.b64decode(frame_b64))
        print(f"Saved {path}")

def load_and_resize_frame(frame_path: str, max_dim: int = 512) -> np.ndarray:
    """Load and resize frame while maintaining aspect ratio."""
    frame = cv2.imread(frame_path)
    if frame is None:
        raise FileNotFoundError(f"Could not load {frame_path}")
    
    # Calculate scaling factor
    h, w = frame.shape[:2]
    scale = min(max_dim/h, max_dim/w)
    
    # Resize
    return cv2.resize(frame, (int(w*scale), int(h*scale)))

def clear_queues():
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)
    r.delete(TASK_QUEUE, RESULT_QUEUE)
    print("Cleared Redis queues.")

if __name__ == "__main__":
    #clear_queues()  # Start fresh
    # Load and resize frames
    try:
        frame1_bgr = load_and_resize_frame("frame_17848.jpg")  # Max dimension 512px
        frame2_bgr = load_and_resize_frame("frame_17850.jpg")
        
        # Convert to RGB
        frame1_rgb = cv2.cvtColor(frame1_bgr, cv2.COLOR_BGR2RGB)
        frame2_rgb = cv2.cvtColor(frame2_bgr, cv2.COLOR_BGR2RGB)
        
        # Submit task for 3 interpolated frames

        submit_task(frame1_rgb, frame2_rgb, num_frames=2, task_id="real_frames_test")
        # Retrieve and save results
        result = retrieve_result("real_frames_test")
        if result:
            save_frames(result)
    except Exception as e:
        print(f"Error: {str(e)}")