import base64
import numpy as np
import cv2
import tensorflow as tf

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