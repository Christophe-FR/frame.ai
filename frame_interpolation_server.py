import redis
import json
import numpy as np
import cv2
from utils import interpolate_frames
from frame_codec import encode_frame_to_base64, decode_base64_to_frame
import yaml
import time
import logging

# Initialize logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configuration
with open("config.yaml", 'r') as f:
    cfg = yaml.safe_load(f)

class FrameInterpolationServer:
    def __init__(self, host: str = cfg['redis']['host'], port: int = cfg['redis']['port'], task_queue: str = cfg['queues']['task'], result_queue: str = cfg['queues']['result']):
        """Initialize the frame interpolation server.
        
        Args:
            host: Redis host address
            port: Redis port number
            task_queue: Redis queue name for tasks
            result_queue: Redis queue name for results
        """
        # Initialize Redis connection
        self.redis = redis.Redis(host=host, port=port)
        self.task_queue = task_queue
        self.result_queue = result_queue
        
    def process_frames(self, frame1_data: str, frame2_data: str, num_frames: int = 1) -> dict:
        """Process frames and return interpolated results.
        
        Args:
            frame1_data: Base64 encoded first frame
            frame2_data: Base64 encoded second frame
            num_frames: Number of frames to interpolate between the two frames
            
        Returns:
            Dictionary containing either the interpolated frames or an error message
        """
        try:
            logger.info("Decoding frames...")
            # Decode frames using frame_codec
            frame1 = decode_base64_to_frame(frame1_data)
            frame2 = decode_base64_to_frame(frame2_data)
            
            logger.info("Interpolating frames...")
            # Interpolate frames
            interpolated_frames = interpolate_frames(frame1, frame2, num_frames)
            
            logger.info("Encoding result frames...")
            # Encode result frames using frame_codec
            result_frames = [encode_frame_to_base64(frame) for frame in interpolated_frames]
            
            logger.info("Processing complete!")
            return {
                'frames': result_frames
            }
            
        except Exception as e:
            error_msg = f"Error in process_frames: {str(e)}"
            logger.error(error_msg)
            return {
                'error': error_msg
            }
            
    def run(self):
        """Run the server in a loop, processing frames from the queue."""
        logger.info("Frame interpolation server started.")
        
        while True:
            try:
                logger.info("Waiting for job...")
                
                # Get next frame pair from Redis
                data = self.redis.blpop(self.task_queue)
                    
                _, message = data
                task_data = json.loads(message)
                logger.info(f"Received task {task_data['task_id']}")
                
                # Process frames
                result = self.process_frames(
                    task_data['frame1'],
                    task_data['frame2'],
                    task_data.get('num_frames', 1)
                )
                
                # Send result back with task_id
                response = {
                    'frames': result.get('frames', []),
                    'error': result.get('error')
                }
                # Store result with task_id as key
                self.redis.set(f"{self.result_queue}:{task_data['task_id']}", json.dumps(response))
                logger.info(f"Sent result for task {task_data['task_id']}")
                
            except Exception as e:
                logger.error(f"Error in server loop: {str(e)}")
                time.sleep(1)

def main():
    server = FrameInterpolationServer()
    server.run()

if __name__ == "__main__":
    main()