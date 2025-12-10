/*
  - Cảm biến vân tay AS608 qua Serial2 
  - Servo mở cửa CHỈ KHI ĐÚNG CẢ VÂN TAY + KHUÔN MẶT
  - Giao tiếp Serial (USB) với Python (bridge.py)
  - IN LOG CHI TIẾT ĐỂ DEBUG
*/

#include <Adafruit_Fingerprint.h>
#include <Servo.h>

// ==============================================================
// 1. KHAI BÁO CHÂN
// ==============================================================
#define SERVO_PIN 9
// Serial2: TX2 (16) → RX AS608, RX2 (17) → TX AS608

// ==============================================================
// 2. KHỞI TẠO ĐỐI TƯỢNG
// ==============================================================
Adafruit_Fingerprint finger = Adafruit_Fingerprint(&Serial2);
Servo doorServo;

// ==============================================================
// 3. BIẾN TOÀN CỤC
// ==============================================================
String command = "";
bool waiting_for_face = false;
uint8_t current_fingerprint_id = 0;

// ==============================================================
// 4. SETUP
// ==============================================================
void setup() {
  Serial.begin(9600);     // Giao tiếp với PC (bridge.py)
  Serial2.begin(57600);   // Giao tiếp với AS608 (Serial2)

  doorServo.attach(SERVO_PIN);
  doorServo.write(0);     // Cửa đóng
  delay(500);

  Serial.println("Arduino ready");

  if (finger.verifyPassword()) {
    Serial.println("FINGERPRINT_SENSOR_OK");
  } else {
    Serial.println("FINGERPRINT_SENSOR_ERROR");
    while (1) delay(1);
  }

  finger.getTemplateCount();
  Serial.print("TEMPLATES:");
  Serial.println(finger.templateCount);
}

// ==============================================================
// 5. VÒNG LẶP CHÍNH
// ==============================================================
void loop() {
  if (Serial.available()) {
    command = Serial.readStringUntil('\n');
    command.trim();
    if (command.length() > 0) {
      handleCommand(command);
    }
  }

  if (waiting_for_face) {
    delay(50);
    return;
  }
}

// ==============================================================
// 6. XỬ LÝ LỆNH TỪ PYTHON
// ==============================================================
void handleCommand(String cmd) {
  Serial.println("CMD_RECEIVED:" + cmd);  // IN RA ĐỂ DEBUG

  if (cmd == "SCAN_FINGERPRINT") {
    scanFingerprint();
  }
  else if (cmd.startsWith("FACE_OK ID:")) {
    // ĐÚNG: "FACE_OK ID:1" → substring(11)
    int id = cmd.substring(11).toInt();
    Serial.println("NHẬN FACE_OK ID:" + String(id));
    Serial.println("CURRENT_ID: " + String(current_fingerprint_id));

    if (id == current_fingerprint_id && id > 0) {
        Serial.println("XÁC THỰC THÀNH CÔNG → MỞ CỬA");
        openDoor();
    } else {
        Serial.println("FACE_MISMATCH → RESET TRẠNG THÁI");
        // RESET DÙ SAI
        waiting_for_face = false;
        current_fingerprint_id = 0;
        Serial.println("SYSTEM_RESET_MISMATCH");
    }
    waiting_for_face = false;
    current_fingerprint_id = 0;
}
  else if (cmd == "FACE_TIMEOUT") {
    Serial.println("FACE_TIMEOUT → RESET");
    waiting_for_face = false;
    current_fingerprint_id = 0;
  }
  else if (cmd.startsWith("ENROLL")) {
    int id = cmd.substring(6).toInt();
    if (id > 0 && id < 128) {
      enrollFingerprint(id);
    }
  }
  else if (cmd == "SCAN_FINGERPRINT") {
    if (waiting_for_face) {
        Serial.println("SKIP: ĐANG CHỜ KHUÔN MẶT");
    } else {
        scanFingerprint();
    }
}
}

// ==============================================================
// 7. QUÉT VÂN TAY
// ==============================================================
void scanFingerprint() {
  if (waiting_for_face) {
    Serial.println("SKIP_SCAN: WAITING_FOR_FACE");
    return;
  }

  Serial.println("SCAN_START");
  uint8_t p = -1;
  unsigned long noFingerTime = 0;

  while (p != FINGERPRINT_OK) {
    p = finger.getImage();
    if (p == FINGERPRINT_OK) {
      Serial.println("IMAGE_TAKEN");
    } else if (p == FINGERPRINT_NOFINGER) {
      if (noFingerTime == 0) noFingerTime = millis();
      if (millis() - noFingerTime > 15000) {
        Serial.println("SCAN_TIMEOUT");
        return;
      }
      delay(50);
      continue;
    } else {
      Serial.println("IMAGE_ERROR");
      return;
    }
    noFingerTime = 0;
  }

  p = finger.image2Tz();
  if (p != FINGERPRINT_OK) {
    Serial.println("CONVERT_ERROR");
    return;
  }

  p = finger.fingerFastSearch();
  if (p == FINGERPRINT_OK) {
    current_fingerprint_id = finger.fingerID;
    waiting_for_face = true;
    Serial.println("FINGERPRINT_OK ID:" + String(current_fingerprint_id));
    Serial.println("WAITING_FOR_FACE");
    return;
  } else {
    Serial.println("FINGERPRINT_NOTFOUND");
  }
}

// ==============================================================
// 8. MỞ CỬA (3 GIÂY)
// ==============================================================
void openDoor() {
  doorServo.write(90);
  Serial.println("DOOR_OPENED");
  delay(3000);
  doorServo.write(0);
  Serial.println("DOOR_CLOSED");

  // RESET HOÀN TOÀN SAU KHI ĐÓNG CỬA
  current_fingerprint_id = 0;
  waiting_for_face = false;  
  Serial.println("SYSTEM_RESET_READY");
}
// ==============================================================
// 9. ĐĂNG KÝ VÂN TAY MỚI
// ==============================================================
void enrollFingerprint(uint8_t id) {
  Serial.print("ENROLL_START ID:");
  Serial.println(id);

  int p = -1;
  while (p != FINGERPRINT_OK) {
    p = finger.getImage();
    if (p == FINGERPRINT_OK) {
      Serial.println("IMAGE1_OK");
    } else if (p == FINGERPRINT_NOFINGER) {
      delay(50);
      continue;
    } else {
      Serial.println("IMAGE1_ERROR");
      return;
    }
  }

  p = finger.image2Tz(1);
  if (p != FINGERPRINT_OK) {
    Serial.println("CONVERT1_ERROR");
    return;
  }

  Serial.println("REMOVE_FINGER");
  delay(2000);
  p = 0;
  while (p != FINGERPRINT_NOFINGER) {
    p = finger.getImage();
  }

  Serial.println("PLACE_SAME_FINGER");
  p = -1;
  while (p != FINGERPRINT_OK) {
    p = finger.getImage();
    if (p == FINGERPRINT_OK) {
      Serial.println("IMAGE2_OK");
    } else if (p == FINGERPRINT_NOFINGER) {
      delay(50);
      continue;
    } else {
      Serial.println("IMAGE2_ERROR");
      return;
    }
  }

  p = finger.image2Tz(2);
  if (p != FINGERPRINT_OK) {
    Serial.println("CONVERT2_ERROR");
    return;
  }

  p = finger.createModel();
  if (p != FINGERPRINT_OK) {
    Serial.println("MODEL_ERROR");
    return;
  }

  p = finger.storeModel(id);
  if (p == FINGERPRINT_OK) {
    Serial.print("ENROLL_SUCCESS ID:");
    Serial.println(id);
  } else {
    Serial.println("STORE_ERROR");
  }
}