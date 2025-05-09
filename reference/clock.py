from machine import I2C, Pin, RTC
import ssd1306
import time
import rob as font
from writer import Writer

WIDTH = const(128)
HEIGHT = const(64)
i2c = I2C(0, scl=Pin(17), sda=Pin(16))
ssd = ssd1306.SSD1306_I2C(WIDTH, HEIGHT, i2c)

rtc = RTC()
rtc.datetime((2023, 10, 1, 0, 12, 0, 0, 0))  # Set the date and time
wri = Writer(ssd, font)

ssd.fill(0)  # Clear the display

while True:
    Writer.set_textpos(ssd, 32, 0)  # verbose = False to suppress console output
    _, _, _, _, hour, minute, second, _ = rtc.datetime()
    wri.printstring(f'{hour:02}:{minute:02}')
    ssd.show()
    time.sleep(5)
    print('')


