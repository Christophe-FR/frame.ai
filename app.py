import streamlit as st
import pandas as pd
import numpy as np
import cv2
from PIL import Image
import io
import tempfile
import os

# Set page config
st.set_page_config(
    page_title="Video Frame Selector",
    page_icon="🎥",
    layout="wide"
)

# Initialize session state for selected frames
if 'selected_frames' not in st.session_state:
    st.session_state.selected_frames = set()
if 'video_frames' not in st.session_state:
    st.session_state.video_frames = []

# Add a title
st.title("Video Frame Selector 🎥")

# File uploader
uploaded_file = st.file_uploader("Choose a video file", type=['mp4', 'avi', 'mov'])

def extract_frames(video_path, max_frames=30):
    """Extract frames from video file"""
    frames = []
    cap = cv2.VideoCapture(video_path)
    
    # Get total frames
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames == 0:
        return frames
    
    # Calculate frame interval to get max_frames
    interval = max(1, total_frames // max_frames)
    
    frame_count = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        if frame_count % interval == 0:
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            # Resize frame to smaller size for display
            height, width = frame_rgb.shape[:2]
            new_width = 300
            new_height = int(height * (new_width / width))
            frame_resized = cv2.resize(frame_rgb, (new_width, new_height))
            frames.append(frame_resized)
            
        frame_count += 1
        
        if len(frames) >= max_frames:
            break
            
    cap.release()
    return frames

def display_frames(frames):
    """Display frames in a grid with selection capability"""
    if not frames:
        return
    
    # Calculate grid dimensions
    n_cols = 3
    n_rows = (len(frames) + n_cols - 1) // n_cols
    
    for row in range(n_rows):
        cols = st.columns(n_cols)
        for col in range(n_cols):
            idx = row * n_cols + col
            if idx < len(frames):
                with cols[col]:
                    # Convert numpy array to PIL Image
                    frame_pil = Image.fromarray(frames[idx])
                    
                    # Create a clickable container
                    container = st.container()
                    with container:
                        st.image(frame_pil, use_column_width=True)
                        
                        # Add frame number
                        st.text(f"Frame {idx + 1}")
                        
                        # Add checkbox for selection
                        is_selected = st.checkbox(
                            "Select",
                            key=f"frame_{idx}",
                            value=idx in st.session_state.selected_frames
                        )
                        
                        if is_selected:
                            st.session_state.selected_frames.add(idx)
                        else:
                            st.session_state.selected_frames.discard(idx)

if uploaded_file is not None:
    # Create a temporary file to store the uploaded video
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        tmp_file_path = tmp_file.name
    
    # Extract frames if not already done
    if not st.session_state.video_frames:
        with st.spinner('Processing video...'):
            st.session_state.video_frames = extract_frames(tmp_file_path)
    
    # Display frames
    st.subheader("Video Frames")
    display_frames(st.session_state.video_frames)
    
    # Display selected frames count
    st.write(f"Selected frames: {len(st.session_state.selected_frames)}")
    
    # Clean up temporary file
    os.unlink(tmp_file_path)

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