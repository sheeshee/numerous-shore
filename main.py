import asyncio
from machine import Pin, PWM, I2C, RTC

from microdot import Microdot, Response, redirect
from primitives import broker, RingbufQueue, EButton
from sched.sched import schedule as async_schedule
import ntptime
from ssd1306 import SSD1306_I2C
from writer import Writer
import roboto
from datetime import datetime, timezone, timedelta


BUTTON = EButton(Pin(1, Pin.IN, Pin.PULL_UP))
BUZZER = PWM(Pin(5), freq=200, duty_u16=0)
BELL = Pin(0, Pin.OUT)
LED = Pin("LED", Pin.OUT)
DUTY = 4000
SCREEN = SSD1306_I2C(128, 64, I2C(0, scl=Pin(17), sda=Pin(16)))


BELL.off()  # be sure BELL is OFF


with open('templates/set_alarm.html', 'r') as f:
    TEMPLATE_SET_ALARM = f.read()

with open('templates/cancel_countdown.html', 'r') as f:
    TEMPLATE_CANCEL_COUNTDOWN = f.read()


class Messages:
    ALARM_OFF = 'alarm/disarm'
    SET_ALARM = 'alarm/set'
    SNOOZE = 'alarm/snooze'
    CANCEL = 'alarm/cancel'


Response.default_content_type = 'text/html'
ntptime.timeout = 10

TIMEZONE = timezone(timedelta(hours=1))  # Set timezone to UTC+1


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
    hour, minute, _ = get_time()
    minute += 1
    if minute >= 60:
        minute = 0
        hour += 1
        if hour >= 24:
            hour = 0
    broker.publish(Messages.SNOOZE, (hour, minute))
    while (hour, minute) != get_time()[0:2]:
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
        asyncio.create_task(self.listen_for_stop())

    def stop(self):
        self._task.cancel()

    async def listen_for_stop(self):
        queue = RingbufQueue(3)
        broker.subscribe(Messages.CANCEL, queue)
        async for _, _ in queue:
            self.stop()
            break


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
        trigger_time = datetime(2023, 1, 1, hour, minute, 0, tzinfo=TIMEZONE)
        utc_trigger_time = trigger_time.astimezone(timezone.utc)
        if self.task is not None:
            self.task.cancel()
        self.task = self.schedule(method, utc_trigger_time.hour, utc_trigger_time.minute)


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

    def hide_alarm(self):
        self.device.rect(0, 0, 128, 16, 0, True)
        self.device.show()

    def update_alarm(self, hour, minute):
        self.alarm = (hour, minute)
        self.device.rect(0, 0, 128, 16, 0, True)
        self.device.text(f'{self.alarm[0]:02}:{self.alarm[1]:02}', 0, 0, 1)
        self.device.show()

    def update_countdown(self, minute, second):
        if self.countdown == (minute, second):
            return
        self.countdown = (minute, second)
        self.device.rect(0, 16, 128, 64, 0, True)
        self.writer.set_textpos(self.device, 32, 0)
        self.writer.printstring(f"{self.countdown[0]:02}:{self.countdown[1]:02}")
        self.device.show()



def get_time():
    """Returns a tuple of hour, minute, second"""
    dt = datetime.now(TIMEZONE)
    return dt.hour, dt.minute, dt.second


class DisplayAgent:

    def __init__(self, display, get_time_method):
        self.display = display
        self.get_time = get_time_method
        self._countdown_active = False

    def start(self):
        asyncio.create_task(self.clock())
        asyncio.create_task(self.alarm())
        asyncio.create_task(self.await_countdown())

    async def clock(self):
        while True:
            hour, minute, _ = self.get_time()
            if not self._countdown_active:
                self.display.update_clock(hour, minute)
            await asyncio.sleep(1)

    async def alarm(self):
        queue = RingbufQueue(3)
        broker.subscribe(Messages.SET_ALARM, queue)
        broker.subscribe(Messages.ALARM_OFF, queue)
        async for topic, params in queue:
            if topic == Messages.ALARM_OFF:
                self.display.hide_alarm()
            else:
                alarm_hour, alarm_minute = params
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
        state.snooze_to(target_hour, target_minute)
        seconds_to = self.seconds_to(target_hour, target_minute)
        while seconds_to > 0:
            minutes = seconds_to // 60
            secondes = seconds_to % 60
            self.display.update_countdown(minutes, secondes)
            seconds_to = self.seconds_to(target_hour, target_minute)
            await asyncio.sleep(0.5)
        self._countdown_active = False

    def seconds_to(self, hour, minute):
        current_hour, current_minute, current_second = self.get_time()
        seconds_to = (hour * 3600 + minute * 60) - (current_hour * 3600 + current_minute * 60 + current_second)
        if seconds_to < 0:
            seconds_to += 24 * 3600
        return seconds_to


class State:

    class AlarmModes:
        OFF = 0
        ON = 1
        SNOOZED = 2
        RINGING = 3

    def __init__(self):
        self.alarm_hour = 0
        self.alarm_minute = 0
        self.target_hour = 0
        self.target_minute = 0
        self.alarm_mode = 0  # 0: OFF, 1: ON, 2: SNOOZE, 3: RINGING

    def get_alarm_mode(self):
        if self.alarm_mode == self.AlarmModes.OFF:
            return 'OFF'
        elif self.alarm_mode == self.AlarmModes.ON:
            return 'ON'
        elif self.alarm_mode == self.AlarmModes.SNOOZED:
            return 'SNOOZED'
        elif self.alarm_mode == self.AlarmModes.RINGING:
            return 'RINGING'
        else:
            return 'UNKNOWN'

    def set_alarm_on(self):
        self.alarm_mode = self.AlarmModes.ON

    def set_alarm_off(self):
        self.alarm_mode = self.AlarmModes.OFF

    def set_alarm_snoozed(self):
        self.alarm_mode = self.AlarmModes.SNOOZED

    def alarm_is_snoozed(self):
        return self.alarm_mode == self.AlarmModes.SNOOZED

    def alarm_is_off(self):
        return self.alarm_mode == self.AlarmModes.OFF

    def snooze_to(self, hour, minute):
        self.target_hour = hour
        self.target_minute = minute
        self.set_alarm_snoozed()


app = Microdot()
state = State()


def make_index(hour, minute, mode):
    return TEMPLATE_SET_ALARM\
        .replace('$alarm_time', f'{hour:02}:{minute:02}')\
        .replace('$alarm_status', mode)


@app.route('/ping', methods=['GET'])
async def ping(*_):
    return 'pong'


@app.route('/', methods=['GET'])
async def index(request):
    global state
    if state.alarm_is_snoozed():
        bell_time = f'{state.target_hour:02}:{state.target_minute:02}'
        return TEMPLATE_CANCEL_COUNTDOWN.replace('$time', bell_time)
    return make_index(state.alarm_hour, state.alarm_minute, state.get_alarm_mode())


@app.route('/', methods=['POST'])
async def set_alarm(request):
    global state
    alarm_time_str = request.form.get('time')
    state.alarm_hour, state.alarm_minute = map(int, alarm_time_str.split(':'))
    state.set_alarm_on()
    # send new time to handle_alarm task
    broker.publish(Messages.SET_ALARM, (state.alarm_hour, state.alarm_minute))
    return make_index(state.alarm_hour, state.alarm_minute, state.get_alarm_mode())


@app.route('/toggle', methods=['POST'])
async def toggle_alarm(request):
    global state
    if state.alarm_is_off():
        state.set_alarm_on()
        broker.publish(Messages.SET_ALARM, (state.alarm_hour, state.alarm_minute))
    else:
        state.set_alarm_off()
        broker.publish(Messages.ALARM_OFF)
    return redirect('/')


@app.route('/cancel', methods=['POST'])
async def cancel_alarm(request):
    state.set_alarm_on()  # Reset the alarm state
    broker.publish(Messages.CANCEL)
    return redirect('/')


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
    scheduler = Scheduler(schedule)
    buzzer_alarm = BuzzerAlarm(BUZZER)
    bell_alarm = BellAlarm(BELL)
    display = Display(SCREEN)
    waker = Waker(BUTTON, buzzer_alarm, bell_alarm, snooze)
    AlarmSchedulingAgent(waker.start, scheduler).start()
    DisplayAgent(display, get_time).start()
    asyncio.create_task(app.start_server(debug=True, port=80))
    run_forever()


if __name__ == '__main__':
    ntptime.settime()  # Set the RTC time from NTP
    asyncio.run(main())
    print("Main loop exited, cleaning up...")
