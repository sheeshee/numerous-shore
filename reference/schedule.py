import asyncio
from sched.sched import schedule
from time import localtime

async def main():
    print("Asynchronous test running...")
    evt = asyncio.Event()
    asyncio.create_task(schedule(evt, hrs=None, mins=None, secs=range(0, 60, 10)))
    while True:
        await evt.wait()  # Multiple tasks may wait on an Event
        evt.clear()  # It must be cleared.
        yr, mo, md, h, m, s, wd = localtime()[:7]
        print(f"Event {h:02d}:{m:02d}:{s:02d} on {md:02d}/{mo:02d}/{yr}")

try:
    asyncio.run(main())
finally:
    _ = asyncio.new_event_loop()
