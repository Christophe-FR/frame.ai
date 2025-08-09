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
          console.log(`📍 Target URL: /${repoUuid || 'pending'}`);
          console.log(`⏱️ Navigation start time: ${new Date().toISOString()}`);
          
          // Navigate immediately without waiting for response
          navigate(`/${repoUuid || 'pending'}`);
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
                  if (currentPath.includes('/pending')) {
        console.log(`🔄 Navigating to correct URL: /${response.uuid}`);
        navigate(`/${response.uuid}`);
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

            xhr.open('POST', 'http://localhost:8500/video_upload');
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
  const [frameNumbers, setFrameNumbers] = useState([]);
  const [selectedFrames, setSelectedFrames] = useState(new Set());
  const [bannerCollapsed, setBannerCollapsed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [totalFrames, setTotalFrames] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [processingStatus, setProcessingStatus] = useState(null);
  const [isProcessing, setIsProcessing] = useState(true);
  const [lastDirModTime, setLastDirModTime] = useState(null);
  const [lastKnownFrameCount, setLastKnownFrameCount] = useState(0);
  const [lastKnownFrameNames, setLastKnownFrameNames] = useState('');
  const [videoInfo, setVideoInfo] = useState(null);
    const [runningTasks, setRunningTasks] = useState([]); // Changed to array for multiple tasks
  const [forceRefreshCounter, setForceRefreshCounter] = useState(0); // Force refresh trigger
  const [cacheBuster, setCacheBuster] = useState(Date.now()); // Cache buster for images
  
  const framesPerPage = 20;

  // Memoize the frame cache to avoid unnecessary re-renders
  const frameCache = useMemo(() => new Map(), []);

  // Handle frame selection
  const toggleFrameSelection = useCallback((frameNumber) => {
    setSelectedFrames(prev => {
      const newSet = new Set(prev);
      if (newSet.has(frameNumber)) {
        newSet.delete(frameNumber);
      } else {
        newSet.add(frameNumber);
      }
      return newSet;
    });
  }, []);

  // Get selected frame numbers as sorted array
  const selectedFrameNumbers = useMemo(() => {
    return Array.from(selectedFrames).sort((a, b) => a - b);
  }, [selectedFrames]);



  // Handle 'pending' case - wait for actual UUID
  useEffect(() => {
    if (repoUuid === 'pending') {
      console.log(`⏳ Waiting for actual UUID to be assigned...`);
      setLoading(true);
    }
  }, [repoUuid]);

  const fetchTotalFrames = useCallback(async (uuid) => {
    try {
      const response = await fetch(`http://localhost:8500/ls/${uuid}/?start=0&end=0`);
      if (response.ok) {
        const data = await response.json();
        setTotalFrames(data.frames.total);
      }
    } catch (err) {
      console.error('Failed to get total frames count:', err);
    }
  }, []);

  const fetchVideoInfo = useCallback(async (uuid) => {
    try {
              const response = await fetch(`http://localhost:8500/static/${uuid}/video_info.json`);
      if (response.ok) {
        const data = await response.json();
        setVideoInfo(data);
      }
    } catch (err) {
      console.error('Failed to get video info:', err);
    }
  }, []);

  const checkProcessingStatus = useCallback(async (uuid) => {
    if (!uuid) return;
    
    try {
      console.log(`🔍 Checking processing status for ${uuid}...`);
      const response = await fetch(`http://localhost:8500/${uuid}/status`);
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
    if (!uuid) {
      console.log(`❌ loadFrames called with no UUID`);
      return;
    }
    
    try {
      console.log(`🖼️ Loading frames for ${uuid}, page ${currentPage}...`);
      setLoading(true);
      const startTime = Date.now();
      
      // Calculate pagination
      const start = (currentPage - 1) * framesPerPage;
      const end = start + framesPerPage - 1;
      
      console.log(`📄 Fetching frames from ${start} to ${end}...`);
      const response = await fetch(`http://localhost:8500/ls/${uuid}/?start=${start}&end=${end}`);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      console.log(`📊 Response data:`, data);
      
      // Use the raw frame paths directly (skip video_info.json and audio.wav)
      const framePaths = data.filenames
        .filter(filename => filename.includes('frame_') && filename.endsWith('.jpg'));
      
      const loadTime = ((Date.now() - startTime) / 1000).toFixed(2);
      console.log(`✅ Loaded ${framePaths.length} frames in ${loadTime}s`);
      
      console.log(`📊 Setting frames state: ${framePaths.length} frames`);
      setFrames(framePaths);
      setFrameNumbers(data.frames.numbers);
      setLoading(false);
      setLastUpdate(new Date());
      console.log(`✅ Frame state updated successfully`);
      
      // Set baseline frame count and names  
      setLastKnownFrameCount(data.frames.total);
      setLastKnownFrameNames(JSON.stringify(data));
      
      // Update total frame count from the response
      console.log(`📊 Total frames from backend: ${data.frames.total}`);
      setTotalFrames(data.frames.total);
    } catch (error) {
      console.error(`❌ Error loading frames: ${error}`);
      setError('Failed to load frames: ' + error.message);
      setLoading(false);
    }
  }, [currentPage, framesPerPage]);

  const checkForChanges = useCallback(async (uuid) => {
    if (!uuid) return false;
    
    try {
      console.log(`🔍 Checking for changes by comparing API response...`);
      
      // Calculate current page frame range
      const start = (currentPage - 1) * framesPerPage;
      const end = start + framesPerPage - 1;
      
      const response = await fetch(`http://localhost:8500/ls/${uuid}/?start=${start}&end=${end}`);
      if (response.ok) {
        const data = await response.json();
        
        // Simple comparison: stringify the entire response
        const currentResponse = JSON.stringify(data);
        
        console.log(`📊 Response size: ${currentResponse.length} chars`);
        
        if (lastKnownFrameNames && lastKnownFrameNames !== currentResponse) {
          console.log(`🔄 API response changed!`);
          setLastKnownFrameNames(currentResponse);
          return true;
        } else if (!lastKnownFrameNames) {
          console.log(`📅 First load - setting baseline response`);
          setLastKnownFrameNames(currentResponse);
        } else {
          console.log(`✅ No changes detected - response identical`);
        }
      }

    } catch (error) {
      console.error(`❌ Error checking for changes: ${error}`);
    }
    return false;
  }, [lastKnownFrameNames, currentPage, framesPerPage]);

  // Add a global function to reset baseline (for debugging)
  useEffect(() => {
    window.resetBaseline = () => {
      setLastKnownFrameNames(null);
      console.log('🔄 Baseline reset - next check will set new baseline');
    };
  }, []);

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

  // Function to poll individual task status
  const pollTaskStatus = useCallback(async (taskId, repoUuid) => {
    const pollInterval = setInterval(async () => {
      try {
        const response = await fetch(`http://localhost:8500/api/tasks/${taskId}/status`);
        if (response.ok) {
          const statusData = await response.json();
          
          setRunningTasks(prev => prev.map(task => {
            if (task.id === taskId) {
              if (statusData.status === 'completed') {
                console.log(`✅ Task ${taskId} completed successfully!`);
                
                // Trigger page refresh since new frames were created
                console.log('🔄 Triggering page refresh due to completed interpolation');
                setForceRefreshCounter(prev => prev + 1);
                setCacheBuster(Date.now());
                loadFrames(repoUuid);
                fetchTotalFrames(repoUuid);
                
                // Mark as completed and schedule removal
                setTimeout(() => {
                  setRunningTasks(prevTasks => prevTasks.filter(t => t.id !== taskId));
                }, 15000); // Remove after 15 seconds
                
                clearInterval(pollInterval);
                return { ...task, status: 'completed', result: statusData.result };
                
              } else if (statusData.status === 'failed') {
                console.error(`❌ Task ${taskId} failed:`, statusData.error);
                clearInterval(pollInterval);
                
                // Remove failed task after 5 seconds
                setTimeout(() => {
                  setRunningTasks(prevTasks => prevTasks.filter(t => t.id !== taskId));
                }, 5000);
                
                return { ...task, status: 'failed', error: statusData.error };
              } else if (statusData.status === 'processing') {
                return { ...task, status: 'processing', progress: statusData.progress };
              }
            }
            return task;
          }));
        }
      } catch (error) {
        console.error(`Error polling task ${taskId}:`, error);
      }
    }, 2000); // Poll every 2 seconds

    // Cleanup after 5 minutes
    setTimeout(() => clearInterval(pollInterval), 300000);
  }, [loadFrames, fetchTotalFrames]);

  // Load video info immediately when component mounts
  useEffect(() => {
    if (repoUuid && repoUuid !== 'pending') {
      console.log(`📹 Loading video info for repo: ${repoUuid}`);
      fetchVideoInfo(repoUuid);
    }
  }, [repoUuid, fetchVideoInfo]);

  // Load frames when page changes or force refresh triggered
  useEffect(() => {
    console.log(`🎬 useEffect triggered with repoUuid: ${repoUuid}`);
    console.log(`🎬 Current page: ${currentPage}`);
    console.log(`🎬 Force refresh counter: ${forceRefreshCounter}`);
    console.log(`🎬 Is processing: ${isProcessing}`);
    
    if (repoUuid && repoUuid !== 'pending') {
      console.log(`🎬 Loading frames for repo: ${repoUuid}`);
      loadFrames(repoUuid);
    } else if (repoUuid === 'pending') {
      console.log(`⏳ Skipping frame load - waiting for actual UUID`);
    } else {
      console.log(`❌ No repoUuid available for frame loading`);
    }
  }, [repoUuid, currentPage, forceRefreshCounter, loadFrames]);

  // Check processing status periodically
  useEffect(() => {
    if (repoUuid && repoUuid !== 'pending') {
      console.log(`🔍 useEffect triggered - checking processing status for repo: ${repoUuid}`);
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
    if (repoUuid && repoUuid !== 'pending') {
      console.log(`🔄 Auto-refresh useEffect triggered`);
      console.log(`🔄 repoUuid: ${repoUuid}`);
      console.log(`🔄 isProcessing: ${isProcessing}`);
      console.log(`🔄 Setting up auto-refresh interval (5 seconds)`);
      
      const interval = setInterval(async () => {
        console.log(`🔄 Auto-refresh: checking for changes...`);
        console.log(`🔄 Current time: ${new Date().toISOString()}`);
        console.log(`🔄 repoUuid: ${repoUuid}`);
        console.log(`🔄 lastDirModTime: ${lastDirModTime ? new Date(lastDirModTime).toISOString() : 'None'}`);
        
        // Check for changes using modification times
        const hasChanges = await checkForChanges(repoUuid);
        
        if (hasChanges) {
          console.log(`🔄 Changes detected! Triggering refresh...`);
          console.log(`🔄 Updating lastUpdate timestamp...`);
          setForceRefreshCounter(prev => prev + 1);
          setCacheBuster(Date.now());
          setLastUpdate(new Date());
          // Check processing status and total frame count
          checkProcessingStatus(repoUuid);
          fetchTotalFrames(repoUuid);
          fetchVideoInfo(repoUuid);
          // Reload frames for current page
          loadFrames(repoUuid);
        } else {
          console.log(`✅ No changes detected, skipping refresh`);
        }
      }, 2500); // Check every 2.5 seconds
      
      console.log(`🔄 Auto-refresh interval set up successfully`);
      
      return () => {
        console.log(`🔄 Cleaning up auto-refresh interval`);
        clearInterval(interval);
      };
    } else if (repoUuid === 'pending') {
      console.log(`⏳ Auto-refresh not started - waiting for actual UUID`);
    } else {
      console.log(`⏸️ Auto-refresh not enabled - no repoUuid`);
      console.log(`⏸️ repoUuid: ${repoUuid}`);
    }
  }, [repoUuid, checkProcessingStatus, loadFrames, fetchTotalFrames, fetchVideoInfo, checkForChanges]);

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
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <button 
            onClick={() => navigate('/')} 
            className="back-button"
          >
            ← Back to Upload
          </button>
          <button 
            onClick={() => {
              console.log('🔄 Manual refresh button clicked');
              setForceRefreshCounter(prev => prev + 1);
              setCacheBuster(Date.now());
              setLastUpdate(new Date());
              loadFrames(repoUuid);
              fetchTotalFrames(repoUuid);
              fetchVideoInfo(repoUuid);
            }} 
            className="refresh-button"
            disabled={loading}
          >
            {loading ? 'Refreshing...' : '🔄 Refresh'}
          </button>
        </div>
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
            
            {/* Video Information Display */}
            {videoInfo && (
              <div className="video-info">
                <h3>📹 Video Information</h3>
                <div className="video-info-grid">
                  {videoInfo.video && (
                    <div className="video-info-section">
                      <h4>🎬 Video Stream</h4>
                      <div className="info-item">
                        <span className="label">Resolution:</span>
                        <span className="value">{videoInfo.video.width} × {videoInfo.video.height}</span>
                      </div>
                      <div className="info-item">
                        <span className="label">Frame Rate:</span>
                        <span className="value">{videoInfo.video.r_frame_rate}</span>
                      </div>
                      <div className="info-item">
                        <span className="label">Codec:</span>
                        <span className="value">{videoInfo.video.codec_name}</span>
                      </div>
                      {videoInfo.video.bit_rate && (
                        <div className="info-item">
                          <span className="label">Bit Rate:</span>
                          <span className="value">{Math.round(videoInfo.video.bit_rate / 1000)} kbps</span>
                        </div>
                      )}
                      {videoInfo.video.pix_fmt && (
                        <div className="info-item">
                          <span className="label">Pixel Format:</span>
                          <span className="value">{videoInfo.video.pix_fmt}</span>
                        </div>
                      )}
                    </div>
                  )}
                  
                  {videoInfo.audio && videoInfo.audio.codec_name && (
                    <div className="video-info-section">
                      <h4>🎵 Audio Stream</h4>
                      <div className="info-item">
                        <span className="label">Codec:</span>
                        <span className="value">{videoInfo.audio.codec_name}</span>
                      </div>
                      {videoInfo.audio.sample_rate && (
                        <div className="info-item">
                          <span className="label">Sample Rate:</span>
                          <span className="value">{Math.round(videoInfo.audio.sample_rate / 1000)} kHz</span>
                        </div>
                      )}
                      {videoInfo.audio.channels && (
                        <div className="info-item">
                          <span className="label">Channels:</span>
                          <span className="value">{videoInfo.audio.channels}</span>
                        </div>
                      )}
                      {videoInfo.audio.bit_rate && (
                        <div className="info-item">
                          <span className="label">Bit Rate:</span>
                          <span className="value">{Math.round(videoInfo.audio.bit_rate / 1000)} kbps</span>
                        </div>
                      )}
                    </div>
                  )}
                  
                  {videoInfo.format && (
                    <div className="video-info-section">
                      <h4>📦 Container</h4>
                      <div className="info-item">
                        <span className="label">Format:</span>
                        <span className="value">{videoInfo.format.format_name}</span>
                      </div>
                      {videoInfo.format.duration && (
                        <div className="info-item">
                          <span className="label">Duration:</span>
                          <span className="value">{Math.round(videoInfo.format.duration)}s</span>
                        </div>
                      )}
                      {videoInfo.format.bit_rate && (
                        <div className="info-item">
                          <span className="label">Total Bit Rate:</span>
                          <span className="value">{Math.round(videoInfo.format.bit_rate / 1000)} kbps</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Running Tasks Status - Stack multiple tasks */}
          {runningTasks.map((task, index) => {
            const getTaskIcon = (status) => {
              switch(status) {
                case 'submitting': return '⏳';
                case 'running': case 'processing': return '🔄';
                case 'completed': return '✅';
                case 'failed': return '❌';
                default: return '🔄';
              }
            };
            
            const getTaskMessage = (status) => {
              switch(status) {
                case 'submitting': return 'Starting interpolation...';
                case 'running': return 'Processing frames...';
                case 'processing': return 'Interpolating frames...';
                case 'completed': return 'Interpolation completed!';
                case 'failed': return 'Interpolation failed!';
                default: return 'Processing...';
              }
            };
            
            return (
              <div 
                key={task.id} 
                className={`task-status-banner task-${task.status}`}
                style={{ top: `${20 + index * 120}px` }}
              >
                <div className="task-status-header">
                  <span>{getTaskIcon(task.status)} {getTaskMessage(task.status)}</span>
                  <button 
                    onClick={() => setRunningTasks(prev => prev.filter(t => t.id !== task.id))}
                    className="task-status-close"
                    title="Dismiss (task continues in background)"
                  >
                    ✕
                  </button>
                </div>
                <div className="task-status-content">
                  <p><strong>Frames ({task.frames.length}):</strong> {task.frames.join(', ')}</p>
                  <p><strong>Task ID:</strong> {task.id.substring(0, 8)}...</p>
                  {task.progress && (
                    <p><strong>Progress:</strong> {task.progress.current || 0}/{task.progress.total || 1}</p>
                  )}
                  {task.status === 'completed' && (
                    <p className="task-status-note">✨ Auto-dismiss in 15s</p>
                  )}
                </div>
              </div>
            );
          })}

          {/* Selected Frames Banner - Bottom Right Corner */}
          {selectedFrameNumbers.length > 0 && (
            <div className={`selected-frames-banner ${bannerCollapsed ? 'collapsed' : ''}`}>
              <div className="banner-header">
                <span className="banner-title">Selected Frames: {selectedFrameNumbers.length}</span>
                <div className="banner-controls">
                  <button 
                    onClick={() => setBannerCollapsed(!bannerCollapsed)}
                    className="banner-toggle-btn"
                    title={bannerCollapsed ? "Expand banner" : "Collapse banner"}
                  >
                    {bannerCollapsed ? '▼' : '▲'}
                  </button>
                  <button 
                    onClick={(event) => {
                      if (selectedFrameNumbers.length > 0) {
                        const blob = new Blob([selectedFrameNumbers.join('\n')], { type: 'text/plain' });
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = `selected_frames_${repoUuid}.txt`;
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                        URL.revokeObjectURL(url);
                        
                        // Show brief success feedback
                        const btn = event.target;
                        const originalText = btn.innerHTML;
                        btn.innerHTML = '✓';
                        btn.style.background = 'rgba(40, 167, 69, 0.8)';
                        setTimeout(() => {
                          btn.innerHTML = originalText;
                          btn.style.background = '';
                        }, 1000);
                      }
                    }}
                    className="banner-download-btn"
                    title="Download selected frame numbers"
                    disabled={selectedFrameNumbers.length === 0}
                  >
                    📥
                  </button>
                  <button 
                    onClick={() => setSelectedFrames(new Set())}
                    className="banner-clear-btn"
                    title="Clear all selections"
                  >
                    ✕
                  </button>
                </div>
              </div>
              {!bannerCollapsed && (
                <div className="banner-content">
                  <textarea
                    value={selectedFrameNumbers.join(', ')}
                    onChange={(e) => {
                      const input = e.target.value;
                      const numbers = input.split(',').map(s => s.trim()).filter(s => s !== '');
                      const validNumbers = numbers.map(n => {
                        const num = parseFloat(n);
                        return isNaN(num) ? null : num;
                      }).filter(n => n !== null);
                      setSelectedFrames(new Set(validNumbers));
                    }}
                    className="banner-textarea"
                    placeholder="Enter frame numbers separated by commas..."
                    rows={3}
                  />
                </div>
              )}
              <div className="banner-run-section">
                <button 
                  onClick={async () => {
                    console.log('🚀 Run button clicked with frames:', selectedFrameNumbers);
                    
                    if (selectedFrameNumbers.length === 0) {
                      alert('Please select frames to process');
                      return;
                    }
                    
                    // Allow multiple tasks to run concurrently
                    
                    const taskId = `temp-${Date.now()}`;
                    
                    try {
                      // Add task to queue with submitting status
                      setRunningTasks(prev => [...prev, { 
                        id: taskId,
                        status: 'submitting', 
                        frames: [...selectedFrameNumbers],
                        startTime: Date.now()
                      }]);
                      
                      // Clear selections immediately
                      setSelectedFrames(new Set());
                      
                      // Submit interpolation job to backend
                      const response = await fetch(`http://localhost:8500/api/interpolate/${repoUuid}`, {
                        method: 'POST',
                        headers: {
                          'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                          target_frames: selectedFrameNumbers
                        })
                      });
                      
                      if (response.ok) {
                        const result = await response.json();
                        console.log('✅ Interpolation job submitted:', result);
                        
                        // Update task with real ID and running status
                        setRunningTasks(prev => prev.map(task => 
                          task.id === taskId 
                            ? { ...task, id: result.task_id, status: 'running' }
                            : task
                        ));
                        
                        // Start polling for this specific task
                        pollTaskStatus(result.task_id, repoUuid);
                        
                        console.log(`✅ Task ${result.task_id} started for ${selectedFrameNumbers.length} frames`);
                        
                      } else {
                        const error = await response.text();
                        console.error('❌ Interpolation failed:', error);
                        alert(`❌ Failed to start interpolation: ${error}`);
                        
                        // Remove failed task
                        setRunningTasks(prev => prev.filter(task => task.id !== taskId));
                      }
                      
                    } catch (error) {
                      console.error('❌ Network error:', error);
                      alert(`❌ Network error: ${error.message}`);
                      
                      // Remove failed task
                      setRunningTasks(prev => prev.filter(task => task.id !== taskId));
                    }
                  }}
                  className="banner-run-btn"
                  title="Run interpolation on selected frames"
                  disabled={selectedFrameNumbers.length === 0}
                >
                  🚀 Run Interpolation
                </button>
              </div>
            </div>
          )}

          <div className="frames-grid" key={`frames-${forceRefreshCounter}-${currentPage}`}>
            {frames.map((framePath, index) => {
              const frameNumber = frameNumbers[index] !== undefined ? frameNumbers[index] : (currentPage - 1) * framesPerPage + index + 1;
              const isSelected = selectedFrames.has(frameNumber);
              
              return (
                <div 
                  key={index} 
                  className={`frame-container ${isSelected ? 'selected' : ''}`}
                  onClick={() => toggleFrameSelection(frameNumber)}
                  style={{ cursor: 'pointer' }}
                >
                <img 
                  src={`http://localhost:8500/${framePath}?cb=${cacheBuster}&fc=${forceRefreshCounter}`}
                    alt={`Frame ${frameNumber}`}
                  className="frame-image"
                  loading="lazy"
                  onError={(e) => {
                    console.error(`Failed to load image: ${framePath}`);
                    e.target.style.display = 'none';
                  }}
                />
                <div className="frame-info">
                    {frameNumber}
                  </div>
                </div>
              );
            })}
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
      <Route path="/:repoUuid" element={<FrameDisplay />} />
    </Routes>
  );
}

export default App; 