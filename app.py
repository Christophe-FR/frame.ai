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
        frames.append(frame_rgb)
        
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

def display_navigation_controls(total_frames):
    """Display navigation controls for frame pages"""
    total_pages = math.ceil(total_frames / st.session_state.frames_per_page)
    fps = st.session_state.video_info['fps']
    duration = st.session_state.video_info['duration']
    
    # Add timestamp slider with navigation buttons
    st.subheader("Video Timeline ⏱️")
    
    # Calculate current time based on page
    current_time = (st.session_state.current_page * st.session_state.frames_per_page) / fps
    
    # First display the slider
    selected_time = st.slider(
        "Current Time",
        min_value=0.0,
        max_value=duration,
        value=current_time,
        step=1.0/fps,  # Step by one frame
        format="%.2f seconds",
        key="time_slider"
    )
    
    # Update current page based on selected time
    new_frame = int(selected_time * fps)
    new_page = new_frame // st.session_state.frames_per_page
    if new_page != st.session_state.current_page:
        st.session_state.current_page = new_page
    
    # Display navigation buttons side by side
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Previous Page", key="prev_page", disabled=st.session_state.current_page == 0):
            st.session_state.current_page -= 1
    
    with col2:
        if st.button("Next Page", key="next_page", disabled=st.session_state.current_page >= total_pages - 1):
            st.session_state.current_page += 1

def display_frames(frames, start_idx, end_idx):
    """Display frames in a 3x3 grid with selection capabilities"""
    # Create a 3x3 grid
    for i in range(3):
        cols = st.columns(3)
        for j in range(3):
            frame_idx = start_idx + (i * 3 + j)
            if frame_idx < end_idx:
                with cols[j]:
                    # Convert frame to RGB for display
                    frame = frames[frame_idx]
                    
                    # Create a container for the frame and its label
                    container = st.container()
                    
                    # Display the frame
                    st.image(frame, use_column_width=True)
                    
                    # Add frame number and selection checkbox
                    frame_number = frame_idx + 1
                    is_selected = frame_number in st.session_state.selected_frames
                    
                    # Show frame number and selection status
                    if is_selected:
                        st.markdown(f"<div style='text-align: center; color: #FF4B4B;'><b>Frame {frame_number}</b></div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div style='text-align: center;'><b>Frame {frame_number}</b></div>", unsafe_allow_html=True)
                    
                    # Add checkbox for selection
                    if st.checkbox("Select", key=f"select_{frame_number}", value=is_selected):
                        if frame_number not in st.session_state.selected_frames:
                            st.session_state.selected_frames.add(frame_number)
                    else:
                        if frame_number in st.session_state.selected_frames:
                            st.session_state.selected_frames.discard(frame_number)

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
    
    # Display concise file information
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write(f"File size: {file_size:.2f} GB")
    with col2:
        st.write(f"Total Duration: {st.session_state.video_info['duration']:.2f}s")
    with col3:
        st.write(f"Total Frames: {st.session_state.video_info['total_frames']}")
    
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