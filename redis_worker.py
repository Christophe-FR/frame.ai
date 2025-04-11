# -*- coding: utf-8 -*-
import tensorflow as tf
import tensorflow_hub as hub
import numpy as np
import redis
import json
import base64
import cv2
from typing import Dict, Any

# Redis configuration
REDIS_HOST = "localhost"  # or "redis" if using Docker service name
REDIS_PORT = 6379
TASK_QUEUE = "frame_interpolation_tasks"
RESULT_QUEUE = "frame_interpolation_results"

# Load the FILM model
model = hub.load("https://tfhub.dev/google/film/1")

def load_image(image_data: bytes) -> np.ndarray:
    """Load an image from bytes and normalize it to [0, 1] range."""
    image = tf.io.decode_image(image_data, channels=3)
    image_numpy = tf.cast(image, dtype=tf.float32).numpy()
    return image_numpy / 255.0  # Normalize to [0, 1]

def process_task(task_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process a frame interpolation task."""
    try:
        # Decode images from base64
        image1 = base64.b64decode(task_data["image1"])
        image2 = base64.b64decode(task_data["image2"])
        time = task_data.get("time", 0.5)  # Default to midway interpolation

        # Load and preprocess images
        image1 = load_image(image1)
        image2 = load_image(image2)

        # Prepare model input with correct shapes
        input_dict = {
            "time": np.array([[time]], dtype=np.float32),  # Shape: (batch_size=1, 1)
            "x0": np.expand_dims(image1, axis=0),  # Shape: (1, height, width, 3)
            "x1": np.expand_dims(image2, axis=0),  # Shape: (1, height, width, 3)
        }

        # Run interpolation
        result = model(input_dict)
        interpolated_frame = result["image"][0].numpy()

        # Ensure the frame is in [0, 255] range and convert to uint8
        interpolated_frame_uint8 = (np.clip(interpolated_frame, 0, 1) * 255).astype(np.uint8)

        # Encode the result as PNG and then to base64
        success, buffer = cv2.imencode(".png", cv2.cvtColor(interpolated_frame_uint8, cv2.COLOR_RGB2BGR))
        if not success:
            raise ValueError("Failed to encode frame as PNG")
        interpolated_image_b64 = base64.b64encode(buffer).decode("utf-8")

        return {
            "task_id": task_data.get("task_id", ""),
            "interpolated_frame": interpolated_image_b64,
        }
    except Exception as e:
        print(f"Error in process_task: {e}")
        raise

def main():
    # Connect to Redis
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)

    print("Worker started. Listening for tasks...")
    while True:
        # Blocking pop from the task queue
        _, task_json = r.blpop(TASK_QUEUE)
        task_data = json.loads(task_json)

        try:
            # Process the task
            result = process_task(task_data)
            # Push the result to the result queue
            r.rpush(RESULT_QUEUE, json.dumps(result))
            print(f"Processed task {result['task_id']}")
        except Exception as e:
            print(f"Error processing task: {e}")

if __name__ == "__main__":
    main()