import numpy as np
import scipy.io.wavfile as wav
from scipy.signal import butter, filtfilt, correlate
import sys
import os
import csv

# --------------------------------------------------
# General Broadband Filter for Sweeps and Chirps
# --------------------------------------------------
def bandpass_broad(data, fs):
    # Filter between 300 Hz and 8000 Hz to cover the sweep and chirps
    low = 20
    high = 8000
    nyq = 0.5 * fs
    b, a = butter(4, [low/nyq, high/nyq], btype='band')
    return filtfilt(b, a, data, axis=0)

# --------------------------------------------------
# Delay computation with constrained lag
# --------------------------------------------------
def compute_delay(sig1, sig2, fs):
    # Using method='fft' for significant speedup
    corr = correlate(sig1, sig2, mode='full', method='fft')

    # Limit search to ±5 ms to cover reasonable array dimensions
    max_lag = int(0.005 * fs)
    center = len(corr) // 2

    corr_window = corr[center - max_lag : center + max_lag + 1]
    lag = np.argmax(corr_window) - max_lag

    return lag / fs

# --------------------------------------------------
# Event extraction (find each sound)
# --------------------------------------------------
def extract_events(data, fs):
    # Detect sound events based on the amplitude envelope of the first channel
    mono = np.abs(data[:, 0])
    
    # 50 ms smoothing window
    window_len = int(0.05 * fs)
    kernel = np.ones(window_len) / window_len
    envelope = np.convolve(mono, kernel, mode='same')
    
    # Adaptive threshold: 10% of the maximum envelope peak
    threshold = np.max(envelope) * 0.1
    is_active = envelope > threshold
    
    # Find where the state changes (inactive to active and vice versa)
    edges = np.diff(is_active.astype(int))
    starts = np.where(edges == 1)[0]
    ends = np.where(edges == -1)[0]
    
    # Handle cases where the audio starts or ends while a sound is playing
    if is_active[0]:
        starts = np.insert(starts, 0, 0)
    if is_active[-1]:
        ends = np.append(ends, len(is_active) - 1)
        
    events = []
    for s, e in zip(starts, ends):
        # Combine closely spaced sounds (e.g. the rapid chirps) or keep them separated.
        # Here we just keep any sound block longer than 50ms.
        if (e - s) > 0.05 * fs:
            # Expand the window slightly to capture the very beginning and end of the sound
            s_pad = max(0, s - int(0.05 * fs))
            e_pad = min(len(data), e + int(0.05 * fs))
            events.append((s_pad, e_pad))
            
    return events

# --------------------------------------------------
# Main
# --------------------------------------------------
def main():
    print("Analyzing delay between channels for each sound event...")

    if len(sys.argv) < 2:
        print("Usage: python3 analise.py file.wav")
        return

    filename = sys.argv[1]
    fs, data = wav.read(filename)

    print(f"\nFile: {filename}")
    print(f"Sample rate: {fs}")
    print(f"Shape: {data.shape}")

    if data.ndim < 2:
        print("Error: not multi-channel audio")
        return

    # Proper conversion from S32_LE
    if data.dtype == np.int32:
        data = data.astype(np.float32) / 2147483648.0
    elif data.dtype == np.int16:
        data = data.astype(np.float32) / 32768.0
    else:
        data = data.astype(np.float32)

    # Remove DC offset & NaN
    data -= np.mean(data, axis=0)
    data = np.nan_to_num(data, nan=0.0, posinf=0.0, neginf=0.0)

    # Filter out room noise outside the buzzer's frequency range
    print("\nFiltering broadband sweep/chirp frequencies (300Hz - 8kHz)...")
    filtered = bandpass_broad(data, fs)
    filtered = np.nan_to_num(filtered)
    
    # Find individual sounds
    events = extract_events(filtered, fs)
    print(f"Found {len(events)} distinct sound events in the recording.")

    if not events:
        print("No sound events found. Ensure the threshold is correct and sound was recorded.")
        return

    num_channels = filtered.shape[1]
    
    # Dictionary to store all delays for every pair across all events
    pair_delays = { (i, j): [] for i in range(num_channels) for j in range(i + 1, num_channels) }

    csv_filename = os.path.splitext(filename)[0] + "_delays.csv"
    print(f"\nWriting detailed results to: {csv_filename}")
    
    with open(csv_filename, 'w', newline='') as csvfile:
        csvwriter = csv.writer(csvfile)
        
        # Write CSV Headers
        headers = ["Event_ID", "Duration_s"]
        for i in range(num_channels):
            for j in range(i + 1, num_channels):
                headers.append(f"Mic{i}_vs_Mic{j}_ms")
        csvwriter.writerow(headers)

        # Analyze each sound individually
        for idx, (start, end) in enumerate(events):
            duration_sec = (end - start) / fs
            print(f"\n--- Event {idx + 1} ({duration_sec:.2f}s duration) ---")
            
            segment = filtered[start:end]
            row = [idx + 1, f"{duration_sec:.4f}"]
            
            for i in range(num_channels):
                for j in range(i + 1, num_channels):
                    sig1 = segment[:, i]
                    sig2 = segment[:, j]

                    # Skip weak signals inside the segment
                    if np.std(sig1) < 1e-6 or np.std(sig2) < 1e-6:
                        print(f"Mic {i} vs {j}: skipped (weak signal)")
                        row.append("NaN")
                        continue

                    delay = compute_delay(sig1, sig2, fs)
                    pair_delays[(i, j)].append(delay)
                    delay_ms = delay * 1000
                    row.append(f"{delay_ms:.4f}")
                    print(f"Mic {i} vs Mic {j}: {delay_ms:.4f} ms")
                    
            csvwriter.writerow(row)

    # Calculate and print the final averages
    print("\n========================================")
    print("FINAL AVERAGED DELAYS ACROSS ALL SOUNDS")
    print("========================================")
    for (i, j), delays in pair_delays.items():
        if delays:
            avg_delay = np.mean(delays)
            std_delay = np.std(delays)
            print(f"Mic {i} vs Mic {j}: Average = {avg_delay * 1000:>7.4f} ms  (StdDev = {std_delay * 1000:.4f} ms)")
        else:
            print(f"Mic {i} vs Mic {j}: No valid delays found.")

if __name__ == "__main__":
    main()