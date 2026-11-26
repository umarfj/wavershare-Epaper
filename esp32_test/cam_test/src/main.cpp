// Camera -> laptop viewer over UART, and laptop -> e-paper.
//
// ESP32 -> laptop frame:  AA 55 AA 55, uint32 LE length, JPEG bytes.
// laptop -> ESP32 image:  'E' 'P' 'D' '!', then EPD_BMP_BYTES bytes (416x240, 1 = black).
//   The laptop does the resize/dither (see viewer.py); the ESP32 just draws it.
// The ESP32 answers with a text line: EPD_DONE or EPD_ERROR ...
#include <Arduino.h>
#include "esp_camera.h"
#include "epd.h"

// Freenove ESP32-S3-WROOM CAM pin map
#define PWDN_GPIO_NUM  -1
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM  15
#define SIOD_GPIO_NUM  4
#define SIOC_GPIO_NUM  5
#define Y9_GPIO_NUM    16
#define Y8_GPIO_NUM    17
#define Y7_GPIO_NUM    18
#define Y6_GPIO_NUM    12
#define Y5_GPIO_NUM    10
#define Y4_GPIO_NUM    8
#define Y3_GPIO_NUM    9
#define Y2_GPIO_NUM    11
#define VSYNC_GPIO_NUM 6
#define HREF_GPIO_NUM  7
#define PCLK_GPIO_NUM  13

static uint8_t epdBuf[EPD_BMP_BYTES];
static const uint8_t EPD_MAGIC[4] = {'E', 'P', 'D', '!'};

static void showOnEpaper() {
  display.init(0);
  display.setRotation(1);
  display.setFullWindow();
  display.firstPage();
  do {
    display.fillScreen(GxEPD_WHITE);
    display.drawBitmap(0, 0, epdBuf, EPD_W, EPD_H, GxEPD_BLACK);
  } while (display.nextPage());  // ~2 s full refresh; the video pauses meanwhile
  display.hibernate();
}

// Looks for the magic in the incoming bytes; on a match reads the bitmap and displays it.
static void pollSerialForImage() {
  static uint8_t idx = 0;
  while (Serial.available()) {
    int c = Serial.read();
    if (c == EPD_MAGIC[idx]) {
      if (++idx == 4) {
        idx = 0;
        size_t got = Serial.readBytes(epdBuf, EPD_BMP_BYTES);
        if (got != EPD_BMP_BYTES) {
          Serial.printf("EPD_ERROR short image %u/%u\n", (unsigned)got, (unsigned)EPD_BMP_BYTES);
          return;
        }
        showOnEpaper();
        Serial.println("EPD_DONE");
      }
    } else {
      idx = (c == EPD_MAGIC[0]) ? 1 : 0;
    }
  }
}

void setup() {
  Serial.setRxBufferSize(32768);  // must hold a whole bitmap while the camera loop runs
  Serial.begin(4000000);
  Serial.setTimeout(3000);
  delay(500);

  epdBegin();

  camera_config_t c = {};
  c.ledc_channel = LEDC_CHANNEL_0;
  c.ledc_timer = LEDC_TIMER_0;
  c.pin_d0 = Y2_GPIO_NUM; c.pin_d1 = Y3_GPIO_NUM; c.pin_d2 = Y4_GPIO_NUM; c.pin_d3 = Y5_GPIO_NUM;
  c.pin_d4 = Y6_GPIO_NUM; c.pin_d5 = Y7_GPIO_NUM; c.pin_d6 = Y8_GPIO_NUM; c.pin_d7 = Y9_GPIO_NUM;
  c.pin_xclk = XCLK_GPIO_NUM; c.pin_pclk = PCLK_GPIO_NUM;
  c.pin_vsync = VSYNC_GPIO_NUM; c.pin_href = HREF_GPIO_NUM;
  c.pin_sccb_sda = SIOD_GPIO_NUM; c.pin_sccb_scl = SIOC_GPIO_NUM;
  c.pin_pwdn = PWDN_GPIO_NUM; c.pin_reset = RESET_GPIO_NUM;
  c.xclk_freq_hz = 20000000;
  c.pixel_format = PIXFORMAT_JPEG;
  c.frame_size = FRAMESIZE_VGA;
  c.jpeg_quality = 10;
  c.fb_count = 2;
  c.fb_location = CAMERA_FB_IN_PSRAM;
  c.grab_mode = CAMERA_GRAB_LATEST;

  esp_err_t err = esp_camera_init(&c);
  if (err != ESP_OK) {
    while (true) {
      Serial.printf("CAMERA_INIT_FAILED 0x%x\n", err);
      delay(1000);
    }
  }
  sensor_t *s = esp_camera_sensor_get();
  Serial.printf("CAMERA_OK pid=0x%x\n", s ? s->id.PID : 0);
}

void loop() {
  pollSerialForImage();
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) { Serial.println("CAPTURE_FAILED"); delay(100); return; }
  if (fb->len < 4 || fb->buf[fb->len-2] != 0xFF || fb->buf[fb->len-1] != 0xD9) {
    esp_camera_fb_return(fb); return;  // truncated JPEG, skip it
  }
  uint8_t hdr[8] = {0xAA, 0x55, 0xAA, 0x55};
  uint32_t n = fb->len;
  memcpy(hdr + 4, &n, 4);
  Serial.write(hdr, 8);
  Serial.write(fb->buf, fb->len);
  esp_camera_fb_return(fb);
}
