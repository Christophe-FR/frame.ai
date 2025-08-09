#!/usr/bin/env python3
"""
Test Video Interpolation Jobs
=============================

Simple script to submit video interpolation jobs to the Celery worker.
"""

import time
from video_interpolation_server import interpolate_video_frames, health_check

def test_interpolation_job():
    """Submit a test interpolation job."""
    print("🧪 Testing Video Interpolation Server")
    print("=" * 40)
    
    # Test health check first
    print("🔍 Checking server health...")
    health_task = health_check.delay()
    health_result = health_task.get(timeout=10)
    print(f"✅ Health check: {health_result}")
    
    # Submit interpolation job
    print("\n📤 Submitting interpolation job...")
    repo_path = "static/my"  # Path to your video frames
    target_frames = [4.5]  # Frame to interpolate between 4 and 5
    
    task = interpolate_video_frames.delay(repo_path, target_frames)
    print(f"🆔 Task ID: {task.id}")
    print(f"📊 Initial status: {task.state}")
    
    # Monitor progress
    print("\n⏳ Monitoring progress...")
    while not task.ready():
        if task.state == 'PROGRESS':
            meta = task.info
            current = meta.get('current', 0)
            total = meta.get('total', 1)
            status = meta.get('status', 'Processing...')
            print(f"📊 Progress: {current}/{total} - {status}")
        time.sleep(1)
    
    # Get final result
    if task.successful():
        result = task.result
        print(f"\n✅ Task completed successfully!")
        print(f"📋 Result: {result}")
    else:
        print(f"\n❌ Task failed: {task.traceback}")
    
    return task

if __name__ == '__main__':
    print("💡 To run this test:")
    print("1. Start the interpolation worker:")
    print("   celery -A video_interpolation_server worker --loglevel=info")
    print("2. Run this test:")
    print("   python test_interpolation.py")
    print()
    
    # Run the test
    test_interpolation_job() 