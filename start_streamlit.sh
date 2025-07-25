#!/bin/bash

# Set environment variables for protobuf
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python

# Start Redis server
redis-server --daemonize yes

# Start the Redis worker in the background
python frame_interpolation_server.py &

# Start the Streamlit app in headless mode (this will run in the foreground)
streamlit run app.py --server.headless true 