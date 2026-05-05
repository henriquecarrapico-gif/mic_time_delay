#!/bin/bash

# Record audio with arecord using timestamped filename
# Usage: ./record_with_timestamp.sh [optional_prefix]

# Get timestamp (YYYY-MM-DD_HH-MM-SS format)
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")

# Optional prefix from command line argument
PREFIX="${1:-recording}"

# Create filename
OUTPUT_FILE="${PREFIX}_${TIMESTAMP}.wav"

echo "Recording to: $OUTPUT_FILE"
echo "Press Ctrl+C to stop recording..."

# Run arecord with the timestamped filename
#arecord -D hw:2,0 -f S32_LE -r 48000 -V stereo -vv -c 2 "$OUTPUT_FILE"
arecord -D hw:0 -f S32_LE -r 48000 -vv -c 4 "$OUTPUT_FILE"

# Kill the buzzer when arecord finishes normally
#kill $BUZZER_PID 2>/dev/null
