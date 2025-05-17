from machine import Pin
import time

button = Pin(1, Pin.IN, Pin.PULL_UP)

while True:
    if button.value() == 0:
        print("Button is Pressed")
    else:
        print("Button is not Pressed")
    time.sleep(0.1)
