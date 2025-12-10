# --------------------------------------------------------------
# bridge.py  –  Serial ↔ Flask Bridge (2FA THẬT SỰ)
# --------------------------------------------------------------
import serial
import serial.tools.list_ports
import requests
import threading
import time
from flask import Flask, request

# ==============================================================
# 1. CẤU HÌNH
# ==============================================================
WEB_URL = "http://localhost:5000"
BAUD_RATE = 9600
SERIAL_TIMEOUT = 1

# ==============================================================
# 2. TỰ ĐỘNG TÌM CỔNG ARDUINO
# ==============================================================
def find_arduino_port():
    ports = serial.tools.list_ports.comports()
    for p in ports:
        desc = p.description.upper()
        if any(keyword in desc for keyword in ["ARDUINO", "CH340", "MEGA", "USB-SERIAL"]):
            return p.device
    return None

ARDUINO_PORT = find_arduino_port()
if not ARDUINO_PORT:
    print("Lỗi: Không tìm thấy Arduino! Cắm USB và thử lại.")
    exit()

print(f"Tìm thấy Arduino tại: {ARDUINO_PORT}")

# ==============================================================
# 3. KẾT NỐI SERIAL (TỰ THỬ LẠI)
# ==============================================================
ser = None
while ser is None:
    try:
        ser = serial.Serial(ARDUINO_PORT, BAUD_RATE, timeout=SERIAL_TIMEOUT)
        time.sleep(2)
        print(f"Đã kết nối Arduino tại {ARDUINO_PORT}")
    except Exception as e:
        print(f"Đang thử lại kết nối... ({e})")
        time.sleep(2)

# ==============================================================
# 4. FLASK SERVER NHỎ – NHẬN LỆNH TỪ WEB
# ==============================================================
bridge_app = Flask(__name__)


# === TRONG receive_command() ===
@bridge_app.route("/send", methods=["POST"])
def receive_command():
    cmd = request.form.get("cmd")
    if cmd and ser and ser.is_open:
        print(f"[GỬI Arduino] {cmd}")  # IN RA ĐÂY
        ser.write((cmd + "\n").encode('utf-8'))
    return "OK", 200
# Chạy server trên port 5001
threading.Thread(
    target=lambda: bridge_app.run(port=5001, use_reloader=False, debug=False),
    daemon=True
).start()

# ==============================================================
# 5. ĐỌC DỮ LIỆU TỪ ARDUINO → GỬI LÊN WEB
# ==============================================================
def arduino_listener():
    buffer = ""
    while True:
        try:
            if ser.in_waiting > 0:
                char = ser.read().decode('utf-8', errors='ignore')
                if char == '\n':
                    line = buffer.strip()
                    if line:
                        print(f"[Arduino] {line}")
                        process_arduino_message(line)
                    buffer = ""
                else:
                    buffer += char
            else:
                time.sleep(0.01)  # Giảm tải CPU
        except Exception as e:
            print(f"Lỗi đọc serial: {e}")
            time.sleep(1)

# === process_arduino_message ===
def process_arduino_message(line):
    try:
        if "FINGERPRINT_OK ID:" in line:
            fid = line.split("ID:")[1].strip()
            threading.Thread(
                target=requests.post,
                args=(f"{WEB_URL}/fingerprint",),
                kwargs={"data": {"status": f"FINGERPRINT_OK ID:{fid}"}, "timeout": 0.5},
                daemon=True
            ).start()

        elif "DOOR_OPENED" in line:
            threading.Thread(
                target=requests.post,
                args=(f"{WEB_URL}/door_status",),
                kwargs={"data": {"status": "OPEN"}, "timeout": 0.5},
                daemon=True
            ).start()
        elif "DOOR_CLOSED" in line:
            threading.Thread(
                target=requests.post,
                args=(f"{WEB_URL}/door_status",),
                kwargs={"data": {"status": "CLOSED"}, "timeout": 0.5},
                daemon=True
            ).start()
    except Exception as e:
        print(f"Lỗi xử lý tin nhắn: {e}")
# ==============================================================
# 6. KHỞI ĐỘNG
# ==============================================================
print("Bridge đang chạy... (Arduino ↔ Web)")

# Bắt đầu lắng nghe
threading.Thread(target=arduino_listener, daemon=True).start()

# Giữ chương trình chạy
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nĐã dừng bridge.")
    if ser and ser.is_open:
        ser.close()