# Project Numerous Shore

An IoT alarm clock using Micropython on a RPi Pico W

# Notes

If ampy can't connect make the port usable again
```bash
sudo chmod 666 /dev/ttyACM0
```

Open REPL with minicom
```bash
minicom -D /dev/ttyACM0 -b 115200
```
