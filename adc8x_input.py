import sounddevice as sd
import numpy as np
import time
import logging
from pathlib import Path
from .base import AudioInput

BOOT_CONFIG = Path("/boot/firmware/config.txt")
OVERLAY_NAME = "hifiberry-adc8x"  # dtoverlay name for ADC8x


class ADC8xInput(AudioInput):
    """Audio input from HiFiBerry ADC8x via ALSA/PortAudio.

    The ADC8x provides 4 stereo I2S lines (SD0-SD3), each carrying an
    opposing mic pair on its L/R channels:
        SD0 L/R → ch0/ch1  (pair 0)
        SD1 L/R → ch2/ch3  (pair 1)
        SD2 L/R → ch4/ch5  (pair 2)
        SD3 L/R → ch6/ch7  (pair 3)

    Set mic.channels to 4 (SD0+SD1) or 8 (all SD lines).
    """

    def __init__(self, config, logger=None):
        super().__init__(config)
        self.device = config['input'].get('adc8x_device', 'default')
        self.gain = float(config['input'].get('gain', 1.0))
        self.logger = logger if logger is not None else logging.getLogger('TowerMic')
        self.stream = None

    # ------------------------------------------------------------------
    # Overlay check
    # ------------------------------------------------------------------
    @staticmethod
    def _overlay_active():
        """Return True if the hifiberry-adc8x overlay is enabled in boot config."""
        try:
            text = BOOT_CONFIG.read_text()
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if OVERLAY_NAME in stripped and "dtoverlay=" in stripped:
                    return True
        except FileNotFoundError:
            # Boot config not accessible (e.g. inside Docker without mount)
            return None  # unknown — can't verify
        return False

    # ------------------------------------------------------------------
    # AudioInput interface
    # ------------------------------------------------------------------
    def open(self):
        # Check overlay
        overlay_status = self._overlay_active()
        if overlay_status is None:
            self.logger.warning(
                f"Cannot verify overlay: {BOOT_CONFIG} not found. "
                f"Assuming overlay is loaded (running in container?)."
            )
        elif not overlay_status:
            self.logger.error(
                f"HiFiBerry overlay '{OVERLAY_NAME}' not found in {BOOT_CONFIG}. "
                f"Add 'dtoverlay={OVERLAY_NAME}' to {BOOT_CONFIG} and reboot."
            )
            return False

        try:
            self.stream = sd.InputStream(
                device=self.device if self.device != "default" else None,
                channels=self.channels,
                samplerate=self.sample_rate,
                dtype='float32',
            )
            self.stream.start()
            self.logger.info(
                f"ADC8x opened: device={self.device}, "
                f"channels={self.channels}, rate={self.sample_rate}"
            )
            return True
        except Exception as e:
            self.logger.error(f"Failed to open ADC8x stream: {e}")
            return False

    def close(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    def read(self, n_samples):
        if not self.stream:
            return None, None

        timestamp = time.time()
        try:
            data, overflow = self.stream.read(n_samples)
            if overflow:
                self.logger.warning("ADC8x input overflow")
            out = data.astype(np.float32)
            # Apply digital gain and clip
            if self.gain != 1.0:
                out = np.clip(out * self.gain, -1.0, 1.0)
            return timestamp, out
        except Exception as e:
            self.logger.error(f"ADC8x read error: {e}")
            return None, None
