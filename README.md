# Frames Viewer

A simple React frontend for viewing frames from a folder with dynamic updates.

## Features

- 📁 **Dynamic Updates**: Automatically refreshes when new frames are added
- 📄 **Multi-page View**: Paginated display of frames
- 🖼️ **Grid Layout**: Responsive grid layout for frame display
- 🔄 **Real-time**: Polls for updates every 2 seconds
- 📱 **Mobile Friendly**: Responsive design

## Setup

### 1. Install Dependencies

**Backend (Python):**
```bash
pip install -r requirements.txt
```

**Frontend (Node.js):**
```bash
npm install
```

### 2. Configure Frames Folder

Edit `server.py` and change the `FRAMES_FOLDER` variable to point to your frames directory:

```python
FRAMES_FOLDER = "frames"  # Change this to your frames folder path
```

### 3. Run the Application

**Start the Flask backend:**
```bash
python server.py
```

**Start the React frontend (in a new terminal):**
```bash
npm start
```

The application will be available at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:5000

## Usage

1. **View Frames**: The app automatically displays all image files from your frames folder
2. **Navigate**: Use the pagination controls to browse through frames
3. **Real-time Updates**: New frames will appear automatically when added to the folder
4. **Responsive**: Works on desktop and mobile devices

## API Endpoints

- `GET /api/frames` - Get list of all frames
- `GET /api/frames/<filename>` - Serve individual frame image
- `GET /api/health` - Health check endpoint

## Supported Image Formats

- JPG/JPEG
- PNG
- BMP
- TIFF

## Development

The React app polls the backend every 2 seconds for updates. You can modify this interval in `src/App.js`:

```javascript
const interval = setInterval(fetchFrames, 2000); // Change 2000 to your desired interval
```

## Troubleshooting

1. **No frames showing**: Check that your frames folder path is correct in `server.py`
2. **Images not loading**: Ensure the frames folder contains supported image formats
3. **CORS errors**: Make sure the Flask-CORS extension is installed and enabled