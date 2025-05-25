from primitives import EButton
import asyncio
from machine import Pin, PWM
from time import sleep


# on button press, beep buzzer
# on second button press, stop beeping
DUTY = 4000

button_pin = Pin(1, Pin.IN, Pin.PULL_UP)
button = EButton(button_pin)
buzzer = PWM(Pin(5), freq=1000, duty_u16=0)



async def beep_buzzer():
    button.press.clear()
    while True:
        await button.press.wait()
        button.press.clear()
        while True:
            buzzer.duty_u16(DUTY)
            await asyncio.sleep(0.5)
            buzzer.duty_u16(0)
            await asyncio.sleep(0.5)
            if button.press.is_set():
                button.press.clear()
                break



async def main():
    print('begin')
    asyncio.create_task(beep_buzzer())
    await asyncio.sleep(3)
    button.press.set()  # Simulate button press to start beeping
    while True:
        await asyncio.sleep(0.1)


asyncio.run(main())  # Run main application code
