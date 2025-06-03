#!/bin/bash

# video_process.sh - Video processing with quality preservation and frame extraction
# Supports common formats while maintaining similar properties to the original
# Now with automatic frame extraction for further processing

set -e

INPUT="$1"

if [ -z "$INPUT" ]; then
    echo "Usage: $0 input_video"
    echo "  Frames will be automatically extracted to RAM"
    exit 1
fi

# Generate output filename based on input
INPUT_BASE="${INPUT%.*}"
INPUT_EXT="${INPUT##*.}"
OUTPUT="${INPUT_BASE}_out.${INPUT_EXT}"
echo "Output will be saved as: $OUTPUT"

# Create frames directory in RAM
FRAMES_DIR="/dev/shm/${INPUT_BASE}_frames"
mkdir -p "$FRAMES_DIR"
echo "Frames will be extracted to RAM: $FRAMES_DIR"

# Create temporary files with safer names
TEMP_VIDEO="temp_video_$$.${INPUT_EXT}"
TEMP_AUDIO="temp_audio_$$.aac"

# Set up cleanup trap
trap 'rm -f "$TEMP_VIDEO" "$TEMP_AUDIO"' EXIT

echo "[1] Extracting video metadata..."
# Get core video properties
FRAMERATE=$(ffprobe -v 0 -select_streams v:0 -show_entries stream=r_frame_rate -of default=noprint_wrappers=1:nokey=1 "$INPUT")
WIDTH=$(ffprobe -v error -select_streams v:0 -show_entries stream=width -of csv=p=0 "$INPUT")
HEIGHT=$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of csv=p=0 "$INPUT")
VCODEC=$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of default=noprint_wrappers=1:nokey=1 "$INPUT")
PIX_FMT=$(ffprobe -v error -select_streams v:0 -show_entries stream=pix_fmt -of default=noprint_wrappers=1:nokey=1 "$INPUT")
VIDEO_BITRATE=$(ffprobe -v error -select_streams v:0 -show_entries stream=bit_rate -of default=noprint_wrappers=1:nokey=1 "$INPUT")

# Get color information
COLOR_SPACE=$(ffprobe -v error -select_streams v:0 -show_entries stream=color_space -of default=noprint_wrappers=1:nokey=1 "$INPUT" 2>/dev/null || echo "")
COLOR_PRIMARIES=$(ffprobe -v error -select_streams v:0 -show_entries stream=color_primaries -of default=noprint_wrappers=1:nokey=1 "$INPUT" 2>/dev/null || echo "")
COLOR_TRANSFER=$(ffprobe -v error -select_streams v:0 -show_entries stream=color_transfer -of default=noprint_wrappers=1:nokey=1 "$INPUT" 2>/dev/null || echo "")

# Get audio properties
ACODEC=$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of default=noprint_wrappers=1:nokey=1 "$INPUT" 2>/dev/null || echo "none")
AUDIO_BITRATE=$(ffprobe -v error -select_streams a:0 -show_entries stream=bit_rate -of default=noprint_wrappers=1:nokey=1 "$INPUT" 2>/dev/null || echo "")

echo "Source: $WIDTH×$HEIGHT, codec: $VCODEC, pixel format: $PIX_FMT"
echo "Video bitrate: $VIDEO_BITRATE bits/s"
echo "Audio: $ACODEC, bitrate: $AUDIO_BITRATE bits/s"

# Extract frames to RAM
echo "[2] Extracting frames to RAM ($FRAMES_DIR)..."
ffmpeg -i "$INPUT" -vsync 0 -q:v 1 "$FRAMES_DIR/frame_%06d.png"
echo "Frames extracted successfully"

# Simple quality detection - enhance lower quality videos more
if [ -n "$VIDEO_BITRATE" ] && [ "$VIDEO_BITRATE" -lt 2000000 ]; then
    BITRATE_MULT=1.2
    echo "Lower quality source detected, enhancing bitrate by 20%"
else
    BITRATE_MULT=1.1
    echo "Standard quality source, enhancing bitrate by 10%"
fi

echo "[3] Extracting audio..."
if [ "$ACODEC" != "none" ]; then
    ffmpeg -y -i "$INPUT" -vn -c:a copy "$TEMP_AUDIO"
else
    echo "No audio stream found, skipping audio extraction"
fi

echo "[4] Processing video..."
# If no bitrate available, set reasonable defaults based on resolution
if [ -z "$VIDEO_BITRATE" ]; then
    if [ "$WIDTH" -ge 1920 ]; then # HD or higher
        VIDEO_BITRATE=8000000   # 8 Mbps
    else # SD
        VIDEO_BITRATE=4000000   # 4 Mbps
    fi
fi

# Calculate target bitrate with proper rounding
TARGET_BITRATE=$(echo "$VIDEO_BITRATE * $BITRATE_MULT" | bc | awk '{printf("%d", $1 + 0.5)}')
echo "Targeting bitrate: $TARGET_BITRATE bits/s"

# Process video based on codec
case "$VCODEC" in
    h264|h265|hevc)
        # H.264/H.265 processing
        CODEC_LIB="libx264"
        if [[ "$VCODEC" == "hevc" || "$VCODEC" == "h265" ]]; then
            CODEC_LIB="libx265"
        fi
        
        # Add color space parameters if available
        COLOR_OPTS=""
        if [ -n "$COLOR_SPACE" ]; then
            COLOR_OPTS="-colorspace $COLOR_SPACE -color_primaries $COLOR_PRIMARIES -color_trc $COLOR_TRANSFER"
        fi
        
        ffmpeg -y -i "$INPUT" -an -c:v $CODEC_LIB -pix_fmt "$PIX_FMT" -preset fast \
            -b:v $TARGET_BITRATE $COLOR_OPTS \
            -vf "scale=${WIDTH}:${HEIGHT}" "$TEMP_VIDEO"
        ;;
    *)
        # Generic approach for other codecs
        ffmpeg -y -i "$INPUT" -an -c:v "$VCODEC" -pix_fmt "$PIX_FMT" \
            -b:v $TARGET_BITRATE -vf "scale=${WIDTH}:${HEIGHT}" "$TEMP_VIDEO"
        ;;
esac

echo "[5] Merging audio back into final video..."
# Check if we have audio to merge
if [ "$ACODEC" != "none" ] && [ -s "$TEMP_AUDIO" ]; then
    ffmpeg -y -i "$TEMP_VIDEO" -i "$TEMP_AUDIO" -i "$INPUT" \
        -map 0:v:0 -map 1:a:0 \
        -map_metadata 2 -map_chapters 2 \
        -c:v copy -c:a "$ACODEC" -b:a "$AUDIO_BITRATE" \
        "$OUTPUT"
else
    # No audio, just copy the video
    ffmpeg -y -i "$TEMP_VIDEO" -i "$INPUT" \
        -map 0:v:0 \
        -map_metadata 1 -map_chapters 1 \
        -c:v copy \
        "$OUTPUT"
fi

echo "✅ Done! Output saved to: $OUTPUT"
echo ""
echo "Original bitrate: $VIDEO_BITRATE bits/s"
echo "Target bitrate: $TARGET_BITRATE bits/s (${BITRATE_MULT}x)"

# Count frames and provide info
FRAME_COUNT=$(ls -1 "$FRAMES_DIR" | wc -l)
echo ""
echo "Extracted $FRAME_COUNT frames to RAM: $FRAMES_DIR"

