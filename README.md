# Project Numerous Shore

An IoT alarm clock using Micropython on a RPi Pico W

# Setup

## Dependencies

* uv

## Wifi Credentials

Create a file on the device called `credentials.txt` with your wifi credentials in the following format:
```
SSID
PASSWORD
```

## Static Files

Static and templates must be copied to the device.

```bash
uv run mpr put templates/index.html templates/
```

## Install dependencies

Dependencies are contained in the lib folder.

Subdirectories such as `lib/primitives` must be created manually before running xrun.


## Compile MPY files

mpr can cross-compile the python files to MPY files for the Pico W using `xrun`

```bash
uv run mpr xrun main
```

This will also change main.py to main.mpy, which is not recognised by Micropython when booting! If you wan to run the compiled code on boot, you must also copy over the main.py file:

```bash
uv run mpr put main.py .
```

# Run Tests

Run tests by mounting the local file system on the device and running the tests in the `tests` folder.


```bash
uv run mpr --mount . run tests/test_main.py
```

# Notes

If ampy can't connect make the port usable again
```bash
sudo chmod 666 /dev/ttyACM0
```

Open REPL with minicom
```bash
minicom -D /dev/ttyACM0 -b 115200
```

Or even better with mpr:
```bash
mpr repl
```

