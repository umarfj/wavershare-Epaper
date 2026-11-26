// Display-only test: draws text and a border, no camera involved.
#include "epd.h"
#include <Fonts/FreeMonoBold18pt7b.h>

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.printf("EPD test: MOSI=%d SCK=%d CS=%d DC=%d RST=%d BUSY=%d\n",
                EPD_MOSI, EPD_SCK, EPD_CS, EPD_DC, EPD_RST, EPD_BUSY);
  epdBegin();
  display.init(115200);  // serial diagnostics on, so a busy timeout is reported
  display.setRotation(1);
  display.setFullWindow();
  display.firstPage();
  do {
    display.fillScreen(GxEPD_WHITE);
    display.setTextColor(GxEPD_BLACK);
    display.setFont(&FreeMonoBold18pt7b);
    int16_t x1, y1; uint16_t w, h;
    const char* msg = "ESP32-S3 EPD OK";
    display.getTextBounds(msg, 0, 0, &x1, &y1, &w, &h);
    display.setCursor((display.width() - w) / 2 - x1, (display.height() - h) / 2 - y1);
    display.print(msg);
    display.drawRect(2, 2, display.width() - 4, display.height() - 4, GxEPD_BLACK);
  } while (display.nextPage());
  display.hibernate();
  Serial.println("EPD_TEST_DONE");
}

void loop() {}
