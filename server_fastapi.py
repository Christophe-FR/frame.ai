from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request
import os
import glob
from utils import video_get_frames_list, video_get_frames_by_index
import cv2
import numpy as np
from io import BytesIO
from fastapi.responses import Response
import base64

app = FastAPI(title="Frames Viewer")

# CORS for React frontend
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"])

FRAMES_FOLDER = "frames"
UPLOADS_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}

@app.get("/{repo_uuid}/frames/count")
async def get_frame_count(repo_uuid: str):
    """Get the total number of frames in a repository."""
    repo_path = os.path.join(UPLOADS_FOLDER, repo_uuid)
    frame_numbers = video_get_frames_list(repo_path)
    return {"total": len(frame_numbers), "repo_uuid": repo_uuid}

@app.get("/{repo_uuid}/frames")
async def api_video_get_frames_by_index(repo_uuid: str, start: int = 0, end: int = None):
    """Get frames by start and end indices."""
    repo_path = os.path.join(UPLOADS_FOLDER, repo_uuid)
    indices = list(range(start, end + 1))
    frames = video_get_frames_by_index(repo_path, indices)
    frame_data = [f"data:image/jpeg;base64,{base64.b64encode(cv2.imencode('.jpg', cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))[1]).decode()}" for frame in frames]
    return {"frames": frame_data}

@app.get("/api/health")
async def health():
     #Health check endpoint. #
    frames = video_get_frames_list(FRAMES_FOLDER)
    return {"status": "ok", "frames": len(frames)}

if __name__ == "__main__":
    os.makedirs(FRAMES_FOLDER, exist_ok=True)
    os.makedirs(UPLOADS_FOLDER, exist_ok=True)
    print(f"🚀 FastAPI server starting on http://localhost:8000")
    print(f"📁 Frames folder: {os.path.abspath(FRAMES_FOLDER)}")
    print(f"📁 Uploads folder: {os.path.abspath(UPLOADS_FOLDER)}")
    
    import uvicorn
    uvicorn.run("server_fastapi:app", host="0.0.0.0", port=8000, reload=True) 