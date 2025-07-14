import asyncio
from machine import Pin
import time
import random

import unittest
from primitives import broker, EButton

from app import (
    SCREEN, AlarmSchedulingAgent, BuzzerAlarm, Scheduler,
    Messages, Waker, BellAlarm, Display, DisplayAgent,
    server, state, connect_to_network, CredentialsGetter
)

from tests.microdot_test_client import TestClient


class MockCredentialsFile:

    _ascii_letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def __init__(self, contents):
        self.contents = contents
        self.filename = "".join(random.choice(self._ascii_letters) for _ in range(10)) + ".txt"

    def __enter__(self):
        with open(self.filename, 'w') as f:
            f.write(self.contents)
            f.flush()
        return self.filename

    def __exit__(self, exc_type, exc_value, traceback):
        os.remove(self.filename)


class FakeNetworkInterface:
    """A mock network interface for testing purposes."""
    def __init__(self, resolved_ip_address='192.168.0.1', resolved_status_code=3):
        self.status_code = 0
        self.resolved_status_code = resolved_status_code
        self.resolved_ip_address = resolved_ip_address

    def active(self, state):
        pass

    def connect(self, ssid, password):
        self.status_code = self.resolved_status_code

    def status(self):
        return self.status_code

    def ifconfig(self):
        return (self.resolved_ip_address,)


def fake_sleep(seconds):
    """A fake sleep function that does nothing."""
    pass


class FakeCredentialsGetter:
    """A mock credentials getter for testing purposes."""
    def get_credentials(self):
        return "test_ssid", "test_password"


class NetworkTest(unittest.TestCase):

    def setUp(self):
        self.fake_network = FakeNetworkInterface()
        self.fake_credentials = FakeCredentialsGetter()

    def test_get_credentials(self):
        file_contents = "test_ssid\ntest_password"
        with MockCredentialsFile(file_contents) as cred_file:
            getter = CredentialsGetter(cred_file)
            ssid, password = getter.get_credentials()
        assert ssid == "test_ssid"
        assert password == "test_password"


    def test_connect_to_network_raises_runtime_error_on_failed_connection(self):
        fake_network = FakeNetworkInterface(resolved_status_code=1)
        fake_credentials = FakeCredentialsGetter()

        with self.assertRaises(RuntimeError):
            connect_to_network(fake_network, fake_credentials, fake_sleep)

    def test_connect_to_network_returns_ip_address_on_success(self):
        fake_network = FakeNetworkInterface(resolved_ip_address='192.168.0.2')
        fake_credentials = FakeCredentialsGetter()
        ip_address = connect_to_network(fake_network, fake_credentials, fake_sleep)
        assert ip_address == '192.168.0.2'


class WebRoutesTestCase(unittest.TestCase):

    def test_ping(self):

        async def test():
            client = TestClient(server)
            res = await client.get('/ping')
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.text, 'pong')

        asyncio.run(test())


    def test_index_shows_alarm_time(self):

        state.alarm_hour = 12
        state.alarm_minute = 30

        async def test():
            client = TestClient(server)
            res = await client.get('/')
            self.assertEqual(res.status_code, 200)
            self.assertIn('12:30', res.text)

        asyncio.run(test())

    def test_index_shows_alarm_state(self):

        state.set_alarm_on()

        async def test():
            client = TestClient(server)
            res = await client.get('/')
            self.assertEqual(res.status_code, 200)
            self.assertIn('ON', res.text)

        asyncio.run(test())

    def test_index_shows_countdown_when_alarm_snoozed(self):

        state.snooze_to(12, 30)

        async def test():
            client = TestClient(server)
            res = await client.get('/')
            self.assertEqual(res.status_code, 200)
            self.assertIn('cancel countdown', res.text.lower())
            self.assertIn('12:30', res.text)

        asyncio.run(test())

    def test_cancel_countdown(self):

        state.snooze_to(12, 30)

        async def test():
            client = TestClient(server)
            res = await client.post('/cancel')
            self.assertEqual(res.status_code, 303)

        asyncio.run(test())

    def test_toggle_alarm_on(self):

        state.set_alarm_off()

        async def test():
            client = TestClient(server)
            res = await client.post('/toggle')
            self.assertEqual(res.status_code, 303)

        asyncio.run(test())

    def test_toggle_alarm_off(self):

        state.set_alarm_on()

        async def test():
            client = TestClient(server)
            res = await client.post('/toggle')
            self.assertEqual(res.status_code, 303)

        asyncio.run(test())

    def test_set_alarm_time(self):

        state.alarm_hour = 0
        state.alarm_minute = 0

        async def test():
            client = TestClient(server)
            res = await client.post(
                '/',
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                body='time=12%3A30'
            )
            self.assertEqual(res.status_code, 303)

        asyncio.run(test())


class AlarmSchedulingAgentTestCase(unittest.TestCase):

    class FakeScheduler:

        def __init__(self):
            self.hour = None
            self.minute = None
            self.method = None
            self.cancelled = False

        def set(self, method, hour, minute):
            self.hour = hour
            self.minute = minute
            self.method = method

        def cancel(self):
            self.cancelled = True

    def test_create_task(self):
        def fake_method(): pass
        agent = AlarmSchedulingAgent(fake_method, self.FakeScheduler())
        self.assertTrue(
            isinstance(agent.start(), asyncio.Task)
        )

    def test_schedule_method_on_subscription_message(self):

        def fake_wake_sequence():
            pass

        scheduler = self.FakeScheduler()

        agent = AlarmSchedulingAgent(fake_wake_sequence, scheduler)

        async def emit_alarm_set_message():
            broker.publish(Messages.SET_ALARM, (12, 30))

        async def test():
            agent.start()
            asyncio.create_task(emit_alarm_set_message())
            for _ in range(3):
                await asyncio.sleep(0)

        asyncio.run(test())

        self.assertEqual(scheduler.hour, 12)
        self.assertEqual(scheduler.minute, 30)
        self.assertEqual(scheduler.method, fake_wake_sequence)

    def test_cancel_scheduled_task_on_alarm_off_message(self):

        def fake_wake_sequence():
            pass

        scheduler = self.FakeScheduler()
        agent = AlarmSchedulingAgent(fake_wake_sequence, scheduler)

        async def emit_alarm_off_message():
            broker.publish(Messages.ALARM_OFF, None)

        async def test():
            agent.start()
            asyncio.create_task(emit_alarm_off_message())
            for _ in range(3):
                await asyncio.sleep(0)

        asyncio.run(test())

        self.assertTrue(scheduler.cancelled)


class SchedulerTestCase(unittest.TestCase):

    def test_set(self):
        global some_value

        some_value = 0

        def fake_wake_sequence():
            global some_value
            some_value = 1

        def fake_schedule_method(method, hrs=None, mins=None, **kwargs):
            # eagerly run the method instead of scheduling it for
            # a specific time
            method()

        async def test():
            scheduler = Scheduler(fake_schedule_method)
            scheduler.set(fake_wake_sequence, 12, 30)
            for _ in range(3):
                await asyncio.sleep(0)

        asyncio.run(test())

        self.assertEqual(some_value, 1)

    def test_set_cancels_previous_task(self):

        class FakeTask:

            tasks = []

            def __init__(self):
                self.cancelled = False

            def cancel(self):
                self.cancelled = True
                self.tasks.append(self)

        def fake_schedule_method(method, hour, minute):
            return FakeTask()

        def fake_wake_sequence():
            pass

        async def test():
            scheduler = Scheduler(fake_schedule_method)
            scheduler.set(fake_wake_sequence, 12, 30)
            scheduler.set(fake_wake_sequence, 12, 31)

        asyncio.run(test())

        self.assertTrue(FakeTask.tasks[0].cancelled)


class WakerTestCase(unittest.TestCase):

    def setUp(self):

        class FakeAlarm:

            def __init__(self) -> None:
                self.is_running = False

            def start(self):
                self.is_running = True

            def stop(self):
                self.is_running = False

        self.button = EButton(Pin(2))
        self.first_alarm = FakeAlarm()
        self.second_alarm = FakeAlarm()

    def test_wake_sequence_rings_first_alarm_if_no_button_press(self):

        async def fake_snooze(): pass

        waker = Waker(
            self.button,
            self.first_alarm,
            self.second_alarm,
            fake_snooze
        )

        async def test():
            asyncio.create_task(waker.run())
            for _ in range(10):
                await asyncio.sleep(0)

        asyncio.run(test())

        self.assertEqual(waker.state, Waker.States.FIRST_ALARM)
        self.assertTrue(self.first_alarm.is_running)
        self.assertFalse(self.second_alarm.is_running)

    def test_wake_sequence_enters_snooze_after_button_press(self):
        global hold_snooze
        hold_snooze = True

        async def fake_snooze():
            while hold_snooze:
                await asyncio.sleep(0)

        waker = Waker(
            self.button,
            self.first_alarm,
            self.second_alarm,
            fake_snooze
        )

        async def test():
            global hold_snooze
            asyncio.create_task(waker.run())
            for _ in range(3):
                await asyncio.sleep(0)
            self.button.press.set()
            self.button.press.clear()
            for _ in range(3):
                await asyncio.sleep(0)

            self.assertEqual(waker.state, Waker.States.SNOOZED)
            self.assertFalse(self.first_alarm.is_running)
            self.assertFalse(self.second_alarm.is_running)
            hold_snooze = False


        asyncio.run(test())

    def test_wake_sequence_rings_second_alarm_after_snooze(self):

        async def fake_snooze(): pass

        waker = Waker(self.button, self.first_alarm, self.second_alarm, fake_snooze)

        async def test():
            asyncio.create_task(waker.run())
            for _ in range(3):
                await asyncio.sleep(0)
            self.button.press.set()
            self.button.press.clear()
            for _ in range(10):
                await asyncio.sleep(0)

        asyncio.run(test())

        self.assertEqual(waker.state, Waker.States.SECOND_ALARM)
        self.assertFalse(self.first_alarm.is_running)
        self.assertTrue(self.second_alarm.is_running)

    def test_cancel_wake_sequence_during_first_alarm(self):

        async def fake_snooze(): pass

        waker = Waker(self.button, self.first_alarm, self.second_alarm, fake_snooze)

        async def test():
            task = asyncio.create_task(waker.run())
            for _ in range(3):
                await asyncio.sleep(0)
            task.cancel()
            for _ in range(3):
                await asyncio.sleep(0)

        asyncio.run(test())

        self.assertEqual(waker.state, Waker.States.IDLE)
        self.assertFalse(self.first_alarm.is_running)
        self.assertFalse(self.second_alarm.is_running)

    def test_cancel_wake_sequence_during_snooze(self):

        async def fake_snooze():
            for _ in range(10):
                await asyncio.sleep(1)

        waker = Waker(self.button, self.first_alarm, self.second_alarm, fake_snooze)

        async def test():
            task = asyncio.create_task(waker.run())
            for _ in range(3):
                await asyncio.sleep(0)
            self.button.press.set()
            self.button.press.clear()
            for _ in range(3):
                await asyncio.sleep(0)
            task.cancel()
            for _ in range(3):
                await asyncio.sleep(0)

        asyncio.run(test())

        self.assertEqual(waker.state, Waker.States.IDLE)
        self.assertFalse(self.first_alarm.is_running)
        self.assertFalse(self.second_alarm.is_running)

    def test_cancel_wake_sequence_during_second_alarm(self):

        async def fake_snooze(): pass

        waker = Waker(self.button, self.first_alarm, self.second_alarm, fake_snooze)

        async def test():
            task = asyncio.create_task(waker.run())
            for _ in range(3):
                await asyncio.sleep(0)
            self.button.press.set()
            self.button.press.clear()
            for _ in range(3):
                await asyncio.sleep(0)
            task.cancel()
            for _ in range(3):
                await asyncio.sleep(0)

        asyncio.run(test())

        self.assertEqual(waker.state, Waker.States.IDLE)
        self.assertFalse(self.first_alarm.is_running)
        self.assertFalse(self.second_alarm.is_running)


class BuzzerAlarmTestCase(unittest.TestCase):

    class FakePWM:

        def __init__(self):
            self._duty_u16 = 0
            self.beep_count = 0

        def duty_u16(self, value=None):
            if value is not None:
                self._duty_u16 = value
                if value > 0:
                    self.beep_count += 1
            return self._duty_u16

    def setUp(self):
        self.buzzer = self.FakePWM()

    def test_start(self):

        alarm = BuzzerAlarm(self.buzzer)

        async def test():
            alarm.start()
            await asyncio.sleep(1)

        asyncio.run(test())

        self.assertTrue(alarm.is_running)
        self.assertGreaterEqual(self.buzzer.beep_count, 1)

    def test_stop(self):

        alarm = BuzzerAlarm(self.buzzer)

        async def test():
            alarm.start()
            await asyncio.sleep(1)
            alarm.stop()
            await asyncio.sleep(0.5)

        asyncio.run(test())

        self.assertFalse(alarm.is_running)
        self.assertEqual(self.buzzer.duty_u16(), 0)
        self.assertGreaterEqual(self.buzzer.beep_count, 1)


class BellAlarmTestCase(unittest.TestCase):

    def test_start(self):

        alarm = BellAlarm(Pin(0, Pin.OUT))

        alarm.start()

        self.assertTrue(alarm.is_running)
        self.assertTrue(alarm.bell.value())

    def test_stop(self):

        alarm = BellAlarm(Pin(0, Pin.OUT))

        alarm.start()
        alarm.stop()

        self.assertFalse(alarm.is_running)
        self.assertFalse(alarm.bell.value())


class DisplayTestCase(unittest.TestCase):

    def test_update_clock(self):
        display = Display(SCREEN)
        display.update_clock(12, 30)
        time.sleep(0.1)  # allow the display to update
        self.assertEqual(display.clock, (12, 30))

    def test_update_alarm(self):
        display = Display(SCREEN)
        display.update_alarm(12, 30)
        time.sleep(0.1)
        self.assertEqual(display.alarm, (12, 30))

    def test_update_countdown(self):
        display = Display(SCREEN)
        display.update_countdown(5, 0)
        time.sleep(0.1)
        self.assertEqual(display.countdown, (5, 0))


class DisplayAgentTestCase(unittest.TestCase):

    class FakeDisplay():

        def __init__(self, rtc=None):
            self._rtc = rtc
            self.clock = (0, 0)
            self.alarm = (0, 0)
            self.show_alarm = True
            self.countdown = (0, 0)

        def update_clock(self, hour, minute):
            self.clock = (hour, minute)

        def update_alarm(self, hour, minute):
            self.alarm = (hour, minute)

        def update_countdown(self, hour, minute):
            self.countdown = (hour, minute)
            if self._rtc:
                self._rtc.pass_time()

        def hide_alarm(self):
            self.show_alarm = False

    class FakeRTC:

        def __init__(self, hour, minute):
            self.hour = hour
            self.minute = minute
            self._second = 0

        def __call__(self):
            return (self.hour, self.minute, self._second)

        def pass_time(self):
            self._second += 1
            if self._second >= 60:
                self._second = 0
                self.minute += 1
                if self.minute >= 60:
                    self.minute = 0
                    self.hour += 1
                    if self.hour >= 24:
                        self.hour = 0

    def test_displays_the_time(self):

        rtc = self.FakeRTC(1, 2)
        display = self.FakeDisplay(rtc)

        agent = DisplayAgent(display, rtc)

        async def test():
            agent.start()
            for _ in range(3):
                await asyncio.sleep(0)

        asyncio.run(test())

        self.assertEqual(display.clock, (1, 2))

    def test_update_alarm_time_on_message_reciept(self):

        display = self.FakeDisplay()
        rtc = self.FakeRTC(1, 2)

        agent = DisplayAgent(display, rtc)

        async def emit_alarm_time_message():
            broker.publish(Messages.SET_ALARM, (12, 30))

        async def test():
            agent.start()
            asyncio.create_task(emit_alarm_time_message())
            for _ in range(3):
                await asyncio.sleep(0)

        asyncio.run(test())

        self.assertEqual(display.alarm, (12, 30))

    def test_hide_alarm_time_on_deactivation_message(self):

        display = self.FakeDisplay()
        display.show_alarm = True
        rtc = self.FakeRTC(1, 2)

        agent = DisplayAgent(display, rtc)

        async def emit_alarm_deactivation_message():
            broker.publish(Messages.ALARM_OFF, None)

        async def test():
            agent.start()
            asyncio.create_task(emit_alarm_deactivation_message())
            for _ in range(3):
                await asyncio.sleep(0)

        asyncio.run(test())

        self.assertFalse(display.show_alarm)

    def test_countdown_updates_display(self):
        display = self.FakeDisplay()
        rtc = self.FakeRTC(5, 55)

        agent = DisplayAgent(display, rtc)

        async def emit_snooze_message():
            broker.publish(Messages.SNOOZE, (6, 0))

        async def test():
            agent.start()
            asyncio.create_task(emit_snooze_message())
            for _ in range(3):
                await asyncio.sleep(0)

        asyncio.run(test())

        self.assertEqual(display.countdown, (5, 0))

    def test_to_seconds(self):
        rtc = self.FakeRTC(0, 0)
        display = self.FakeDisplay(rtc)

        agent = DisplayAgent(display, rtc)

        self.assertEqual(agent.seconds_to(0, 1), 60)

    def test_to_seconds_wraps_around_midnight(self):
        rtc = self.FakeRTC(23, 59)
        display = self.FakeDisplay(rtc)

        agent = DisplayAgent(display, rtc)

        self.assertEqual(agent.seconds_to(0, 1), 120)


if __name__ == '__main__':
    unittest.main()
