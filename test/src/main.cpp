// WeAct 3.7" e-paper (240x416, UC8253) on STM32 Nucleo F411RE
// Known-good. READ README.md BEFORE CHANGING THE SPI SETUP BELOW.
//
// Wiring (display -> Nucleo):
//   VCC->3V3  GND->GND  SDA->D11(PA7,MOSI)  SCL->D13(PA5,SCK)
//   CS->D10(PB6)  D/C->D9(PC7)  RES->D8(PA9)  BUSY->D7(PA8)
#include <Arduino.h>
#include <SPI.h>
#include <GxEPD2_BW.h>
#include <Fonts/FreeMonoBold18pt7b.h>

// Use STM32 port names (PBx), NOT Dx: PlatformIO builds the *generic* F411
// variant here, where Dx / default SPI pins are not the Nucleo header.
#define EPD_CS   PB6
#define EPD_DC   PC7
#define EPD_RST  PA9
#define EPD_BUSY PA8

SPIClass* epdSPI;

// WeAct 3.7" 240x416 = UC8253 = GDEY037T03 (NOT GxEPD2_370_TC1, that is a
// different 280x480 Waveshare panel and will give lines / gray / no image).
GxEPD2_BW<GxEPD2_370_GDEY037T03, GxEPD2_370_GDEY037T03::HEIGHT> display(
    GxEPD2_370_GDEY037T03(EPD_CS, EPD_DC, EPD_RST, EPD_BUSY));

void setup() {
  // Explicit SPI1 pins, built from STM32 port names.
  epdSPI = new SPIClass(pinNametoDigitalPin(PA_7), pinNametoDigitalPin(PA_6),
                        pinNametoDigitalPin(PA_5), PNUM_NOT_DEFINED);
  // REQUIRED WORKAROUND: the core only calls spi_init() when requested settings
  // differ from the stored defaults (4 MHz, MSB, mode 0). The display driver
  // asks for exactly those, so SPI would never start (clock off, hang in
  // spi_transfer). Request something different once to force the init.
  epdSPI->beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE0));
  epdSPI->endTransaction();
  display.epd2.selectSPI(*epdSPI, SPISettings(4000000, MSBFIRST, SPI_MODE0));

  display.init(0);          // 0 = no serial diagnostics
  display.setRotation(1);   // landscape 416x240
  display.setFullWindow();
  display.firstPage();
  do {
    display.fillScreen(GxEPD_WHITE);
    display.setTextColor(GxEPD_BLACK);
    display.setFont(&FreeMonoBold18pt7b);
    int16_t x1, y1; uint16_t w, h;
    const char* msg = "HELLO MY WORLD";
    display.getTextBounds(msg, 0, 0, &x1, &y1, &w, &h);
    display.setCursor((display.width() - w) / 2 - x1, (display.height() - h) / 2 - y1);
    display.print(msg);
    display.drawRect(2, 2, display.width() - 4, display.height() - 4, GxEPD_BLACK);
  } while (display.nextPage());
  display.hibernate();
}

void loop() {}
