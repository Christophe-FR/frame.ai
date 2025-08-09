#!/usr/bin/env python3
"""
Video Interpolation Server
==========================

A dedicated Celery worker that handles video frame interpolation tasks.
Uses the existing video_interpolate_frames function from utils.py.

Usage:
    python video_interpolation_server.py

Or run as Celery worker:
    celery -A video_interpolation_server worker --loglevel=info
"""

import os
import time
from typing import List
from celery import Celery
from utils import video_interpolate_frames

# Redis broker configuration
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Create Celery app
app = Celery('video_interpolation', broker=REDIS_URL, backend=REDIS_URL)

# Celery configuration
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    result_expires=3600,  # 1 hour
    task_routes={
        'video_interpolation_server.interpolate_video_frames': {'queue': 'interpolation'},
    },
    # Use solo pool to avoid CUDA/TensorFlow fork issues
    worker_pool='solo',
    worker_concurrency=1,
)

@app.task(bind=True, name='video_interpolation_server.interpolate_video_frames')
def interpolate_video_frames(self, repo_path: str, target_frames: List[float]):
    """
    Celery task for video frame interpolation.
    
    Args:
        repo_path: Path to the repository containing video frames
        target_frames: List of frame numbers to interpolate
        
    Returns:
        Dict with interpolation results
    """
    try:
        # Update task state
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 0, 
                'total': len(target_frames), 
                'status': f'Starting interpolation of {len(target_frames)} frames...'
            }
        )
        
        print(f"🎬 Starting video interpolation for {repo_path}")
        print(f"🎯 Target frames: {target_frames}")
        
        start_time = time.time()
        
        # Update progress
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 0, 
                'total': len(target_frames), 
                'status': 'Analyzing frame dependencies...'
            }
        )
        
        # Call the actual interpolation function from utils.py
        video_interpolate_frames(repo_path, target_frames)
        
        processing_time = time.time() - start_time
        
        # Update final progress
        self.update_state(
            state='PROGRESS',
            meta={
                'current': len(target_frames), 
                'total': len(target_frames), 
                'status': 'Interpolation completed!'
            }
        )
        
        result = {
            'repo_path': repo_path,
            'target_frames': target_frames,
            'frames_interpolated': len(target_frames),
            'processing_time': processing_time,
            'status': 'completed'
        }
        
        print(f"✅ Video interpolation completed in {processing_time:.2f} seconds")
        return result
        
    except Exception as exc:
        print(f"❌ Error during video interpolation: {exc}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(exc), 'repo_path': repo_path}
        )
        raise exc

@app.task(name='video_interpolation_server.health_check')
def health_check():
    """Simple health check task."""
    return {
        'status': 'healthy',
        'timestamp': time.time(),
        'worker': 'video_interpolation_server'
    }

if __name__ == '__main__':
    print("🚀 Video Interpolation Server")
    print("=" * 40)
    print("✅ Ready to process frame interpolation tasks")
    print("📡 Connected to Redis:", REDIS_URL)
    print("🔧 Queue: interpolation")
    print("")
    print("💡 To start as worker:")
    print("   celery -A video_interpolation_server worker --loglevel=info")
    print("")
    print("💡 To submit test job:")
    print("   from video_interpolation_server import interpolate_video_frames")
    print("   task = interpolate_video_frames.delay('/path/to/repo', [1.5, 2.5])")
    print("")
    
    # Test the health check
    print("🧪 Testing health check...")
    try:
        health_result = health_check()
        print(f"✅ Health check passed: {health_result}")
    except Exception as e:
        print(f"❌ Health check failed: {e}") 