#!/bin/bash

# compare_videos.sh - Compare two video files for encoding similarities
# Usage: ./compare_videos.sh video1.mp4 video2.mp4

set -e

if [ $# -ne 2 ]; then
    echo "Usage: $0 <video1> <video2>"
    echo "Example: $0 input.mp4 input_out.mp4"
    exit 1
fi

VIDEO1="$1"
VIDEO2="$2"

if [ ! -f "$VIDEO1" ]; then
    echo "Error: File not found: $VIDEO1"
    exit 1
fi

if [ ! -f "$VIDEO2" ]; then
    echo "Error: File not found: $VIDEO2"
    exit 1
fi

echo "===== Comparing Video Files ====="
echo "Video 1: $VIDEO1"
echo "Video 2: $VIDEO2"
echo "=============================="

# Function to extract specific details
get_video_detail() {
    local file="$1"
    local detail="$2"
    local stream="$3"
    
    ffprobe -v error -select_streams "$stream" -show_entries stream="$detail" \
        -of default=noprint_wrappers=1:nokey=1 "$file"
}

# Compare a specific detail
compare_detail() {
    local name="$1"
    local detail="$2"
    local stream="$3"
    
    local val1=$(get_video_detail "$VIDEO1" "$detail" "$stream")
    local val2=$(get_video_detail "$VIDEO2" "$detail" "$stream")
    
    printf "%-20s: %-30s %-30s " "$name" "$val1" "$val2"
    
    if [ "$val1" = "$val2" ]; then
        echo "[MATCH]"
    else
        echo "[DIFFERENT]"
    fi
}

# File size comparison
SIZE1=$(du -h "$VIDEO1" | awk '{print $1}')
SIZE1_BYTES=$(du -b "$VIDEO1" | awk '{print $1}')
SIZE2=$(du -h "$VIDEO2" | awk '{print $1}')
SIZE2_BYTES=$(du -b "$VIDEO2" | awk '{print $1}')

echo -e "\n===== File Size Comparison ====="
printf "%-20s: %-30s %-30s %s\n" "File Size" "$SIZE1 ($SIZE1_BYTES bytes)" "$SIZE2 ($SIZE2_BYTES bytes)" "[INFO]"

# Calculate size difference
if [ "$SIZE1_BYTES" -gt "$SIZE2_BYTES" ]; then
    DIFF=$(echo "scale=2; ($SIZE1_BYTES - $SIZE2_BYTES) * 100 / $SIZE1_BYTES" | bc)
    echo "Video 1 is $DIFF% larger than Video 2"
else
    DIFF=$(echo "scale=2; ($SIZE2_BYTES - $SIZE1_BYTES) * 100 / $SIZE1_BYTES" | bc)
    echo "Video 2 is $DIFF% larger than Video 1"
fi

echo
echo "===== Video Stream Details ====="
printf "%-20s: %-30s %-30s %s\n" "Parameter" "$VIDEO1" "$VIDEO2" "Status"
printf "%s\n" "----------------------------------------------------------------------"

# Video codec details
compare_detail "Video Codec" "codec_name" "v:0"
compare_detail "Profile" "profile" "v:0"
compare_detail "Pixel Format" "pix_fmt" "v:0"
compare_detail "Width" "width" "v:0"
compare_detail "Height" "height" "v:0"
compare_detail "Frame Rate" "r_frame_rate" "v:0"
compare_detail "Color Space" "color_space" "v:0"
compare_detail "Color Range" "color_range" "v:0"
compare_detail "Level" "level" "v:0"

echo
echo "===== Audio Stream Details ====="
printf "%-20s: %-30s %-30s %s\n" "Parameter" "$VIDEO1" "$VIDEO2" "Status"
printf "%s\n" "----------------------------------------------------------------------"

# Audio codec details
compare_detail "Audio Codec" "codec_name" "a:0"
compare_detail "Sample Rate" "sample_rate" "a:0"
compare_detail "Channels" "channels" "a:0"

echo
echo "===== Duration & Bitrate ====="
printf "%-20s: %-30s %-30s %s\n" "Parameter" "$VIDEO1" "$VIDEO2" "Status"
printf "%s\n" "----------------------------------------------------------------------"

# Get duration and bitrate from container
compare_detail "Duration" "duration" "v:0"
compare_detail "Video Bitrate" "bit_rate" "v:0"
compare_detail "Audio Bitrate" "bit_rate" "a:0"

echo
echo "===== Frame Count Check ====="
FRAMES1=$(ffprobe -v error -count_frames -select_streams v:0 -show_entries stream=nb_read_frames -of default=noprint_wrappers=1:nokey=1 "$VIDEO1")
FRAMES2=$(ffprobe -v error -count_frames -select_streams v:0 -show_entries stream=nb_read_frames -of default=noprint_wrappers=1:nokey=1 "$VIDEO2")

printf "%-20s: %-30s %-30s " "Frame Count" "$FRAMES1" "$FRAMES2"
if [ "$FRAMES1" = "$FRAMES2" ]; then
    echo "[MATCH]"
else
    echo "[DIFFERENT]"
fi

echo
echo "===== Summary ====="
echo "The files have been compared. Check the [DIFFERENT] entries to see what changed."
echo "Note: Some differences might be acceptable depending on your requirements."
echo "For example, different bitrates might still result in visually identical videos." 