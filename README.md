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

