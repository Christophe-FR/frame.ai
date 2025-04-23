import numpy as np
import cv2
import tensorflow as tf
import tensorflow_hub as hub
from typing import Dict, Any, List
import base64

# Load FILM model (only when this module is used directly)
model = hub.load("https://tfhub.dev/google/film/1")

def load_frame(path: str) -> np.ndarray:
    """Load a frame from disk and convert to RGB."""
    frame = cv2.imread(path)
    if frame is None:
        raise FileNotFoundError(f"Could not load image: {path}")
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

def encode_frame_to_base64(frame_rgb: np.ndarray) -> str:
    """Encode an RGB frame to base64.
    
    Args:
        frame_rgb: RGB frame as numpy array
        
    Returns:
        Base64 encoded string
    """
    _, buffer = cv2.imencode(".png", cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR))
    return base64.b64encode(buffer).decode("utf-8")

def decode_base64_to_frame(b64: str) -> np.ndarray:
    """Decode a base64 string to an RGB frame.
    
    Args:
        b64: Base64 encoded string
        
    Returns:
        RGB frame as numpy array
    """
    image_data = base64.b64decode(b64)
    image = tf.io.decode_image(image_data, channels=3)
    return image.numpy()

def normalize(frame: np.ndarray) -> np.ndarray:
    """Convert frame to float32 in [0, 1] range."""
    return tf.cast(frame, tf.float32).numpy() / 255.0

def denormalize(frame: np.ndarray) -> np.ndarray:
    """Convert frame from float [0, 1] to uint8 [0, 255]."""
    return (np.clip(frame, 0, 1) * 255).astype(np.uint8)

def resize_frame(frame: np.ndarray, max_width: int = 2048, max_height: int = 1080) -> tuple:
    """Resize frame if it exceeds maximum dimensions while maintaining aspect ratio.
    
    Args:
        frame: Input frame as numpy array
        max_width: Maximum allowed width
        max_height: Maximum allowed height
        
    Returns:
        tuple: (resized_frame, original_shape)
    """
    height, width = frame.shape[:2]
    original_shape = (width, height)
    
    # Check if resizing is needed
    if width <= max_width and height <= max_height:
        return frame, original_shape
    
    # Calculate new dimensions while maintaining aspect ratio
    scale = min(max_width / width, max_height / height)
    new_width = int(width * scale)
    new_height = int(height * scale)
    
    # Resize the frame
    resized = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)
    return resized, original_shape

def restore_frame_size(frame: np.ndarray, original_shape: tuple) -> np.ndarray:
    """Restore frame to its original size.
    
    Args:
        frame: Resized frame as numpy array
        original_shape: Original (width, height) tuple
        
    Returns:
        Restored frame as numpy array
    """
    return cv2.resize(frame, original_shape, interpolation=cv2.INTER_LANCZOS4)

def interpolate_frames(frame1: np.ndarray, frame2: np.ndarray, num_frames: int = 1) -> List[np.ndarray]:
    """Interpolate frames using FILM model.

    Args:
        frame1: First frame
        frame2: Second frame
        num_frames: Number of in-between frames to generate (default: 1)

    Returns:
        List of interpolated frames as numpy arrays (RGB uint8)
    """
    # Resize frames if needed
    frame1_resized, original_shape = resize_frame(frame1)
    frame2_resized, _ = resize_frame(frame2)
    
    interpolated = []
    frame1_norm = normalize(frame1_resized)
    frame2_norm = normalize(frame2_resized)

    for i in range(1, num_frames + 1):
        time = i / (num_frames + 1)
        input_dict = {
            "time": np.array([[time]], dtype=np.float32),
            "x0": np.expand_dims(frame1_norm, axis=0),
            "x1": np.expand_dims(frame2_norm, axis=0),
        }
        result = model(input_dict)
        interpolated_frame = result["image"][0].numpy()
        interpolated.append(denormalize(interpolated_frame))
    
    # Restore original size for all frames
    restored_frames = []
    for frame in interpolated:
        restored = restore_frame_size(frame, original_shape)
        restored_frames.append(restored)
    
    return restored_frames

def save_frames(frames: List[np.ndarray], prefix: str = "interpolated") -> List[str]:
    """Save frames to disk."""
    saved_paths = []
    for i, frame in enumerate(frames):
        path = f"{prefix}_frame_{i+1}.png"
        cv2.imwrite(path, cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
        saved_paths.append(path)
    return saved_paths

if __name__ == "__main__":
    # Example: local test of interpolation pipeline
    try:
        # Load frames using the new function
        frame1 = load_frame("frame_17848.jpg")
        frame2 = load_frame("frame_17850.jpg")

        # Run interpolation
        print("Running local test interpolation...")
        frames = interpolate_frames(frame1, frame2, num_frames=2)

        # Save to disk
        saved = save_frames(frames, prefix="test_output")
        print("Saved interpolated frames:", saved)

    except Exception as e:
        print(f"Test error: {e}") 