import streamlit as st
import pandas as pd
import numpy as np
import cv2
from PIL import Image
import io
import tempfile
import os
import math
import subprocess
from stqdm import stqdm
from frame_interpolation_client import FrameInterpolationClient

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
if 'interpolation_client' not in st.session_state:
    st.session_state.interpolation_client = None

# Add a title
st.title("Remove this Flash ⚡🎥")

st.write("The AI solution to remove flash from videos and replace individual frames in videos.")

# File uploader with size limit message
uploaded_file = st.file_uploader("Upload a video file (max 4GB)", type=['mp4', 'avi', 'mov'])

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

def get_video_codec(video_path):
    """Detect the video codec of the input file"""
    cap = cv2.VideoCapture(video_path)
    fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
    codec = chr(fourcc & 0xff) + chr((fourcc >> 8) & 0xff) + chr((fourcc >> 16) & 0xff) + chr((fourcc >> 24) & 0xff)
    cap.release()
    return codec

def create_video_from_frames(frames, output_path, input_video_path, start_frame, end_frame):
    """Replace frames in the input video with the provided frames while preserving original quality, format, and audio."""
    try:
        # Step 1: Get original video properties
        cap = cv2.VideoCapture(input_video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        original_codec = get_video_codec(input_video_path)
        
        # Get input file extension
        input_ext = os.path.splitext(input_video_path)[1].lower()
        
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

        # Create a temporary directory for intermediate files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Step 2: Save frames as lossless PNG files
            frame_files = []
            for i, frame in enumerate(original_frames):
                frame_path = os.path.join(temp_dir, f"frame_{i:06d}.png")
                cv2.imwrite(frame_path, cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
                frame_files.append(frame_path)

            # Step 3: Create a lossless intermediate video
            temp_output = os.path.join(temp_dir, "temp_video.mkv")
            cmd = [
                "ffmpeg", "-y",
                "-framerate", str(fps),
                "-i", os.path.join(temp_dir, "frame_%06d.png"),
                "-c:v", "ffv1",  # Lossless codec
                "-pix_fmt", "yuv420p",
                temp_output
            ]
            subprocess.run(cmd, check=True)

            # Step 4: Re-encode to final format while preserving quality, original container, and audio
            if input_ext == '.avi':
                # For AVI files, use FFV1 codec which is well-supported in AVI containers
                cmd = [
                    "ffmpeg", "-y", "-i", temp_output,
                    "-i", input_video_path,  # Add original video as second input for audio
                    "-c:v", "ffv1",  # Lossless codec
                    "-c:a", "copy",  # Copy audio without re-encoding
                    "-pix_fmt", "yuv420p",
                    "-f", "avi",  # Force AVI container
                    output_path
                ]
            else:
                # For other formats (MP4, MOV), use H.264 with lossless settings
                cmd = [
                    "ffmpeg", "-y", "-i", temp_output,
                    "-i", input_video_path,  # Add original video as second input for audio
                    "-c:v", "libx264",  # H.264 codec
                    "-c:a", "copy",  # Copy audio without re-encoding
                    "-preset", "veryslow",  # Best compression
                    "-crf", "0",  # Lossless
                    "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart",
                    output_path
                ]
            subprocess.run(cmd, check=True)

        if os.path.exists(output_path):
            st.write(f"🔍 Debug: Successfully created output video at {output_path}")
            return True
        else:
            st.error("🔍 Debug: Output video not created!")
            return False

    except Exception as e:
        st.error(f"🔍 Debug: Video frame replacement failed: {str(e)}")
        return False

def reencode_video(input_path, output_path):
    """Re-encode video using FFmpeg with lossless settings while preserving audio."""
    try:
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-c:v", "libx264",  # H.264 codec
            "-c:a", "copy",  # Copy audio without re-encoding
            "-preset", "veryslow",  # Best compression
            "-crf", "0",  # Lossless
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            output_path
        ]
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        st.error(f"FFmpeg re-encoding failed: {str(e)}")
        return False

def process_selected_frames(video_path, selected_frames):
    """Process selected frames using frame interpolation."""
    if not selected_frames:
        st.warning("No frames selected. Please select frames to process.")
        return

    # Initialize interpolation client if not already done
    if st.session_state.interpolation_client is None:
        st.session_state.interpolation_client = FrameInterpolationClient()

    # Get input file extension
    input_ext = os.path.splitext(video_path)[1].lower()

    # Sort selected frames
    sorted_frames = sorted(selected_frames)
    
    # Create a temporary directory for processed frames
    with tempfile.TemporaryDirectory() as temp_dir:
        # Initialize variables for video reconstruction
        cap = cv2.VideoCapture(video_path)
        original_frames = []
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            original_frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        cap.release()

        # Process all selected ranges first
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
                # Extract frames
                cap = cv2.VideoCapture(video_path)
                cap.set(cv2.CAP_PROP_POS_FRAMES, prev_frame - 1)
                _, frame1 = cap.read()
                cap.set(cv2.CAP_PROP_POS_FRAMES, next_frame - 1)
                _, frame2 = cap.read()
                cap.release()
                
                # Convert to RGB
                frame1_rgb = cv2.cvtColor(frame1, cv2.COLOR_BGR2RGB)
                frame2_rgb = cv2.cvtColor(frame2, cv2.COLOR_BGR2RGB)
                
                try:
                    # Process frames using interpolation client
                    interpolated_frames = st.session_state.interpolation_client.process_frames(
                        frame1_rgb, frame2_rgb, num_frames=next_frame - prev_frame - 1
                    )
                    
                    # Replace frames in the original video
                    replace_start = first - 1
                    replace_end = last - 1
                    
                    for i in range(len(interpolated_frames)):
                        pos = replace_start + i
                        if pos < len(original_frames):
                            original_frames[pos] = interpolated_frames[i]
                            
                except Exception as e:
                    st.error(f"Error processing frames {first}-{last}: {e}")
                    continue

        # Create output video path with the same extension as input
        output_path = os.path.join(temp_dir, f"processed_video{input_ext}")
        
        # Create video from processed frames
        if create_video_from_frames(
            original_frames,
            output_path,
            video_path,
            0,
            len(original_frames) - 1
        ):
            # For browser preview, we need to create an MP4 version
            preview_path = os.path.join(temp_dir, "preview.mp4")
            if reencode_video(output_path, preview_path):
                # Display video preview
                st.success("Video processing completed successfully!")
                with open(preview_path, "rb") as f:
                    video_bytes = f.read()
                    st.video(video_bytes, format="video/mp4")
                
                # Display download button with original format
                with open(output_path, "rb") as f:
                    download_bytes = f.read()
                    st.download_button(
                        label="Download Processed Video",
                        data=download_bytes,
                        file_name=f"processed_video{input_ext}",
                        mime=f"video/{input_ext[1:]}"  # Remove the dot from extension
                    )
            else:
                st.error("Failed to create video preview")
        else:
            st.error("Failed to create processed video")

# Main application logic
if uploaded_file is not None:
    # Show file size
    file_size = uploaded_file.size / (1024 * 1024 * 1024)  # Convert to GB
    
    # Get the original file extension
    original_ext = os.path.splitext(uploaded_file.name)[1].lower()
    
    # Create a temporary file to store the uploaded video with original extension
    with tempfile.NamedTemporaryFile(delete=False, suffix=original_ext) as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        st.session_state.temp_file_path = tmp_file.name
    
    # Get video information if not already done
    if not st.session_state.video_info:
        with st.spinner('Loading video information...'):
            st.session_state.video_info = get_video_info(st.session_state.temp_file_path)
            
        # Display video information
        st.write(f"ℹ️ Resolution: {st.session_state.video_info['width']}x{st.session_state.video_info['height']}, FPS: {st.session_state.video_info['fps']}")

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
        process_selected_frames(st.session_state.temp_file_path, st.session_state.selected_frames)
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
