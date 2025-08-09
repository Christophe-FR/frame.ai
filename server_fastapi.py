import os
import uuid
import glob
import time
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from utils import video_get_frames_list, video_decompose, _video_get_frames_filenames, get_file_modification_time, _extract_numbers_from_frames, video_create_repo
import cv2
import numpy as np
from io import BytesIO
from fastapi.responses import Response
import base64
import asyncio
from typing import List
from pydantic import BaseModel

# Celery imports
try:
    from video_interpolation_server import interpolate_video_frames
    from celery.result import AsyncResult
    from video_interpolation_server import app as celery_app
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    print("⚠️ Celery not available - interpolation endpoints disabled")

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

# Custom static file handler with cache-busting headers
@app.get("/static/{file_path:path}")
async def serve_static_file(file_path: str):
    """Serve static files with no-cache headers to prevent browser caching of updated frames"""
    import os
    full_path = os.path.join(STATIC_FOLDER, file_path)
    
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    # Return file with cache-busting headers
    response = FileResponse(
        path=full_path,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache", 
            "Expires": "0"
        }
    )
    return response

# Keep the mount for other static files (fallback)
# app.mount("/static", StaticFiles(directory=STATIC_FOLDER), name="static")

@app.post("/video_upload")
async def upload_video(file: UploadFile = File(...)):
    request_start = time.time()
    print(f"🚀 Upload request received at {time.strftime('%H:%M:%S')}")
    print(f"📁 File details: name={file.filename}, size={file.size if file.size else 'unknown'}")
    
    try:
        # Generate a new repository using utils function
        repo_uuid, repo_path = video_create_repo()

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

@app.get("/ls/{repo_uuid}/")
async def ls(repo_uuid: str, start: int = 0, end: int = None):
    try:
        repo_path = os.path.join(STATIC_FOLDER, repo_uuid)
        
        # Check if repository directory exists
        if not os.path.exists(repo_path):
            raise HTTPException(status_code=404, detail="Repository not found")
        
        # Define potential file paths
        video_info_filename = os.path.join(repo_path, "video_info.json")
        audio_filename = os.path.join(repo_path, "audio.wav")
        
        # Get frame information (this function should handle missing frames gracefully)
        try:
            frame_numbers, frame_filenames = video_get_frames_list(repo_path, include_filenames=True)
        except Exception as e:
            print(f"⚠️ Error getting frames for {repo_uuid}: {e}")
            # If frames can't be listed, assume no frames yet
            frame_numbers, frame_filenames = [], []
        
        total_frames = len(frame_numbers)
        
        # Apply pagination to frames
        if end is None:
            frame_numbers = frame_numbers[start:]
            frame_filenames = frame_filenames[start:]
        else:
            frame_numbers = frame_numbers[start:end + 1]
            frame_filenames = frame_filenames[start:end + 1]
        
        # Build list of files that actually exist
        existing_files = []
        if os.path.exists(video_info_filename):
            existing_files.append(video_info_filename)
        if os.path.exists(audio_filename):
            existing_files.append(audio_filename)
        
        # Add existing frame files
        existing_files.extend(frame_filenames)
        
        # Get modification times only for files that exist
        modification_times = get_file_modification_time(existing_files)
        
        return {
            "filenames": existing_files, 
            "modification_times": modification_times, 
            "frames": {"numbers": frame_numbers, "total": total_frames}
        }
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        print(f"❌ Error in ls endpoint for {repo_uuid}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")



# Pydantic models for interpolation
class InterpolateRequest(BaseModel):
    target_frames: List[float]

@app.get("/api/health")
async def health():
    return {"status": "ok"}

# =============================================================================
# CELERY INTERPOLATION ENDPOINTS 
# =============================================================================

@app.post("/api/interpolate/{repo_uuid}")
async def start_interpolation(repo_uuid: str, request: InterpolateRequest):
    """Submit video interpolation task for a repository"""
    if not CELERY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Celery service not available")
    
    try:
        # Build repo path
        repo_path = os.path.join(STATIC_FOLDER, repo_uuid)
        
        # Check if repo exists
        if not os.path.exists(repo_path):
            raise HTTPException(status_code=404, detail="Repository not found")
        
        # Submit to Celery
        task = interpolate_video_frames.delay(repo_path, request.target_frames)
        
        return {
            "status": "accepted", 
            "task_id": task.id,
            "repo_uuid": repo_uuid,
            "target_frames": request.target_frames,
            "message": f"Interpolation started for {len(request.target_frames)} frames"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start interpolation: {str(e)}")

@app.get("/api/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    """Get status of interpolation task"""
    if not CELERY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Celery service not available")
    
    try:
        task = AsyncResult(task_id, app=celery_app)
        
        if task.state == 'PENDING':
            return {"status": "pending", "message": "Task queued"}
        elif task.state == 'PROGRESS':
            return {"status": "processing", "progress": task.info}
        elif task.state == 'SUCCESS':
            return {"status": "completed", "result": task.result}
        elif task.state == 'FAILURE':
            return {"status": "failed", "error": str(task.info)}
        else:
            return {"status": task.state}
            
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Task not found: {str(e)}")

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
    uvicorn.run("server_fastapi:app", host="0.0.0.0", port=8500, reload=True)
