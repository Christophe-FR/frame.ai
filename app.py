import streamlit as st
import pandas as pd
import numpy as np
import cv2
from PIL import Image
import io
import tempfile
import os
import math
import redis
import json
import base64
import uuid
from typing import Dict, Any
import subprocess
from stqdm import stqdm

# Set page config
st.set_page_config(
    page_title="Video Frame Selector",
    page_icon="🎥",
    layout="wide"
)

# Initialize session state
if 'selected_frames' not in st.session_state:
    st.session_state.selected_frames = set()
if 'current_page' not in st.session_state:
    st.session_state.current_page = 0
if 'frames_per_page' not in st.session_state:
    st.session_state.frames_per_page = 9  # 3x3 grid
if 'video_info' not in st.session_state:
    st.session_state.video_info = None
if 'temp_file_path' not in st.session_state:
    st.session_state.temp_file_path = None

# Add a title
st.title("Video Frame Selector 🎥")

# File uploader with size limit message
st.write("Upload a video file (max 4GB)")
uploaded_file = st.file_uploader("Choose a video file", type=['mp4', 'avi', 'mov'])

REDIS_HOST = "localhost"  # or "redis" if using Docker
REDIS_PORT = 6379
TASK_QUEUE = "frame_interpolation_tasks"
RESULT_QUEUE = "frame_interpolation_results"

def get_video_info(video_path):
    """Get video information"""
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    duration = total_frames / fps if fps > 0 else 0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    
    return {
        'total_frames': total_frames,
        'fps': fps,
        'duration': duration,
        'width': width,
        'height': height
    }

def extract_frames(video_path, start_frame=0, num_frames=9):
    """Extract frames dynamically for the current page."""
    if 'frame_cache' not in st.session_state:
        st.session_state.frame_cache = {}

    cache_key = f"{video_path}_{start_frame}_{num_frames}"
    if cache_key in st.session_state.frame_cache:
        return st.session_state.frame_cache[cache_key]

    frames = []
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    
    # Progress bar
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i in range(num_frames):
        ret, frame = cap.read()
        if not ret:
            break
        frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        progress_bar.progress((i + 1) / num_frames)
        status_text.text(f"Loading frame {start_frame + i + 1}")
    
    cap.release()
    progress_bar.empty()
    status_text.empty()

    st.session_state.frame_cache[cache_key] = frames
    return frames

def display_navigation_controls(total_frames):
    """Navigation controls with time slider and page info."""
    total_pages = math.ceil(total_frames / st.session_state.frames_per_page)
    current_page = st.session_state.current_page
    fps = st.session_state.video_info['fps']
    start_frame = current_page * st.session_state.frames_per_page
    end_frame = min((current_page + 1) * st.session_state.frames_per_page, total_frames)

    # Time slider (top)
    selected_time = st.slider(
        "Jump to Time",
        min_value=0.0,
        max_value=st.session_state.video_info['duration'],
        value=(start_frame / fps),
        step=1.0/fps,
        format="%.2f s",
        key="time_slider"
    )

    # Navigation controls (bottom)
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        if st.button("⬅️ Previous", disabled=current_page == 0):
            st.session_state.current_page -= 1
            st.experimental_rerun()
    
    with col2:
        st.markdown(
            f"<div style='text-align: center; font-weight: bold;'>"
            f"Page {current_page + 1}/{total_pages} | Frames {start_frame + 1}-{end_frame} of {total_frames}"
            f"</div>",
            unsafe_allow_html=True
        )
    
    with col3:
        if st.button("➡️ Next", disabled=current_page >= total_pages - 1):
            st.session_state.current_page += 1
            st.experimental_rerun()

    # Update page if slider is moved
    new_page = int(selected_time * fps) // st.session_state.frames_per_page
    if new_page != current_page:
        st.session_state.current_page = new_page
        st.experimental_rerun()

def display_frames(frames, start_idx, end_idx):
    """Display frames with selection checkboxes."""
    grid = st.columns(3)
    for i, frame in enumerate(frames):
        col = grid[i % 3]
        frame_number = start_idx + i + 1
        is_selected = frame_number in st.session_state.selected_frames

        with col:
            st.image(frame, use_column_width=True, caption=f"Frame {frame_number}")
            if st.checkbox(
                "Select", 
                key=f"select_{frame_number}", 
                value=is_selected,
                label_visibility="collapsed"
            ):
                st.session_state.selected_frames.add(frame_number)
            else:
                st.session_state.selected_frames.discard(frame_number)

            # Highlight selected frames
            if is_selected:
                st.markdown(
                    f"<style>div[data-testid='stImage']:has(> img[alt='Frame {frame_number}']) {{border: 2px solid #FF4B4B;}}</style>",
                    unsafe_allow_html=True
                )

def encode_frame_to_base64(frame_rgb: np.ndarray) -> str:
    """Encode an RGB frame to base64."""
    _, buffer = cv2.imencode(".png", cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR))
    return base64.b64encode(buffer).decode("utf-8")

def submit_to_worker(prev_img: np.ndarray, next_img: np.ndarray, separation: int, task_id: str) -> bool:
    """Submit frames with separation parameter (silent mode)."""
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)
        task_data = {
            "image1": encode_frame_to_base64(prev_img),
            "image2": encode_frame_to_base64(next_img),
            "num_frames": separation,
            "task_id": task_id
        }
        r.rpush(TASK_QUEUE, json.dumps(task_data))
        return True
    except Exception:
        return False

def get_worker_result(task_id: str, timeout: int = 60) -> list:
    """Retrieve processed frames from Redis."""
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)
    try:
        _, result_json = r.blpop(RESULT_QUEUE, timeout=timeout)
        if result_json:
            result = json.loads(result_json)
            if result["task_id"] == task_id: 
                return result["interpolated_frames"]
    except Exception as e:
        st.error(f"Result retrieval failed: {str(e)}")
    return None

def get_video_codec(video_path):
    """Detect the video codec of the input file"""
    cap = cv2.VideoCapture(video_path)
    fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
    codec = chr(fourcc & 0xff) + chr((fourcc >> 8) & 0xff) + chr((fourcc >> 16) & 0xff) + chr((fourcc >> 24) & 0xff)
    cap.release()
    return codec

def create_video_from_frames(frames, output_path, input_video_path):
    """Create an HTML5-compatible video with minimal logging."""
    cap = cv2.VideoCapture(input_video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    try:
        # Save frames as temporary PNG files
        temp_dir = tempfile.mkdtemp()
        frame_paths = []
        for i, frame in enumerate(frames):
            frame_path = os.path.join(temp_dir, f"frame_{i:04d}.png")
            cv2.imwrite(frame_path, cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
            frame_paths.append(frame_path)

        # FFmpeg command (silent unless error occurs)
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-framerate", str(fps),
            "-i", os.path.join(temp_dir, "frame_%04d.png"),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-vf", f"scale={width}:{height}",
            "-movflags", "+faststart",
            output_path
        ]
        subprocess.run(cmd, check=True)
        return True

    except subprocess.CalledProcessError as e:
        st.error(f"Video creation failed: {e.stderr.decode('utf-8')}")
        return False
    finally:
        # Clean up temporary files
        for frame_path in frame_paths:
            if os.path.exists(frame_path):
                os.remove(frame_path)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)

def reencode_video(input_path, output_path):
    """Re-encode video using FFmpeg with strict H.264 settings."""
    try:
        cmd = [
            "ffmpeg", "-i", input_path,
            "-c:v", "libx264",       # Force H.264
            "-preset", "ultrafast",  # Speed up encoding (adjust if quality is poor)
            "-crf", "18",            # Higher quality (lower = better, 18-28 is typical)
            "-pix_fmt", "yuv420p",   # Mandatory for browser playback
            "-movflags", "+faststart",  # Enable streaming
            "-an",                   # Remove audio (if any)
            output_path
        ]
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        st.error(f"FFmpeg re-encoding failed: {str(e)}")
        return False

if uploaded_file is not None:
    # Show file size
    file_size = uploaded_file.size / (1024 * 1024 * 1024)  # Convert to GB
    
    # Create a temporary file to store the uploaded video
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        st.session_state.temp_file_path = tmp_file.name
    
    # Get video information if not already done
    if not st.session_state.video_info:
        with st.spinner('Loading video information...'):
            st.session_state.video_info = get_video_info(st.session_state.temp_file_path)

    # Calculate frame range for current page
    start_idx = st.session_state.current_page * st.session_state.frames_per_page
    end_idx = min(start_idx + st.session_state.frames_per_page, 
                 st.session_state.video_info['total_frames'])
    
    # Extract and display frames for current page
    with st.spinner('Loading frames...'):
        frames = extract_frames(st.session_state.temp_file_path, start_idx, st.session_state.frames_per_page)
    
    # Display navigation controls
    display_navigation_controls(st.session_state.video_info['total_frames'])
    
    # Display frames
    st.subheader("Video Frames")
    display_frames(frames, start_idx, end_idx)
    
    # Display selected frames information at the bottom
    st.markdown("---")
    if st.session_state.selected_frames:
        # Sort the frames for better readability
        sorted_frames = sorted(list(st.session_state.selected_frames))
        st.write(f"Selected Frames ({len(st.session_state.selected_frames)}): {sorted_frames}")
    else:
        st.write("No frames selected")

    if st.button("Run the AI 🚀", key="run_algorithm"):
        if hasattr(st.session_state, 'selected_frames') and st.session_state.selected_frames:
            with st.spinner("Initializing video processing..."):
                # Initialize variables for video reconstruction
                all_frames = []
                cap = cv2.VideoCapture(st.session_state.temp_file_path)
                fps = st.session_state.video_info['fps']
                width = st.session_state.video_info['width']
                height = st.session_state.video_info['height']
                
                # Read all original frames
                original_frames = []
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    original_frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                cap.release()
                
                # Process selected ranges with stqdm
                modified_frames = original_frames.copy()
                sorted_frames = sorted(st.session_state.selected_frames)
                ranges = []
                current_range = [sorted_frames[0]]
                
                for i in range(1, len(sorted_frames)):
                    if sorted_frames[i] == sorted_frames[i-1] + 1:
                        current_range.append(sorted_frames[i])
                    else:
                        ranges.append(current_range)
                        current_range = [sorted_frames[i]]
                ranges.append(current_range)
                
                # Main processing with progress bar
                progress_bar = stqdm(ranges, desc="Processing frame ranges")
                for frame_range in progress_bar:
                    first, last = frame_range[0], frame_range[-1]
                    progress_bar.set_description(f"Processing frames {first}-{last}")
                    
                    prev_frame = first - 1 if first > 1 else None
                    next_frame = last + 1 if last < st.session_state.video_info['total_frames'] else None
                    
                    if prev_frame and next_frame:
                        prev_img = extract_frames(st.session_state.temp_file_path, prev_frame-1, 1)[0]
                        next_img = extract_frames(st.session_state.temp_file_path, next_frame-1, 1)[0]
                        task_id = str(uuid.uuid4())
                        
                        if submit_to_worker(prev_img, next_img, next_frame - prev_frame - 1, task_id):
                            with st.spinner(f"Generating {next_frame - prev_frame - 1} intermediate frames..."):
                                result_frames = get_worker_result(task_id)
                                
                                if result_frames:
                                    for i, frame_b64 in enumerate(result_frames):
                                        frame_idx = first - 1 + i
                                        frame = cv2.imdecode(np.frombuffer(base64.b64decode(frame_b64), np.uint8), cv2.IMREAD_COLOR)
                                        modified_frames[frame_idx] = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Video creation
                with st.spinner("Creating final video..."):
                    if create_video_from_frames(modified_frames, "modified_video.mp4", st.session_state.temp_file_path):
                        st.success("🎉 Processing complete!")
                        try:
                            with open("modified_video.mp4", "rb") as f:
                                video_bytes = f.read()
                                st.video(video_bytes, format="video/mp4")
                                st.success("🎉 Video processing complete!")
                                
                                st.download_button(
                                    label="Download Modified Video",
                                    data=video_bytes,
                                    file_name=f"modified_{uploaded_file.name}",
                                    mime="video/mp4"
                                )
                        except Exception as e:
                            st.error(f"Video display error: {str(e)}")
                    else:
                        st.error("Video creation failed!")
        else:
            st.warning("No frames selected!")
else:
    # Clean up temporary file when no file is uploaded
    if st.session_state.temp_file_path and os.path.exists(st.session_state.temp_file_path):
        os.unlink(st.session_state.temp_file_path)
        st.session_state.temp_file_path = None
        st.session_state.video_info = None
        st.session_state.selected_frames = set()
        st.session_state.current_page = 0

# Add some styling
st.markdown("""
<style>
.stImage {
    cursor: pointer;
    transition: transform 0.2s;
}
.stImage:hover {
    transform: scale(1.05);
}
</style>
""", unsafe_allow_html=True)
