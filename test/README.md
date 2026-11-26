# WeAct 3.7" e-paper on STM32 Nucleo F411RE

Working project: prints "HELLO MY WORLD". Build/flash from this folder:

    %USERPROFILE%\.platformio\penv\Scripts\pio.exe run -t upload

(or `pio run -t upload` if pio is on PATH). Flashing uses the on-board ST-Link,
so no COM port needs to be chosen. The ST-Link virtual COM port is COM6
(115200 baud, USART2) if you want serial debug prints.

## Hardware

- Display: WeAct 3.7" e-paper, **240x416**, controller **UC8253**
  (the listing said 240x216, that is a typo)
- Board: Nucleo F411RE (STM32F411RET6), ST-Link on COM6
- Display jumper/selector must be 4-wire SPI

| Display | Nucleo | STM32 pin |
|---|---|---|
| VCC | 3V3 | |
| GND | GND | |
| SDA | D11 | PA7 (SPI1 MOSI) |
| SCL | D13 (labelled SCK/D13) | PA5 (SPI1 SCK) |
| CS  | D10 | PB6 |
| D/C | D9  | PC7 |
| RES | D8  | PA9 |
| BUSY| D7  | PA8 |

"SCL" on the display is the SPI clock. Use D13/SCK, **not** D15/SCL (that is I2C).

## The three bugs that cost hours (all fixed in src/main.cpp)

1. **Wrong driver class.** `GxEPD2_370_TC1` is a 280x480 SSD1677 Waveshare
   panel. The WeAct 3.7" is `GxEPD2_370_GDEY037T03` (240x416, UC8253).
   Symptom of the wrong one: screen unchanged, or thin vertical lines and a
   gray cast. This does NOT damage the panel; a correct full refresh clears it.

2. **PlatformIO uses the generic F411 variant, not the Nucleo one.** `Dx` names
   and the default SPI pins are therefore not the Nucleo header pins
   (default SPI ends up on PA1/PB13/PA11). Use STM32 port names (`PB6`, `PC7`,
   `PA9`, `PA8`) and build the SPI object explicitly from `PA_7/PA_6/PA_5`
   via `pinNametoDigitalPin()`.

3. **STM32 core never initialises SPI with default settings.**
   `SPIClass::configSpi()` only calls `spi_init()` if the requested settings
   differ from the stored ones. A new SPIClass already stores 4 MHz/MSB/MODE0,
   which is exactly what `begin()` and GxEPD2 request, so the SPI1 clock
   (RCC APB2ENR bit 12) is never enabled and the first `spi_transfer` spins
   forever. Symptom: firmware hangs at the first refresh, no "Busy Timeout".
   Fix: call `beginTransaction()` once with different settings (1 MHz) first.

Also needed in platformio.ini: the include path for `avr/pgmspace.h`
(`-I...framework-arduinoststm32/cores/arduino/api/deprecated-avr-comp`),
otherwise GxEPD2 fails to compile.

## Debugging tips (what actually found the problems)

- Serial: **call `Serial.begin()` first**; printing before it blocks forever.
- A hang with no output: halt with OpenOCD and resolve the PC with
  `arm-none-eabi-addr2line -f -e .pio/build/nucleo_f411re/firmware.elf <pc>`.
  PC inside `spi_transfer` with `r7 = 0` meant the SPI instance was never set up.
- Read `RCC->APB2ENR` / `SPI1->CR1`: if SPI1 clock (0x1000) is missing, SPI
  was never initialised.
- Healthy run: each full refresh takes about 2 s (`_Update_Full : 2039000`
  with diagnostics on) and BUSY goes low during it.
- A full refresh flashes the screen; that is normal. Avoid unplugging mid-refresh.
- `backup/main_debug.cpp.txt` is the verbose diagnostic version (pin map
  checks, reset-cause, SPI register prints, white/black/white clear cycle).

## Sketches

- `src/main.cpp`: rolling cat animation (partial refresh of a 416x152 strip per
  frame, full refresh after each back-and-forth pass to clear ghosting).
- `backup/main_hello.cpp.txt`: clean "HELLO MY WORLD" sketch. Copy over
  `src/main.cpp` to go back to it.
- Keep the SPI setup block at the top of `setup()` in any new sketch (bug 3).
- (Photo sketch saved as `backup/main_photo.cpp.txt`; needs `src/photo.h`.) Photo sketch: `tools/img2header.py` converts any image
  to `src/photo.h` (trims dark borders, cover-crops to 240x416, dithers to 1-bit):
  `python tools/img2header.py "image copy.png" src/photo.h tools/photo_preview.png 1.6 1.6`
  (last two args = contrast and gamma, both default 1.6; raise for darker/punchier, lower toward 1.0 for lighter)
  Previous sketches: `backup/main_cat.cpp.txt`, `backup/main_hello.cpp.txt`.
