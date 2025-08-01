import os
import uuid
import glob
import time
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from utils import video_decompose, video_get_frames_filenames, get_file_modification_time, extract_numbers_from_filenames
import cv2
import numpy as np
from io import BytesIO
from fastapi.responses import Response
import base64
import asyncio

app = FastAPI(title="Frames Viewer")

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3500"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

FRAMES_FOLDER = "frames"
STATIC_FOLDER = "static"
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}

# Mount static files for direct image access
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.post("/upload_video")
async def upload_video(file: UploadFile = File(...)):
    request_start = time.time()
    print(f"🚀 Upload request received at {time.strftime('%H:%M:%S')}")
    print(f"📁 File details: name={file.filename}, size={file.size if file.size else 'unknown'}")
    
    try:
        # Generate a new UUID for this upload
        repo_uuid = str(uuid.uuid4())
        repo_path = os.path.join(STATIC_FOLDER, repo_uuid)
        os.makedirs(repo_path, exist_ok=True)

        print(f"📁 Created repository: {repo_path}")
        print(f"🎯 Generated UUID: {repo_uuid}")

        # Handle file extension
        if file.filename:
            video_filename = "input_video" + os.path.splitext(file.filename)[-1]
        else:
            video_filename = "input_video.mp4"  # Default extension
        
        video_path = os.path.join(repo_path, video_filename)
        print(f"🎬 Video will be saved as: {video_path}")
        
        # Read the entire file content first
        print(f"📤 Starting file content reading...")
        read_start = time.time()
        content = await file.read()
        read_time = time.time() - read_start
        file_size = len(content)
        print(f"✅ File content read: {file_size / 1024 / 1024:.1f} MB in {read_time:.2f}s")
        print(f"📊 Read speed: {file_size / 1024 / 1024 / read_time:.1f} MB/s")
        
        # Return response immediately
        response_start = time.time()
        print(f"🚀 Preparing immediate response for {repo_uuid}")
        
        response_data = {"uuid": repo_uuid}
        print(f"📄 Response data: {response_data}")
        
        # Start file writing and processing in background
        def write_and_process():
            try:
                print(f"💾 Starting background file write for {repo_uuid}...")
                write_start = time.time()
                
                # Write file to disk
                with open(video_path, "wb") as f:
                    f.write(content)
                
                write_time = time.time() - write_start
                file_size_mb = file_size / 1024 / 1024
                print(f"✅ File written successfully!")
                print(f"   📏 Size: {file_size_mb:.1f} MB")
                print(f"   ⏱️  Write time: {write_time:.1f}s")
                print(f"   🚀 Write speed: {file_size_mb / write_time:.1f} MB/s")
                
                # Start video decomposition
                print(f"🎬 Starting video decomposition for {repo_uuid}...")
                process_start = time.time()
                
                # Check if file exists and has content
                if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
                    print(f"📁 Video file verified: {os.path.getsize(video_path) / 1024 / 1024:.1f} MB")
                    video_decompose(video_path, repo_path)
                    process_time = time.time() - process_start
                    print(f"✅ Video decomposition completed for {repo_uuid} in {process_time:.1f}s")
                else:
                    print(f"❌ Video file is empty or doesn't exist for {repo_uuid}")
            except Exception as e:
                print(f"❌ Error in background processing for {repo_uuid}: {e}")
        
        # Run in background thread
        import threading
        thread = threading.Thread(target=write_and_process)
        thread.daemon = True
        thread.start()
        
        print(f"🔄 Background processing started for {repo_uuid}")
        
        # Calculate total request time
        total_time = time.time() - request_start
        response_time = time.time() - response_start
        print(f"📤 Sending response to client")
        print(f"   ⏱️  Total request time: {total_time:.2f}s")
        print(f"   ⏱️  Response preparation time: {response_time:.2f}s")
        print(f"   🎯 Response: {response_data}")
        
        return response_data
    except Exception as e:
        total_time = time.time() - request_start
        print(f"❌ Error in upload_video after {total_time:.2f}s: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/get_upload_path")
async def get_upload_path():
    """Get a file path for direct upload."""
    # Generate a new UUID for this upload
    repo_uuid = str(uuid.uuid4())
    repo_path = os.path.join(STATIC_FOLDER, repo_uuid)
    os.makedirs(repo_path, exist_ok=True)
    
    # Return the path where the frontend should write the file
    return {
        "uuid": repo_uuid,
        "upload_path": repo_path,
        "video_path": os.path.join(repo_path, "input_video.mp4")
    }

@app.post("/start_processing/{repo_uuid}")
async def start_processing(repo_uuid: str):
    """Start video processing for a file that was uploaded directly."""
    repo_path = os.path.join(STATIC_FOLDER, repo_uuid)
    video_path = os.path.join(repo_path, "input_video.mp4")
    
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file not found")
    
    # Start video decomposition in background
    def process_video():
        try:
            # Check if file exists and has content
            if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
                video_decompose(video_path, repo_path)
                print(f"✅ Video decomposition completed for {repo_uuid}")
            else:
                print(f"❌ Video file is empty or doesn't exist for {repo_uuid}")
        except Exception as e:
            print(f"❌ Video decomposition failed for {repo_uuid}: {e}")
    
    # Run in background thread
    import threading
    thread = threading.Thread(target=process_video)
    thread.daemon = True
    thread.start()
    
    return {"uuid": repo_uuid, "status": "processing_started"}


@app.get("/{repo_uuid}/frames") # example: http://localhost:8000/2afaa5d5-b243-41d7-a7a8-efa21083d290/frames?start=5&end=10
async def api_video_get_frames_filenames(repo_uuid: str, start: int = 0, end: int = None):
    try:
        repo_path = os.path.join(STATIC_FOLDER, repo_uuid)
        
        if not os.path.exists(repo_path):
            raise HTTPException(status_code=404, detail="Repository not found")
        
        frame_paths = video_get_frames_filenames(repo_path)
        
        # First extract the relevant indices
        if end is None:
            relevant_paths = frame_paths[start:]
        else:
            relevant_paths = frame_paths[start:end + 1]
        
        # Then convert the relevant paths to just filenames for frontend
        frames = [os.path.basename(frame_path) for frame_path in relevant_paths]

        frame_numbers = extract_numbers_from_filenames(relevant_paths)

        return {"frames": frames, "frame_numbers": frame_numbers, "count":len(relevant_paths), "total":len(frame_paths)}
    
    except Exception as e:
        print(f"Error in frames endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/{repo_uuid}/dir_mod_time")
async def get_directory_modification_time(repo_uuid: str):
    """Get the directory modification time to detect file changes."""
    try:
        repo_path = os.path.join(STATIC_FOLDER, repo_uuid)
        
        if not os.path.exists(repo_path):
            raise HTTPException(status_code=404, detail="Repository not found")
        
        dir_mod_time = os.path.getmtime(repo_path)
        
        # Debug: Get current file count and list some files
        import glob
        frame_pattern = os.path.join(repo_path, "frame_*.jpg")
        frames = glob.glob(frame_pattern)
        
        print(f"🔍 Dir mod time check for {repo_uuid}:")
        print(f"   📁 Directory: {repo_path}")
        print(f"   ⏰ Mod time: {dir_mod_time} ({dir_mod_time})")
        print(f"   📊 Frame count: {len(frames)}")
        if len(frames) > 0:
            print(f"   📄 Sample files: {[os.path.basename(f) for f in frames[:3]]}")
        
        return {"dir_mod_time": dir_mod_time}
    
    except Exception as e:
        print(f"Error in dir_mod_time endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))





@app.get("/api/health")
async def health():
    return {"status": "ok"}

@app.get("/{repo_uuid}/status")
async def get_processing_status(repo_uuid: str):
    """Check if video processing is complete."""
    repo_path = os.path.join(STATIC_FOLDER, repo_uuid)
    
    if not os.path.exists(repo_path):
        print(f"❌ Status check failed: Repository {repo_uuid} not found")
        raise HTTPException(status_code=404, detail="Repository not found")
    
    # Check if processing is complete by looking for frames
    frame_pattern = os.path.join(repo_path, "frame_*.jpg")
    frames = glob.glob(frame_pattern)
    
    # Check if metadata exists
    metadata_path = os.path.join(repo_path, "video_info.json")
    has_metadata = os.path.exists(metadata_path)
    
    # Check if video file exists
    video_path = os.path.join(repo_path, "input_video.mp4")
    has_video = os.path.exists(video_path)
    
    status_data = {
        "uuid": repo_uuid,
        "processing_complete": len(frames) > 0 and has_metadata,
        "frame_count": len(frames),
        "has_metadata": has_metadata,
        "has_video": has_video
    }
    
    if status_data["processing_complete"]:
        print(f"✅ Status: Processing complete for {repo_uuid} ({len(frames)} frames)")
    else:
        print(f"⏳ Status: Still processing {repo_uuid} ({len(frames)} frames, metadata: {has_metadata})")
    
    return status_data

if __name__ == "__main__":
    os.makedirs(FRAMES_FOLDER, exist_ok=True)
    os.makedirs(STATIC_FOLDER, exist_ok=True)
    print(f"🚀 FastAPI server starting on http://localhost:8500")
    print(f"📁 Frames folder: {os.path.abspath(FRAMES_FOLDER)}")
    print(f"📁 Static folder: {os.path.abspath(STATIC_FOLDER)}")
    
    import uvicorn
    uvicorn.run("server_fastapi:app", host="0.0.0.0", port=8500, reload=False) 

    