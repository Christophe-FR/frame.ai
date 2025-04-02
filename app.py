import streamlit as st
import pandas as pd
import numpy as np
import cv2
from PIL import Image
import io
import tempfile
import os
import math

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
    """Extract frames from video file without skipping"""
    frames = []
    cap = cv2.VideoCapture(video_path)
    
    # Set initial frame position
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    
    # Create a progress bar
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    frame_count = 0
    while frame_count < num_frames and cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        # Convert BGR to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        # Resize frame to smaller size for display
        height, width = frame_rgb.shape[:2]
        new_width = 300
        new_height = int(height * (new_width / width))
        frame_resized = cv2.resize(frame_rgb, (new_width, new_height))
        frames.append(frame_resized)
        
        # Update progress
        progress = (frame_count + 1) / num_frames
        progress_bar.progress(progress)
        status_text.text(f"Loading frame {frame_count + 1} of {num_frames}")
            
        frame_count += 1
            
    cap.release()
    
    # Clear progress indicators
    progress_bar.empty()
    status_text.empty()
    
    return frames

def display_frames(frames, start_idx, end_idx):
    """Display frames in a grid with selection capability"""
    if not frames:
        return
    
    # Calculate grid dimensions
    n_cols = 3
    n_rows = 3  # Fixed 3x3 grid
    
    for row in range(n_rows):
        cols = st.columns(n_cols)
        for col in range(n_cols):
            # Calculate the frame index relative to the current page
            frame_idx = row * n_cols + col
            if frame_idx < len(frames):
                with cols[col]:
                    # Convert numpy array to PIL Image
                    frame_pil = Image.fromarray(frames[frame_idx])
                    
                    # Create a clickable container
                    container = st.container()
                    with container:
                        st.image(frame_pil, use_column_width=True)
                        
                        # Add frame number (using the actual frame number from start_idx)
                        actual_frame_number = start_idx + frame_idx
                        st.text(f"Frame {actual_frame_number + 1}")
                        
                        # Add checkbox for selection
                        is_selected = st.checkbox(
                            "Select",
                            key=f"frame_{actual_frame_number}",
                            value=actual_frame_number in st.session_state.selected_frames
                        )
                        
                        if is_selected:
                            st.session_state.selected_frames.add(actual_frame_number)
                        else:
                            st.session_state.selected_frames.discard(actual_frame_number)

def display_navigation_controls(total_frames):
    """Display navigation controls for frame pages"""
    total_pages = math.ceil(total_frames / st.session_state.frames_per_page)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        if st.button("Previous Page", disabled=st.session_state.current_page == 0):
            st.session_state.current_page -= 1
    
    with col2:
        st.write(f"Page {st.session_state.current_page + 1} of {total_pages}")
        st.write(f"Total Frames: {total_frames}")
        st.write(f"Selected Frames: {len(st.session_state.selected_frames)}")
        st.write(f"Frames per page: {st.session_state.frames_per_page}")
    
    with col3:
        if st.button("Next Page", disabled=st.session_state.current_page >= total_pages - 1):
            st.session_state.current_page += 1

if uploaded_file is not None:
    # Show file size
    file_size = uploaded_file.size / (1024 * 1024 * 1024)  # Convert to GB
    st.write(f"File size: {file_size:.2f} GB")
    
    # Create a temporary file to store the uploaded video
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        st.session_state.temp_file_path = tmp_file.name
    
    # Get video information if not already done
    if not st.session_state.video_info:
        with st.spinner('Loading video information...'):
            st.session_state.video_info = get_video_info(st.session_state.temp_file_path)
            st.write("Video Info:")
            st.write(f"- Total Frames: {st.session_state.video_info['total_frames']}")
            st.write(f"- FPS: {st.session_state.video_info['fps']}")
            st.write(f"- Duration: {st.session_state.video_info['duration']:.2f} seconds")
            st.write(f"- Resolution: {st.session_state.video_info['width']}x{st.session_state.video_info['height']}")
    
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