#!/usr/bin/env python3
"""
Passive Buzzer Controller for Raspberry Pi
Generates continuous sweeping and chirping sounds at an audible frequency on GPIO13
"""

import RPi.GPIO as GPIO
import time
import sys

# GPIO pin configuration (GPIO13 on Raspberry Pi - Physical pin 33)
BUZZER_PIN = 13
MIN_FREQUENCY = 20    # Minimum audible frequency
MAX_FREQUENCY = 8000  # Maximum audible frequency

def setup_buzzer():
    """Initialize GPIO and PWM for the buzzer"""
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUZZER_PIN, GPIO.OUT)
    pwm = GPIO.PWM(BUZZER_PIN, MIN_FREQUENCY)
    return pwm

def buzz_loop(duration=None):
    """
    Generate sweeps and chirps in a loop
    
    Args:
        duration: Time to run in seconds. If None, runs indefinitely until interrupted.
    """
    try:
        pwm = setup_buzzer()
        pwm.start(0)  # Start PWM with 0% duty cycle (silent)
        
        print(f"Generating sweeps and chirps on GPIO{BUZZER_PIN}...")
        print("Press Ctrl+C to stop")
        
        start_time = time.time()
        
        while True:
            frequencies = [300, 1000, 2000, 8000]
            
            for freq in frequencies:
                # 5 beeps per frequency
                for _ in range(5):
                    if duration and (time.time() - start_time) > duration:
                        return
                    
                    # Play beep for 0.5 seconds
                    pwm.ChangeDutyCycle(50)
                    pwm.ChangeFrequency(freq)
                    time.sleep(0.5)
                    
                    # Silence for 2 seconds
                    pwm.ChangeDutyCycle(0)
                    time.sleep(2.0)
                    
            # If duration is 0 or very large, it will repeat the whole pattern
    
    except KeyboardInterrupt:
        print("\nStopping buzzer...")
    
    finally:
        pwm.stop()
        # Force the PWM object to be garbage collected BEFORE GPIO.cleanup()
        # This prevents rpi-lgpio from crashing during __del__ when the script exits
        del pwm
        GPIO.cleanup()
        print("Buzzer stopped cleanly.")

if __name__ == "__main__":
    duration = 30
    if len(sys.argv) > 1:
        try:
            duration = int(sys.argv[1])
        except ValueError:
            pass
    buzz_loop(duration)
