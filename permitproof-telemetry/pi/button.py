import threading
from pi.pins import BUTTON


class RealButton:
    def __init__(self, factory):
        from gpiozero import Button
        self.pending = threading.Event()
        self.button = Button(BUTTON, pull_up=True, bounce_time=0.05, pin_factory=factory)
        self.button.when_pressed = self.pending.set

    def poll(self):
        if self.pending.is_set():
            self.pending.clear()
            return True
        return False

    def close(self):
        self.button.close()
