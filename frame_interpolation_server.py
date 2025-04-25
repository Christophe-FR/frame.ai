import redis
import json
import base64
import numpy as np
import cv2
from job_manager import JobManager, JobStatus
from utils import interpolate_frames
import yaml
import time

# Load configuration
with open("config.yaml", 'r') as f:
    config = yaml.safe_load(f)

def process_job(job_data: dict) -> dict:
    """Process a single job."""
    try:
        # Decode frames
        frame1_data = base64.b64decode(job_data['frame1'])
        frame2_data = base64.b64decode(job_data['frame2'])
        
        frame1 = cv2.imdecode(np.frombuffer(frame1_data, dtype=np.uint8), cv2.IMREAD_COLOR)
        frame2 = cv2.imdecode(np.frombuffer(frame2_data, dtype=np.uint8), cv2.IMREAD_COLOR)
        
        # Convert to RGB
        frame1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2RGB)
        frame2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2RGB)
        
        # Interpolate frames
        num_frames = job_data.get('num_frames', 1)
        interpolated_frames = interpolate_frames(frame1, frame2, num_frames)
        
        # Encode result frames
        result_frames = []
        for frame in interpolated_frames:
            _, buffer = cv2.imencode('.png', cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
            result_frames.append(base64.b64encode(buffer).decode('utf-8'))
        
        return {
            'frames': result_frames
        }
        
    except Exception as e:
        return {
            'error': str(e)
        }

def main():
    # Initialize job manager
    job_manager = JobManager()
    
    print("Frame interpolation server started. Waiting for jobs...")
    
    while True:
        # Get next job
        job = job_manager.get_next_job()
        
        if job is None:
            # No jobs available, wait a bit
            time.sleep(0.1)
            continue
        
        try:
            # Process job
            result = process_job(job['data'])
            
            # Update job status
            if 'error' in result:
                job_manager.update_job_status(job['id'], JobStatus.FAILED, result)
            else:
                job_manager.update_job_status(job['id'], JobStatus.COMPLETED, result)
                
        except Exception as e:
            # Update job status to failed
            job_manager.update_job_status(
                job['id'],
                JobStatus.FAILED,
                {'error': str(e)}
            )

if __name__ == "__main__":
    main()