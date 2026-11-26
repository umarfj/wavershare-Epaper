# E-paper camera

Take a picture with an ESP32-S3 camera board and show it on a 3.7" e-paper display.
A laptop viewer shows the live camera feed over USB; clicking **Capture to e-paper**
dithers the current frame to black and white and draws it on the display.

```
camera --> ESP32-S3 --USB-UART (4 Mbaud)--> laptop viewer (live video)
                 ^                                  |
                 +---- 1-bit 416x240 bitmap --------+  (Capture button)
                 |
              e-paper (SPI)
```

## Hardware

- Freenove ESP32-S3-WROOM CAM board (camera attached, 8 MB PSRAM)
- WeAct 3.7" e-paper, 240x416, UC8253 controller, 4-wire SPI
- USB cable to the board's **USB-UART** port (CH343 chip, shows up as a COM port)

### Wiring

The camera uses GPIO 4-13 and 15-18, so the display must avoid those pins.

| Display | ESP32-S3 GPIO |
|---|---|
| VCC | 3V3 |
| GND | GND |
| SDA (MOSI) | 21 |
| SCL (SCK) | 14 |
| CS | 47 |
| D/C | 42 |
| RES | 41 |
| BUSY | 2 |

The pins are defined in `esp32_test/cam_test/src/epd.h` and can be overridden with
`-D` build flags.

## Run it

Requires Python 3 and PlatformIO.

```
pip install platformio pyserial opencv-python numpy pillow
cd esp32_test/cam_test

# build and flash (replace COM9 with your board's port)
python -m platformio run -e freenove_s3 -t upload --upload-port COM9

# start the viewer (close any serial monitor first: only one program can hold the port)
python gui_viewer.py COM9
```

In the viewer: the left side is the live video. **Capture to e-paper** sends the
current frame to the display; a full refresh takes about 2-3 seconds and the video
pauses meanwhile. Controls:

- **Rotate**: turns the live view and the captured image.
- **Auto contrast / gamma**: adapts each capture to the lighting. The brightness
  target slider makes the result darker or lighter. `AUTO_TARGET` and `GAMMA_MIN`
  at the top of `gui_viewer.py` set the defaults.
- Untick Auto to use manual contrast and gamma sliders.

`viewer.py` is a simpler OpenCV window (press space to capture).

## Test the display on its own

The `epd_test` environment draws text on the display without touching the camera.
It uses the original wiring (SDA 13, SCL 14, CS 15, D/C 4, RES 12, BUSY 2), so
connect the display that way for this test only:

```
python -m platformio run -e epd_test -t upload --upload-port COM9
```

A healthy run prints `_Update_Full : 2040000` (about 2 s) on serial at 115200 baud.

## How it works

- **Camera stream.** The firmware sends each JPEG frame as `AA 55 AA 55`, a 4-byte
  little-endian length, then the JPEG bytes. Truncated JPEGs (the sensor produces a
  few) are dropped. At VGA, quality 10, 4 Mbaud this gives about 25 fps.
- **To the display.** The laptop crops, auto-contrasts, dithers (Floyd-Steinberg)
  and packs the frame to 416x240, 1 bit per pixel (52 bytes per row, MSB first,
  1 = black). It sends `EPD!` followed by the 12,480 bytes. The firmware draws it
  with GxEPD2 and replies `EPD_DONE`.
- **Display driver.** Use `GxEPD2_370_GDEY037T03`. `GxEPD2_370_TC1` is a different,
  280x480 panel and gives lines or a gray screen.

## `test/`: earlier STM32 version

`test/` is the first working version of the display on an STM32 Nucleo F411RE,
including notes on the three bugs that cost the most time. See `test/README.md`.
The STM32 SPI workaround described there is not needed on the ESP32.
