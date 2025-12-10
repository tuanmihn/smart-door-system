# --------------------------------------------------------------
# app.py  –  Flask + OpenCV + Arduino Bridge (2FA THẬT SỰ)
# --------------------------------------------------------------
from flask import Flask, render_template, request, jsonify
import cv2
import numpy as np
import os
import threading
import time
import glob
import json
from datetime import datetime
import requests
from flask import session
import uuid
app = Flask(__name__)
KNOWN_FACES_DIR = "known_faces"
MAPPING_FILE = "user_mapping.json"
os.makedirs(KNOWN_FACES_DIR, exist_ok=True)

# ==============================================================
# 1. TRẠNG THÁI HỆ THỐNG
# ==============================================================
status = {
    "fingerprint": "Chưa quét",
    "face":        "Chưa nhận diện",
    "door":        "Đóng",
    "last_log":    "",
    "users":       []
}

# ==============================================================
# 2. ÁNH XẠ: ID VÂN TAY → TÊN KHUÔN MẶT
# ==============================================================
USER_MAPPING = {}  # {fingerprint_id: name}

def load_mapping():
    global USER_MAPPING
    if os.path.exists(MAPPING_FILE):
        try:
            with open(MAPPING_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                USER_MAPPING = {int(k): v for k, v in data.items()}
        except:
            USER_MAPPING = {}
load_mapping()

def save_mapping():
    with open(MAPPING_FILE, "w", encoding="utf-8") as f:
        json.dump(USER_MAPPING, f, ensure_ascii=False, indent=2)

# ==============================================================
# 3. BIẾN TOÀN CỤC
# ==============================================================
camera_window_active = False
cap = None
face_ok = False
current_fingerprint_id = None  # ID vân tay đang xác thực

# ==============================================================
# 4. TẢI DANH SÁCH NGƯỜI DÙNG
# ==============================================================
def reload_users():
    status["users"] = []
    for fp in glob.glob(os.path.join(KNOWN_FACES_DIR, "*.jpg")):
        name = os.path.basename(fp).replace(".jpg", "")
        if name not in status["users"]:
            status["users"].append(name)
reload_users()

# ==============================================================
# 5. SO SÁNH KHUÔN MẶT (ngưỡng 0.1)
# ==============================================================
def check_registered_face(gray_frame):
    small = cv2.resize(gray_frame, (100, 100))
    best_name = None
    best_score = 1.0  

    for name in status["users"]:
        path = os.path.join(KNOWN_FACES_DIR, f"{name}.jpg")
        if not os.path.exists(path):
            continue
        tmpl = cv2.imread(path, 0)
        if tmpl is None:
            continue
        tmpl = cv2.resize(tmpl, (100, 100))

        # DÙNG SQDIFF: KHOẢNG CÁCH
        res = cv2.matchTemplate(small, tmpl, cv2.TM_SQDIFF_NORMED)
        min_val = np.min(res)  # LẤY GIÁ TRỊ NHỎ NHẤT
        print(f"[DEBUG] Khoảng cách {name}: {min_val:.3f}")

        if min_val < best_score:
            best_score = min_val
            best_name = name

    # NGƯỠNG: < 0.5 = ĐÚNG
    if best_score < 0.6:
        print(f"[THÀNH CÔNG] {best_name}: {best_score:.3f} < 0.5")
        return best_name

    print(f"[THẤT BẠI] Tốt nhất: {best_score:.3f} >= 0.5")
    return None
# ==============================================================
# 6. MỞ CAMERA
# ==============================================================
def open_face_camera():
    global cap, camera_window_active
    if camera_window_active:
        return
    
    def start_camera():
        global cap, camera_window_active
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            log("Lỗi: Không mở được camera")
            return
        
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        camera_window_active = True
        threading.Thread(target=face_recognition_loop, daemon=True).start()
        log("Camera mở – Nhìn vào trong 15s")
    
    threading.Thread(target=start_camera, daemon=True).start()
# ==============================================================
# 7. NHẬN DIỆN KHUÔN MẶT (CHỈ CHẤP NHẬN NGƯỜI KHỚP)
# ==============================================================
# === SỬA face_recognition_loop() ===
def face_recognition_loop():
    global camera_window_active, face_ok
    start = time.time()
    expected_name = USER_MAPPING.get(current_fingerprint_id)

    while camera_window_active and (time.time() - start < 15):
        ret, frame = cap.read()
        if not ret:
            continue
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        name = check_registered_face(gray)
        remain = int(15 - (time.time() - start))

        
        if name and name == expected_name:
           
            status["face"] = f"Đúng ({name})"
            log(f"Xác thực thành công: {name}")
            send_to_arduino(f"FACE_OK ID:{current_fingerprint_id}")
            close_camera()
            reset_status()
            return

        # HIỂN THỊ NHANH
        cv2.putText(frame, f"Nhìn vào... ({remain}s)", (10, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
        cv2.imshow("Xác thực khuôn mặt", frame)
        
        # GIẢM ĐỘ TRỄ
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    if camera_window_active:
        status["face"] = "Hết thời gian"
        log("Hết thời gian nhận diện")
        close_camera()
def send_to_arduino(command):
    try:
        print(f"[GỬI Arduino] {command}")  # IN RA ĐỂ DEBUG
        requests.post("http://localhost:5001/send", data={"cmd": command}, timeout=0.5)
    except Exception as e:
        print(f"Lỗi gửi lệnh: {e}")
# ==============================================================
# 8. ĐÓNG CAMERA
# ==============================================================
def close_camera():
    global cap, camera_window_active
    if cap:
        cap.release()
    cv2.destroyAllWindows()
    camera_window_active = False

# ==============================================================
# 9. MỞ CỬA – GỬI LỆNH CHO ARDUINO
# ==============================================================
def check_open_door():
    global face_ok, current_fingerprint_id
    if status["fingerprint"].startswith("Đúng") and face_ok:
        status["door"] = "Mở"
        log("Cửa mở – Đủ 2 lớp!")
        send_to_arduino("OPEN_DOOR")
        # Reset ngay
        status["fingerprint"] = "Chưa quét"
        status["face"]        = "Chưa nhận diện"
        face_ok = False
        current_fingerprint_id = None

# ==============================================================
# 10. GHI LOG
# ==============================================================
def log(msg):
    status["last_log"] = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"

# ==============================================================
# 11. GỬI LỆNH QUA BRIDGE
# ==============================================================
def send_to_arduino(command):
    try:
        requests.post("http://localhost:5001/send", data={"cmd": command}, timeout=1)
    except:
        pass

# === HÀM RESET TRẠNG THÁI ===
def reset_status():
    global status, current_fingerprint_id, face_ok
    status.update({
        "fingerprint": "Chưa quét",
        "face":        "Chưa nhận diện",
        "door":        "Đóng",
        "last_log":    ""
    })
    current_fingerprint_id = None
    face_ok = False
    log("Hệ thống đã được reset (reload trang)")

    
def reset_if_new_session():
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
        reset_status()
# ==============================================================
# 12. ROUTES
# ==============================================================
@app.route("/")
def index():
    # TẠO SESSION ID MỚI MỖI LẦN TẢI TRANG
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
        reset_status()  # RESET TRẠNG THÁI
    return render_template("index.html")
# ---------- Vân tay ----------
# === SỬA ROUTE /fingerprint ===
@app.route("/fingerprint", methods=["POST"])
def fingerprint():
    reset_if_new_session()
    global current_fingerprint_id
    data = request.form.get("status")
    if "FINGERPRINT_OK" in data:
        fid = int(data.split("ID:")[1])
        current_fingerprint_id = fid
        status["fingerprint"] = f"Đúng (ID:{fid})"
        log(f"Vân tay hợp lệ ID {fid}")
        
        # MỞ CAMERA TRONG THREAD RIÊNG
        threading.Thread(target=open_face_camera, daemon=True).start()
        
        return jsonify(status)  # Trả về ngay
    return jsonify(status), 400
# === SỬA ROUTE register ===
@app.route("/register", methods=["POST"])
def register():
    name = request.form.get("name")
    fid_str = request.form.get("fingerprint_id")
    
    # Kiểm tra dữ liệu đầu vào
    if not name or not fid_str or not fid_str.isdigit():
        return jsonify({"success": False, "message": "Thiếu tên hoặc ID vân tay"}), 400
    
    fid = int(fid_str)
    if fid < 1 or fid > 127:
        return jsonify({"success": False, "message": "ID vân tay phải từ 1-127"}), 400
    if fid in USER_MAPPING:
        return jsonify({"success": False, "message": f"ID {fid} đã được dùng"}), 400

    if "image" not in request.files:
        return jsonify({"success": False, "message": "Chưa chọn ảnh"}), 400
    
    file = request.files["image"]
    if file.filename == '':
        return jsonify({"success": False, "message": "Chưa chọn ảnh"}), 400

    # Lưu ảnh
    path = os.path.join(KNOWN_FACES_DIR, f"{name}.jpg")
    file.save(path)

    # Lưu ánh xạ
    USER_MAPPING[fid] = name
    save_mapping()
    reload_users()
    
    return jsonify({"success": True, "message": f"Đã đăng ký: {name} (ID: {fid})"})
# ---------- Nút thủ công ----------
@app.route("/trigger_fingerprint", methods=["POST"])
def trigger_fingerprint():
    reset_if_new_session()
    send_to_arduino("SCAN_FINGERPRINT")
    return jsonify({"message": "Đã gửi lệnh quét vân tay!"})

@app.route("/trigger_face", methods=["POST"])
def trigger_face():
    reset_if_new_session()
    open_face_camera()
    return jsonify({"message": "Camera mở! Nhìn vào 15s"})

# ---------- Trạng thái cửa ----------
@app.route("/door_status", methods=["POST"])
def door_status():
    st = request.form.get("status")
    if st == "OPEN":
        status["door"] = "Mở"
    elif st == "CLOSED":
        status["door"] = "Đóng"
    return jsonify(status)

# ---------- Trạng thái chung ----------
@app.route("/status")
def get_status():
    return jsonify(status)

app.secret_key = "super_secret_key_123"  # CHO SESSION
# ==============================================================
# 13. CHẠY SERVER
# ==============================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
