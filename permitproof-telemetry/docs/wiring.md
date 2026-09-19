# Fixed wiring reference — do not use generated pictures for exact holes

Power off and unplug the Pi before changing wiring. The PN532 loose header must be soldered; tape is not a substitute. There are no pin changes in this project relative to the latest agreed table.

## PN532 SPI

Switch 1 OFF, switch 2 ON. Follow the printed board labels.

| PN532 | Pi physical pin | BCM |
|---|---:|---|
| VCC | 1 | 3.3 V supply |
| GND | 6 | Ground |
| MOSI | 19 | 10 |
| MISO | 21 | 9 |
| SCK | 23 | 11 |
| SS | **29** | **5** |
| IRQ, RSTO | Disconnected | — |

The current driver uses GPIO5. Physical pin 24 from an early draft is obsolete for this code. SDA/SCL are unused on this NFC module in SPI mode.

## LEDs and button

Every LED needs its **own 1 kΩ, ¼ W series resistor**. GPIO → resistor → anode → cathode → ground. No solder is needed on a breadboard.

| Component | Pi physical pin | BCM |
|---|---:|---:|
| Green | 11 | 17 |
| Yellow | 13 | 27 |
| Red | 15 | 22 |
| Blue | 16 | 23 |
| White | 18 | 24 |
| Button | 22 | 25 |
| Shared ground | 14 (or another GND, including 6) | — |

Use switched button contacts, not an internally joined pair. Software enables the internal pull-up and 50 ms debounce. Do not connect the button to 5 V.

The previous single-red-LED exercise used LED anode e20, cathode e21, resistor a20↔a24, GPIO jumper b24 and ground jumper b21. This is one valid placement, not a claim that the photos were verified. Pin and continuity verification are required before real tests.

## LCD

Your 1602 I²C backpack has not been electrically verified for a direct Pi connection. Keep it disconnected until suitable bidirectional I²C level shifting or a verified compatible replacement is available. Do not use ordinary resistor dividers on I²C.

Conditional wiring with a suitable shifter: Pi pin 1 → LV; pin 2 → HV and LCD VCC; common GND; pin 3/GPIO2 → LV1, HV1 → LCD SDA; pin 5/GPIO3 → LV2, HV2 → LCD SCL. Confirm the actual module supply and chip. The optional software assumes PCF8574, address configured via `.env` (0x27 is only an initial default).

Enabling real LCD requires both `--lcd` and `PERMITPROOF_LCD_VERIFIED=1`. This setting is a human confirmation, not automatic electrical verification.

Buzzer is intentionally not driven; no verified driver circuit is available. DHT22/PIR are outside the currently selected Number 1 hardware.
