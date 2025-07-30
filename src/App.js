import React, { useState, useCallback, useEffect, useMemo } from 'react';
import { useParams, useNavigate, Routes, Route } from 'react-router-dom';
import './App.css';

function UploadInterface() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadStatus, setUploadStatus] = useState('');
  const [uploadSpeed, setUploadSpeed] = useState(0);
  const [uploadStartTime, setUploadStartTime] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [repoUuid, setRepoUuid] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingStatus, setProcessingStatus] = useState('');
  const [totalFrames, setTotalFrames] = useState(0);
  const navigate = useNavigate();

  const handleFileSelect = (file) => {
    console.log('📂 File selected:', {
      name: file?.name,
      type: file?.type,
      size: file?.size
    });
    
    if (file && file.type.startsWith('video/')) {
      console.log('✅ Valid video file selected');
      setSelectedFile(file);
      setUploadStatus('');
      // Automatically start upload when file is selected
      handleUpload(file);
    } else {
      console.warn('❌ Invalid file type selected:', file?.type);
      setUploadStatus('Please select a valid video file.');
      setSelectedFile(null);
    }
  };

  const handleFileInputChange = (e) => {
    console.log('🖱️ File input change event');
    const file = e.target.files[0];
    handleFileSelect(file);
  };

  const handleUpload = useCallback(async (file) => {
    if (!file) return;

    console.log(`🚀 Starting upload for file: ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`);
    const startTime = Date.now();

    setUploadStatus('Uploading...');
    setUploadProgress(0);
    setUploadSpeed('');
    setIsUploading(true);

    const formData = new FormData();
    formData.append('file', file);

    const xhr = new XMLHttpRequest();
    
    xhr.upload.addEventListener('progress', (event) => {
      if (event.lengthComputable) {
        const percentComplete = (event.loaded / event.total) * 100;
        const elapsed = (Date.now() - startTime) / 1000;
        const speed = (event.loaded / 1024 / 1024 / elapsed).toFixed(2);
        
        console.log(`📤 Upload progress: ${percentComplete.toFixed(1)}% (${speed} MB/s)`);
        setUploadProgress(percentComplete);
        setUploadSpeed(`${speed} MB/s`);
        
        // Navigate immediately when upload reaches 100%
        if (percentComplete >= 100) {
          console.log(`🚀 Upload reached 100% - navigating immediately`);
          console.log(`📍 Target URL: /frames/${repoUuid || 'pending'}`);
          console.log(`⏱️ Navigation start time: ${new Date().toISOString()}`);
          
          // Navigate immediately without waiting for response
          navigate(`/frames/${repoUuid || 'pending'}`);
        }
      }
    });

    xhr.addEventListener('load', () => {
      const uploadTime = ((Date.now() - startTime) / 1000).toFixed(2);
      console.log(`✅ Upload completed in ${uploadTime}s`);
      console.log(`📡 Response status: ${xhr.status}`);
      console.log(`📡 Response headers:`, xhr.getAllResponseHeaders());
      
      if (xhr.status === 200) {
        console.log(`📄 Raw response text:`, xhr.responseText);
        
        try {
          const response = JSON.parse(xhr.responseText);
          console.log(`🎯 Parsed response:`, response);
          console.log(`🎯 Backend assigned UUID: ${response.uuid}`);
          
          // Update UUID if we navigated with 'pending'
          if (repoUuid === 'pending' || !repoUuid) {
            console.log(`🔄 Updating UUID from 'pending' to: ${response.uuid}`);
            setRepoUuid(response.uuid);
            
            // Navigate to the correct URL if we were on pending
            const currentPath = window.location.pathname;
            if (currentPath.includes('/frames/pending')) {
              console.log(`🔄 Navigating to correct URL: /frames/${response.uuid}`);
              navigate(`/frames/${response.uuid}`);
            }
          }
          
          setUploadStatus('Upload successful! Navigating to frames page...');
          setIsUploading(false);
          setUploadProgress(100);
          setUploadSpeed('');
          
        } catch (parseError) {
          console.error(`❌ Failed to parse response JSON:`, parseError);
          console.error(`❌ Raw response was:`, xhr.responseText);
          setUploadStatus('Upload failed! Invalid server response');
          setIsUploading(false);
        }
      } else {
        console.error(`❌ Upload failed with status ${xhr.status}: ${xhr.responseText}`);
        console.error(`❌ Response headers:`, xhr.getAllResponseHeaders());
        setUploadStatus('Upload failed!');
        setIsUploading(false);
      }
    });

    xhr.addEventListener('error', () => {
      const uploadTime = ((Date.now() - startTime) / 1000).toFixed(2);
      console.error(`💥 Upload error after ${uploadTime}s: Network error`);
      setUploadStatus('Upload failed! Network error');
      setIsUploading(false);
    });

    xhr.addEventListener('timeout', () => {
      const uploadTime = ((Date.now() - startTime) / 1000).toFixed(2);
      console.error(`⏰ Upload timeout after ${uploadTime}s`);
      setUploadStatus('Upload failed! Timeout');
      setIsUploading(false);
    });

    xhr.open('POST', 'http://localhost:8000/upload_video');
    xhr.timeout = 600000; // 10 minutes
    console.log(`🌐 Sending request to backend...`);
    xhr.send(formData);
  }, []);

  const handleDrop = (e) => {
    e.preventDefault();
    console.log('📥 File dropped');
    const file = e.dataTransfer.files[0];
    handleFileSelect(file);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    console.log('📤 File drag over');
  };

  return (
    <div className="app">
      <header className="header">
        <h1>Remove this Flash ⚡🎥</h1>
        <p className="description">
          Upload a video to remove flash and replace individual frames using AI.
        </p>
      </header>
      
      <div className="upload-container">
        <div 
          className={`upload-area ${selectedFile ? 'has-file' : ''} ${isUploading ? 'uploading' : ''}`}
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
                {isUploading && <p className="upload-status">Uploading automatically...</p>}
                {isProcessing && <p className="processing-status">Processing video...</p>}
              </div>
            ) : (
              <div>
                <p>📁 Drop video file here or click to select</p>
                <p className="upload-hint">Upload starts automatically when video is selected</p>
              </div>
            )}
          </label>
        </div>

        {isUploading && (
          <div className="upload-progress">
            <div className="progress-bar">
              <div 
                className="progress-fill" 
                style={{ width: `${uploadProgress}%` }}
              ></div>
            </div>
            <p>{uploadStatus}</p>
            {uploadSpeed && (
              <p className="upload-speed">Speed: {uploadSpeed}</p>
            )}
          </div>
        )}

        {isProcessing && (
          <div className="processing-status">
            <div className="processing-spinner"></div>
            <p>{processingStatus}</p>
            <p className="processing-hint">This may take several minutes for large videos</p>
          </div>
        )}

        {uploadStatus && !isUploading && !isProcessing && (
          <p className="upload-status">{uploadStatus}</p>
        )}
      </div>
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
  
  console.log(`🎬 FrameDisplay component initialized`);
  console.log(`🎬 repoUuid from params:`, repoUuid);
  
  const [frames, setFrames] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [totalFrames, setTotalFrames] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [processingStatus, setProcessingStatus] = useState(null);
  const [isProcessing, setIsProcessing] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  
  const framesPerPage = 20;

  // Memoize the frame cache to avoid unnecessary re-renders
  const frameCache = useMemo(() => new Map(), []);

  // Handle 'pending' case - wait for actual UUID
  useEffect(() => {
    if (repoUuid === 'pending') {
      console.log(`⏳ Waiting for actual UUID to be assigned...`);
      setLoading(true);
    }
  }, [repoUuid]);

  const fetchTotalFrames = useCallback(async (uuid) => {
    try {
      const response = await fetch(`http://localhost:8000/${uuid}/frames/count`);
      if (response.ok) {
        const data = await response.json();
        setTotalFrames(data.total);
      }
    } catch (err) {
      console.error('Failed to get total frames count:', err);
    }
  }, []);

  const checkProcessingStatus = useCallback(async (uuid) => {
    if (!uuid) return;
    
    try {
      console.log(`🔍 Checking processing status for ${uuid}...`);
      const response = await fetch(`http://localhost:8000/${uuid}/status`);
      const data = await response.json();
      
      console.log(`📊 Processing status: ${JSON.stringify(data)}`);
      
      if (data.processing_complete) {
        console.log(`🎉 Video processing completed! Found ${data.frame_count} frames`);
        setIsProcessing(false);
        setProcessingStatus('Processing complete!');
      } else {
        console.log(`⏳ Still processing... (${data.frame_count} frames, metadata: ${data.has_metadata})`);
        setProcessingStatus(`Processing video... (${data.frame_count} frames available)`);
        setIsProcessing(true);
      }
    } catch (error) {
      console.error(`❌ Error checking processing status: ${error}`);
      setProcessingStatus('Error checking status');
    }
  }, []);

  const loadFrames = useCallback(async (uuid) => {
    if (!uuid) return;
    
    try {
      console.log(`🖼️ Loading frames for ${uuid}, page ${currentPage}...`);
      setLoading(true);
      const startTime = Date.now();
      
      // Calculate pagination
      const start = (currentPage - 1) * framesPerPage;
      const end = start + framesPerPage - 1;
      
      const response = await fetch(`http://localhost:8000/${uuid}/frames?start=${start}&end=${end}`);
      const data = await response.json();
      
      const loadTime = ((Date.now() - startTime) / 1000).toFixed(2);
      console.log(`✅ Loaded ${data.frames.length} frames in ${loadTime}s`);
      
      setFrames(data.frames);
      setLoading(false);
      setLastUpdate(new Date());
      
      // Fetch accurate total frame count from backend
      try {
        const countResponse = await fetch(`http://localhost:8000/${uuid}/frames/count`);
        if (countResponse.ok) {
          const countData = await countResponse.json();
          console.log(`📊 Actual total frames from backend: ${countData.total}`);
          setTotalFrames(countData.total);
        }
      } catch (countError) {
        console.error(`❌ Error fetching frame count: ${countError}`);
      }
    } catch (error) {
      console.error(`❌ Error loading frames: ${error}`);
      setError('Failed to load frames: ' + error.message);
      setLoading(false);
    }
  }, [currentPage, framesPerPage]);

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

  // Load frames when page changes
  useEffect(() => {
    if (repoUuid && repoUuid !== 'pending') {
      console.log(`🎬 useEffect triggered - loading frames for repo: ${repoUuid}`);
      console.log(`🎬 Current page: ${currentPage}`);
      console.log(`🎬 Auto-refresh enabled: ${autoRefresh}`);
      console.log(`🎬 Is processing: ${isProcessing}`);
      
      loadFrames(repoUuid);
    } else if (repoUuid === 'pending') {
      console.log(`⏳ Skipping frame load - waiting for actual UUID`);
    } else {
      console.log(`❌ No repoUuid available for frame loading`);
    }
  }, [repoUuid, currentPage, loadFrames]);

  // Check processing status periodically
  useEffect(() => {
    if (repoUuid && repoUuid !== 'pending') {
      console.log(`🔍 useEffect triggered - checking processing status for repo: ${repoUuid}`);
      console.log(`🔍 Auto-refresh enabled: ${autoRefresh}`);
      console.log(`🔍 Is processing: ${isProcessing}`);
      
      // Check processing status once when component loads
      checkProcessingStatus(repoUuid);
    } else if (repoUuid === 'pending') {
      console.log(`⏳ Skipping processing status check - waiting for actual UUID`);
    } else {
      console.log(`❌ No repoUuid available for processing status check`);
    }
  }, [repoUuid, checkProcessingStatus]);

  // Auto-refresh functionality
  useEffect(() => {
    if (repoUuid && repoUuid !== 'pending' && autoRefresh) {
      console.log(`🔄 Auto-refresh useEffect triggered`);
      console.log(`🔄 repoUuid: ${repoUuid}`);
      console.log(`🔄 autoRefresh: ${autoRefresh}`);
      console.log(`🔄 isProcessing: ${isProcessing}`);
      console.log(`🔄 Setting up auto-refresh interval (5 seconds)`);
      
      const interval = setInterval(() => {
        console.log(`🔄 Auto-refresh: checking for new frames...`);
        console.log(`🔄 Current time: ${new Date().toISOString()}`);
        // Check processing status and total frame count
        checkProcessingStatus(repoUuid);
        fetchTotalFrames(repoUuid);
        // Reload frames for current page
        loadFrames(repoUuid);
      }, 5000); // Check every 5 seconds
      
      console.log(`🔄 Auto-refresh interval set up successfully`);
      
      return () => {
        console.log(`🔄 Cleaning up auto-refresh interval`);
        clearInterval(interval);
      };
    } else if (repoUuid === 'pending') {
      console.log(`⏳ Auto-refresh not started - waiting for actual UUID`);
    } else {
      console.log(`⏸️ Auto-refresh not enabled or no repoUuid`);
      console.log(`⏸️ repoUuid: ${repoUuid}`);
      console.log(`⏸️ autoRefresh: ${autoRefresh}`);
    }
  }, [repoUuid, autoRefresh, checkProcessingStatus, loadFrames, fetchTotalFrames]);

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
        <div className="loading">
          <div>Loading frames...</div>
        </div>
      ) : (
        <>
          <div className="info">
            <p>Total frames: {totalFrames}</p>
            {!isProcessing && totalFrames > 0 && (
              <p style={{ color: '#28a745', fontWeight: '500' }}>
                ✅ Processing complete! {totalFrames} frames available
              </p>
            )}
            {lastUpdate && (
              <p className="last-update">
                Last updated: {lastUpdate.toLocaleTimeString()}
              </p>
            )}
            <div className="controls">
              <button 
                onClick={() => {
                  loadFrames(repoUuid);
                  // Also fetch the latest frame count
                  fetchTotalFrames(repoUuid);
                }} 
                className="refresh-button"
                disabled={loading}
              >
                {loading ? 'Refreshing...' : '🔄 Refresh'}
              </button>
              
              <div className="auto-refresh-toggle">
                <label>
                  <input
                    type="checkbox"
                    checked={autoRefresh}
                    onChange={(e) => setAutoRefresh(e.target.checked)}
                  />
                  <span className="toggle-label">
                    {autoRefresh ? '🔄 Auto-refresh ON' : '⏸️ Auto-refresh OFF'}
                  </span>
                </label>
              </div>
            </div>
          </div>

          <div className="frames-grid">
            {frames.map((framePath, index) => (
              <div key={index} className="frame-container">
                <img 
                  src={`http://localhost:8000/static/${repoUuid}/${framePath}`}
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