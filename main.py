import asyncio
from primitives import EButton, broker, RingbufQueue
from sched.sched import schedule
import ntptime
import roboto
import ssd1306
from machine import I2C, PWM, RTC, Pin, Timer
from writer import Writer
from microdot import Microdot, Response, redirect


Response.default_content_type = 'text/html'
ntptime.timeout = 10


# init display
i2c = I2C(0, scl=Pin(17), sda=Pin(16))
display = ssd1306.SSD1306_I2C(128, 64, i2c)
display.text('Starting...', 0, 40, 1)
display.show()

print('Fetching time from NTP server...')
ntptime.settime()
print('Time set successfully!')

def display_time():
    rtc = RTC()
    _, _, _, _, hour, minute, _, _ = rtc.datetime()
    writer = Writer(display, roboto, verbose=False)
    Writer.set_textpos(display, 32, 0)
    writer.printstring(f"{hour:02}:{minute:02}")
    display.show()

display_time()


clock_setting_timer = Timer()
clock_setting_timer.init(period=5000, mode=Timer.PERIODIC, callback=lambda _: display_time())


async def run_wake_up_sequence():
    global alarm_mode
    # beep buzzer until button is pressed
    while not button.press.is_set():
        buzzer.duty_u16(DUTY)
        await asyncio.sleep(0.5)
        buzzer.duty_u16(0)
        await asyncio.sleep(0.5)
    button.press.clear()
    alarm_mode = ALARM_MODE_SNOOZE  # Set alarm mode to snooze

    # itiate countdown
    for i in range(10, 0, -1):
        display.fill(0)
        display.text(str(i), 0, 0, 1)
        display.show()
        await asyncio.sleep(1)

    bell_pin.on()  # turn on bell
    alarm_mode = ALARM_MODE_RINGING  # Set alarm mode to ringing
    await button.press.wait()  # wait for button press to stop ringing
    bell_pin.off()  # turn off bell


# enter stable state
led = Pin("LED", Pin.OUT)
button_pin = Pin(1, Pin.IN, Pin.PULL_UP)
DUTY = 4000
button = EButton(button_pin)
button.press_func = None
buzzer = PWM(Pin(5), freq=200, duty_u16=0)

bell_pin = Pin(0, Pin.OUT)
bell_pin.off()  # ensure bell is off at start

ALARM_MODE_OFF = 0
ALARM_MODE_ON = 1
ALARM_MODE_SNOOZE = 2
ALARM_MODE_RINGING = 3

alarm_status_dict = {
    ALARM_MODE_OFF: 'Off',
    ALARM_MODE_ON: 'On',
    ALARM_MODE_SNOOZE: 'Snoozed',
    ALARM_MODE_RINGING: 'Ringing',
}

alarm_hour = 17
alarm_minute = 50
alarm_mode = ALARM_MODE_OFF  # Start in snooze mode

app = Microdot()

with open('templates/set_alarm.html', 'r') as f:
    set_alarm_template = f.read()

with open('templates/cancel_countdown.html', 'r') as f:
    cancel_countdown_template = f.read()

@app.route('/', methods=['GET'])
async def index(request):
    global alarm_hour, alarm_minute, alarm_mode
    print(alarm_status_dict[alarm_mode])
    if alarm_mode == ALARM_MODE_SNOOZE:
        bell_minute = (alarm_minute + 1)
        bell_minute_adj = bell_minute % 60
        bell_hour = (alarm_hour + bell_minute // 60) + 1
        bell_hour_adj = bell_hour % 24

        year, month, day, _, _, _, _, _ = RTC().datetime()

        bell_day = day + (bell_hour // 24)
        bell_day_adj = bell_day % 31  # Simplified, does not account for month length

        bell_month = month + (bell_day // 31)
        bell_month_adj = bell_month % 12
        bell_year = year + (bell_month // 12)

        bell_time = f'{bell_hour_adj:02}:{bell_minute_adj:02}'
        date =  f'{bell_year:04}-{bell_month_adj:02}-{bell_day_adj:02}'
        # if snoozed, show cancel countdown
        return cancel_countdown_template.replace('$time', bell_time)\
                .replace('$date', date)
    return set_alarm_template.replace('$alarm_time', f'{alarm_hour:02}:{alarm_minute:02}')\
        .replace('$alarm_status', alarm_status_dict[alarm_mode])


@app.route('/', methods=['POST'])
async def set_alarm(request):
    global alarm_hour, alarm_minute, alarm_mode
    alarm_time_str = request.form.get('time')
    hour, minute = map(int, alarm_time_str.split(':'))

    alarm_hour = hour
    alarm_minute = minute
    alarm_mode = ALARM_MODE_ON
    # send new time to handle_alarm task
    broker.publish('alarm/set', (alarm_hour, alarm_minute))
    return set_alarm_template.replace('$alarm_time', f'{alarm_hour:02}:{alarm_minute:02}')\
        .replace('$alarm_status', alarm_status_dict[alarm_mode])

@app.route('/toggle', methods=['POST'])
async def toggle_alarm(request):
    global alarm_mode
    if alarm_mode == ALARM_MODE_OFF:
        alarm_mode = ALARM_MODE_ON
    elif alarm_mode == ALARM_MODE_ON:
        alarm_mode = ALARM_MODE_OFF
    else:
        alarm_mode = ALARM_MODE_OFF
    # send new status to handle_alarm task
    broker.publish('alarm/status', alarm_mode)
    return redirect('/')


@app.route('/cancel', methods=['POST'])
async def cancel_alarm(request):
    global alarm_mode
    if alarm_mode in (ALARM_MODE_RINGING, ALARM_MODE_SNOOZE):
        alarm_mode = ALARM_MODE_ON
        # send new status to handle_alarm task
        broker.publish('alarm/status', alarm_mode)
    return redirect('/')


async def handle_alarm():
    queue = RingbufQueue(20)
    broker.subscribe('alarm/set', queue)
    task = None
    async for topic, (alarm_hour, alarm_minute) in queue:
        if task is not None:
            task.cancel()
        print(f"Alarm set for {alarm_hour:02}:{alarm_minute:02}")
        task = asyncio.create_task(schedule(run_wake_up_sequence, hrs=alarm_hour, mins=alarm_minute, secs=0))
        await asyncio.sleep(0)


async def handle_alarm_text():
    queue = RingbufQueue(20)
    broker.subscribe('alarm/set', queue)
    async for topic, (alarm_hour, alarm_minute) in queue:
        display.rect(0, 0, 128, 16, 0, True)
        display.text(f'{alarm_hour:02}:{alarm_minute:02}', 0, 0, 1)
        display.show()
        await asyncio.sleep(2)


async def main():
    asyncio.create_task(handle_alarm())
    asyncio.create_task(handle_alarm_text())
    asyncio.create_task(app.start_server(debug=True, port=80))
    while True:
        await asyncio.sleep(10)

asyncio.run(main())

