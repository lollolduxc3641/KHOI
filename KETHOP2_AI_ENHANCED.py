#!/usr/bin/env python3
"""
HỆ THỐNG KHÓA BẢO MẬT 4 LỚP - GIAO DIỆN TIẾNG VIỆT
Tác giả: Khoi - Luận án tốt nghiệp
Phiên bản: v2.2 - Vietnamese Interface for Students
"""

import cv2
import time
import json
import os
import logging
import threading
import tkinter as tk
from tkinter import ttk, font
from PIL import Image, ImageTk
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
import sys
import numpy as np
import asyncio

# Import modules của dự án (giữ nguyên)
try:
    from improved_face_recognition import ImprovedFaceRecognition, FaceDetectionResult
    from enhanced_components import (
        Colors, EnhancedBuzzerManager, EnhancedNumpadDialog, 
        EnhancedMessageBox, AdminDataManager, ImprovedAdminGUI
    )
    from discord_integration import DiscordSecurityBot
except ImportError as e:
    print(f"❌ Lỗi import modules: {e}")
    print("🔧 Đảm bảo các file sau tồn tại:")
    print("   - improved_face_recognition.py")
    print("   - enhanced_components.py")
    print("   - discord_integration.py")
    sys.exit(1)

# Hardware imports (giữ nguyên phần này)
try:
    from picamera2 import Picamera2
    from gpiozero import LED, PWMOutputDevice
    from pyfingerprint.pyfingerprint import PyFingerprint
    import board
    import busio
    from adafruit_pn532.i2c import PN532_I2C
except ImportError as e:
    logging.error(f"Không thể import thư viện phần cứng: {e}")
    print("⚠️ Hardware import failed - running in simulation mode")
    
    # Mock hardware classes for testing
    class MockPicamera2:
        def configure(self, config): pass
        def start(self): pass
        def stop(self): pass
        def capture_array(self): 
            return np.zeros((600, 800, 3), dtype=np.uint8)
    
    class MockLED:
        def __init__(self, pin): self.state = True
        def on(self): self.state = True
        def off(self): self.state = False
    
    class MockPN532:
        def SAM_configuration(self): pass
        def read_passive_target(self, timeout=1): return None
    
    class MockFingerprint:
        def verifyPassword(self): return True
        def readImage(self): return False
        def convertImage(self, slot): pass
        def searchTemplate(self): return (-1, 0)
        def createTemplate(self): pass
        def storeTemplate(self, pos, slot): pass
        def deleteTemplate(self, pos): pass
        def loadTemplate(self, pos, slot): pass
    
    Picamera2 = MockPicamera2
    LED = MockLED
    
    class MockBoard:
        SCL = None
        SDA = None
    
    class MockBusIO:
        def I2C(self, scl, sda): return None
    
    board = MockBoard()
    busio = MockBusIO()
    PN532_I2C = lambda i2c, debug=False: MockPN532()
    PyFingerprint = lambda *args, **kwargs: MockFingerprint()

# ==== CONFIGURATION - GIỮ NGUYÊN ====
@dataclass
class Config:
    # Paths
    PROJECT_PATH: str = "/home/khoi/Desktop/KHOI_LUANAN"
    MODELS_PATH: str = "/home/khoi/Desktop/KHOI_LUANAN/models"
    FACE_DATA_PATH: str = "/home/khoi/Desktop/KHOI_LUANAN/face_data"
    ADMIN_DATA_PATH: str = "/home/khoi/Desktop/KHOI_LUANAN"
    
    # GPIO
    BUZZER_GPIO: int = 17
    RELAY_GPIO: int = 5
    
    # Face Recognition
    FACE_CONFIDENCE_THRESHOLD: float = 0.5
    FACE_RECOGNITION_THRESHOLD: float = 85.0
    FACE_REQUIRED_CONSECUTIVE: int = 5
    FACE_DETECTION_INTERVAL: float = 0.03
    
    # Camera
    CAMERA_WIDTH: int = 800
    CAMERA_HEIGHT: int = 600
    DISPLAY_WIDTH: int = 650
    DISPLAY_HEIGHT: int = 490
    
    # Admin
    ADMIN_UID: List[int] = None
    ADMIN_PASS: str = "0809"
    
    # Timing
    LOCK_OPEN_DURATION: int = 3
    MAX_ATTEMPTS: int = 5
    
    def __post_init__(self):
        if self.ADMIN_UID is None:
            self.ADMIN_UID = [0xe5, 0xa8, 0xbd, 0x2]
        
        for path in [self.MODELS_PATH, self.FACE_DATA_PATH, self.ADMIN_DATA_PATH]:
            os.makedirs(path, exist_ok=True)

class AuthStep(Enum):
    FACE = "face"
    FINGERPRINT = "fingerprint"
    RFID = "rfid"
    PASSCODE = "passcode"
    ADMIN = "admin"

# ==== LOGGING SETUP ====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('/home/khoi/Desktop/KHOI_LUANAN/system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==== GIAO DIỆN TIẾNG VIỆT CHO SINH VIÊN ====
class VietnameseSecurityGUI:
    def __init__(self, root):
        self.root = root
        self.fps_counter = 0
        self.fps_start_time = time.time()
        self.current_fps = 0
        self.detection_stats = {"total": 0, "recognized": 0, "unknown": 0}
        
        self._setup_window()
        self._create_widgets()
        self._setup_bindings()
    
    def _setup_window(self):
        self.root.title("HỆ THỐNG KHÓA CỬA THÔNG MINH 4 LỚP BẢO MẬT")
        self.root.geometry("1500x900")
        self.root.configure(bg=Colors.DARK_BG)
        self.root.attributes('-fullscreen', True)
        self.root.minsize(1200, 800)
    
    def _create_widgets(self):
        # Container chính
        main_container = tk.Frame(self.root, bg=Colors.DARK_BG)
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        main_container.grid_columnconfigure(0, weight=2)
        main_container.grid_columnconfigure(1, weight=1)
        main_container.grid_rowconfigure(0, weight=1)
        
        # BÊN TRÁI - CAMERA NHẬN DIỆN
        self._create_camera_panel(main_container)
        
        # BÊN PHẢI - TRẠNG THÁI HỆ THỐNG
        self._create_status_panel(main_container)
        
        # PHÍA DƯỚI - THANH TRẠNG THÁI
        self._create_status_bar()
    
    def _create_camera_panel(self, parent):
        camera_panel = tk.Frame(parent, bg=Colors.CARD_BG, relief=tk.RAISED, bd=4)
        camera_panel.grid(row=0, column=0, padx=(0,10), pady=0, sticky="nsew")
        
        # Tiêu đề camera
        header = tk.Frame(camera_panel, bg=Colors.PRIMARY, height=100)
        header.pack(fill=tk.X, padx=4, pady=4)
        header.pack_propagate(False)
        
        # Tiêu đề chính
        header_left = tk.Frame(header, bg=Colors.PRIMARY)
        header_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        tk.Label(header_left, text="CAMERA NHẬN DIỆN KHUÔN MẶT",
                font=('Arial', 26, 'bold'), fg='white', bg=Colors.PRIMARY,
                anchor='w').pack(side=tk.LEFT, padx=20, expand=True, fill=tk.X)
        
        # Thông số kỹ thuật
        stats_frame = tk.Frame(header, bg=Colors.PRIMARY)
        stats_frame.pack(side=tk.RIGHT, padx=20)
        
        self.fps_label = tk.Label(stats_frame, text="Tốc độ: -- khung/giây", 
                                 font=('Arial', 16, 'bold'), fg='white', bg=Colors.PRIMARY)
        self.fps_label.pack()
        
        self.detection_count_label = tk.Label(stats_frame, text="Phát hiện: 0", 
                                            font=('Arial', 14), fg='white', bg=Colors.PRIMARY)
        self.detection_count_label.pack()
        
        # Màn hình camera
        self.camera_frame = tk.Frame(camera_panel, bg='black', relief=tk.SUNKEN, bd=4)
        self.camera_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        self.camera_label = tk.Label(self.camera_frame, 
                                   text="Đang khởi động camera nhận diện...\n\nĐang tải mô hình nhận dạng...",
                                   font=('Arial', 22), fg='white', bg='black')
        self.camera_label.pack(expand=True)
        
        # Trạng thái nhận diện
        status_frame = tk.Frame(camera_panel, bg=Colors.CARD_BG, height=80)
        status_frame.pack(fill=tk.X, pady=10)
        status_frame.pack_propagate(False)
        
        self.face_status = tk.Label(status_frame, text="Hệ thống đang khởi động...",
                                   font=('Arial', 18, 'bold'), 
                                   fg=Colors.PRIMARY, bg=Colors.CARD_BG)
        self.face_status.pack(expand=True)
        
        self.detection_info = tk.Label(status_frame, text="Chuẩn bị hệ thống nhận diện...",
                                      font=('Arial', 16), 
                                      fg=Colors.TEXT_SECONDARY, bg=Colors.CARD_BG)
        self.detection_info.pack()
    
    def _create_status_panel(self, parent):
        status_panel = tk.Frame(parent, bg=Colors.CARD_BG, relief=tk.RAISED, bd=4)
        status_panel.grid(row=0, column=1, padx=(10,0), pady=0, sticky="nsew")
        
        # Tiêu đề trạng thái
        header = tk.Frame(status_panel, bg=Colors.SUCCESS, height=100)
        header.pack(fill=tk.X, padx=4, pady=4)
        header.pack_propagate(False)
        
        tk.Label(header, text="TRẠNG THÁI XÁC THỰC",
                font=('Arial', 22, 'bold'), fg='white', bg=Colors.SUCCESS).pack(expand=True)
        
        # Bước hiện tại
        self.step_frame = tk.Frame(status_panel, bg=Colors.CARD_BG)
        self.step_frame.pack(fill=tk.X, padx=25, pady=25)
        
        self.step_number = tk.Label(self.step_frame, text="1", 
                                   font=('Arial', 52, 'bold'),
                                   fg='white', bg=Colors.PRIMARY,
                                   width=2, relief=tk.RAISED, bd=5)
        self.step_number.pack(side=tk.LEFT, padx=(0,25))
        
        step_info = tk.Frame(self.step_frame, bg=Colors.CARD_BG)
        step_info.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.step_title = tk.Label(step_info, text="NHẬN DIỆN KHUÔN MẶT",
                                  font=('Arial', 30, 'bold'),
                                  fg=Colors.TEXT_PRIMARY, bg=Colors.CARD_BG,
                                  anchor='w')
        self.step_title.pack(fill=tk.X)
        
        self.step_subtitle = tk.Label(step_info, text="Hệ thống đang phân tích...",
                                     font=('Arial', 20),
                                     fg=Colors.TEXT_SECONDARY, bg=Colors.CARD_BG,
                                     anchor='w')
        self.step_subtitle.pack(fill=tk.X)
        
        # Các bước xác thực
        progress_frame = tk.Frame(status_panel, bg=Colors.CARD_BG)
        progress_frame.pack(fill=tk.X, padx=25, pady=20)
        
        tk.Label(progress_frame, text="CÁC BƯỚC XÁC THỰC:",
                font=('Arial', 22, 'bold'),
                fg=Colors.TEXT_PRIMARY, bg=Colors.CARD_BG).pack(anchor='w')
        
        steps_frame = tk.Frame(progress_frame, bg=Colors.CARD_BG)
        steps_frame.pack(fill=tk.X, pady=15)
        
        self.step_indicators = {}
        step_names = [
            "NHẬN DIỆN KHUÔN MẶT", 
            "QUÉT VÂN TAY", 
            "QUÉt THẺ RFID", 
            "NHẬP MẬT KHẨU"
        ]
        
        for i, name in enumerate(step_names):
            container = tk.Frame(steps_frame, bg=Colors.CARD_BG)
            container.pack(fill=tk.X, pady=8)
            
            circle = tk.Label(container, text=f"{i+1}",
                             font=('Arial', 22, 'bold'),
                             fg='white', bg=Colors.TEXT_SECONDARY,
                             width=3, relief=tk.RAISED, bd=4)
            circle.pack(side=tk.LEFT, padx=(0,20))
            
            label = tk.Label(container, text=name,
                            font=('Arial', 20, 'bold'),
                            fg=Colors.TEXT_PRIMARY, bg=Colors.CARD_BG,
                            anchor='w')
            label.pack(side=tk.LEFT, fill=tk.X, expand=True)
            
            self.step_indicators[i+1] = {
                'circle': circle,
                'label': label
            }
        
        # Khu vực thông tin chi tiết
        msg_frame = tk.Frame(status_panel, bg=Colors.BACKGROUND, relief=tk.SUNKEN, bd=4)
        msg_frame.pack(fill=tk.X, padx=25, pady=20)
        
        tk.Label(msg_frame, text="THÔNG TIN CHI TIẾT:",
                font=('Arial', 18, 'bold'),
                fg=Colors.TEXT_PRIMARY, bg=Colors.BACKGROUND).pack(anchor='w', padx=20, pady=(15,8))
        
        self.detail_message = tk.Label(msg_frame, text="Khởi động hệ thống nhận diện...\nĐang tải dữ liệu mẫu...",
                                      font=('Arial', 16),
                                      fg=Colors.TEXT_SECONDARY, bg=Colors.BACKGROUND,
                                      wraplength=450, justify=tk.LEFT, anchor='w')
        self.detail_message.pack(fill=tk.X, padx=20, pady=(0,15))
        
        # Hiển thị thời gian
        self.time_label = tk.Label(status_panel, text="",
                                  font=('Arial', 16),
                                  fg=Colors.TEXT_SECONDARY, bg=Colors.CARD_BG)
        self.time_label.pack(side=tk.BOTTOM, pady=10)
        
        self._update_time()
    
    def _create_status_bar(self):
        status_bar = tk.Frame(self.root, bg=Colors.PRIMARY, height=90)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=20, pady=(0,20))
        status_bar.pack_propagate(False)
        
        self.main_status = tk.Label(status_bar, 
                                   text="HỆ THỐNG KHÓA CỬA THÔNG MINH - ĐANG KHỞI ĐỘNG...",
                                   font=('Arial', 22, 'bold'),
                                   fg='white', bg=Colors.PRIMARY)
        self.main_status.pack(expand=True)
    
    def _setup_bindings(self):
        self.root.bind('<Key>', self._on_key)
        self.root.bind('<F11>', lambda e: self.root.attributes('-fullscreen', 
                                                              not self.root.attributes('-fullscreen')))
        self.root.focus_set()
    
    def _on_key(self, event):
        key = event.keysym
        if key == 'asterisk' or key == 'KP_Multiply':
            if hasattr(self, 'system_ref'):
                self.system_ref._force_admin_mode()
        elif key == 'numbersign' or key == 'KP_Add':
            if hasattr(self, 'system_ref'):
                self.system_ref.start_authentication()
        elif key == 'Escape':
            if hasattr(self, 'system_ref') and hasattr(self.system_ref, 'buzzer'):
                if EnhancedMessageBox.ask_yesno(self.root, "Thoát hệ thống", 
                                            "Bạn có chắc chắn muốn thoát?", self.system_ref.buzzer):
                    self.root.quit()
    
    def _update_time(self):
        current_time = datetime.now().strftime("%H:%M:%S - %d/%m/%Y")
        self.time_label.config(text=current_time)
        self.root.after(1000, self._update_time)
    
    def update_camera(self, frame: np.ndarray, detection_result: Optional[FaceDetectionResult] = None):
        """Cập nhật hiển thị camera với thông tin nhận diện"""
        try:
            # Tính toán FPS
            self.fps_counter += 1
            current_time = time.time()
            if current_time - self.fps_start_time >= 1.0:
                self.current_fps = self.fps_counter
                self.fps_counter = 0
                self.fps_start_time = current_time
                self.fps_label.config(text=f"Tốc độ: {self.current_fps} khung/giây")
            
            # Cập nhật thống kê
            if detection_result:
                self.detection_stats["total"] += 1
                if detection_result.recognized:
                    self.detection_stats["recognized"] += 1
                elif detection_result.detected:
                    self.detection_stats["unknown"] += 1
                
                self.detection_count_label.config(
                    text=f"Tổng: {self.detection_stats['total']} | Đúng: {self.detection_stats['recognized']}"
                )
            
            # Thay đổi kích thước để hiển thị
            height, width = frame.shape[:2]
            display_height = Config.DISPLAY_HEIGHT
            display_width = int(width * display_height / height)
            
            img = cv2.resize(frame, (display_width, display_height))
            rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            img_pil = Image.fromarray(rgb_img)
            img_tk = ImageTk.PhotoImage(img_pil)
            
            self.camera_label.config(image=img_tk, text="")
            self.camera_label.image = img_tk
            
            # Cập nhật trạng thái nhận diện
            if detection_result:
                if detection_result.detected:
                    if detection_result.recognized:
                        self.face_status.config(
                            text=f"ĐÃ XÁC NHẬN: {detection_result.person_name}",
                            fg=Colors.SUCCESS
                        )
                        self.detection_info.config(
                            text=f"Độ chính xác: {detection_result.confidence:.1f} | Trạng thái: CHO PHÉP",
                            fg=Colors.SUCCESS
                        )
                    else:
                        self.face_status.config(
                            text="PHÁT HIỆN: KHUÔN MẶT KHÔNG ĐƯỢC PHÉP",
                            fg=Colors.ERROR
                        )
                        self.detection_info.config(
                            text="Phát hiện khuôn mặt nhưng chưa được đăng ký | Từ chối truy cập",
                            fg=Colors.ERROR
                        )
                else:
                    self.face_status.config(
                        text="ĐANG QUÉT: Tìm kiếm khuôn mặt...",
                        fg=Colors.WARNING
                    )
                    self.detection_info.config(
                        text="Hệ thống đang phân tích video từ camera...",
                        fg=Colors.TEXT_SECONDARY
                    )
            
        except Exception as e:
            logger.error(f"Lỗi cập nhật camera: {e}")
    
    def update_step(self, step_num, title, subtitle, color=None):
        if color is None:
            color = Colors.PRIMARY
            
        self.step_number.config(text=str(step_num), bg=color)
        self.step_title.config(text=title)
        self.step_subtitle.config(text=subtitle)
        
        # Cập nhật các chỉ báo tiến trình
        for i in range(1, 5):
            indicator = self.step_indicators[i]
            if i < step_num:
                indicator['circle'].config(bg=Colors.SUCCESS)
                indicator['label'].config(fg=Colors.TEXT_PRIMARY)
            elif i == step_num:
                indicator['circle'].config(bg=color)
                indicator['label'].config(fg=Colors.TEXT_PRIMARY)
            else:
                indicator['circle'].config(bg=Colors.TEXT_SECONDARY)
                indicator['label'].config(fg=Colors.TEXT_SECONDARY)
    
    def update_status(self, message, color=None):
        if color is None:
            color = 'white'
        self.main_status.config(text=message, fg=color)
    
    def update_detail(self, message, color=None):
        if color is None:
            color = Colors.TEXT_SECONDARY
        self.detail_message.config(text=message, fg=color)
    
    def set_system_reference(self, system):
        self.system_ref = system

# ==== HỆ THỐNG BẢO MẬT VIỆT HÓA ====
class VietnameseSecuritySystem:
    
    def _init_discord_bot(self):
        """Khởi tạo Discord bot integration"""
        try:
            logger.info("Khởi tạo Discord bot integration...")
            self.discord_bot = DiscordSecurityBot(self)
            logger.info("Discord bot integration đã sẵn sàng")
        except Exception as e:
            logger.error(f"Lỗi khởi tạo Discord bot: {e}")
            logger.info("Tiếp tục chạy mà không có Discord bot...")
            self.discord_bot = None
    
    def _send_discord_notification(self, message):
        """Helper function để gửi Discord notification từ sync context"""
        try:
            if self.discord_bot and self.discord_bot.bot:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.discord_bot.send_notification(message))
                loop.close()
        except Exception as e:
            logger.error(f"Discord notification error: {e}")       
    
    def __init__(self):
        self.config = Config()
        logger.info("Khởi tạo Hệ thống Khóa Cửa Thông minh...")
        
        self._init_hardware()
        self._init_components()
        self._init_gui()
        self._init_discord_bot()
        
        self.auth_state = {
            "step": AuthStep.FACE,
            "consecutive_face_ok": 0,
            "fingerprint_attempts": 0,
            "rfid_attempts": 0,
            "pin_attempts": 0
        }

        self.failed_attempts = {
            "face": 0,
            "fingerprint": 0, 
            "rfid": 0,
            "pin": 0,
            "total_today": 0
        }
        
        self.running = True
        self.face_thread = None
        
        logger.info("Hệ thống Khóa Cửa Thông minh khởi tạo thành công!")
    
    def _init_hardware(self):
        """Khởi tạo phần cứng"""
        try:
            logger.info("Khởi tạo phần cứng...")
            
            # Buzzer
            try:
                self.buzzer = EnhancedBuzzerManager(self.config.BUZZER_GPIO)
            except:
                logger.warning("Buzzer mock mode")
                self.buzzer = type('MockBuzzer', (), {'beep': lambda x, y: None})()
            
            # Camera
            self.picam2 = Picamera2()
            if hasattr(self.picam2, 'configure'):
                self.picam2.configure(self.picam2.create_video_configuration(
                    main={"format": 'XRGB8888', "size": (self.config.CAMERA_WIDTH, self.config.CAMERA_HEIGHT)}
                ))
                self.picam2.start()
                time.sleep(2)
            
            # Relay (Door lock)
            self.relay = LED(self.config.RELAY_GPIO)
            self.relay.on()  # Locked by default
            
            # RFID
            i2c = busio.I2C(board.SCL, board.SDA)
            self.pn532 = PN532_I2C(i2c, debug=False)
            self.pn532.SAM_configuration()
            
            # Fingerprint sensor
            self.fingerprint = PyFingerprint('/dev/ttyUSB0', 57600, 0xFFFFFFFF, 0x00000000)
            if not self.fingerprint.verifyPassword():
                logger.warning("Fingerprint sensor simulation mode")
            
            logger.info("Tất cả phần cứng đã sẵn sàng")
            
        except Exception as e:
            logger.error(f"Lỗi khởi tạo phần cứng: {e}")
            logger.info("Continuing in simulation mode...")
    
    def _init_components(self):
        """Khởi tạo các thành phần hệ thống"""
        try:
            logger.info("Khởi tạo các thành phần hệ thống...")
            
            # Admin data manager
            self.admin_data = AdminDataManager(self.config.ADMIN_DATA_PATH)
            
            # Face Recognition
            self.face_recognizer = ImprovedFaceRecognition(
                models_path=self.config.MODELS_PATH,
                face_data_path=self.config.FACE_DATA_PATH,
                confidence_threshold=self.config.FACE_CONFIDENCE_THRESHOLD,
                recognition_threshold=self.config.FACE_RECOGNITION_THRESHOLD
            )
            
            logger.info("Các thành phần hệ thống đã sẵn sàng")
            
        except Exception as e:
            logger.error(f"Lỗi khởi tạo thành phần hệ thống: {e}")
            raise
    
    def _init_gui(self):
        """Khởi tạo giao diện"""
        try:
            logger.info("Khởi tạo giao diện...")
            
            self.root = tk.Tk()
            self.gui = VietnameseSecurityGUI(self.root)  # SỬ DỤNG GUI VIỆT HÓA
            self.gui.set_system_reference(self)
            
            # Admin GUI
            self.admin_gui = ImprovedAdminGUI(self.root, self)
            
            logger.info("Giao diện đã sẵn sàng")
            
        except Exception as e:
            logger.error(f"Lỗi khởi tạo giao diện: {e}")
            raise
    
    def _force_admin_mode(self):
        """Chế độ admin nhanh bằng phím *"""
        self.root.focus_force()
        self.root.update()
        
        dialog = EnhancedNumpadDialog(self.root, "TRUY CẬP QUẢN TRỊ",
                                    "Nhập mật khẩu quản trị:", True, self.buzzer)
        
        if hasattr(dialog, 'dialog'):
            dialog.dialog.focus_force()
            dialog.dialog.grab_set()
            dialog.dialog.lift()
        
        password = dialog.show()
        
        if password == self.config.ADMIN_PASS:
            self.gui.update_status("CHẾ ĐỘ QUẢN TRỊ ĐÃ KÍCH HOẠT", 'lightgreen')
            self.gui.update_detail("Xác thực quản trị thành công! Đang mở bảng điều khiển...", Colors.SUCCESS)
            self.buzzer.beep("success")
            self.admin_gui.show_admin_panel()
        elif password is not None:
            self.gui.update_status("TỪ CHỐI TRUY CẬP QUẢN TRỊ", 'orange')
            self.gui.update_detail("Mật khẩu quản trị không đúng!", Colors.ERROR)
            self.buzzer.beep("error")
    
    def start_authentication(self):
        """Bắt đầu quy trình xác thực"""
        logger.info("Bắt đầu quy trình xác thực")
        
        self.auth_state = {
            "step": AuthStep.FACE,
            "consecutive_face_ok": 0,
            "fingerprint_attempts": 0,
            "rfid_attempts": 0,
            "pin_attempts": 0
        }
        
        self.gui.update_step(1, "NHẬN DIỆN KHUÔN MẶT", "Hệ thống đang phân tích...", Colors.PRIMARY)
        self.gui.update_status("ĐANG PHÂN TÍCH KHUÔN MẶT - VUI LÒNG NHÌN VÀO CAMERA", 'white')
        self.gui.update_detail("Hệ thống nhận diện đang quét và phân tích khuôn mặt.\nNhìn thẳng vào camera và giữ nguyên vị trí.", Colors.PRIMARY)
        
        # Reset detection stats
        self.gui.detection_stats = {"total": 0, "recognized": 0, "unknown": 0}
        
        if self.face_thread and self.face_thread.is_alive():
            return
        
        self.face_thread = threading.Thread(target=self._face_recognition_loop, daemon=True)
        self.face_thread.start()
    
    def _face_recognition_loop(self):
        """Vòng lặp nhận diện khuôn mặt"""
        logger.info("Bắt đầu vòng lặp nhận diện khuôn mặt")
        consecutive_count = 0
        
        while self.running and self.auth_state["step"] == AuthStep.FACE:
            try:
                # Capture frame
                frame = self.picam2.capture_array()
                if frame is None:
                    continue
                
                # Xử lý nhận diện
                annotated_frame, result = self.face_recognizer.process_frame(frame)
                
                # Cập nhật GUI
                self.root.after(0, lambda: self.gui.update_camera(annotated_frame, result))
                
                if result.recognized:
                    consecutive_count += 1
                    self.auth_state["consecutive_face_ok"] = consecutive_count
                    
                    progress = consecutive_count / self.config.FACE_REQUIRED_CONSECUTIVE * 100
                    msg = f"Đã xác nhận ({consecutive_count}/{self.config.FACE_REQUIRED_CONSECUTIVE}) - {progress:.0f}%"
                    
                    self.root.after(0, lambda: self.gui.update_step(1, "NHẬN DIỆN THÀNH CÔNG", msg, Colors.SUCCESS))
                    self.root.after(0, lambda: self.gui.update_detail(
                        f"Danh tính: {result.person_name}\n"
                        f"Đang xác minh... còn {self.config.FACE_REQUIRED_CONSECUTIVE - consecutive_count} lần xác nhận\n"
                        f"Độ chính xác: {result.confidence:.1f}/100", 
                        Colors.SUCCESS))
                    
                    if consecutive_count >= self.config.FACE_REQUIRED_CONSECUTIVE:
                        logger.info(f"Nhận diện khuôn mặt thành công: {result.person_name}")
                        self.buzzer.beep("success")
                        self.root.after(0, lambda: self.gui.update_status(f"ĐÃ XÁC NHẬN KHUÔN MẶT: {result.person_name.upper()}!", 'lightgreen'))
                        self.root.after(1500, self._proceed_to_fingerprint)
                        break
                        
                elif result.detected:
                    consecutive_count = 0
                    self.auth_state["consecutive_face_ok"] = 0
                    self.root.after(0, lambda: self.gui.update_step(1, "PHÁT HIỆN KHUÔN MẶT", "Khuôn mặt chưa đăng ký", Colors.WARNING))
                    self.root.after(0, lambda: self.gui.update_detail(
                        "Hệ thống phát hiện khuôn mặt nhưng chưa có trong cơ sở dữ liệu.\n"
                        f"Độ chính xác phát hiện: {result.confidence:.1f}\n"
                        "Vui lòng đảm bảo bạn đã được đăng ký trong hệ thống.", 
                        Colors.WARNING))
                else:
                    consecutive_count = 0
                    self.auth_state["consecutive_face_ok"] = 0
                    self.root.after(0, lambda: self.gui.update_step(1, "ĐANG QUÉT", "Tìm kiếm khuôn mặt...", Colors.PRIMARY))
                
                time.sleep(self.config.FACE_DETECTION_INTERVAL)
                
            except Exception as e:
                logger.error(f"Lỗi vòng lặp nhận diện khuôn mặt: {e}")
                self.root.after(0, lambda: self.gui.update_detail(f"Lỗi hệ thống: {str(e)}", Colors.ERROR))
                time.sleep(1)
    
    def _proceed_to_fingerprint(self):
        """Chuyển sang bước quét vân tay"""
        logger.info("Chuyển sang xác thực vân tay")
        self.auth_state["step"] = AuthStep.FINGERPRINT
        self.auth_state["fingerprint_attempts"] = 0
        
        self.gui.update_step(2, "QUÉT VÂN TAY", "Đặt ngón tay lên cảm biến", Colors.WARNING)
        self.gui.update_status("ĐANG CHỜ QUÉT VÂN TAY...", 'yellow')
        self.gui.update_detail("Vui lòng đặt ngón tay đã đăng ký lên cảm biến sinh trắc học.\nCảm biến đã sẵn sàng để quét.", Colors.WARNING)
        
        threading.Thread(target=self._fingerprint_loop, daemon=True).start()
    
    def _fingerprint_loop(self):
        """Vòng lặp xác thực vân tay"""
        while (self.auth_state["fingerprint_attempts"] < self.config.MAX_ATTEMPTS and 
            self.auth_state["step"] == AuthStep.FINGERPRINT):
            
            try:
                self.auth_state["fingerprint_attempts"] += 1
                attempt_msg = f"Lần thử {self.auth_state['fingerprint_attempts']}/{self.config.MAX_ATTEMPTS}"
                
                self.root.after(0, lambda: self.gui.update_step(2, "QUÉT VÂN TAY", attempt_msg, Colors.WARNING))
                
                timeout = 10
                start_time = time.time()
                
                while time.time() - start_time < timeout:
                    if self.fingerprint.readImage():
                        self.fingerprint.convertImage(0x01)
                        result = self.fingerprint.searchTemplate()
                        
                        if result[0] != -1:
                            # THÀNH CÔNG
                            logger.info(f"Xác thực vân tay thành công: ID {result[0]}")
                            self.buzzer.beep("success")
                            self.root.after(0, lambda: self.gui.update_status("VÂN TAY ĐÃ XÁC THỰC! CHUYỂN ĐẾN THẺ RFID...", 'lightgreen'))
                            self.root.after(1500, self._proceed_to_rfid)
                            return
                        else:
                            # THẤT BẠI
                            details = f"Không tìm thấy mẫu vân tay | Kết quả cảm biến: {result[1]}"
                            logger.warning(f"Vân tay không được nhận diện: lần thử {self.auth_state['fingerprint_attempts']}")
                            
                            self._send_discord_failure_alert("fingerprint", self.auth_state['fingerprint_attempts'], details)
                            
                            self.buzzer.beep("error")
                            remaining = self.config.MAX_ATTEMPTS - self.auth_state["fingerprint_attempts"]
                            if remaining > 0:
                                self.root.after(0, lambda: self.gui.update_detail(
                                    f"Vân tay không được nhận diện!\nCòn {remaining} lần thử\nVui lòng thử lại với ngón tay đã đăng ký.", Colors.ERROR))
                                time.sleep(2)
                                break
                    time.sleep(0.1)
                
                if time.time() - start_time >= timeout:
                    # HẾT THỜI GIAN
                    details = f"Hết thời gian quét - không phát hiện ngón tay ({timeout}s)"
                    logger.warning(f"Hết thời gian vân tay: lần thử {self.auth_state['fingerprint_attempts']}")
                    
                    self._send_discord_failure_alert("fingerprint", self.auth_state['fingerprint_attempts'], details)
                    
                    remaining = self.config.MAX_ATTEMPTS - self.auth_state["fingerprint_attempts"]
                    if remaining > 0:
                        self.root.after(0, lambda: self.gui.update_detail(
                            f"Hết thời gian quét!\nCòn {remaining} lần thử\nVui lòng đặt ngón tay đúng cách lên cảm biến.", Colors.WARNING))
                        time.sleep(1)
                    
            except Exception as e:
                # LỖI PHẦN CỨNG
                details = f"Lỗi phần cứng: {str(e)}"
                logger.error(f"Lỗi vân tay: {e}")
                
                self._send_discord_failure_alert("fingerprint", self.auth_state['fingerprint_attempts'], details)
                
                self.root.after(0, lambda: self.gui.update_detail(f"Lỗi cảm biến: {str(e)}", Colors.ERROR))
                time.sleep(1)
        
        # HẾT SỐ LẦN THỬ
        if self.auth_state["fingerprint_attempts"] >= self.config.MAX_ATTEMPTS:
            details = f"Đã vượt quá số lần thử vân tay tối đa ({self.config.MAX_ATTEMPTS})"
            logger.critical(f"Vân tay vượt quá số lần thử: {self.auth_state['fingerprint_attempts']}")
            
            self._send_discord_failure_alert("fingerprint", self.auth_state['fingerprint_attempts'], details)
        
        logger.warning("Vân tay: Đã vượt quá số lần thử tối đa")
        self.root.after(0, lambda: self.gui.update_status("VÂN TAY THẤT BẠI - KHỞI ĐỘNG LẠI XÁC THỰC", 'orange'))
        self.buzzer.beep("error")
        self.root.after(3000, self.start_authentication)
    
    def _proceed_to_rfid(self):
        """Chuyển sang bước quét thẻ RFID"""
        logger.info("Chuyển sang xác thực thẻ RFID")
        self.auth_state["step"] = AuthStep.RFID
        self.auth_state["rfid_attempts"] = 0
        
        self.gui.update_step(3, "QUÉT THẺ RFID", "Đưa thẻ lại gần đầu đọc", Colors.ACCENT)
        self.gui.update_status("ĐANG CHỜ THẺ RFID...", 'lightblue')
        self.gui.update_detail("Vui lòng đưa thẻ RFID lại gần đầu đọc.\nĐầu đọc đang hoạt động và quét thẻ.", Colors.ACCENT)
        
        threading.Thread(target=self._rfid_loop, daemon=True).start()
    
    def _rfid_loop(self):
        """Vòng lặp xác thực thẻ RFID"""
        while (self.auth_state["rfid_attempts"] < self.config.MAX_ATTEMPTS and 
            self.auth_state["step"] == AuthStep.RFID):
            
            try:
                self.auth_state["rfid_attempts"] += 1
                attempt_msg = f"Lần thử {self.auth_state['rfid_attempts']}/{self.config.MAX_ATTEMPTS}"
                
                # Cập nhật GUI
                self.root.after(0, lambda: self.gui.update_step(3, "QUÉT THẺ TỪ", attempt_msg, Colors.ACCENT))
                self.root.after(0, lambda: self.gui.update_detail(
                    f"Đang quét thẻ từ... (Lần thử {self.auth_state['rfid_attempts']}/{self.config.MAX_ATTEMPTS})\n"
                    "Giữ thẻ trong khoảng 2-5cm từ đầu đọc.", 
                    Colors.ACCENT))
                
                # Quét thẻ từ
                uid = self.pn532.read_passive_target(timeout=8)
                
                if uid:
                    uid_list = list(uid)
                    logger.info(f"Phát hiện thẻ từ: {uid_list}")
                    
                    # Kiểm tra thẻ admin
                    if uid_list == self.config.ADMIN_UID:
                        self.root.after(0, lambda: self._admin_authentication())
                        return
                    
                    # Kiểm tra thẻ thông thường
                    valid_uids = self.admin_data.get_rfid_uids()
                    if uid_list in valid_uids:
                        # THÀNH CÔNG
                        logger.info(f"Thẻ từ được xác thực: {uid_list}")
                        self.buzzer.beep("success")
                        self.root.after(0, lambda: self.gui.update_status("THẺ TỪ ĐÃ XÁC THỤC! NHẬP MẬT KHẨU...", 'lightgreen'))
                        self.root.after(0, lambda: self.gui.update_detail(f"Xác thực thẻ từ thành công!\nMã thẻ: {uid_list}\nChuyển đến bước nhập mật khẩu cuối cùng.", Colors.SUCCESS))
                        self.root.after(1500, self._proceed_to_passcode)
                        return
                    else:
                        # THẤT BẠI - Thẻ không được phép
                        details = f"Thẻ không được phép | UID: {uid_list} | Không có trong cơ sở dữ liệu"
                        logger.warning(f"Thẻ từ không được phép: {uid_list}")
                        
                        self._send_discord_failure_alert("rfid", self.auth_state['rfid_attempts'], details)
                        
                        self.buzzer.beep("error")
                        remaining = self.config.MAX_ATTEMPTS - self.auth_state["rfid_attempts"]
                        
                        error_msg = f"THẺ TỪ KHÔNG ĐƯỢC PHÉP!\n"
                        error_msg += f"Mã thẻ phát hiện: {uid_list}\n"
                        error_msg += f"Thẻ chưa được đăng ký trong hệ thống\n"
                        error_msg += f"Còn {remaining} lần thử" if remaining > 0 else "Hết lần thử"
                        
                        self.root.after(0, lambda: self.gui.update_detail(error_msg, Colors.ERROR))
                        
                        if remaining > 0:
                            time.sleep(3)
                        else:
                            break
                else:
                    # THẤT BẠI - Không phát hiện thẻ
                    details = f"Không phát hiện thẻ từ trong thời gian chờ ({8}s)"
                    logger.warning(f"Hết thời gian thẻ từ: lần thử {self.auth_state['rfid_attempts']}")
                    
                    self._send_discord_failure_alert("rfid", self.auth_state['rfid_attempts'], details)
                    
                    remaining = self.config.MAX_ATTEMPTS - self.auth_state["rfid_attempts"]
                    
                    timeout_msg = f"KHÔNG PHÁT HIỆN THẺ!\n"
                    timeout_msg += f"Hết thời gian quét sau {8} giây\n"
                    timeout_msg += f"Vui lòng đưa thẻ gần đầu đọc hơn\n"
                    timeout_msg += f"Còn {remaining} lần thử" if remaining > 0 else "Hết lần thử"
                    
                    self.root.after(0, lambda: self.gui.update_detail(timeout_msg, Colors.WARNING))
                    
                    if remaining > 0:
                        time.sleep(2)
                    else:
                        break
                    
            except Exception as e:
                # LỖI PHẦN CỨNG
                details = f"Lỗi phần cứng đầu đọc thẻ từ: {str(e)}"
                logger.error(f"Lỗi thẻ từ: {e}")
                
                self._send_discord_failure_alert("rfid", self.auth_state['rfid_attempts'], details)
                
                self.root.after(0, lambda: self.gui.update_detail(f"LỖI ĐẦU ĐỌC THẺ TỪ!\n{str(e)}\nVui lòng kiểm tra kết nối phần cứng", Colors.ERROR))
                time.sleep(2)
        
        # HẾT SỐ LẦN THỬ
        if self.auth_state["rfid_attempts"] >= self.config.MAX_ATTEMPTS:
            details = f"Đã vượt quá số lần thử thẻ từ tối đa ({self.config.MAX_ATTEMPTS}) | Có thể có hành vi xâm nhập"
            logger.critical(f"Thẻ từ vượt quá số lần thử: {self.auth_state['rfid_attempts']}")
            
            self._send_discord_failure_alert("rfid", self.auth_state['rfid_attempts'], details)
        
        logger.warning("Thẻ từ: Đã vượt quá số lần thử tối đa - Khởi động lại xác thực")
        self.root.after(0, lambda: self.gui.update_status("THẺ TỪ THẤT BẠI - KHỞI ĐỘNG LẠI XÁC THỰC", 'orange'))
        self.root.after(0, lambda: self.gui.update_detail(
            "XÁC THỰC THẺ TỪ THẤT BẠI!\n"
            f"Đã hết tất cả {self.config.MAX_ATTEMPTS} lần thử\n"
            "Đang khởi động lại toàn bộ quy trình xác thực...\n"
            "Sự kiện bảo mật đã được ghi lại", Colors.ERROR))
        self.buzzer.beep("error")
        self.root.after(4000, self.start_authentication)
    
    def _proceed_to_passcode(self):
        """Chuyển sang bước cuối - nhập mật khẩu"""
        logger.info("Chuyển đến bước xác thực mật khẩu cuối cùng")
        self.auth_state["step"] = AuthStep.PASSCODE
        self.auth_state["pin_attempts"] = 0
        
        # Discord notification về bước cuối
        if self.discord_bot:
            threading.Thread(
                target=self._send_discord_notification,
                args=("BƯỚC XÁC THỰC CUỐI CÙNG\nĐang chuyển đến nhập mật khẩu\nNgười dùng đã vượt qua 3/4 lớp bảo mật",),
                daemon=True
            ).start()
        
        self.gui.update_step(4, "NHẬP MẬT KHẨU CUỐI", "Nhập mật khẩu hệ thống", Colors.SUCCESS)
        self.gui.update_status("NHẬP MẬT KHẨU CUỐI CÙNG...", 'lightgreen')
        self.gui.update_detail(
            "BƯỚC XÁC THỰC CUỐI CÙNG\n"
            "✅ Nhận diện khuôn mặt: THÀNH CÔNG\n"
            "✅ Quét vân tay: THÀNH CÔNG\n" 
            "✅ Quét thẻ từ: THÀNH CÔNG\n"
            "🔄 Mật khẩu: ĐANG CHỜ\n\n"
            "Nhập mật khẩu số để hoàn tất xác thực.", 
            Colors.SUCCESS)
        
        self._request_passcode()

    def _request_passcode(self):
        """Nhập mật khẩu"""
        
        # Kiểm tra số lần thử tối đa
        if self.auth_state["pin_attempts"] >= self.config.MAX_ATTEMPTS:
            # Gửi cảnh báo nghiêm trọng cuối cùng
            details = f"Đã vượt quá số lần thử mật khẩu tối đa ({self.config.MAX_ATTEMPTS}) | Bước xác thực cuối cùng thất bại"
            logger.critical(f"Mật khẩu vượt quá số lần thử: {self.auth_state['pin_attempts']}")
            
            self._send_discord_failure_alert("passcode", self.auth_state['pin_attempts'], details)
            
            logger.warning("Mật khẩu: Đã vượt quá số lần thử tối đa")
            self.gui.update_status("MẬT KHẨU THẤT BẠI - KHỞI ĐỘNG LẠI", 'orange')
            self.gui.update_detail(
                "XÁC THỰC MẬT KHẨU THẤT BẠI!\n"
                f"Đã hết tất cả {self.config.MAX_ATTEMPTS} lần thử\n"
                "Người dùng đã vượt qua tất cả lớp bảo mật khác\n"
                "Đang khởi động lại toàn bộ quy trình xác thực...\n"
                "Sự kiện bảo mật nghiêm trọng đã được ghi lại", Colors.ERROR)
            self.buzzer.beep("error")
            self.root.after(4000, self.start_authentication)
            return
        
        # Tăng bộ đếm lần thử
        self.auth_state["pin_attempts"] += 1
        attempt_msg = f"Lần thử {self.auth_state['pin_attempts']}/{self.config.MAX_ATTEMPTS}"
        
        # Cập nhật GUI
        self.gui.update_step(4, "NHẬP MẬT KHẨU", attempt_msg, Colors.SUCCESS)
        self.gui.update_detail(
            f"Nhập mật khẩu hệ thống... (Lần thử {self.auth_state['pin_attempts']}/{self.config.MAX_ATTEMPTS})\n"
            "✅ Các bước trước đã hoàn thành thành công\n"
            "🎯 Sử dụng bàn phím số để nhập mã\n"
            "⚠️ Đây là bước xác thực cuối cùng", Colors.SUCCESS)
        
        # FORCE FOCUS
        self.root.focus_force()
        self.root.update()
        
        # Hiển thị dialog
        dialog = EnhancedNumpadDialog(
            self.root, 
            "XÁC THỰC CUỐI CÙNG",
            f"Nhập mật khẩu hệ thống (Lần thử {self.auth_state['pin_attempts']}/{self.config.MAX_ATTEMPTS}):", 
            True, 
            self.buzzer
        )
        
        if hasattr(dialog, 'dialog'):
            dialog.dialog.focus_force()
            dialog.dialog.grab_set()
            dialog.dialog.lift()
        
        # Lấy input
        entered_pin = dialog.show()
        
        if entered_pin is None:
            # Người dùng hủy
            logger.info("Nhập mật khẩu bị hủy bởi người dùng")
            self.gui.update_detail("❌ Việc nhập mật khẩu đã bị hủy\n🔄 Đang khởi động lại xác thực...", Colors.WARNING)
            self.buzzer.beep("click")
            self.root.after(2000, self.start_authentication)
            return
        
        # Xác thực mật khẩu
        correct_passcode = self.admin_data.get_passcode()
        
        if entered_pin == correct_passcode:
            # THÀNH CÔNG
            logger.info("✅ Mật khẩu đã xác thực - HOÀN TẤT TẤT CẢ XÁC THỰC!")
            self.gui.update_status("XÁC THỰC HOÀN TẤT! ĐANG MỞ KHÓA CỬA...", 'lightgreen')
            self.gui.update_detail(
                "🎉 XÁC THỰC THÀNH CÔNG!\n"
                "✅ Tất cả 4 lớp bảo mật đã được xác minh:\n"
                "  👤 Nhận diện khuôn mặt: THÀNH CÔNG\n"
                "  👆 Quét vân tay: THÀNH CÔNG\n"
                "  📱 Quét thẻ từ: THÀNH CÔNG\n"
                "  🔑 Mật khẩu: THÀNH CÔNG\n\n"
                "🔓 Đang mở khóa cửa...", Colors.SUCCESS)
            self.buzzer.beep("success")
            
            # Gửi thông báo thành công đến Discord
            if self.discord_bot:
                threading.Thread(
                    target=self._send_discord_notification,
                    args=("🔓 **XÁC THỰC HOÀN TẤT** - Tất cả 4 lớp đã được xác minh thành công!",),
                    daemon=True
                ).start()
            
            self._unlock_door()
            
        else:
            # THẤT BẠI - Mật khẩu sai
            remaining = self.config.MAX_ATTEMPTS - self.auth_state["pin_attempts"]
            
            details = f"Mật khẩu không đúng | Độ dài mong đợi: {len(correct_passcode)}, Nhận được: {len(entered_pin)} | Người dùng đã đến bước cuối"
            logger.warning(f"Mật khẩu không đúng: lần thử {self.auth_state['pin_attempts']}")
            
            self._send_discord_failure_alert("passcode", self.auth_state['pin_attempts'], details)
            
            self.buzzer.beep("error")
            
            if remaining > 0:
                # Vẫn còn lần thử
                error_msg = f"MẬT KHẨU KHÔNG ĐÚNG!\n"
                error_msg += f"🔢 Mật khẩu không khớp với hồ sơ hệ thống\n"
                error_msg += f"🔄 Còn {remaining} lần thử\n"
                error_msg += f"⚠️ Vui lòng xác minh mật khẩu và thử lại\n"
                error_msg += f"🛡️ Lần thử này đã được ghi lại"
                
                self.gui.update_detail(error_msg, Colors.ERROR)
                self.root.after(2500, self._request_passcode)
            else:
                # Hết lần thử
                final_error_msg = f"🚫 XÁC THỰC MẬT KHẨU THẤT BẠI!\n"
                final_error_msg += f"❌ Đã hết tất cả {self.config.MAX_ATTEMPTS} lần thử\n"
                final_error_msg += f"⚠️ Người dùng đã hoàn thành 3/4 lớp bảo mật nhưng thất bại ở bước cuối\n"
                final_error_msg += f"🔄 Đang khởi động lại toàn bộ quy trình xác thực...\n"
                final_error_msg += f"🛡️ Vi phạm bảo mật nghiêm trọng đã được ghi lại"
                
                self.gui.update_status("MẬT KHẨU THẤT BẠI - KHỞI ĐỘNG LẠI XÁC THỰC", 'orange')
                self.gui.update_detail(final_error_msg, Colors.ERROR)
                self.root.after(4000, self.start_authentication)

    def _admin_authentication(self):
        """Xác thực quản trị nâng cao qua thẻ từ"""
        # Discord notification về việc truy cập admin
        if self.discord_bot:
            threading.Thread(
                target=self._send_discord_notification,
                args=("🔧 **PHÁT HIỆN THẺ QUẢN TRỊ**\nThẻ quản trị đã được quét - yêu cầu xác thực mật khẩu",),
                daemon=True
            ).start()
        
        # FORCE FOCUS TRƯỚC KHI MỞ DIALOG
        self.root.focus_force()
        self.root.update()
        
        dialog = EnhancedNumpadDialog(
            self.root, 
            "🔧 TRUY CẬP QUẢN TRỊ VIA THẺ TỪ",
            "Đã phát hiện thẻ quản trị. Nhập mật khẩu quản trị:", 
            True, 
            self.buzzer
        )
        
        # FORCE FOCUS CHO DIALOG
        if hasattr(dialog, 'dialog'):
            dialog.dialog.focus_force()
            dialog.dialog.grab_set()
            dialog.dialog.lift()
        
        password = dialog.show()
        
        if password == self.config.ADMIN_PASS:
            # Xác thực quản trị thành công
            if self.discord_bot:
                threading.Thread(
                    target=self._send_discord_notification,
                    args=(f"✅ **CẤP QUYỀN TRUY CẬP QUẢN TRỊ**\nQuản trị viên đã xác thực thành công qua thẻ từ + mật khẩu\nĐang mở bảng điều khiển quản trị...",),
                    daemon=True
                ).start()
            
            logger.info("✅ Xác thực quản trị qua thẻ từ thành công")
            self.gui.update_status("THẺ QUẢN TRỊ ĐÃ XÁC THỰC! ĐANG MỞ BẢNG ĐIỀU KHIỂN", 'lightgreen')
            self.gui.update_detail(
                "🔧 XÁC THỰC QUẢN TRỊ THÀNH CÔNG!\n"
                "✅ Thẻ từ quản trị đã được xác minh\n"
                "✅ Mật khẩu quản trị đã được xác minh\n"
                "🎛️ Đang mở bảng điều khiển quản trị...", Colors.SUCCESS)
            self.buzzer.beep("success")
            self.admin_gui.show_admin_panel()
            
        elif password is not None:
            # Mật khẩu quản trị sai
            if self.discord_bot:
                threading.Thread(
                    target=self._send_discord_notification,
                    args=("❌ **TỪ CHỐI TRUY CẬP QUẢN TRỊ**\nThẻ quản trị đúng nhưng mật khẩu sai\n⚠️ Có thể có hành vi truy cập trái phép",),
                    daemon=True
                ).start()
            
            logger.warning("❌ Phát hiện thẻ quản trị nhưng mật khẩu sai")
            self.gui.update_status("MẬT KHẨU QUẢN TRỊ KHÔNG ĐÚNG", 'orange')
            self.gui.update_detail(
                "❌ TỪ CHỐI TRUY CẬP QUẢN TRỊ!\n"
                "✅ Thẻ từ quản trị đã được xác minh\n"
                "❌ Mật khẩu quản trị không đúng\n"
                "⚠️ Vi phạm bảo mật đã được ghi lại\n"
                "🔄 Đang quay về xác thực...", Colors.ERROR)
            self.buzzer.beep("error")
            time.sleep(3)
            self.start_authentication()
        else:
            # Quản trị hủy
            if self.discord_bot:
                threading.Thread(
                    target=self._send_discord_notification,
                    args=("🔄 **HỦY TRUY CẬP QUẢN TRỊ**\nQuản trị viên đã hủy việc nhập mật khẩu\nĐang quay về xác thực bình thường",),
                    daemon=True
                ).start()
            
            logger.info("Truy cập quản trị đã bị hủy")
            self.gui.update_detail("🔄 Truy cập quản trị đã bị hủy\nĐang quay về xác thực...", Colors.WARNING)
            self.start_authentication()
    

    def _send_discord_failure_alert(self, step, attempts, details=""):
        """Helper method để gửi Discord failure alert"""
        def send_alert():
            try:
                if self.discord_bot and self.discord_bot.bot:
                    # Tạo event loop mới
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    # Log để debug
                    logger.info(f"Đang gửi cảnh báo Discord: {step} - {attempts} lần thử")
                    
                    # Gửi alert
                    loop.run_until_complete(
                        self.discord_bot.send_authentication_failure_alert(step, attempts, details)
                    )
                    loop.close()
                    
                    logger.info(f"Cảnh báo Discord đã gửi thành công: {step}")
                    
                else:
                    logger.warning("Discord bot không khả dụng cho cảnh báo")
                    
            except Exception as e:
                logger.error(f"Lỗi cảnh báo Discord: {e}")
                import traceback
                traceback.print_exc()
        
        # Chạy trong thread riêng
        threading.Thread(target=send_alert, daemon=True).start()

    def _send_discord_success(self, step, details=""):
        """Enhanced helper function để gửi Discord success notification"""
        try:
            if self.discord_bot:
                # Create event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Record the success
                loop.run_until_complete(
                    self.discord_bot.record_authentication_success(step)
                )
                
                # Send additional success notification with details if provided
                if details:
                    success_message = f"✅ **{step.upper()} XÁC THỰC THÀNH CÔNG**\n{details}"
                    loop.run_until_complete(
                        self.discord_bot.send_security_notification(success_message, "SUCCESS")
                    )
                
                loop.close()
                logger.info(f"Thông báo thành công Discord đã gửi cho {step}")
                
        except Exception as e:
            logger.error(f"Lỗi thông báo thành công Discord cho {step}: {e}")

    def _unlock_door(self):
        """Enhanced door unlock với Discord notifications"""
        try:
            logger.info(f"🔓 Đang mở khóa cửa trong {self.config.LOCK_OPEN_DURATION} giây")
            
            # Thông báo thành công cuối cùng đến Discord
            if self.discord_bot:
                unlock_message = f"🔓 **CỬA ĐÃ MỞ KHÓA THÀNH CÔNG**\n"
                unlock_message += f"🎉 Hoàn thành xác thực 4 lớp:\n"
                unlock_message += f"  ✅ Nhận diện khuôn mặt: THÀNH CÔNG\n"
                unlock_message += f"  ✅ Quét vân tay: THÀNH CÔNG\n"
                unlock_message += f"  ✅ Quét thẻ từ: THÀNH CÔNG\n"
                unlock_message += f"  ✅ Mật khẩu: THÀNH CÔNG\n\n"
                unlock_message += f"🕐 Cửa sẽ tự động khóa lại sau {self.config.LOCK_OPEN_DURATION} giây\n"
                unlock_message += f"📅 Thời gian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                
                threading.Thread(
                    target=self._send_discord_notification,
                    args=(unlock_message,),
                    daemon=True
                ).start()
            
            self.gui.update_step(4, "HOÀN TẤT", "CỬA ĐÃ MỞ KHÓA", Colors.SUCCESS)
            self.gui.update_status(f"CỬA ĐANG MỞ - TỰ ĐỘNG KHÓA SAU {self.config.LOCK_OPEN_DURATION} GIÂY", 'lightgreen')
            
            # Mở khóa cửa
            self.relay.off()  # Unlock door
            self.buzzer.beep("success")
            
            # Đếm ngược với hiệu ứng hình ảnh
            for i in range(self.config.LOCK_OPEN_DURATION, 0, -1):
                self.root.after((self.config.LOCK_OPEN_DURATION - i) * 1000, 
                            lambda t=i: self.gui.update_detail(
                                f"🔓 CỬA ĐANG MỞ\n"
                                f"⏰ Tự động khóa sau {t} giây\n"
                                f"🚶 Vui lòng vào và đóng cửa\n"
                                f"🛡️ Tất cả hệ thống bảo mật đang hoạt động", Colors.SUCCESS))
                self.root.after((self.config.LOCK_OPEN_DURATION - i) * 1000,
                            lambda t=i: self.gui.update_status(f"CỬA MỞ - KHÓA SAU {t} GIÂY", 'lightgreen'))
                
                # Tiếng bíp đếm ngược cho 3 giây cuối
                if i <= 3:
                    self.root.after((self.config.LOCK_OPEN_DURATION - i) * 1000,
                                lambda: self.buzzer.beep("click"))
            
            # Lên lịch tự động khóa
            self.root.after(self.config.LOCK_OPEN_DURATION * 1000, self._lock_door)
            
        except Exception as e:
            logger.error(f"Lỗi mở khóa cửa: {e}")
            
            # Thông báo lỗi đến Discord
            if self.discord_bot:
                error_message = f"❌ **LỖI MỞ KHÓA CỬA**\nLỗi phần cứng khi mở khóa: {str(e)}\n⚠️ Có thể cần can thiệp thủ công"
                threading.Thread(
                    target=self._send_discord_notification,
                    args=(error_message,),
                    daemon=True
                ).start()
            
            self.gui.update_detail(f"🔧 LỖI MỞ KHÓA CỬA!\n{str(e)}\nVui lòng kiểm tra phần cứng", Colors.ERROR)
            self.buzzer.beep("error")

    def _lock_door(self):
        """Enhanced door lock với Discord notifications"""
        try:
            logger.info("🔒 Đang khóa cửa và đặt lại hệ thống")
            
            # Khóa cửa
            self.relay.on()  # Lock door
            
            # Discord notification về auto-lock
            if self.discord_bot:
                lock_message = f"🔒 **CỬA ĐÃ TỰ ĐỘNG KHÓA**\n"
                lock_message += f"✅ Cửa đã được bảo mật sau {self.config.LOCK_OPEN_DURATION} giây\n"
                lock_message += f"🔄 Hệ thống sẵn sàng cho người dùng tiếp theo\n"
                lock_message += f"🛡️ Tất cả lớp bảo mật đã được đặt lại\n"
                lock_message += f"📅 Thời gian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                
                threading.Thread(
                    target=self._send_discord_notification,
                    args=(lock_message,),
                    daemon=True
                ).start()
            
            self.gui.update_status("CỬA ĐÃ KHÓA - HỆ THỐNG SẴN SÀNG CHO NGƯỜI DÙNG TIẾP THEO", 'white')
            self.gui.update_detail(
                "🔒 CỬA ĐÃ TỰ ĐỘNG KHÓA\n"
                "✅ Hệ thống bảo mật đã đặt lại\n"
                "🔄 Sẵn sàng cho chu kỳ xác thực tiếp theo\n"
                "🛡️ Tất cả cảm biến đang hoạt động và giám sát", Colors.PRIMARY)
            self.buzzer.beep("click")
            
            # Reset detection stats
            self.gui.detection_stats = {"total": 0, "recognized": 0, "unknown": 0}
            
            # Reset authentication state hoàn toàn
            self.auth_state = {
                "step": AuthStep.FACE,
                "consecutive_face_ok": 0,
                "fingerprint_attempts": 0,
                "rfid_attempts": 0,
                "pin_attempts": 0
            }
            
            # Bắt đầu chu kỳ xác thực mới
            self.root.after(3000, self.start_authentication)
            
        except Exception as e:
            logger.error(f"Lỗi khóa cửa: {e}")
            
            # Thông báo lỗi nghiêm trọng đến Discord
            if self.discord_bot:
                critical_message = f"🚨 **NGHIÊM TRỌNG: LỖI KHÓA CỬA**\n"
                critical_message += f"❌ Không thể khóa cửa: {str(e)}\n"
                critical_message += f"⚠️ NGUY CƠ VI PHẠM BẢO MẬT\n"
                critical_message += f"🔧 CẦN CAN THIỆP THỦ CÔNG NGAY LẬP TỨC"
                
                threading.Thread(
                    target=self._send_discord_notification,
                    args=(critical_message,),
                    daemon=True
                ).start()
            
            self.gui.update_detail(f"🚨 NGHIÊM TRỌNG: LỖI KHÓA CỬA!\n{str(e)}\n⚠️ Cần can thiệp thủ công", Colors.ERROR)
            self.buzzer.beep("error")

    
    def run(self):
        """Chạy hệ thống chính"""
        try:
            logger.info("Đang khởi động Hệ thống Khóa Cửa Thông minh")

            if self.discord_bot:
                logger.info("Đang khởi động Discord bot...")
            if self.discord_bot.start_bot():
                logger.info("✅ Discord bot đã khởi động thành công!")
            else:
                logger.warning("⚠️ Không thể khởi động Discord bot")

            # Hiệu ứng khởi động
            self.gui.update_status("HỆ THỐNG KHÓA CỬA THÔNG MINH v2.2 - SẴN SÀNG!", 'lightgreen')
            self.gui.update_detail("Hệ thống nhận diện đã tải và sẵn sàng\n"
                                 "Hệ thống bảo mật 4 lớp đang hoạt động\n"
                                 "Tích hợp Discord bot đã được bật\n"
                                 "Hiệu suất nâng cao cho Raspberry Pi 5", Colors.SUCCESS)
            
            self.buzzer.beep("startup")
            
            # Hiển thị thông tin hệ thống
            face_info = self.face_recognizer.get_database_info()
            self.gui.update_detail(f"Trạng thái hệ thống:\n"
                                 f"Khuôn mặt đã đăng ký: {face_info['total_people']}\n"
                                 f"Vân tay: {len(self.admin_data.get_fingerprint_ids())}\n"
                                 f"Thẻ từ: {len(self.admin_data.get_rfid_uids())}\n"
                                 f"Trạng thái nhận diện: Sẵn sàng", Colors.SUCCESS)
            
            # Bắt đầu xác thực sau 3 giây
            self.root.after(3000, self.start_authentication)
            
            # Setup cleanup
            self.root.protocol("WM_DELETE_WINDOW", self.cleanup)
            
            # Bắt đầu main loop
            self.root.mainloop()
            
        except KeyboardInterrupt:
            logger.info("Hệ thống dừng theo yêu cầu người dùng")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Cleanup tài nguyên khi thoát"""
        logger.info("Đang dọn dẹp tài nguyên hệ thống...")
        self.running = False
        
        try:
            # CLEANUP DISCORD BOT
            if hasattr(self, 'discord_bot') and self.discord_bot:
                self.discord_bot.stop_bot()
                logger.info("Discord bot đã dừng")
            
            if hasattr(self, 'picam2'):
                self.picam2.stop()
                logger.info("Camera đã dừng")
                
            if hasattr(self, 'relay'):
                self.relay.on()  # Ensure door is locked
                logger.info("Cửa đã khóa")
                
            if hasattr(self, 'buzzer') and hasattr(self.buzzer, 'buzzer') and self.buzzer.buzzer:
                self.buzzer.buzzer.off()
                logger.info("Buzzer đã dừng")
                
        except Exception as e:
            logger.error(f"Lỗi cleanup: {e}")
        
        if hasattr(self, 'root'):
            self.root.quit()
        
        logger.info("Cleanup hoàn tất")
    
    

# ==== MAIN EXECUTION ====
if __name__ == "__main__":
    try:
        print("=" * 100)
        print("HỆ THỐNG KHÓA CỬA THÔNG MINH 4 LỚP BẢO MẬT - PHIÊN BẢN TIẾNG VIỆT")
        print("   Tác giả: Khoi - Luận án tốt nghiệp")
        print("   Ngày: 2025-01-16 - Vietnamese Interface for Students")
        print("=" * 100)
        print()
        print("CẢI TIẾN ĐẶC BIỆT:")
        print("   ✓ Nhận diện khuôn mặt với mô hình MobileNet SSD")
        print("   ✓ Nhận dạng LBPH với độ chính xác cao")
        print("   ✓ Tốc độ cao 30+ khung/giây với phản hồi trực quan")
        print("   ✓ Khung viền màu sắc (xanh/đỏ)")
        print("   ✓ Cửa sổ camera lớn hơn 60% so với phiên bản cũ")
        print("   ✓ Tối ưu hoàn toàn cho Raspberry Pi 5")
        print("   ✓ Âm thanh nâng cao với nhiều mẫu")
        print("   ✓ Thống kê và giám sát thời gian thực")
        print("   ✓ Giao diện tiếng Việt thân thiện")
        print("   ✓ Thuật ngữ đơn giản dễ hiểu")
        print()
        print("4 LỚP BẢO MẬT TUẦN TỰ:")
        print("   1. Nhận diện khuôn mặt (Camera thông minh)")
        print("   2. Sinh trắc học vân tay (Cảm biến AS608)")
        print("   3. Thẻ từ/NFC (Đầu đọc PN532)")
        print("   4. Mật khẩu số (Bàn phím)")
        print()
        print("ĐIỀU KHIỂN NÂNG CAO:")
        print("   * hoặc KP_* = Chế độ quản trị")
        print("   # hoặc KP_+ = Bắt đầu xác thực")
        print("   ESC = Thoát hệ thống")
        print("   F11 = Chuyển đổi toàn màn hình")
        print("   Phím mũi tên = Điều hướng dialog")
        print("   Enter/Space = Xác nhận")
        print("   Dấu chấm (.) = Hủy/Thoát dialog")
        print("   1-9 = Lựa chọn nhanh")
        print()
        print("KIỂM TRA PHẦN CỨNG:")
        
        hardware_components = [
            ("CAM", "Camera Raspberry Pi Module 2"),
            ("VT", "Cảm biến vân tay AS608 (USB/UART)"),
            ("THẺ", "Đầu đọc thẻ từ PN532 (I2C)"),
            ("KHÓA", "Khóa điện từ + Relay 4 kênh"),
            ("BUZZER", "Buzzer nâng cao (GPIO PWM)"),
            ("PHÍM", "Bàn phím số USB"),
            ("DATA", "Lưu trữ mô hình nhận diện"),
            ("HỆ THỐNG", "Cơ sở dữ liệu khuôn mặt")
        ]
        
        for prefix, component in hardware_components:
            print(f"   {prefix}: {component}")
            time.sleep(0.2)
        
        print()
        print("ĐANG KHỞI TẠO HỆ THỐNG ...")
        print("=" * 100)
        
        # Khởi tạo và chạy hệ thống
        system = VietnameseSecuritySystem()
        
        print()
        print("TẤT CẢ THÀNH PHẦN ĐÃ SẴN SÀNG!")
        print("Đang khởi động giao diện người dùng...")
        print("Kết nối phần cứng thành công!")
        print("Mô hình nhận diện đã được tải!")
        print("=" * 100)
        print("HỆ THỐNG SẴN SÀNG! BẮT ĐẦU SỬ DỤNG...")
        print("=" * 100)
        
        system.run()
        
    except Exception as e:
        print()
        print("=" * 100)
        print(f"LỖI KHỞI ĐỘNG NGHIÊM TRỌNG: {e}")
        print()
        print("DANH SÁCH KIỂM TRA KHẮC PHỤC:")
        
        troubleshooting_items = [
            ("HW", "Kiểm tra kết nối phần cứng và nguồn điện"),
            ("MODEL", "Đảm bảo các file mô hình nhận diện tồn tại"),
            ("GPIO", "Kiểm tra quyền truy cập GPIO và USB"),
            ("THƯ VIỆN", "Cài đặt đầy đủ thư viện Python"),
            ("BUZZER", "Cấu hình đúng GPIO cho Buzzer"),
            ("CAM", "Quyền camera và drivers"),
            ("Ổ CỨNG", "Kiểm tra dung lượng ổ cứng"),
            ("I2C", "Kết nối I2C và UART hoạt động"),
            ("MODEL", "Tải mô hình nhận diện (chạy download_models.py)"),
            ("LOG", "Kiểm tra file log để xem chi tiết lỗi")
        ]
        
        for prefix, item in troubleshooting_items:
            print(f"   {prefix}: {item}")
        
        print()
        print("HƯỚNG DẪN KHẮC PHỤC:")
        print("   1. Chạy: python3 download_models.py")
        print("   2. Kiểm tra: ls -la /home/khoi/Desktop/KHOI_LUANAN/models/")
        print("   3. Test camera: python3 -c 'from picamera2 import Picamera2; print(\"OK\")'")
        print("   4. Test OpenCV: python3 -c 'import cv2; print(cv2.__version__)'")
        print("   5. Kiểm tra log: tail -f /home/khoi/Desktop/KHOI_LUANAN/system.log")
        print()
        print("=" * 100)
        
        logger.error(f"System startup failed: {e}")
        sys.exit(1)
