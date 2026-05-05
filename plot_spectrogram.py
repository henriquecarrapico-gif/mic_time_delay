import sys
import os
import numpy as np
import scipy.io.wavfile as wav
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Import detection functions from analise.py
from analise import bandpass_narrow, extract_events_for_freq

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 plot_spectrogram.py file.wav")
        return

    filename = sys.argv[1]
    
    print(f"Reading audio file: {filename}")
    fs, data = wav.read(filename)

    # Normalize data as in analise.py
    if data.dtype == np.int32:
        data = data.astype(np.float32) / 2147483648.0
    elif data.dtype == np.int16:
        data = data.astype(np.float32) / 32768.0
    else:
        data = data.astype(np.float32)

    data -= np.mean(data, axis=0)
    data = np.nan_to_num(data, nan=0.0, posinf=0.0, neginf=0.0)

    # Use first channel for the spectrogram
    mono_data = data[:, 0]

    target_frequencies = [300, 1000, 2000, 8000]
    
    print("Detecting events...")
    all_events = {}
    for freq in target_frequencies:
        filtered = bandpass_narrow(data, fs, freq)
        filtered = np.nan_to_num(filtered)
        events = extract_events_for_freq(filtered, fs)
        all_events[freq] = events
        print(f"  {freq} Hz: found {len(events)} events")

    print("Generating spectrogram...")
    fig, ax = plt.subplots(figsize=(15, 6))
    
    # Plot spectrogram
    Pxx, freqs, bins, im = ax.specgram(mono_data, Fs=fs, NFFT=2048, noverlap=1024, cmap='viridis', scale='dB')
    
    # Add bounding boxes and labels for detected events
    colors = {
        300: 'red',
        1000: 'orange',
        2000: 'yellow',
        8000: 'magenta'
    }

    for freq, events in all_events.items():
        color = colors.get(freq, 'white')
        for start_idx, end_idx in events:
            start_time = start_idx / fs
            end_time = end_idx / fs
            duration = end_time - start_time
            
            # Create a rectangle patch
            # We'll make the height of the box cover +/- 10% of the target frequency to match the filter
            low_freq = freq * 0.85
            high_freq = freq * 1.15
            freq_height = high_freq - low_freq
            
            rect = patches.Rectangle((start_time, low_freq), duration, freq_height, 
                                     linewidth=2, edgecolor=color, facecolor='none')
            ax.add_patch(rect)
            
            # Add text label above the rectangle
            ax.text(start_time, high_freq + (fs * 0.01), f"{freq}Hz", 
                    color=color, fontsize=8, verticalalignment='bottom')

    ax.set_title(f"Spectrogram with Detected Events: {os.path.basename(filename)}")
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Frequency (Hz)')
    ax.set_ylim(0, 10000) # Limit y-axis to 10kHz to better see the 8kHz events
    
    # Add a legend for the colors
    from matplotlib.lines import Line2D
    legend_elements = [Line2D([0], [0], color=colors[f], lw=2, label=f'{f} Hz Beep') for f in target_frequencies]
    ax.legend(handles=legend_elements, loc='upper right')

    output_filename = os.path.splitext(filename)[0] + "_spectrogram.png"
    plt.tight_layout()
    plt.savefig(output_filename, dpi=150)
    print(f"Spectrogram saved to {output_filename}")

if __name__ == "__main__":
    main()
