import asyncio
from machine import Pin, PWM, I2C, RTC

from microdot import Microdot, Response, redirect
from primitives import broker, RingbufQueue, EButton
from sched.sched import schedule as async_schedule
import ntptime
from ssd1306 import SSD1306_I2C
from writer import Writer
import roboto


BUTTON = EButton(Pin(1, Pin.IN, Pin.PULL_UP))
BUZZER = PWM(Pin(5), freq=200, duty_u16=0)
BELL = Pin(0, Pin.OUT)
LED = Pin("LED", Pin.OUT)
DUTY = 4000
SCREEN = SSD1306_I2C(128, 64, I2C(0, scl=Pin(17), sda=Pin(16)))


BELL.off()  # be sure BELL is OFF


class Messages:
    SET_ALARM = 'alarm/set'
    SNOOZE = 'alarm/snooze'


Response.default_content_type = 'text/html'
ntptime.timeout = 10


class Alarm:

    def __init__(self):
        self.is_running = False

    def start(self):
        self.is_running = True

    def stop(self):
        self.is_running = False


class BuzzerAlarm(Alarm):

    def __init__(self, buzzer_pwm):
        super().__init__()
        self.buzzer = buzzer_pwm
        self._task = None

    async def _buzz(self):
        try:
            while True:
                self.buzzer.duty_u16(0)
                await asyncio.sleep(0.5)
                self.buzzer.duty_u16(DUTY)
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            print(' >>> buzzer task cancelled')
        finally:
            self.buzzer.duty_u16(0)

    def start(self):
        super().start()
        self._task = asyncio.create_task(self._buzz())

    def stop(self):
        super().stop()
        if self._task is not None:
            self._task.cancel()
        self.buzzer.duty_u16(0)


class BellAlarm(Alarm):

    def __init__(self, bell_pin):
        super().__init__()
        self.bell = bell_pin
        self._task = None

    def start(self):
        super().start()
        self.bell.on()

    def stop(self):
        super().stop()
        self.bell.off()


async def snooze():
    current_time = RTC().datetime()
    hour, minute = current_time[4], current_time[5]
    minute += 1
    if minute >= 60:
        minute = 0
        hour += 1
        if hour >= 24:
            hour = 0
    broker.publish(Messages.SNOOZE, (hour, minute))
    while (hour, minute) != RTC().datetime()[4:6]:
        await asyncio.sleep(1)


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

    async def run(self):
        try:
            self.state = self.States.FIRST_ALARM
            self.first_alarm.start()
            await self.button.press.wait()
            self.first_alarm.stop()
            self.state = self.States.SNOOZED
            await self.snooze_method()
            self.state = self.States.SECOND_ALARM
            self.second_alarm.start()
            for _ in range(60):
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            print(' >>> wake sequence cancelled')
        finally:
            self.first_alarm.stop()
            self.second_alarm.stop()
            self.state = self.States.IDLE

    def start(self):
        self._task = asyncio.create_task(self.run())

    def stop(self):
        self._task.cancel()

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

    def start(self):
        return asyncio.create_task(self.main())


class Display:

    def __init__(self, device):
        self.device = device
        self.writer = Writer(device, roboto, verbose=False)
        self.clock = (0, 0)
        self.alarm = (0, 0)
        self.countdown = (0, 0)

    def update_clock(self, hour, minute):
        if self.clock == (hour, minute):
            return
        self.clock = (hour, minute)
        self.device.rect(0, 16, 128, 64, 0, True)
        self.writer.set_textpos(self.device, 32, 0)
        self.writer.printstring(f"{self.clock[0]:02}:{self.clock[1]:02}")
        self.device.show()

    def update_alarm(self, hour, minute):
        if self.alarm == (hour, minute):
            return
        self.alarm = (hour, minute)
        self.device.rect(0, 0, 128, 16, 0, True)
        self.device.text(f'{self.alarm[0]:02}:{self.alarm[1]:02}', 0, 0, 1)
        self.device.show()

    def update_countdown(self, minute, second):
        print(f'Updating countdown to {minute:02}:{second:02}')
        if self.countdown == (minute, second):
            print('Countdown already set to this value, skipping update.')
            return
        self.countdown = (minute, second)
        self.device.rect(0, 16, 128, 64, 0, True)
        self.writer.set_textpos(self.device, 32, 0)
        self.writer.printstring(f"{self.countdown[0]:02}:{self.countdown[1]:02}")
        self.device.show()


class DisplayAgent:

    def __init__(self, display, rtc):
        self.display = display
        self.rtc = rtc
        self._countdown_active = False

    def start(self):
        asyncio.create_task(self.clock())
        asyncio.create_task(self.alarm())
        asyncio.create_task(self.await_countdown())

    async def clock(self):
        while True:
            _, _, _, _, hour, minute, _, _ = self.rtc.datetime()
            if not self._countdown_active:
                self.display.update_clock(hour, minute)
            await asyncio.sleep(1)

    async def alarm(self):
        queue = RingbufQueue(3)
        broker.subscribe(Messages.SET_ALARM, queue)
        async for topic, (alarm_hour, alarm_minute) in queue:
            self.display.update_alarm(alarm_hour, alarm_minute)
            await asyncio.sleep(1)

    async def await_countdown(self):
        queue = RingbufQueue(3)
        broker.subscribe(Messages.SNOOZE, queue)
        async for topic, (hour, minute) in queue:
            await self.countdown(hour, minute)
            await asyncio.sleep(1)

    async def countdown(self, target_hour, target_minute):
        self._countdown_active = True
        seconds_to = self.seconds_to(target_hour, target_minute)
        while seconds_to > 0:
            minutes = seconds_to // 60
            secondes = seconds_to % 60
            self.display.update_countdown(minutes, secondes)
            seconds_to = self.seconds_to(target_hour, target_minute)
            await asyncio.sleep(0.5)
        self._countdown_active = False

    def seconds_to(self, hour, minute):
        _, _, _, _, current_hour, current_minute, current_second, _ = self.rtc.datetime()
        print('current_hour:', current_hour, 'current_minute:', current_minute)
        print('target_hour:', hour, 'target_minute:', minute)
        seconds_to = (hour * 3600 + minute * 60) - (current_hour * 3600 + current_minute * 60 + current_second)
        if seconds_to < 0:
            seconds_to += 24 * 3600
        return seconds_to


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
    buzzer_alarm = BuzzerAlarm(BUZZER)
    bell_alarm = BellAlarm(BELL)
    display = Display(SCREEN)
    waker = Waker(BUTTON, buzzer_alarm, bell_alarm, snooze)
    AlarmSchedulingAgent(waker.start, scheduler).start()
    DisplayAgent(display, RTC()).start()
    run_forever()


if __name__ == '__main__':
    ntptime.settime()  # Set the RTC time from NTP
    asyncio.run(main())
    print("Main loop exited, cleaning up...")
