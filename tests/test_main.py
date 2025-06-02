import asyncio
import time
from machine import Pin

import unittest
from primitives import broker, EButton

from main import AlarmSchedulingAgent, Scheduler, ping, Messages, Waker



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
            isinstance(agent.create_task(), asyncio.Task)
        )

    def test_schedule_method_on_subscription_message(self):

        def fake_wake_sequence():
            pass

        scheduler = self.FakeScheduler()

        agent = AlarmSchedulingAgent(fake_wake_sequence, scheduler)

        async def emit_alarm_set_message():
            broker.publish(Messages.SET_ALARM, (12, 30))

        async def test():
            agent.create_task()
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


if __name__ == '__main__':
    unittest.main()
