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
    page_title="Remove this Flash",
    page_icon="⚡",
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
st.title("Remove this Flash ⚡🎥")

st.write("The AI solution to remove flash from videos and replace individual frames in videos.")

# File uploader with size limit message
uploaded_file = st.file_uploader("Upload a video file (max 4GB)", type=['mp4', 'avi', 'mov'])

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

def create_video_from_frames(frames, output_path, input_video_path, start_frame, end_frame):
    """Replace frames in the input video with the provided frames and re-encode for browser compatibility."""
    try:
        # Step 1: Replace frames and save a temporary video
        temp_output = "temp_video.mp4"
        
        # Read the original video and extract all frames
        cap = cv2.VideoCapture(input_video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # Read all frames from the original video
        original_frames = []
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            original_frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        cap.release()

        # Replace the target frames with the new frames
        for i, frame in enumerate(frames):
            if start_frame + i < len(original_frames):
                original_frames[start_frame + i] = frame
            else:
                st.warning(f"🔍 Debug: Frame index {start_frame + i} is out of bounds")

        # Write the updated frames to a temporary video (using mp4v codec)
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        temp_writer = cv2.VideoWriter(temp_output, fourcc, fps, (width, height))
        for frame in original_frames:
            temp_writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
        temp_writer.release()

        # Step 2: Re-encode the temporary video for browser compatibility
        cmd = [
            "ffmpeg", "-y", "-i", temp_output,
            "-c:v", "libx264",       # H.264 codec
            "-preset", "fast",       # Balance between speed and compression
            "-crf", "23",            # Quality (lower = better, 18-28 is typical)
            "-pix_fmt", "yuv420p",   # Required for browser playback
            "-movflags", "+faststart",  # Enable streaming
            "-c:a", "aac",           # Add silent audio track (required by some browsers)
            "-ar", "44100",          # Audio sample rate
            "-f", "mp4",             # Force MP4 container
            output_path
        ]

        # Execute the command
        subprocess.run(cmd, check=True)

        # Debug: Confirm the output video exists
        if os.path.exists(output_path):
            st.write(f"🔍 Debug: Successfully created output video at {output_path}")
            return True
        else:
            st.error("🔍 Debug: Output video not created!")
            return False

    except Exception as e:
        st.error(f"🔍 Debug: Video frame replacement failed: {str(e)}")
        return False
    finally:
        # Clean up temporary files
        if os.path.exists(temp_output):
            os.remove(temp_output)

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
                cap = cv2.VideoCapture(st.session_state.temp_file_path)
                original_frames = []
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    original_frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                cap.release()

                # Process all selected ranges first
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

                # Process all ranges before creating final video
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
                            result_frames = get_worker_result(task_id)
                            
                            if result_frames:
                                interpolated_frames = [
                                    cv2.cvtColor(
                                        cv2.imdecode(np.frombuffer(base64.b64decode(frame_b64), np.uint8), cv2.IMREAD_COLOR),
                                        cv2.COLOR_BGR2RGB
                                    )
                                    for frame_b64 in result_frames
                                ]

                                replace_start = first - 1
                                replace_end = last - 1

                                for i in range(len(interpolated_frames)):
                                    pos = replace_start + i
                                    if pos < len(original_frames):
                                        original_frames[pos] = interpolated_frames[i]

                # Create single final video after all replacements
                if create_video_from_frames(
                    original_frames,
                    "modified_video.mp4",
                    st.session_state.temp_file_path,
                    0,
                    len(original_frames) - 1
                ):
                    with open("modified_video.mp4", "rb") as f:
                        video_bytes = f.read()
                        st.video(video_bytes, format="video/mp4")
                        
                        st.download_button(
                            label="Download Modified Video",
                            data=video_bytes,
                            file_name=f"modified_{uploaded_file.name}",
                            mime="video/mp4"
                        )
                else:
                    st.error("Video processing failed")
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
