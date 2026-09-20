"""BCM numbering for code. PHYSICAL is the 40-pin header position."""
LEDS = {"green": 17, "yellow": 27, "red": 22, "blue": 23, "white": 24}
BUTTON = 25
PN532_CS = 5  # Physical 29, NOT physical 24 from the older wiring draft.
PHYSICAL = {"green": 11, "yellow": 13, "red": 15, "blue": 16, "white": 18,
            "button": 22, "pn532_cs": 29, "mosi": 19, "miso": 21, "sck": 23}
