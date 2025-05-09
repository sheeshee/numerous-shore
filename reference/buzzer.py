from picozero import Speaker
from time import sleep

speaker = Speaker(5)

while True:
    print("Playing sound")
    speaker.play(440, 1)  # Play a 440 Hz tone
    print("Stopped sound")
    sleep(1)  # Play for 1 second
