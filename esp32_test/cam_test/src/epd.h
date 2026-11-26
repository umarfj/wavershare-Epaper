// WeAct 3.7" e-paper (240x416, UC8253 = GDEY037T03) on the Freenove ESP32-S3.
// See ../../test/README.md for the display facts. NOTE: the STM32-specific SPI
// workaround from that README is NOT needed on the ESP32.
//
// Default pins avoid every camera pin (4-13, 15-18). Override with -D flags.
//   display SDA -> GPIO21   display SCL -> GPIO14   display CS   -> GPIO47
//   display D/C -> GPIO42   display RES -> GPIO41   display BUSY -> GPIO2
#pragma once
#include <Arduino.h>
#include <SPI.h>
#include <GxEPD2_BW.h>

#ifndef EPD_MOSI
#define EPD_MOSI 21
#endif
#ifndef EPD_SCK
#define EPD_SCK 14
#endif
#ifndef EPD_CS
#define EPD_CS 47
#endif
#ifndef EPD_DC
#define EPD_DC 42
#endif
#ifndef EPD_RST
#define EPD_RST 41
#endif
#ifndef EPD_BUSY
#define EPD_BUSY 2
#endif

// Landscape (rotation 1): 416 wide x 240 high. Bitmap = 52 bytes/row, MSB first, 1 = black.
#define EPD_W 416
#define EPD_H 240
#define EPD_BMP_BYTES ((EPD_W / 8) * EPD_H)

static SPIClass epdSPI(FSPI);
static GxEPD2_BW<GxEPD2_370_GDEY037T03, GxEPD2_370_GDEY037T03::HEIGHT> display(
    GxEPD2_370_GDEY037T03(EPD_CS, EPD_DC, EPD_RST, EPD_BUSY));

static void epdBegin() {
  epdSPI.begin(EPD_SCK, -1, EPD_MOSI, -1);  // CS is driven by GxEPD2
  display.epd2.selectSPI(epdSPI, SPISettings(4000000, MSBFIRST, SPI_MODE0));
}
