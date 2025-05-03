from machine import I2C, Pin
import ssd1306


i2c = I2C(0, scl=Pin(17), sda=Pin(16))

print("I2C scan")
devices = i2c.scan()
if devices:
    print("I2C devices found:", [hex(device) for device in devices])
else:
    print("No I2C devices found")



display = ssd1306.SSD1306_I2C(128, 64, i2c)

display.text('Hello, world!', 0, 40, 1)
display.show()


