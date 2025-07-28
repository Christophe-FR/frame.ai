import React, { useState, useCallback, useEffect } from 'react';
import { Routes, Route, useNavigate, useParams, useLocation } from 'react-router-dom';
import './App.css';

// Upload Component
function UploadInterface() {
  const [isDragOver, setIsDragOver] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState(null);
  const [accessLink, setAccessLink] = useState(null);
  
  const navigate = useNavigate();

  // Handle drag and drop events
  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setIsDragOver(false);
    
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      handleFileSelect(files[0]);
    }
  }, []);

  // Handle file selection (both drag & drop and click)
  const handleFileSelect = (file) => {
    setError(null);
    setAccessLink(null);
    
    // Check file type
    const allowedTypes = ['video/mp4', 'video/avi', 'video/mov', 'video/quicktime'];
    if (!allowedTypes.includes(file.type)) {
      setError('Please select a valid video file (MP4, AVI, or MOV)');
      return;
    }
    
    // Check file size (500MB limit)
    const maxSize = 500 * 1024 * 1024; // 500MB in bytes
    if (file.size > maxSize) {
      setError('File size must be less than 500MB');
      return;
    }
    
    setSelectedFile(file);
    
    // Auto-start upload
    handleUpload(file);
  };

  // Handle file input change
  const handleFileInputChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      handleFileSelect(file);
    }
  };

  // Handle upload
  const handleUpload = async (file) => {
    if (!file) return;
    
    setIsUploading(true);
    setUploadProgress(0);
    setError(null);
    setAccessLink(null);
    
    try {
      // Create FormData for file upload
      const formData = new FormData();
      formData.append('video', file);
      
      // Send file to backend with timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 300000); // 5 minutes timeout
      
      const response = await fetch('/api/upload-video', {
        method: 'POST',
        body: formData,
        signal: controller.signal,
      });
      
      clearTimeout(timeoutId);
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Upload failed');
      }
      
      const result = await response.json();
      
      // Update progress to 100%
      setUploadProgress(100);
      
      // Store the access link
      setAccessLink(result.access_link);
      
      // Extract UUID from access link and navigate to it
      const uuidMatch = result.access_link.match(/\/api\/([a-f0-9-]+)\/?$/);
      if (uuidMatch) {
        const repoUuid = uuidMatch[1];
        
        // Navigate to the job page
        navigate(`/${repoUuid}`);
      }
      
      console.log('Upload successful:', result);
      
    } catch (err) {
      if (err.name === 'AbortError') {
        setError('Upload timed out. Video processing is taking longer than expected.');
      } else {
        setError('Upload failed: ' + err.message);
      }
    } finally {
      setIsUploading(false);
    }
  };

  // Format file size
  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className="app">
      <header className="header">
        <h1>Remove this Flash ⚡🎥</h1>
        <p className="description">
          The AI solution to remove flash from videos and replace individual frames in videos.
        </p>
      </header>

      <div className="upload-container">
        <div 
          className={`upload-area ${isDragOver ? 'drag-over' : ''} ${selectedFile ? 'has-file' : ''}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          {!selectedFile ? (
            <>
              <div className="upload-icon">📁</div>
              <h3>Upload your video</h3>
              <p>Drag and drop your video file here, or click to browse</p>
              <p className="upload-limits">
                Supported formats: MP4, AVI, MOV<br />
                Maximum size: 500MB
              </p>
              <input
                type="file"
                id="file-input"
                accept="video/mp4,video/avi,video/mov,video/quicktime"
                onChange={handleFileInputChange}
                style={{ display: 'none' }}
              />
              <label htmlFor="file-input" className="browse-button">
                Browse Files
              </label>
            </>
          ) : (
            <div className="file-info">
              <div className="file-icon">🎥</div>
              <h3>{selectedFile.name}</h3>
              <p>Size: {formatFileSize(selectedFile.size)}</p>
              <p>Type: {selectedFile.type}</p>
            </div>
          )}
        </div>

        {isUploading && (
          <div className="upload-progress">
            <div className="progress-bar">
              <div 
                className="progress-fill" 
                style={{ width: `${uploadProgress}%` }}
              ></div>
            </div>
            <p>Uploading... {uploadProgress}%</p>
          </div>
        )}

        {error && (
          <div className="error-message">
            {error}
          </div>
        )}

        {accessLink && (
          <div className="success-message">
            <p>Upload successful!</p>
            <p>Your video is ready at: <a href={accessLink} target="_blank" rel="noopener noreferrer">{accessLink}</a></p>
          </div>
        )}
      </div>
    </div>
  );
}

// Frame Display Component
function FrameDisplay() {
  const { repoUuid } = useParams();
  const navigate = useNavigate();
  
  const [frames, setFrames] = useState([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalFrames, setTotalFrames] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  
  const framesPerPage = 20;

  useEffect(() => {
    if (repoUuid) {
      fetchFramesFromRepo(repoUuid);
      
      // Set up polling to keep frames in sync
      const pollInterval = setInterval(() => {
        fetchFramesFromRepo(repoUuid, true); // silent update
      }, 2000); // Poll every 2 seconds
      
      return () => clearInterval(pollInterval);
    }
  }, [repoUuid]);

  const fetchFramesFromRepo = async (uuid, silent = false) => {
    if (!silent) {
      setLoading(true);
    }
    
    try {
      const response = await fetch(`/api/${uuid}/frames`);
      if (!response.ok) {
        throw new Error('Failed to fetch frames');
      }
      const data = await response.json();
      
      // Check if frames have changed
      const framesChanged = JSON.stringify(data.frames) !== JSON.stringify(frames);
      
      if (framesChanged) {
        setFrames(data.frames);
        setTotalFrames(data.total);
        setLastUpdate(new Date());
        
        // Adjust current page if it's now out of bounds
        const maxPage = Math.ceil(data.total / framesPerPage);
        if (currentPage > maxPage && maxPage > 0) {
          setCurrentPage(maxPage);
        }
        
        if (!silent) {
          console.log(`Frames updated: ${data.total} frames found`);
        }
      }
    } catch (err) {
      if (!silent) {
        setError('Failed to load frames: ' + err.message);
      }
    } finally {
      if (!silent) {
        setLoading(false);
      }
    }
  };

  // Format file size
  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  // Pagination functions
  const goToPage = (page) => {
    setCurrentPage(page);
  };

  const goToNextPage = () => {
    if (currentPage < Math.ceil(totalFrames / framesPerPage)) {
      goToPage(currentPage + 1);
    }
  };

  const goToPrevPage = () => {
    if (currentPage > 1) {
      goToPage(currentPage - 1);
    }
  };

  // Calculate current frames to display
  const startIndex = (currentPage - 1) * framesPerPage;
  const endIndex = startIndex + framesPerPage;
  const currentFrames = frames.slice(startIndex, endIndex);

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
            {currentFrames.map((frame, index) => (
              <div key={index} className="frame-item">
                <img 
                  src={`http://localhost:8000/uploads/${repoUuid}/${frame}`}
                  alt={frame}
                  onError={(e) => {
                    e.target.style.display = 'none';
                    e.target.nextSibling.style.display = 'block';
                  }}
                />
                <div className="frame-error" style={{ display: 'none' }}>
                  Failed to load image
                </div>
                <div className="frame-info">
                  <div className="frame-name">{frame}</div>
                </div>
              </div>
            ))}
          </div>

          {totalFrames > framesPerPage && (
            <div className="pagination">
              <button 
                className="nav-button" 
                onClick={goToPrevPage}
                disabled={currentPage === 1}
              >
                Previous
              </button>
              
              <div className="page-numbers">
                {Array.from({ length: Math.ceil(totalFrames / framesPerPage) }, (_, i) => i + 1)
                  .filter(page => page === 1 || page === Math.ceil(totalFrames / framesPerPage) || 
                                 (page >= currentPage - 2 && page <= currentPage + 2))
                  .map((page, index, array) => (
                    <React.Fragment key={page}>
                      {index > 0 && array[index - 1] !== page - 1 && <span>...</span>}
                      <button
                        className={`page-button ${page === currentPage ? 'active' : ''}`}
                        onClick={() => goToPage(page)}
                      >
                        {page}
                      </button>
                    </React.Fragment>
                  ))}
              </div>
              
              <button 
                className="nav-button" 
                onClick={goToNextPage}
                disabled={currentPage === Math.ceil(totalFrames / framesPerPage)}
              >
                Next
              </button>
            </div>
          )}
        </>
      )}

      {error && (
        <div className="error-message">
          {error}
        </div>
      )}
    </div>
  );
}

// Main App Component
function App() {
  return (
    <Routes>
      <Route path="/" element={<UploadInterface />} />
      <Route path="/:repoUuid" element={<FrameDisplay />} />
    </Routes>
  );
}

export default App; 