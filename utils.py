import numpy as np
import cv2
import os
import logging
import subprocess
import glob

import tensorflow as tf
import tensorflow_hub as hub
from typing import Dict, Any, List, Tuple, Union
import json

# Suppress TensorFlow logging
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # 0=all, 1=no INFO, 2=no INFO/WARN, 3=no INFO/WARN/ERROR

# Configure GPU memory growth to prevent memory issues

gpus = tf.config.experimental.list_physical_devices('GPU')
if gpus:
    try:
        for gpu in gpus:
            tf.config.experimental.set_memory_growth(gpu, True)
    except RuntimeError as e:
        print(e)


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


logger.info("Loading FILM model from TensorFlow Hub...")
logger.info(f"Cache directory: {os.environ['TFHUB_CACHE_DIR']}")

# Load the model with progress tracking
model = hub.load("https://tfhub.dev/google/film/1")
logger.info("FILM model loaded successfully!")
    

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

def interpolate_frames_at_times(frame1: np.ndarray, frame2: np.ndarray, times: List[float]) -> List[np.ndarray]:
    """Interpolate frames at specific times between two frames using FILM model.
    
    Args:
        frame1: First frame
        frame2: Second frame
        times: List of interpolation times (0.0 = frame1, 1.0 = frame2)

    Returns:
        List of interpolated frames as numpy arrays (RGB uint8)
    """
    # Resize frames if needed
    frame1_resized, original_shape = resize_frame(frame1)
    frame2_resized, _ = resize_frame(frame2)
    
    # Normalize frames
    frame1_norm = normalize(frame1_resized)
    frame2_norm = normalize(frame2_resized)
    
    interpolated = []
    
    for time_val in times:
        input_dict = {
            "time": np.array([[time_val]], dtype=np.float32),
            "x0": np.expand_dims(frame1_norm, axis=0),
            "x1": np.expand_dims(frame2_norm, axis=0),
        }
        result = model(input_dict)
        interpolated_frame = result["image"][0].numpy()
        interpolated.append(restore_frame_size(denormalize(interpolated_frame), original_shape))
    
    return interpolated

def interpolate_frames(frame1: np.ndarray, frame2: np.ndarray, num_frames: int = 1) -> List[np.ndarray]:
    """Interpolate frames using FILM model.

    Args:
        frame1: First frame
        frame2: Second frame
        num_frames: Number of in-between frames to generate (default: 1)

    Returns:
        List of interpolated frames as numpy arrays (RGB uint8)
    """
    # Calculate evenly spaced times
    times = [i / (num_frames + 1) for i in range(1, num_frames + 1)]
    
    # Use interpolate_frames_at_times to do the actual work
    return interpolate_frames_at_times(frame1, frame2, times)

def save_frames(frames: List[np.ndarray], filenames: List[str], root_folder: str = "", extension: str = "") -> List[str]:
    """Save frames to disk with custom filenames and paths."""
    if len(frames) > len(filenames):
        raise ValueError(f"Not enough filenames: {len(frames)} frames but only {len(filenames)} filenames provided")
    
    saved_paths = []
    for i, frame in enumerate(frames):
        filename = filenames[i]
        if extension and not filename.endswith(extension):
            filename += extension
        
        if root_folder:
            path = os.path.join(root_folder, filename)
            os.makedirs(root_folder, exist_ok=True)
        else:
            path = filename
            
        cv2.imwrite(path, cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
        saved_paths.append(path)
    return saved_paths

def extract_video_frames(video_path: str, repo_path: str) -> None:
    """Extract frames from video."""
    output_pattern = os.path.join(repo_path, "frame_%06d.jpg")
    subprocess.run(['ffmpeg', '-i', video_path, '-q:v', '1', '-y', output_pattern], capture_output=True, check=True)
    for frame_path in glob.glob(os.path.join(repo_path, "frame_*.jpg")):
        if '.' not in os.path.basename(frame_path)[6:-4]:
            os.rename(frame_path, frame_path.replace('.jpg', '.000.jpg'))

def extract_video_audio(video_path: str, repo_path: str) -> None:
    """Extract audio from video with original sample rate."""
    audio_path = os.path.join(repo_path, "audio.wav")
    
    # Get original sample rate from video
    sample_rate_cmd = ['ffprobe', '-v', 'error', '-select_streams', 'a:0', '-show_entries', 'stream=sample_rate', '-of', 'csv=p=0', video_path]
    sample_rate = subprocess.run(sample_rate_cmd, capture_output=True, check=True, text=True).stdout.strip()
    
    cmd = ['ffmpeg', '-i', video_path, '-vn', '-acodec', 'pcm_s16le', '-ar', sample_rate, '-ac', '2', '-y', audio_path]
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
    extract_video_audio(video_path, repo_path)
    extract_video_frames(video_path, repo_path)

def recompose_video(repo_path: str, output_video_path: str) -> None:
    """Recompose video using original metadata."""
    if not os.path.exists(repo_path):
        raise FileNotFoundError(f"Repo not found: {repo_path}")
    
    frame_pattern = os.path.join(repo_path, "frame_*.jpg")
    frames = glob.glob(frame_pattern)
    if not frames:
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
    
    # Sort frames and create file list
    frames.sort(key=lambda x: float(os.path.basename(x)[6:-8]))
    file_list = os.path.join(repo_path, "frames_list.txt")
    with open(file_list, 'w') as f:
        for frame in frames:
            f.write(f"file '{os.path.abspath(frame)}'\n")
    
    # Build ffmpeg command
    cmd = ['ffmpeg', '-f', 'concat', '-safe', '0', '-i', file_list]
    if has_audio:
        cmd.extend(['-i', audio_path])
    cmd.extend(['-framerate', fps, '-c:v', codec, '-pix_fmt', pix_fmt, '-vf', f'scale={width}:{height}'])
    if has_audio:
        cmd.extend(['-c:a', 'aac', '-shortest'])
    cmd.extend(['-y', output_video_path])
    
    subprocess.run(cmd, capture_output=True, check=True)
    #os.remove(file_list)

def schedule_interpolate_video(repo_path: str, targets: List[float]):
    frame_pattern = os.path.join(repo_path, "frame_*.jpg")
    frames = glob.glob(frame_pattern)
    anchors = []
    for frame in frames:
        # Extract the frame number part (everything between "frame_" and ".jpg")
        frame_name = os.path.basename(frame)
        if frame_name.startswith("frame_") and frame_name.endswith(".jpg"):
            frame_number_str = frame_name[6:-4]  # Remove "frame_" and ".jpg"
            try:
                frame_number = float(frame_number_str)
                anchors.append(frame_number)
            except ValueError:
                print(f"Warning: Could not parse frame number from {frame_name}")
    
    anchors = set(anchors)
    targets = set(targets)
    ineligible = anchors & targets
    available = anchors - ineligible
    age = {a: 0 for a in anchors}
    age_counter = 1
    result = []

    points = set(available)

    while targets:
        made_progress = False
        sorted_points = sorted(points)

        for i in range(len(sorted_points) - 1):
            a, b = sorted_points[i], sorted_points[i + 1]
            between = [t for t in targets if a < t < b]
            if not between:
                continue

            mid = (a + b) / 2

            def score(t):
                dist = abs(t - mid)
                bias = abs(t - a) if age[a] <= age[b] else abs(t - b)
                return (dist, bias)

            t = min(between, key=score)
            result.append((t, a, b))
            targets.remove(t)
            points.add(t)
            age[t] = age_counter
            age_counter += 1
            if t in ineligible:
                ineligible.remove(t)
            made_progress = True
            break  # Do one per iteration to preserve priority

        if not made_progress:
            raise RuntimeError("Unable to compute all targets. Some may not be between usable anchors.")

    return result

def interpolate_frames_video(repo_path: str, targets: List[float]):
    schedule = schedule_interpolate_video(repo_path, targets)
    for target, a, b in schedule:
        # Handle frame indices for both input and output
        # Use format to match actual frame names: frame_XXXXXX.000.jpg
        frame1_path = os.path.join(repo_path, f"frame_{a:010.3f}.jpg")
        frame2_path = os.path.join(repo_path, f"frame_{b:010.3f}.jpg")
        
        # Calculate time for interpolation
        time = (target - a) / (b - a)
        print(f"Interpolating frame {target:.3f} between {a:.3f} and {b:.3f} at time t={time:.3f}")
        
        # Load frames and interpolate
        frame1 = load_frame(frame1_path)
        frame2 = load_frame(frame2_path)
        frames = interpolate_frames_at_times(frame1, frame2, [time])
        
        # Save interpolated frames
        output_path = os.path.join(repo_path, f"frame_{target:010.3f}.jpg")
        save_frames(frames, [output_path])

def copy_frame_video(repo_path: str, source: float, target: float) -> None:
    """Copy a frame from source_index to target_index in a repo.
    
    Args:
        repo_path: Path to the frame repository
        source_index: Source frame index to copy from
        target_index: Target frame index to copy to
    """
    source_path = os.path.join(repo_path, f"frame_{source:010.3f}.jpg")
    target_path = os.path.join(repo_path, f"frame_{target:010.3f}.jpg")
    
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Source frame not found: {source_path}")
    
    # Copy the file
    import shutil
    shutil.copy2(source_path, target_path)
    print(f"Copied frame_{source:010.3f}.jpg to frame_{target:010.3f}.jpg")

def get_frames_video_list(repo_path: str) -> List[str]:
    if not os.path.exists(repo_path):
        return []
    frame_pattern = os.path.join(repo_path, "frame_*.jpg")
    frames = glob.glob(frame_pattern)
    return frames

if __name__ == "__main__":

    frames = get_frames_video_list("/workspace/uploads/2afaa5d5-b243-41d7-a7a8-efa21083d290")
    print(frames)
    """
    # Example: local test of interpolation pipeline
    #Decompose video to frames
    video_path = "sample/wedding.mp4"
    output_video_path = "sample/output_video.mp4"
    repo_path = "frames"

    decompose_video(video_path, repo_path)
    
    defects = [
        16101,16103,16106,16598,16600,16602,16605,16607,16609,16611,16615,
        16617,16619,16622,16646,16648,16651,16653,16686,16689,16725,16727,
        16740,16742,16762,16764,16766,16785,16787,16789,16957,16959,17065,
        17067,17100,17448,17450,17454,17848,17850,17854,17861,17865,
        17869,17874,17878,17882,17886,17893,17897,17901,
        17905,17909,17913,17916,17920,17924,17928,17958,17960,17964,17968,
        17971,17975,17979,17983,17987,17998,18000,18004,18008,18012,18016,
        18020,18023,18027,18074,18077,18094,18096,18100,18259,18270,18272,
        18276,18280,18284,18288,18292,18295,18299,18215,18315,18317,18321,18325,
        18329,18338,18341,18353,18355,18359,18361,18365,18369,18372,
        18376,18380,18384,18388,18392,18485,18487,18491,18503,18506,18509,
        18574,18578,18581,18700,18702,18711,18715,18719,18723,19146,19148,
        19186,19188,19382,19384,19405,19407,19447,19449,19535,19537,19593,
        19595,19689,19691,19790,19792,20255,20257,20334,20336,20536,20538,20717,20719,
        20934,20937,21199,21201,21313,21315,21319,21339,21341,21362,21364,
        21368,21372,21399,21401,21425,21427,21431,21435,21456,21462,21611,21613,21985,21987,
        24737,24739,24752,24755,24757,24880,24882,24889,24894,24899,24901,
        25222,25225,25360,25364,25373,25389,25423,25806,
        25827,25829,25849,25851,25853,25804
    ]
    for defect in defects:
        interpolate_frames_from_indices(repo_path, defect-1, defect+1)

    #interpolate_frames_from_indices(repo_path, 3774-1, 3783+1)
    interpolate_frames_from_indices(repo_path, 17097-1, 17098+1)
    interpolate_frames_from_indices(repo_path, 17889-1, 17890+1)
    interpolate_frames_from_indices(repo_path, 18332-1, 18333+1)
    interpolate_frames_from_indices(repo_path, 18706-1, 18707+1)
    interpolate_frames_from_indices(repo_path, 17857-1, 17858+1)
    interpolate_frames_from_indices(repo_path, 25367-1, 25368+1)
    interpolate_frames_from_indices(repo_path, 25376-1, 25377+1)
    interpolate_frames_from_indices(repo_path, 25395-1, 25396+1)

    # Copy frame 16262 to frame 16263
    copy_frame(repo_path, 16262, 16263)
    # Copy frame 12169 to frame 12170
    copy_frame(repo_path, 12169, 12170)
    """
    # Load frames using the new function
    #frame1 = load_frame("frame_17848.jpg")
    #frame2 = load_frame("frame_17850.jpg")

    #frames = interpolate_frames(frame1, frame2, 2)

    # Save results
    #saved = save_frames(frames, filenames=["frame_17849-1.jpg", "frame_17849-2.jpg"])
    #print(f"Saved interpolated frames: {saved}")

    #interpolate_frames_from_files("frames/frame_000081.jpg", "frames/frame_000083.jpg", ["frames/frame_000082.jpg"])
    #interpolate_frames_from_files("frames/frame_000083.jpg", "frames/frame_000085.jpg", ["frames/frame_000084.jpg"])
 
    #interpolate_frames_from_indices(repo_path, 81, 85)
    
    #interpolate_frames_video(repo_path, [float(i)+0.5 for i in range(40,60)])

    #copy_frame_video(repo_path, 110, 108.5)

    #Recompose video from frames
    #recompose_video(repo_path, output_video_path)
    
    print("Done")
