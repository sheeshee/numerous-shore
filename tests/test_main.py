import asyncio
from machine import Pin
import time

import unittest
from primitives import broker, EButton

from main import (
    SCREEN, AlarmSchedulingAgent, BuzzerAlarm, Scheduler,
    ping, Messages, Waker, BellAlarm, Display, DisplayAgent
)


class WebRoutesTestCase(unittest.TestCase):

    def test_ping(self):
        result = asyncio.run(ping())
        self.assertEqual(result, 'pong')


class AlarmSchedulingAgentTestCase(unittest.TestCase):

    class FakeScheduler:

        def __init__(self):
            self.hour = None
            self.minute = None
            self.method = None

        def set(self, method, hour, minute):
            self.hour = hour
            self.minute = minute
            self.method = method

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
            self.countdown = (0, 0)

        def update_clock(self, hour, minute):
            self.clock = (hour, minute)

        def update_alarm(self, hour, minute):
            self.alarm = (hour, minute)

        def update_countdown(self, hour, minute):
            self.countdown = (hour, minute)
            if self._rtc:
                self._rtc.pass_time()

    class FakeRTC:

        def __init__(self, hour, minute):
            self.hour = hour
            self.minute = minute
            self._second = 0

        def datetime(self):
            return (2023, 10, 1, 0, self.hour, self.minute, 0, 0)

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
