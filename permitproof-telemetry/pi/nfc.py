"""PN532 SPI adapter. Nothing is imported or powered in mock mode."""
import time


class RealNFC:
    def __init__(self):
        import board
        import busio
        from digitalio import DigitalInOut
        from adafruit_pn532.spi import PN532_SPI
        self.spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
        self.cs = None
        try:
            self.cs = DigitalInOut(board.D5)  # GPIO5 / physical pin 29
            self.reader = PN532_SPI(self.spi, self.cs, debug=False)
            chip, major, minor, _ = self.reader.firmware_version
            print(f"PN532 responded: {chip:02X}, firmware {major}.{minor}")
            self.reader.SAM_configuration()
        except Exception:
            self.close()
            raise
        self.last_uid, self.last_seen = None, 0

    def poll(self):
        uid = self.reader.read_passive_target(timeout=0.1)
        now = time.monotonic()
        if uid is None:
            if now - self.last_seen > 1.0:
                self.last_uid = None
            return None
        value = uid.hex(":").upper()
        self.last_seen = now
        if value == self.last_uid:
            return None
        self.last_uid = value
        return value

    def close(self):
        if self.cs is not None:
            self.cs.deinit()
        self.spi.deinit()
