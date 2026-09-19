from pi.pins import LEDS


class MockLEDs:
    def show(self, colour):
        if colour not in LEDS:
            raise ValueError("Unknown LED colour")
        print(f"[MOCK LED] {colour.upper()} (all other LEDs off)", flush=True)

    def close(self):
        pass


class RealLEDs:
    def __init__(self, factory):
        from gpiozero import LED
        self.outputs = {}
        try:
            for colour, pin in LEDS.items():
                self.outputs[colour] = LED(pin, pin_factory=factory, initial_value=False)
        except Exception:
            self.close()
            raise

    def show(self, colour):
        if colour not in self.outputs:
            raise ValueError("Unknown LED colour")
        for led in self.outputs.values():
            led.off()
        self.outputs[colour].on()

    def close(self):
        for led in self.outputs.values():
            led.off()
            led.close()
