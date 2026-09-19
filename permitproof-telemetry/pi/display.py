"""16x2 pages. Real LCD is opt-in after electrical verification."""
import os


class MockDisplay:
    backend = "console"

    def show(self, pages):
        for index, page in enumerate(pages, 1):
            print(f"[MOCK LCD page {index}] {page[0][:16]:16} | {page[1][:16]:16}", flush=True)

    def tick(self):
        pass

    def close(self):
        pass


class RealDisplay:
    backend = "i2c"

    def __init__(self):
        if os.getenv("PERMITPROOF_LCD_VERIFIED") != "1":
            raise RuntimeError("LCD blocked: verify level shifting before enabling real I2C")
        import time
        from RPLCD.i2c import CharLCD
        self.time = time
        self.lcd = CharLCD("PCF8574", int(os.getenv("PERMITPROOF_LCD_ADDRESS", "0x27"), 0),
                           port=1, cols=16, rows=2, charmap="A00")
        self.pages, self.index, self.deadline = [], 0, 0

    def _draw(self):
        self.lcd.clear()
        for row, line in enumerate(self.pages[self.index]):
            self.lcd.cursor_pos = (row, 0)
            self.lcd.write_string(line[:16])
        self.deadline = self.time.monotonic() + 2

    def show(self, pages):
        if not pages or any(len(page) != 2 for page in pages):
            raise ValueError("LCD needs two lines per page")
        self.pages, self.index = pages, 0
        self._draw()

    def tick(self):
        if len(self.pages) > 1 and self.time.monotonic() >= self.deadline:
            self.index = (self.index + 1) % len(self.pages)
            self._draw()

    def close(self):
        self.lcd.close(clear=True)
