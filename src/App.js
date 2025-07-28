import React, { useState, useCallback, useEffect, useMemo } from 'react';
import { useParams, useNavigate, Routes, Route } from 'react-router-dom';
import './App.css';

function UploadInterface() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadStatus, setUploadStatus] = useState('');
  const navigate = useNavigate();

  const handleFileSelect = (file) => {
    if (file && file.type.startsWith('video/')) {
      setSelectedFile(file);
      setUploadStatus('');
    } else {
      setUploadStatus('Please select a valid video file.');
      setSelectedFile(null);
    }
  };

  const handleFileInputChange = (e) => {
    const file = e.target.files[0];
    handleFileSelect(file);
  };

  const handleUpload = async (file) => {
    if (!file) return;

    setUploading(true);
    setUploadProgress(0);
    setUploadStatus('Uploading video...');

    const formData = new FormData();
    formData.append('video', file);

    try {
      const response = await fetch('http://localhost:8000/upload', {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        const data = await response.json();
        setUploadStatus('Upload successful! Processing video...');
        setUploadProgress(100);
        
        // Wait a moment for processing to start, then navigate
        setTimeout(() => {
          navigate(`/frames/${data.repo_uuid}`);
        }, 1000);
      } else {
        throw new Error('Upload failed');
      }
    } catch (error) {
      setUploadStatus('Upload failed: ' + error.message);
      setUploadProgress(0);
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    handleFileSelect(file);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  return (
    <div className="upload-container">
      <h1>Remove this Flash ⚡🎥</h1>
      <p className="description">
        Upload a video to remove flash and replace individual frames using AI.
      </p>
      
      <div 
        className="upload-area"
        onDrop={handleDrop}
        onDragOver={handleDragOver}
      >
        <input
          type="file"
          accept="video/*"
          onChange={handleFileInputChange}
          id="file-input"
          style={{ display: 'none' }}
        />
        <label htmlFor="file-input" className="upload-label">
          {selectedFile ? (
            <div>
              <p>Selected: {selectedFile.name}</p>
              <p className="file-info">
                Size: {formatFileSize(selectedFile.size)}
              </p>
            </div>
          ) : (
            <div>
              <p>📁 Drop video file here or click to select</p>
              <p className="upload-hint">Supports MP4, AVI, MOV, and other video formats</p>
            </div>
          )}
        </label>
      </div>

      {selectedFile && (
        <button 
          onClick={() => handleUpload(selectedFile)}
          disabled={uploading}
          className="upload-button"
        >
          {uploading ? 'Uploading...' : 'Upload Video'}
        </button>
      )}

      {uploading && (
        <div className="upload-progress">
          <div className="progress-bar">
            <div 
              className="progress-fill" 
              style={{ width: `${uploadProgress}%` }}
            ></div>
          </div>
          <p>{uploadStatus}</p>
        </div>
      )}

      {uploadStatus && !uploading && (
        <p className="upload-status">{uploadStatus}</p>
      )}
    </div>
  );
}

function formatFileSize(bytes) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function FrameDisplay() {
  const { repoUuid } = useParams();
  const navigate = useNavigate();
  
  const [frames, setFrames] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [totalFrames, setTotalFrames] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [lastUpdate, setLastUpdate] = useState(null);
  
  const framesPerPage = 20;

  // Memoize the frame cache to avoid unnecessary re-renders
  const frameCache = useMemo(() => new Map(), []);

  useEffect(() => {
    if (repoUuid) {
      console.log(`🎬 Loading frames for repo: ${repoUuid}`);
      fetchTotalFrames(repoUuid);
      fetchFramesFromRepo(repoUuid);
    }
  }, [repoUuid, currentPage]); // Only fetch when repoUuid or currentPage changes

  const fetchTotalFrames = async (uuid) => {
    try {
      const response = await fetch(`http://localhost:8000/${uuid}/frames/count`);
      if (response.ok) {
        const data = await response.json();
        setTotalFrames(data.total);
      }
    } catch (err) {
      console.error('Failed to get total frames count:', err);
    }
  };

  const fetchFramesFromRepo = async (uuid, silent = false) => {
    if (!silent) {
      setLoading(true);
      console.log(`🔄 Fetching frames for ${uuid}, page ${currentPage}, start=${(currentPage - 1) * framesPerPage}, end=${(currentPage - 1) * framesPerPage + framesPerPage - 1}`);
    }
    
    try {
      // Calculate the start and end indices for the current page
      const start = (currentPage - 1) * framesPerPage;
      const end = start + framesPerPage - 1;
      
      // Check cache first
      const cacheKey = `${uuid}-${start}-${end}`;
      if (frameCache.has(cacheKey)) {
        console.log(`📦 Using cached frames for ${cacheKey}`);
        setFrames(frameCache.get(cacheKey));
        setLastUpdate(new Date());
        if (!silent) {
          setLoading(false);
        }
        return;
      }
      
      console.log(`🌐 Making API request to: http://localhost:8000/${uuid}/frames?start=${start}&end=${end}`);
      const response = await fetch(`http://localhost:8000/${uuid}/frames?start=${start}&end=${end}`);
      console.log(`📡 Response status: ${response.status}`);
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error(`❌ API error: ${response.status} - ${errorText}`);
        throw new Error(`Failed to fetch frames: ${response.status} - ${errorText}`);
      }
      
      const data = await response.json();
      console.log(`✅ Received ${data.frames.length} frames`);
      
      // Cache the result
      frameCache.set(cacheKey, data.frames);
      
      // Limit cache size to prevent memory issues
      if (frameCache.size > 50) {
        const firstKey = frameCache.keys().next().value;
        frameCache.delete(firstKey);
      }
      
      setFrames(data.frames);
      setLastUpdate(new Date());
      
      if (!silent) {
        console.log(`Frames loaded: ${data.frames.length} frames for page ${currentPage}`);
      }
    } catch (err) {
      console.error(`❌ Error in fetchFramesFromRepo:`, err);
      if (!silent) {
        setError('Failed to load frames: ' + err.message);
      }
    } finally {
      if (!silent) {
        setLoading(false);
        console.log(`🏁 Loading finished`);
      }
    }
  };

  // Pagination functions
  const goToPage = useCallback((page) => {
    setCurrentPage(page);
  }, []);

  const goToNextPage = useCallback(() => {
    if (currentPage < Math.ceil(totalFrames / framesPerPage)) {
      goToPage(currentPage + 1);
    }
  }, [currentPage, totalFrames, framesPerPage, goToPage]);

  const goToPrevPage = useCallback(() => {
    if (currentPage > 1) {
      goToPage(currentPage - 1);
    }
  }, [currentPage, goToPage]);

  // Calculate current frames to display
  const currentFrames = frames; // No need to slice since API returns only the frames for current page

  return (
    <div className="app">
      <header className="header">
        <h1>Remove this Flash ⚡🎥</h1>
        <p className="description">
          The AI solution to remove flash from videos and replace individual frames in videos.
        </p>
        <p className="repo-info">
          Viewing frames from repository: {repoUuid}
        </p>
        <button 
          onClick={() => navigate('/')} 
          className="back-button"
        >
          ← Back to Upload
        </button>
      </header>

      {loading ? (
        <div className="loading">Loading frames...</div>
      ) : (
        <>
          <div className="info">
            <p>Total frames: {totalFrames}</p>
            {lastUpdate && (
              <p className="last-update">
                Last updated: {lastUpdate.toLocaleTimeString()}
              </p>
            )}
            <button 
              onClick={() => fetchFramesFromRepo(repoUuid)} 
              className="refresh-button"
              disabled={loading}
            >
              {loading ? 'Refreshing...' : '🔄 Refresh'}
            </button>
          </div>

          <div className="frames-grid">
            {currentFrames.map((framePath, index) => (
              <div key={index} className="frame-container">
                <img 
                  src={`http://localhost:8000/${framePath}`}
                  alt={`Frame ${(currentPage - 1) * framesPerPage + index + 1}`}
                  className="frame-image"
                  loading="lazy"
                  onError={(e) => {
                    console.error(`Failed to load image: ${framePath}`);
                    e.target.style.display = 'none';
                  }}
                />
                <div className="frame-info">
                  Frame {(currentPage - 1) * framesPerPage + index + 1}
                </div>
              </div>
            ))}
          </div>

          {totalFrames > framesPerPage && (
            <div className="pagination">
              <button 
                onClick={goToPrevPage} 
                disabled={currentPage === 1}
                className="page-button"
              >
                ← Previous
              </button>
              
              <div className="page-numbers">
                {Array.from({ length: Math.ceil(totalFrames / framesPerPage) }, (_, i) => i + 1)
                  .filter(page => page === 1 || page === Math.ceil(totalFrames / framesPerPage) ||
                                 (page >= currentPage - 2 && page <= currentPage + 2))
                  .map((page, index, array) => (
                    <React.Fragment key={page}>
                      {index > 0 && array[index - 1] !== page - 1 && (
                        <span className="page-ellipsis">...</span>
                      )}
                      <button
                        onClick={() => goToPage(page)}
                        className={`page-button ${currentPage === page ? 'active' : ''}`}
                      >
                        {page}
                      </button>
                    </React.Fragment>
                  ))}
              </div>
              
              <button 
                onClick={goToNextPage} 
                disabled={currentPage === Math.ceil(totalFrames / framesPerPage)}
                className="page-button"
              >
                Next →
              </button>
            </div>
          )}
        </>
      )}

      {error && (
        <div className="error">
          {error}
        </div>
      )}
    </div>
  );
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<UploadInterface />} />
      <Route path="/frames/:repoUuid" element={<FrameDisplay />} />
      <Route path="/:repoUuid" element={<FrameDisplay />} />
    </Routes>
  );
}

export default App; 