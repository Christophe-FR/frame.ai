# Remove this Flash ⚡🎥

An AI-powered tool to remove flashes from videos by replacing individual frames with interpolated frames.

## Features
- Upload and preview videos
- Select frames affected by flashes
- Replace selected frames with AI-interpolated frames
- Download the modified video

## Prerequisites
- Python 3.8+
- Redis server (for worker communication)
- FFmpeg (for video processing)

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### 1. Start the Redis Server
The worker relies on Redis for task queuing. Ensure Redis is running before starting the worker or the app:
   ```bash
   redis-server
   ```

### 2. Start the Worker
Run the worker script to process frame interpolation tasks:
   ```bash
   python worker.py
   ```

### 3. Run the App
Start the Streamlit app to upload and process videos:
   ```bash
   streamlit run app.py
   ```

### 4. Use the App
1. Upload a video file (MP4, AVI, or MOV).
2. Navigate through frames and select those affected by flashes.
3. Click **Run the AI 🚀** to replace the selected frames.
4. Preview and download the modified video.

## Configuration
- **Redis Host/Port**: Modify `REDIS_HOST` and `REDIS_PORT` in `app.py` if Redis is not running locally.
- **Video Size Limit**: The app supports videos up to 4GB.

## Troubleshooting
- **Worker Not Responding**: Ensure Redis is running and the worker script is active.
- **Video Playback Issues**: Verify FFmpeg is installed and accessible in your PATH.
- **Debugging**: Enable debug logs in `app.py` for detailed output.

## License
MIT