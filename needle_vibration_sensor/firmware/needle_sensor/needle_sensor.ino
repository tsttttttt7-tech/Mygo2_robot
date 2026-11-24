/*
 * Wireless piezo needle sensor - ESP32-S3 firmware (Arduino-ESP32 core 3.x, ESP-IDF 5.x drivers)
 *
 * ADC_MODE 0 : ESP32-S3 internal 12-bit ADC, 80 kSPS, input GPIO1 (ADC1_CH0)   <- parts available in Baghdad
 * ADC_MODE 1 : PCM1808 module, 24-bit, 48 kSPS stereo over I2S (ESP32 = clock master)
 *
 * The ESP32 creates its own Wi-Fi network "NEEDLE-SENSOR" (password needle1234).
 * Connect the laptop to it and run  software/receiver.py . Data goes as UDP to port 5005.
 *
 * Packet (little endian):  'N''D''L''1' | uint32 seq | uint32 fs | uint8 fmt | uint8 nch | uint8 trig | uint8 rsv | payload
 *   fmt 1 = uint16 raw 12-bit ADC codes     fmt 2 = int24 packed, interleaved channels
 */
#include <WiFi.h>
#include <WiFiUdp.h>

#define ADC_MODE 0            // 0 = internal ADC, 1 = PCM1808

// ---------------- pins (free on ESP32-S3-DevKitC-1 and on the N16R8 CAM board) ----------------
#define PIN_ADC     1         // GPIO1 = ADC1 channel 0 (never use ADC2 pins with Wi-Fi)
#define PIN_MCLK    38        // PCM1808 SCK (system clock, 12.288 MHz)
#define PIN_BCK     39        // PCM1808 BCK
#define PIN_LRCK    40        // PCM1808 LRC
#define PIN_DIN     41        // PCM1808 OUT
#define PIN_TRIG    42        // optional sync input from robot (3.3 V logic, HIGH = inserting)

static const char *AP_SSID = "NEEDLE-SENSOR";
static const char *AP_PASS = "needle1234";
static const uint16_t PORT = 5005;

WiFiUDP udp;
IPAddress client;
bool haveClient = false;
uint32_t seq = 0, lastHello = 0;
uint8_t pkt[1472];

static void putHeader(uint32_t fs, uint8_t fmt, uint8_t nch) {
  memcpy(pkt, "NDL1", 4);
  memcpy(pkt + 4, &seq, 4);
  memcpy(pkt + 8, &fs, 4);
  pkt[12] = fmt; pkt[13] = nch; pkt[14] = digitalRead(PIN_TRIG); pkt[15] = 0;
}

static void pollClient() {                       // laptop sends "hello" -> we stream to it
  int n = udp.parsePacket();
  if (n > 0) {
    char b[16]; udp.read(b, sizeof(b));
    client = udp.remoteIP(); haveClient = true; lastHello = millis();
  }
  if (haveClient && millis() - lastHello > 5000) haveClient = false;   // laptop gone
}

static void sendPacket(size_t len) {
  if (!haveClient) return;
  udp.beginPacket(client, PORT);
  udp.write(pkt, len);
  udp.endPacket();
  seq++;
}

#if ADC_MODE == 0
// ======================================================================== internal ADC
#include "esp_adc/adc_continuous.h"
static const uint32_t FS = 80000;
static const int SAMPLES_PER_PKT = 640;          // 8 ms, 1280 bytes payload
adc_continuous_handle_t adc;
uint8_t raw[SAMPLES_PER_PKT * SOC_ADC_DIGI_RESULT_BYTES];

void setupAcq() {
  adc_continuous_handle_cfg_t hc = {};
  hc.max_store_buf_size = 32768;
  hc.conv_frame_size = sizeof(raw);
  ESP_ERROR_CHECK(adc_continuous_new_handle(&hc, &adc));

  adc_digi_pattern_config_t pat = {};
  pat.atten = ADC_ATTEN_DB_12;                   // ~0-3.1 V input range
  pat.channel = ADC_CHANNEL_0;                   // GPIO1
  pat.unit = ADC_UNIT_1;
  pat.bit_width = SOC_ADC_DIGI_MAX_BITWIDTH;

  adc_continuous_config_t cfg = {};
  cfg.pattern_num = 1;
  cfg.adc_pattern = &pat;
  cfg.sample_freq_hz = FS;
  cfg.conv_mode = ADC_CONV_SINGLE_UNIT_1;
  cfg.format = ADC_DIGI_OUTPUT_FORMAT_TYPE2;
  ESP_ERROR_CHECK(adc_continuous_config(adc, &cfg));
  ESP_ERROR_CHECK(adc_continuous_start(adc));
}

void acquireAndSend() {
  uint32_t got = 0;
  if (adc_continuous_read(adc, raw, sizeof(raw), &got, 100) != ESP_OK) return;
  putHeader(FS, 1, 1);
  uint16_t *out = (uint16_t *)(pkt + 16);
  int n = 0;
  for (uint32_t i = 0; i + SOC_ADC_DIGI_RESULT_BYTES <= got && n < SAMPLES_PER_PKT; i += SOC_ADC_DIGI_RESULT_BYTES) {
    adc_digi_output_data_t *d = (adc_digi_output_data_t *)&raw[i];
    out[n++] = d->type2.data;
  }
  sendPacket(16 + 2 * n);
}

#else
// ======================================================================== PCM1808 over I2S
#include "driver/i2s_std.h"
static const uint32_t FS = 48000;
static const int FRAMES_PER_PKT = 240;           // 5 ms, 2 ch x 3 bytes x 240 = 1440 bytes payload
i2s_chan_handle_t rx;
int32_t buf[FRAMES_PER_PKT * 2];

void setupAcq() {
  i2s_chan_config_t cc = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
  cc.dma_desc_num = 8;
  cc.dma_frame_num = FRAMES_PER_PKT;
  ESP_ERROR_CHECK(i2s_new_channel(&cc, NULL, &rx));

  i2s_std_config_t sc = {};
  sc.clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(FS);
  sc.clk_cfg.mclk_multiple = I2S_MCLK_MULTIPLE_256;          // 12.288 MHz system clock
  sc.slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_32BIT, I2S_SLOT_MODE_STEREO);  // BCK = 64 fs
  sc.gpio_cfg.mclk = (gpio_num_t)PIN_MCLK;
  sc.gpio_cfg.bclk = (gpio_num_t)PIN_BCK;
  sc.gpio_cfg.ws = (gpio_num_t)PIN_LRCK;
  sc.gpio_cfg.dout = I2S_GPIO_UNUSED;
  sc.gpio_cfg.din = (gpio_num_t)PIN_DIN;
  ESP_ERROR_CHECK(i2s_channel_init_std_mode(rx, &sc));
  ESP_ERROR_CHECK(i2s_channel_enable(rx));
}

void acquireAndSend() {
  size_t got = 0;
  if (i2s_channel_read(rx, buf, sizeof(buf), &got, 100) != ESP_OK) return;
  putHeader(FS, 2, 2);
  uint8_t *p = pkt + 16;
  int n = got / 4;
  for (int i = 0; i < n; i++) {
    int32_t s = buf[i] >> 8;                     // 24-bit sample, MSB-aligned in 32-bit slot
    *p++ = s & 0xFF; *p++ = (s >> 8) & 0xFF; *p++ = (s >> 16) & 0xFF;
  }
  sendPacket(16 + 3 * n);
}
#endif

void setup() {
  Serial.begin(115200);
  pinMode(PIN_TRIG, INPUT_PULLDOWN);
  WiFi.mode(WIFI_AP);
  WiFi.softAP(AP_SSID, AP_PASS, 6);              // channel 6
  WiFi.setSleep(false);                          // no power-save = no dropouts
  WiFi.setTxPower(WIFI_POWER_11dBm);             // short range, less RF noise into the ADC
  udp.begin(PORT);
  setupAcq();
  Serial.printf("AP %s ready at %s, mode %d\n", AP_SSID, WiFi.softAPIP().toString().c_str(), ADC_MODE);
}

void loop() {
  pollClient();
  acquireAndSend();
}
