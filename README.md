# KHÓA CỬA THÔNG MINH 2 LỚP – VÂN TAY + KHUÔN MẶT

**Đề tài:** Xây dựng hệ thống khóa cửa bảo mật cao sử dụng xác thực sinh trắc học 2 lớp (2FA)  
**Mục tiêu:** Chỉ mở cửa khi **cả vân tay và khuôn mặt cùng đúng của một người**

---

### ĐẶC ĐIỂM NỔI BẬT

- **2FA:** Vân tay + khuôn mặt **phải cùng 1 người**  
- **1 người = nhiều vân tay** (tối đa 127 ID)  
- **Giao diện web đẹp, responsive** (Bootstrap 5 + Font Awesome)  
- **Tự động reset** sau mở cửa hoặc reload trang  
- **Chạy local hoàn toàn** – Không cần Internet  
- **Chi phí dưới 1.500.000 VNĐ**

---

### CẤU TRÚC HỆ THỐNG
Người dùng (Web)
↓ HTTP
Flask Server (app.py) → OpenCV nhận diện khuôn mặt
↓ HTTP
Bridge (bridge.py) → Chuyển lệnh Serial
↓ Serial (USB)
Arduino Mega 2560
├── AS608 Fingerprint Sensor
└── Servo Motor (mở/đóng cửa)
### CÀI ĐẶT & CHẠY DỰ ÁN

#### 1. Yêu cầu
- Python 3.8+
- Arduino IDE
- Thư viện Python: `flask`, `opencv-python`, `pyserial`, `requests`, `pillow`

```bash
pip install flask opencv-python pyserial requests pillow
````
#### 2. Chạy dự án
- Terminal 1
python bridge.py

- Terminal 2
python app.py
