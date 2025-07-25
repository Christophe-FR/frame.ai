from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import glob

app = FastAPI(title="Frames Viewer")

# CORS for React frontend
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"])

FRAMES_FOLDER = "frames"
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}

def get_frames():
    """Get list of frame files."""
    if not os.path.exists(FRAMES_FOLDER):
        return []
    
    frames = []
    for ext in ALLOWED_EXTENSIONS:
        frames.extend(glob.glob(os.path.join(FRAMES_FOLDER, f"*{ext}")))
    
    return [{"name": os.path.basename(f), "size": os.path.getsize(f)} for f in sorted(frames)]

@app.get("/api/frames")
async def list_frames():
    """Get all frames."""
    frames = get_frames()
    return {"frames": frames, "total": len(frames)}

@app.get("/api/frames/{filename}")
async def get_frame(filename: str):
    """Serve frame image."""
    frame_path = os.path.join(FRAMES_FOLDER, filename)
    if not os.path.exists(frame_path):
        raise HTTPException(404, "Frame not found")
    return FileResponse(frame_path)

@app.get("/api/health")
async def health():
    """Health check."""
    return {"status": "ok", "frames": len(get_frames())}

if __name__ == "__main__":
    os.makedirs(FRAMES_FOLDER, exist_ok=True)
    print(f"🚀 FastAPI server starting on http://localhost:8000")
    print(f"📁 Frames folder: {os.path.abspath(FRAMES_FOLDER)}")
    
    import uvicorn
    uvicorn.run("server_fastapi:app", host="0.0.0.0", port=8000, reload=True) 