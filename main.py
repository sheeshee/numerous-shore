from time import sleep

import ntptime
import roboto
import ssd1306
from machine import I2C, RTC, Pin, Timer, PWM
from network import STA_IF, WLAN
from writer import Writer

ntptime.timeout = 10


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


print('Fetching time from NTP server...')
ntptime.settime()
print('Time set successfully!')

def display_time():
    rtc = RTC()
    _, _, _, _, hour, minute, _, _ = rtc.datetime()
    display.fill(0)
    writer = Writer(display, roboto, verbose=False)
    Writer.set_textpos(display, 32, 0)
    writer.printstring(f"{hour:02}:{minute:02}")
    display.show()

display_time()


clock_setting_timer = Timer()
clock_setting_timer.init(period=5000, mode=Timer.PERIODIC, callback=lambda _: display_time())



def buzzer_trigger_callback():
    rtc = RTC()
    _, _, _, _, hour, minute, second, _ = rtc.datetime()
    if not(hour == 7 and minute == 55 and second == 0):
        return
    DUTY = 400
    buzzer = PWM(Pin(5), freq=1000, duty_u16=DUTY)
    buzzer.duty_u16(DUTY)
    print("Buzzer triggered!")
    sleep(2)
    buzzer.deinit()

buzzer_trigger_timer = Timer()
buzzer_trigger_timer.init(period=1000, mode=Timer.PERIODIC, callback=lambda _: buzzer_trigger_callback())


# enter stable state
led = Pin("LED", Pin.OUT)

while True:
    led.value(not led.value())
    print("LED is ON" if led.value() else "LED is OFF")
    sleep(0.5)
