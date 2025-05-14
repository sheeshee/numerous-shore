from time import sleep

from machine import Pin, I2C
from network import WLAN, STA_IF
import ssd1306


# init display
i2c = I2C(0, scl=Pin(17), sda=Pin(16))
display = ssd1306.SSD1306_I2C(128, 64, i2c)
display.text('Starting...', 0, 40, 1)
display.show()

# init internet connection
with open('credentials.txt', 'r') as f:
    ssid, password = f.read().strip().split('\n')
wlan = WLAN(STA_IF)
wlan.active(True)
wlan.connect(ssid, password)

# Wait for Wi-Fi connection
connection_timeout = 10
while connection_timeout > 0:
    if wlan.status() >= 3:
        break
    connection_timeout -= 1
    print('Waiting for Wi-Fi connection...')
    sleep(1)

# Check if connection is successful
if wlan.status() != 3:
    display.fill(0)
    display.text('Connection error', 0, 40, 1)
    display.show()
    raise RuntimeError('Failed to establish a network connection')
else:
    print('Connection successful!')
    network_info = wlan.ifconfig()
    print('IP address:', network_info[0])


# enter stable state
led = Pin("LED", Pin.OUT)

while True:
    led.value(not led.value())
    print("LED is ON" if led.value() else "LED is OFF")
    sleep(0.5)
