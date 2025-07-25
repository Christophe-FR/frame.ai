import React, { useState, useEffect, useCallback } from 'react';
import './App.css';

function App() {
  const [frames, setFrames] = useState([]);
  const [currentPage, setCurrentPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [totalFrames, setTotalFrames] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [error, setError] = useState(null);
  const framesPerPage = 12; // 3x4 grid

  // Fetch frames from the FastAPI backend
  const fetchFrames = useCallback(async () => {
    try {
      setError(null);
      const url = searchQuery 
        ? `/api/frames/search/${encodeURIComponent(searchQuery)}`
        : '/api/frames';
      
      const response = await fetch(url);
      if (response.ok) {
        const data = await response.json();
        setFrames(data.frames || []);
        setTotalFrames(data.total || 0);
      } else {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
    } catch (error) {
      console.error('Error fetching frames:', error);
      setError(error.message);
    } finally {
      setLoading(false);
    }
  }, [searchQuery]);

  // Poll for updates every 2 seconds
  useEffect(() => {
    fetchFrames();
    
    const interval = setInterval(fetchFrames, 2000);
    return () => clearInterval(interval);
  }, [fetchFrames]); // Now includes fetchFrames as dependency

  // Calculate pagination
  const totalPages = Math.ceil(frames.length / framesPerPage);
  const startIndex = currentPage * framesPerPage;
  const endIndex = startIndex + framesPerPage;
  const currentFrames = frames.slice(startIndex, endIndex);

  // Navigation functions
  const goToPage = (page) => {
    setCurrentPage(Math.max(0, Math.min(page, totalPages - 1)));
  };

  const goToNextPage = () => goToPage(currentPage + 1);
  const goToPrevPage = () => goToPage(currentPage - 1); // Fixed: was currentPage + 1

  // Handle search
  const handleSearch = (e) => {
    e.preventDefault();
    setCurrentPage(0); // Reset to first page when searching
    fetchFrames();
  };

  // Format file size
  const formatFileSize = (bytes) => {
    if (bytes === null || bytes === undefined) return 'Unknown';
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    if (bytes === 0) return '0 Bytes';
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
  };

  if (loading && frames.length === 0) {
    return <div className="loading">Loading frames...</div>;
  }

  return (
    <div className="app">
      <header className="header">
        <h1>Frames Viewer</h1>
        <div className="info">
          <span>Total frames: {totalFrames}</span>
          <span>Page {currentPage + 1} of {totalPages}</span>
        </div>
        
        {/* Search form */}
        <form onSubmit={handleSearch} className="search-form">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search frames..."
            className="search-input"
          />
          <button type="submit" className="search-button">
            Search
          </button>
          {searchQuery && (
            <button 
              type="button" 
              onClick={() => {
                setSearchQuery('');
                setCurrentPage(0);
              }}
              className="clear-button"
            >
              Clear
            </button>
          )}
        </form>
      </header>

      {error && (
        <div className="error-message">
          Error: {error}
        </div>
      )}

      <div className="frames-grid">
        {currentFrames.map((frame, index) => (
          <div key={frame.name} className="frame-item">
            <img 
              src={`/api/frames/${encodeURIComponent(frame.name)}`} 
              alt={frame.name}
              onError={(e) => {
                e.target.style.display = 'none';
                e.target.nextSibling.style.display = 'block';
              }}
            />
            <div className="frame-error" style={{ display: 'none' }}>
              Failed to load
            </div>
            <div className="frame-info">
              <div className="frame-name">{frame.name}</div>
              {frame.size && (
                <div className="frame-size">{formatFileSize(frame.size)}</div>
              )}
            </div>
          </div>
        ))}
      </div>

      {totalPages > 1 && (
        <div className="pagination">
          <button 
            onClick={goToPrevPage} 
            disabled={currentPage === 0}
            className="nav-button"
          >
            Previous
          </button>
          
          <div className="page-numbers">
            {Array.from({ length: totalPages }, (_, i) => (
              <button
                key={i}
                onClick={() => goToPage(i)}
                className={`page-button ${currentPage === i ? 'active' : ''}`}
              >
                {i + 1}
              </button>
            ))}
          </div>
          
          <button 
            onClick={goToNextPage} 
            disabled={currentPage === totalPages - 1}
            className="nav-button"
          >
            Next
          </button>
        </div>
      )}

      {frames.length === 0 && !loading && (
        <div className="no-frames">
          {searchQuery 
            ? `No frames found matching "${searchQuery}"`
            : "No frames found. Make sure the frames folder exists and contains images."
          }
        </div>
      )}
    </div>
  );
}

export default App; 