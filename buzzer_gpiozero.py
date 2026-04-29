#!/usr/bin/env python3
"""
Passive Buzzer Controller for Raspberry Pi (using gpiozero)
Alternative, simpler implementation using gpiozero library
"""

from gpiozero import PWMLED
from signal import pause
import time

# GPIO pin configuration (GPIO13 on Raspberry Pi - Physical pin 33)
BUZZER_PIN = 13

def buzz_with_gpiozero():
    """
    Generate continuous buzzing sound using gpiozero library
    """
    try:
        buzzer = PWMLED(BUZZER_PIN)
        buzzer.pulse(fade_in_time=0, fade_out_time=5)  # Creates buzzing effect 
        frequency = 440  # Set a fixed frequency (440hz)
        buzzer.frequency = frequency

        print(f"Buzzing on GPIO{BUZZER_PIN} using gpiozero...")
        print("Press Ctrl+C to stop")
        
        pause()  # Keep running indefinitely
    
    except KeyboardInterrupt:
        print("\nStopping buzzer...")
    
    finally:
        buzzer.off()
        print("Buzzer stopped and GPIO cleaned up")

if __name__ == "__main__":
    buzz_with_gpiozero()
