from machine import Pin
import asyncio
from primitives import Pushbutton

def toggle(led):
    led.toggle()

async def my_app():
    pin = Pin(1, Pin.IN, Pin.PULL_UP)  # Pushbutton to gnd
    red = Pin('LED', Pin.OUT)  # LED on pin 'LED'
    pb = Pushbutton(pin)
    pb.press_func(toggle, (red,))  # Note how function and args are passed
    await asyncio.sleep(60)  # Dummy

asyncio.run(my_app())  # Run main application code
