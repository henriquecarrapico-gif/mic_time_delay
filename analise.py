import numpy as np
import scipy.io.wavfile as wav
from scipy.signal import butter, filtfilt, correlate
import sys
import os
import csv

# --------------------------------------------------
# Narrow Bandpass Filter for specific targeted frequencies
# --------------------------------------------------
def bandpass_narrow(data, fs, target_freq):
    # Filter tightly around the target frequency (+/- 10%)
    low = target_freq * 0.85
    high = target_freq * 1.15
    # Safety checks for Nyquist
    if high >= fs / 2:
        high = (fs / 2) * 0.95
    if low <= 0:
        low = 10
        
    nyq = 0.5 * fs
    b, a = butter(4, [low/nyq, high/nyq], btype='band')
    return filtfilt(b, a, data, axis=0)

# --------------------------------------------------
# Delay computation with constrained lag
# --------------------------------------------------
def compute_delay(sig1, sig2, fs):
    corr = correlate(sig1, sig2, mode='full', method='fft')
    max_lag = int(0.005 * fs) # ±5 ms lag limit
    center = len(corr) // 2
    corr_window = corr[center - max_lag : center + max_lag + 1]
    lag = np.argmax(corr_window) - max_lag
    return lag / fs

# --------------------------------------------------
# Event extraction for a specific isolated frequency band
# --------------------------------------------------
def extract_events_for_freq(data, fs):
    mono = np.abs(data[:, 0])
    
    # 50 ms smoothing window
    window_len = int(0.05 * fs)
    kernel = np.ones(window_len) / window_len
    envelope = np.convolve(mono, kernel, mode='same')
    
    # Adaptive threshold: 15% of peak or 5x noise floor
    noise_floor = np.median(envelope)
    threshold = max(np.max(envelope) * 0.15, noise_floor * 5)
    is_active = envelope > threshold
    
    edges = np.diff(is_active.astype(int))
    starts = np.where(edges == 1)[0]
    ends = np.where(edges == -1)[0]
    
    if is_active[0]: starts = np.insert(starts, 0, 0)
    if is_active[-1]: ends = np.append(ends, len(is_active) - 1)
        
    # Merge gaps smaller than 300ms
    min_gap = int(0.3 * fs)
    merged_events = []
    if len(starts) > 0:
        curr_s = starts[0]
        curr_e = ends[0]
        for i in range(1, len(starts)):
            if starts[i] - curr_e < min_gap:
                curr_e = max(curr_e, ends[i])
            else:
                merged_events.append((curr_s, curr_e))
                curr_s = starts[i]
                curr_e = ends[i]
        merged_events.append((curr_s, curr_e))
        
    final_events = []
    for s, e in merged_events:
        # Keep events longer than 400ms (to reliably catch the 0.5s beeps)
        if (e - s) > 0.4 * fs:
            s_pad = max(0, s - int(0.05 * fs))
            e_pad = min(len(data), e + int(0.05 * fs))
            final_events.append((s_pad, e_pad))
            
    return final_events

# --------------------------------------------------
# Main
# --------------------------------------------------
def main():
    print("Frequency-Targeted Audio Analyzer")

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

    if data.dtype == np.int32:
        data = data.astype(np.float32) / 2147483648.0
    elif data.dtype == np.int16:
        data = data.astype(np.float32) / 32768.0
    else:
        data = data.astype(np.float32)

    data -= np.mean(data, axis=0)
    data = np.nan_to_num(data, nan=0.0, posinf=0.0, neginf=0.0)

    num_channels = data.shape[1]
    target_frequencies = [300, 1000, 2000, 8000]
    
    csv_filename = os.path.splitext(filename)[0] + "_delays.csv"
    print(f"\nWriting detailed results to: {csv_filename}")
    
    # Store delays to calculate final averages later
    all_pair_delays = { (f, i, j): [] for f in target_frequencies for i in range(num_channels) for j in range(i + 1, num_channels) }

    with open(csv_filename, 'w', newline='') as csvfile:
        csvwriter = csv.writer(csvfile)
        
        # Write CSV Headers
        headers = ["Target_Freq_Hz", "Beep_Index", "Duration_s", "Event_Avg_ms"]
        for i in range(num_channels):
            for j in range(i + 1, num_channels):
                headers.append(f"Mic{i}_vs_Mic{j}_ms")
        csvwriter.writerow(headers)

        total_events_found = 0

        for freq in target_frequencies:
            print(f"\n=====================================")
            print(f" Hunting for {freq} Hz Beeps ")
            print(f"=====================================")
            
            filtered = bandpass_narrow(data, fs, freq)
            filtered = np.nan_to_num(filtered)
            
            events = extract_events_for_freq(filtered, fs)
            print(f"Found {len(events)} valid events in this frequency band.")
            
            for idx, (start, end) in enumerate(events):
                duration_sec = (end - start) / fs
                print(f"--- Beep {idx + 1} ({duration_sec:.2f}s duration) ---")
                
                segment = filtered[start:end]
                row_prefix = [freq, idx + 1, f"{duration_sec:.4f}"]
                row_delays = []
                event_delays_list = []
                
                for i in range(num_channels):
                    for j in range(i + 1, num_channels):
                        sig1 = segment[:, i]
                        sig2 = segment[:, j]

                        if np.std(sig1) < 1e-6 or np.std(sig2) < 1e-6:
                            row_delays.append("NaN")
                            continue

                        delay = compute_delay(sig1, sig2, fs)
                        delay_ms = delay * 1000
                        all_pair_delays[(freq, i, j)].append(delay_ms)
                        event_delays_list.append(delay_ms)
                        row_delays.append(f"{delay_ms:.4f}")
                        
                if event_delays_list:
                    row_prefix.append(f"{np.mean(event_delays_list):.4f}")
                else:
                    row_prefix.append("NaN")
                    
                csvwriter.writerow(row_prefix + row_delays)
                total_events_found += 1

        # Write overall averages and std dev at the bottom, per frequency!
        csvwriter.writerow([])
        csvwriter.writerow(["OVERALL SUMMARY STATISTICS"])
        
        for freq in target_frequencies:
            csvwriter.writerow([])
            avg_row = [f"{freq} Hz AVERAGE", "", "", ""]
            std_row = [f"{freq} Hz STD_DEV", "", "", ""]
            
            print(f"\n--- Final Averages for {freq} Hz ---")
            for i in range(num_channels):
                for j in range(i + 1, num_channels):
                    delays = all_pair_delays[(freq, i, j)]
                    if delays:
                        avg_val = np.mean(delays)
                        std_val = np.std(delays)
                        avg_row.append(f"{avg_val:.4f}")
                        std_row.append(f"{std_val:.4f}")
                        print(f"Mic {i} vs Mic {j}: Avg = {avg_val:>7.4f} ms  (Std = {std_val:.4f} ms)")
                    else:
                        avg_row.append("NaN")
                        std_row.append("NaN")
                        
            csvwriter.writerow(avg_row)
            csvwriter.writerow(std_row)

    print(f"\nDone! Found {total_events_found} total events across all target frequencies.")
    print(f"Detailed results saved to {csv_filename}")

if __name__ == "__main__":
    main()