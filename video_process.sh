#!/bin/bash

# video_process.sh - Rebuild video from extracted frames, preserving quality and metadata

set -e

INPUT="$1"

if [ -z "$INPUT" ]; then
    echo "Usage: $0 input_video"
    echo "  Frames will be automatically extracted to RAM"
    exit 1
fi

INPUT_BASE="${INPUT%.*}"
INPUT_EXT="${INPUT##*.}"
OUTPUT="${INPUT_BASE}_out.${INPUT_EXT}"
echo "Output will be saved as: $OUTPUT"

FRAMES_DIR="/dev/shm/${INPUT_BASE}_frames"
mkdir -p "$FRAMES_DIR"
echo "Frames will be extracted to RAM: $FRAMES_DIR"

TEMP_VIDEO="temp_video_$$.${INPUT_EXT}"
TEMP_AUDIO="temp_audio_$$.aac"

trap 'rm -f "$TEMP_VIDEO" "$TEMP_AUDIO"' EXIT

echo "[1] Extracting video metadata..."
FRAMERATE=$(ffprobe -v 0 -select_streams v:0 -show_entries stream=r_frame_rate -of default=noprint_wrappers=1:nokey=1 "$INPUT")
WIDTH=$(ffprobe -v error -select_streams v:0 -show_entries stream=width -of csv=p=0 "$INPUT")
HEIGHT=$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of csv=p=0 "$INPUT")
VCODEC=$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of default=noprint_wrappers=1:nokey=1 "$INPUT")
PIX_FMT=$(ffprobe -v error -select_streams v:0 -show_entries stream=pix_fmt -of default=noprint_wrappers=1:nokey=1 "$INPUT")
VIDEO_BITRATE=$(ffprobe -v error -select_streams v:0 -show_entries stream=bit_rate -of default=noprint_wrappers=1:nokey=1 "$INPUT")

COLOR_SPACE=$(ffprobe -v error -select_streams v:0 -show_entries stream=color_space -of default=noprint_wrappers=1:nokey=1 "$INPUT" 2>/dev/null || echo "")
COLOR_PRIMARIES=$(ffprobe -v error -select_streams v:0 -show_entries stream=color_primaries -of default=noprint_wrappers=1:nokey=1 "$INPUT" 2>/dev/null || echo "")
COLOR_TRANSFER=$(ffprobe -v error -select_streams v:0 -show_entries stream=color_transfer -of default=noprint_wrappers=1:nokey=1 "$INPUT" 2>/dev/null || echo "")

ACODEC=$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of default=noprint_wrappers=1:nokey=1 "$INPUT" 2>/dev/null || echo "none")
AUDIO_BITRATE=$(ffprobe -v error -select_streams a:0 -show_entries stream=bit_rate -of default=noprint_wrappers=1:nokey=1 "$INPUT" 2>/dev/null || echo "")

echo "Source: $WIDTH×$HEIGHT, codec: $VCODEC, pixel format: $PIX_FMT"
echo "Video bitrate: $VIDEO_BITRATE bits/s"
echo "Audio: $ACODEC, bitrate: $AUDIO_BITRATE bits/s"

echo "[2] Extracting frames to RAM ($FRAMES_DIR)..."
ffmpeg -i "$INPUT" -vsync 0 -q:v 1 "$FRAMES_DIR/frame_%06d.png"
echo "Frames extracted successfully"

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

echo "[4] Rebuilding video from frames..."
if [ -z "$VIDEO_BITRATE" ]; then
    if [ "$WIDTH" -ge 1920 ]; then
        VIDEO_BITRATE=8000000
    else
        VIDEO_BITRATE=4000000
    fi
fi

TARGET_BITRATE=$(echo "$VIDEO_BITRATE * $BITRATE_MULT" | bc | awk '{printf("%d", $1 + 0.5)}')
echo "Targeting bitrate: $TARGET_BITRATE bits/s"

case "$VCODEC" in
    h264|h265|hevc)
        CODEC_LIB="libx264"
        [ "$VCODEC" = "h265" ] || [ "$VCODEC" = "hevc" ] && CODEC_LIB="libx265"
        
        COLOR_OPTS=""
        if [ -n "$COLOR_SPACE" ]; then
            COLOR_OPTS="-colorspace $COLOR_SPACE -color_primaries $COLOR_PRIMARIES -color_trc $COLOR_TRANSFER"
        fi

        ffmpeg -y -framerate "$FRAMERATE" -i "$FRAMES_DIR/frame_%06d.png" \
            -an -c:v $CODEC_LIB -pix_fmt "$PIX_FMT" -preset fast \
            -b:v $TARGET_BITRATE $COLOR_OPTS \
            -vf "scale=${WIDTH}:${HEIGHT}" "$TEMP_VIDEO"
        ;;
    *)
        ffmpeg -y -framerate "$FRAMERATE" -i "$FRAMES_DIR/frame_%06d.png" \
            -an -c:v "$VCODEC" -pix_fmt "$PIX_FMT" \
            -b:v $TARGET_BITRATE -vf "scale=${WIDTH}:${HEIGHT}" "$TEMP_VIDEO"
        ;;
esac

echo "[5] Merging audio back into final video..."
if [ "$ACODEC" != "none" ] && [ -s "$TEMP_AUDIO" ]; then
    ffmpeg -y -i "$TEMP_VIDEO" -i "$TEMP_AUDIO" -i "$INPUT" \
        -map 0:v:0 -map 1:a:0 \
        -map_metadata 2 -map_chapters 2 \
        -c:v copy -c:a "$ACODEC" -b:a "$AUDIO_BITRATE" \
        "$OUTPUT"
else
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

FRAME_COUNT=$(ls -1 "$FRAMES_DIR" | wc -l)
echo ""
echo "Extracted $FRAME_COUNT frames to RAM: $FRAMES_DIR"
