import asyncio

from microdot import Microdot, Response, redirect
from primitives import broker, RingbufQueue
from sched.sched import schedule as async_schedule
import ntptime


class Messages:
    SET_ALARM = 'alarm/set'


Response.default_content_type = 'text/html'
ntptime.timeout = 10
#
#
# # init display
# i2c = I2C(0, scl=Pin(17), sda=Pin(16))
# display = ssd1306.SSD1306_I2C(128, 64, i2c)
# display.text('Starting...', 0, 40, 1)
# display.show()
#
# print('Fetching time from NTP server...')
# ntptime.settime()
# print('Time set successfully!')
#
# def display_time():
#     rtc = RTC()
#     _, _, _, _, hour, minute, _, _ = rtc.datetime()
#     writer = Writer(display, roboto, verbose=False)
#     Writer.set_textpos(display, 32, 0)
#     writer.printstring(f"{hour:02}:{minute:02}")
#     display.show()



#
# display_time()
#
#
# clock_setting_timer = Timer()
# clock_setting_timer.init(period=5000, mode=Timer.PERIODIC, callback=lambda _: display_time())
#
#
class Alarm:

    def __init__(self):
        self.is_running = False

    def start(self):
        self.is_running = True

    def stop(self):
        self.is_running = False


class Waker:

    class States:
        IDLE = 'idle'
        FIRST_ALARM = 'first_alarm'
        SECOND_ALARM = 'second_alarm'
        SNOOZED = 'snoozed'

    def __init__(self, button, first_alarm, second_alarm, snooze_method):
        self.state = self.States.IDLE
        self.button = button
        self.first_alarm = first_alarm
        self.second_alarm = second_alarm
        self.snooze_method = snooze_method
        self.stop_event = asyncio.Event()

    async def run(self):
        self.state = self.States.FIRST_ALARM
        self.first_alarm.start()
        await self.button.press.wait()
        self.first_alarm.stop()
        self.state = self.States.SNOOZED
        await self.snooze_method()
        self.state = self.States.SECOND_ALARM
        self.second_alarm.start()
        await self.stop_event.wait()
        self.stop_event.clear()
        self.second_alarm.stop()
        self.state = self.States.IDLE


#
#
# # enter stable state
# led = Pin("LED", Pin.OUT)
# button_pin = Pin(1, Pin.IN, Pin.PULL_UP)
# DUTY = 4000
# button = EButton(button_pin)
# button.press_func = None
# buzzer = PWM(Pin(5), freq=200, duty_u16=0)
#
# bell_pin = Pin(0, Pin.OUT)
# bell_pin.off()  # ensure bell is off at start
#
# ALARM_MODE_OFF = 0
# ALARM_MODE_ON = 1
# ALARM_MODE_SNOOZE = 2
# ALARM_MODE_RINGING = 3
#
# alarm_status_dict = {
#     ALARM_MODE_OFF: 'Off',
#     ALARM_MODE_ON: 'On',
#     ALARM_MODE_SNOOZE: 'Snoozed',
#     ALARM_MODE_RINGING: 'Ringing',
# }
#
# alarm_hour = 17
# alarm_minute = 50
# alarm_mode = ALARM_MODE_OFF  # Start in snooze mode
#
app = Microdot()

@app.route('/ping', methods=['GET'])
async def ping(*_):
    return 'pong'
#
# with open('templates/set_alarm.html', 'r') as f:
#     set_alarm_template = f.read()
#
# with open('templates/cancel_countdown.html', 'r') as f:
#     cancel_countdown_template = f.read()
#
# @app.route('/', methods=['GET'])
# async def index(request):
#     global alarm_hour, alarm_minute, alarm_mode
#     print(alarm_status_dict[alarm_mode])
#     if alarm_mode == ALARM_MODE_SNOOZE:
#         bell_minute = (alarm_minute + 1)
#         bell_minute_adj = bell_minute % 60
#         bell_hour = (alarm_hour + bell_minute // 60) + 1
#         bell_hour_adj = bell_hour % 24
#
#         year, month, day, _, _, _, _, _ = RTC().datetime()
#
#         bell_day = day + (bell_hour // 24)
#         bell_day_adj = bell_day % 31  # Simplified, does not account for month length
#
#         bell_month = month + (bell_day // 31)
#         bell_month_adj = bell_month % 12
#         bell_year = year + (bell_month // 12)
#
#         bell_time = f'{bell_hour_adj:02}:{bell_minute_adj:02}'
#         date =  f'{bell_year:04}-{bell_month_adj:02}-{bell_day_adj:02}'
#         # if snoozed, show cancel countdown
#         return cancel_countdown_template.replace('$time', bell_time)\
#                 .replace('$date', date)
#     return set_alarm_template.replace('$alarm_time', f'{alarm_hour:02}:{alarm_minute:02}')\
#         .replace('$alarm_status', alarm_status_dict[alarm_mode])

#
# @app.route('/', methods=['POST'])
# async def set_alarm(request):
#     global alarm_hour, alarm_minute, alarm_mode
#     alarm_time_str = request.form.get('time')
#     hour, minute = map(int, alarm_time_str.split(':'))
#
#     alarm_hour = hour
#     alarm_minute = minute
#     alarm_mode = ALARM_MODE_ON
#     # send new time to handle_alarm task
#     broker.publish('alarm/set', (alarm_hour, alarm_minute))
#     return set_alarm_template.replace('$alarm_time', f'{alarm_hour:02}:{alarm_minute:02}')\
#         .replace('$alarm_status', alarm_status_dict[alarm_mode])
#
# @app.route('/toggle', methods=['POST'])
# async def toggle_alarm(request):
#     global alarm_mode
#     if alarm_mode == ALARM_MODE_OFF:
#         alarm_mode = ALARM_MODE_ON
#     elif alarm_mode == ALARM_MODE_ON:
#         alarm_mode = ALARM_MODE_OFF
#     else:
#         alarm_mode = ALARM_MODE_OFF
#     # send new status to handle_alarm task
#     broker.publish('alarm/status', alarm_mode)
#     return redirect('/')
#
#
# @app.route('/cancel', methods=['POST'])
# async def cancel_alarm(request):
#     global alarm_mode
#     if alarm_mode in (ALARM_MODE_RINGING, ALARM_MODE_SNOOZE):
#         alarm_mode = ALARM_MODE_ON
#         # send new status to handle_alarm task
#         broker.publish('alarm/status', alarm_mode)
#     return redirect('/')
#
#

def schedule(method, hour, minute):
    return asyncio.create_task(async_schedule(method, hrs=hour, mins=minute, secs=0))


class Scheduler:
    """
    Calls the given schedule_method, passing a method, hour and minute. Assumes that
    schedule_method returns a task, and will cancel the preceding task if one exists.
    """

    def __init__(self, schedule_method):
        self.schedule = schedule_method
        self.task = None

    def set(self, method, hour, minute):
        if self.task is not None:
            self.task.cancel()
        self.task = self.schedule(method, hour, minute)


class AlarmSchedulingAgent:
    """
    Asks the Scheduler to run it's schedule method with a method, hour and
    minute whenver a message is recieved on the SET_ALARM channel
    """

    def __init__(self, wake_sequence, scheduler):
        self.wake_sequence = wake_sequence
        self.scheduler = scheduler

    async def main(self):
        queue = RingbufQueue(3)
        broker.subscribe(Messages.SET_ALARM, queue)
        async for _, (hour, minute) in queue:
            self.scheduler.set(self.wake_sequence, hour, minute)
            await asyncio.sleep(0)

    def create_task(self):
        return asyncio.create_task(self.main())
#
# async def handle_alarm_text():
#     queue = RingbufQueue(20)
#     broker.subscribe('alarm/set', queue)
#     async for topic, (alarm_hour, alarm_minute) in queue:
#         display.rect(0, 0, 128, 16, 0, True)
#         display.text(f'{alarm_hour:02}:{alarm_minute:02}', 0, 0, 1)
#         display.show()
#         await asyncio.sleep(2)


def run_forever():
    loop = asyncio.get_event_loop()
    try:
        print("Use Ctrl+C to stop the event loop.")
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
        print("Event loop closed.")


async def main():
    asyncio.create_task(app.start_server(debug=True, port=80))
    scheduler = Scheduler(schedule)
    AlarmSchedulingAgent(wake_sequence, scheduler).create_task()
    # asyncio.create_task(handle_alarm())
    # asyncio.create_task(handle_alarm_text())
    run_forever()


if __name__ == '__main__':
    from primitives import EButton, broker, RingbufQueue
    import ntptime
    import roboto
    import ssd1306
    from machine import I2C, PWM, RTC, Pin, Timer
    from writer import Writer

    asyncio.run(main())
