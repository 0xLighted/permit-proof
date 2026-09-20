from pi.leds import MockLEDs, RealLEDs
from pi.display import MockDisplay, RealDisplay


class Hardware:
    def __init__(self, real=False, lcd=False):
        self.real = real
        self.resources = []
        self.leds, self.display = MockLEDs(), MockDisplay()
        self.nfc, self.button = None, None
        try:
            if real:
                from gpiozero.pins.lgpio import LGPIOFactory
                from pi.nfc import RealNFC
                from pi.button import RealButton
                self.factory = LGPIOFactory()
                self.resources.append(self.factory)
                self.leds = RealLEDs(self.factory)
                self.resources.append(self.leds)
                self.button = RealButton(self.factory)
                self.resources.append(self.button)
                self.nfc = RealNFC()
                self.resources.append(self.nfc)
            if lcd:
                if not real:
                    raise ValueError("Real LCD requires hardware mode")
                self.display = RealDisplay()
                self.resources.append(self.display)
        except Exception:
            self.close()
            raise

    def apply(self, state):
        self.leds.show(state.led)
        self.display.show(state.lcd_pages)

    def offline(self):
        self.leds.show("yellow")
        self.display.show([["Server unavailable", "State unconfirmed"]])

    def close(self):
        for resource in reversed(self.resources):
            try:
                resource.close()
            except Exception:
                pass
        self.resources = []
