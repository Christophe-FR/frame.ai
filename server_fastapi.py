from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request
import os
import glob
from utils import video_get_frames_filenames
import cv2
import numpy as np
from io import BytesIO
from fastapi.responses import Response
import base64
import time
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Frames Viewer")

# CORS for React frontend
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"])

FRAMES_FOLDER = "frames"
STATIC_FOLDER = "static"
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}

# Mount static files for direct image access
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/{repo_uuid}/frames") # example: http://localhost:8000/2afaa5d5-b243-41d7-a7a8-efa21083d290/frames?start=5&end=10
async def api_video_get_frames_by_index(repo_uuid: str, start: int = 0, end: int = None):
    repo_path = os.path.join(STATIC_FOLDER, repo_uuid)
    frame_paths = video_get_frames_filenames(repo_path)
    return {"frames": frame_paths[start:end + 1]}

@app.get("/{repo_uuid}/frames/count")
async def get_frame_count(repo_uuid: str):
    """Get the total number of frames in a repository."""
    repo_path = os.path.join(STATIC_FOLDER, repo_uuid)
    frame_numbers = video_get_frames_filenames(repo_path)
    return {"total": len(frame_numbers)}

@app.get("/api/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    os.makedirs(FRAMES_FOLDER, exist_ok=True)
    os.makedirs(STATIC_FOLDER, exist_ok=True)
    print(f"🚀 FastAPI server starting on http://localhost:8000")
    print(f"📁 Frames folder: {os.path.abspath(FRAMES_FOLDER)}")
    print(f"📁 Static folder: {os.path.abspath(STATIC_FOLDER)}")
    
    import uvicorn
    uvicorn.run("server_fastapi:app", host="0.0.0.0", port=8000, reload=True) 

    