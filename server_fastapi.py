from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi import Request
import os
import glob
from utils import get_frames_video_list

app = FastAPI(title="Frames Viewer")

# CORS for React frontend
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"])

FRAMES_FOLDER = "frames"
UPLOADS_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}

@app.get("/uploads/{repo_uuid}/{filename}")
@app.head("/uploads/{repo_uuid}/{filename}")
async def get_frame_image(repo_uuid: str, filename: str, request: Request):
    """Serve frame images from uploads directory."""
    file_path = os.path.join(UPLOADS_FOLDER, repo_uuid, filename)
    if not os.path.exists(file_path):
        raise HTTPException(404, "Frame not found")
    return FileResponse(file_path)

@app.get("/api/{repo_uuid}/frames")
async def api_get_frames_video_list(repo_uuid: str):
     #Get frames from a specific repository. #
    repo_path = os.path.join(UPLOADS_FOLDER, repo_uuid)
    frames = get_frames_video_list(repo_path)
    if not frames:
        raise HTTPException(404, "Repository not found")
    # Convert full paths to just filenames for frontend
    frame_names = [os.path.basename(f) for f in sorted(frames)]
    return {"frames": frame_names, "total": len(frame_names), "repo_uuid": repo_uuid}

@app.get("/api/health")
async def health():
     #Health check endpoint. #
    frames = get_frames_video_list(FRAMES_FOLDER)
    return {"status": "ok", "frames": len(frames)}

if __name__ == "__main__":
    os.makedirs(FRAMES_FOLDER, exist_ok=True)
    os.makedirs(UPLOADS_FOLDER, exist_ok=True)
    print(f"🚀 FastAPI server starting on http://localhost:8000")
    print(f"📁 Frames folder: {os.path.abspath(FRAMES_FOLDER)}")
    print(f"📁 Uploads folder: {os.path.abspath(UPLOADS_FOLDER)}")
    print(f"🔗 Direct access: http://localhost:8000/uploads/<uuid>/frame_*.jpg")
    
    import uvicorn
    uvicorn.run("server_fastapi:app", host="0.0.0.0", port=8000, reload=True) 