import numpy as np
import cv2
import tensorflow as tf
import tensorflow_hub as hub
from typing import Dict, Any, List, Tuple
import os
import logging
import os
import subprocess
import glob
import json

# Suppress TensorFlow logging
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # 0=all, 1=no INFO, 2=no INFO/WARN, 3=no INFO/WARN/ERROR


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info(f"TensorFlow version: {tf.__version__}")
logger.info(tf.config.list_physical_devices('GPU'))

# Set cache directory for TensorFlow Hub (inside Docker container)
cache_dir = os.path.join(os.getcwd(), 'tfhub_cache')
os.environ['TFHUB_CACHE_DIR'] = cache_dir
os.makedirs(cache_dir, exist_ok=True)

# Initialize model as None
model = None
'''
try:
    logger.info("Loading FILM model from TensorFlow Hub...")
    logger.info(f"Cache directory: {os.environ['TFHUB_CACHE_DIR']}")
    
    # Load the model with progress tracking
    model = hub.load("https://tfhub.dev/google/film/1")
    logger.info("FILM model loaded successfully!")
    
except Exception as e:
    logger.error(f"Failed to load FILM model: {e}")
    logger.error("Please check your internet connection and try again.")
    logger.error(f"Cache directory: {os.environ['TFHUB_CACHE_DIR']}")
    raise
'''
def load_frame(path: str) -> np.ndarray:
    """Load a frame from disk and convert to RGB."""
    frame = cv2.imread(path)
    if frame is None:
        raise FileNotFoundError(f"Could not load image: {path}")
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

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

def extract_video_frames(video_path: str, repo_path: str) -> None:
    """Extract frames from video."""
    output_pattern = os.path.join(repo_path, "frame_%06d.jpg")
    subprocess.run(['ffmpeg', '-i', video_path, '-q:v', '1', '-y', output_pattern], capture_output=True, check=True)

def extract_video_audio(video_path: str, repo_path: str, sample_rate: str = None) -> None:
    """Extract audio from video, optionally at a given sample rate."""
    audio_path = os.path.join(repo_path, "audio.wav")
    cmd = ['ffmpeg', '-i', video_path, '-vn', '-acodec', 'pcm_s16le']
    if sample_rate:
        cmd.extend(['-ar', str(sample_rate)])
    cmd.extend(['-ac', '2', '-y', audio_path])
    subprocess.run(cmd, capture_output=True, check=True)

def extract_video_metadata(video_path: str, repo_path: str) -> None:
    """Extract comprehensive video metadata."""
    import json
    
    # Video stream info
    video_cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', 
                 '-show_entries', 'stream=width,height,r_frame_rate,avg_frame_rate,codec_name,bit_rate,pix_fmt,color_space,color_transfer,color_primaries,field_order,has_b_frames,profile,level,color_range', 
                 '-of', 'json', video_path]
    
    # Audio stream info  
    audio_cmd = ['ffprobe', '-v', 'error', '-select_streams', 'a:0',
                 '-show_entries', 'stream=codec_name,bit_rate,sample_rate,channels,channel_layout',
                 '-of', 'json', video_path]
    
    # Container info
    format_cmd = ['ffprobe', '-v', 'error',
                  '-show_entries', 'format=format_name,duration,bit_rate,start_time',
                  '-of', 'json', video_path]
    
    video_info = json.loads(subprocess.run(video_cmd, capture_output=True, check=True, text=True).stdout)
    audio_info = json.loads(subprocess.run(audio_cmd, capture_output=True, check=True, text=True).stdout)
    format_info = json.loads(subprocess.run(format_cmd, capture_output=True, check=True, text=True).stdout)
    
    # Combine all metadata
    metadata = {
        'video': video_info.get('streams', [{}])[0] if video_info.get('streams') else {},
        'audio': audio_info.get('streams', [{}])[0] if audio_info.get('streams') else {},
        'format': format_info.get('format', {})
    }
    
    metadata_path = os.path.join(repo_path, "video_info.json")
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)

def decompose_video(video_path: str, repo_path: str) -> None:
    """Decompose video into frames, audio, and metadata."""
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")
    os.makedirs(repo_path, exist_ok=True)
    extract_video_metadata(video_path, repo_path)
    # Read sample rate from metadata
    import json
    metadata_path = os.path.join(repo_path, "video_info.json")
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
    sample_rate = metadata.get('audio', {}).get('sample_rate', None)
    extract_video_audio(video_path, repo_path, sample_rate)
    extract_video_frames(video_path, repo_path)

def recompose_video(repo_path: str, output_video_path: str) -> None:
    """Recompose video using original metadata."""
    if not os.path.exists(repo_path):
        raise FileNotFoundError(f"Repo not found: {repo_path}")
    
    frame_pattern = os.path.join(repo_path, "frame_*.jpg")
    if not glob.glob(frame_pattern):
        raise FileNotFoundError(f"No frames in {repo_path}")
    
    # Load metadata
    metadata_path = os.path.join(repo_path, "video_info.json")
    if not os.path.exists(metadata_path):
        raise FileNotFoundError(f"Metadata not found: {metadata_path}")
    
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
    
    video_info = metadata.get('video', {})
    audio_info = metadata.get('audio', {})
    format_info = metadata.get('format', {})
    
    # Extract key parameters
    fps = video_info.get('r_frame_rate', '30/1')
    width = video_info.get('width', 1920)
    height = video_info.get('height', 1080)
    codec = video_info.get('codec_name', 'libx264')
    original_pix_fmt = video_info.get('pix_fmt', 'yuv420p')
    
    # Use 8-bit pixel format for compatibility with JPEG frames
    pix_fmt = 'yuv420p' if '10le' in original_pix_fmt else original_pix_fmt
    
    audio_path = os.path.join(repo_path, "audio.wav")
    has_audio = os.path.exists(audio_path)
    
    output_dir = os.path.dirname(output_video_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # Build ffmpeg command with original parameters
    cmd = ['ffmpeg', '-framerate', fps, '-i', os.path.join(repo_path, "frame_%06d.jpg")]
    
    if has_audio:
        cmd.extend(['-i', audio_path])
    
    # Video encoding settings
    cmd.extend([
        '-c:v', codec,
        '-pix_fmt', pix_fmt,
        '-vf', f'scale={width}:{height}',
        '-y', output_video_path
    ])
    
    subprocess.run(cmd, capture_output=True, check=True)

if __name__ == "__main__":
    # Example: local test of interpolation pipeline
    #Decompose video to frames
    video_path = "bromo.MOV"
    repo_path = "frames"
    decompose_video(video_path, repo_path)
    
    #Recompose video from frames
    output_video_path = "output_video.MOV"
    recompose_video(repo_path, output_video_path)

    # Load frames using the new function
    frame1 = load_frame("frame_17848.jpg")
    frame2 = load_frame("frame_17850.jpg")

    # Run interpolation
    #print("Running local test interpolation...")
    #frames = interpolate_frames(frame1, frame2, num_frames=2)

    # Save to disk
    #saved = save_frames(frames, prefix="test_output")
    #print("Saved interpolated frames:", saved)
