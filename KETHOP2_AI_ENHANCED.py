#!/usr/bin/env python3
"""
HỆ THỐNG KHÓA BẢO MẬT 4 LỚP - VIETNAMESE SPEAKER INTEGRATION
Tác giả: Khoi - Luận án tốt nghiệp
Phiên bản: v2.4.0 - Vietnamese Speaker Integration
Ngày cập nhật: 2025-07-06 05:52:51 UTC - KHOI1235567
Cải thiện: Tích hợp loa tiếng Việt thật, thay thế buzzer bằng giọng nói
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

# Import modules của dự án
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

# Hardware imports - GIỮ NGUYÊN
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
    
    # Mock hardware classes - GIỮ NGUYÊN
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
        @property
        def value(self): return self.state
    
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

# ==== ENHANCED CONFIGURATION - GIỮ NGUYÊN ====
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
    
    # Authentication modes
    DEFAULT_AUTH_MODE: str = "sequential"
    
    def __post_init__(self):
        if self.ADMIN_UID is None:
            self.ADMIN_UID = [0xe5, 0xa8, 0xbd, 0x2]
        
        for path in [self.MODELS_PATH, self.FACE_DATA_PATH, self.ADMIN_DATA_PATH]:
            os.makedirs(path, exist_ok=True)

# ==== AUTH STEP ENUM - GIỮ NGUYÊN ====
class AuthStep(Enum):
    FACE = "face"
    FINGERPRINT = "fingerprint"
    RFID = "rfid"
    PASSCODE = "passcode"
    ADMIN = "admin"
    ANY_AUTH = "any_auth"
    COMPLETED = "completed"

# ==== AUTH STATE CLASS - GIỮ NGUYÊN ====
class AuthenticationState:
    """Enhanced authentication state management"""
    def __init__(self, auth_mode: str = "sequential"):
        self.auth_mode = auth_mode
        self.reset()
        
    def reset(self):
        if self.auth_mode == "sequential":
            self.step = AuthStep.FACE
        else:
            self.step = AuthStep.ANY_AUTH
            
        self.consecutive_face_ok = 0
        self.fingerprint_attempts = 0
        self.rfid_attempts = 0
        self.pin_attempts = 0
        
        self.any_mode_attempts = {
            "face": 0,
            "fingerprint": 0,
            "rfid": 0,
            "passcode": 0
        }
        self.any_mode_successes = []
        
    def set_mode(self, mode: str):
        if mode in ["sequential", "any"]:
            self.auth_mode = mode
            self.reset()
            return True
        return False
    
    def is_sequential_mode(self):
        return self.auth_mode == "sequential"
    
    def is_any_mode(self):
        return self.auth_mode == "any"
    
    def get_current_step_display(self):
        step_names = {
            AuthStep.FACE: "NHẬN DIỆN KHUÔN MẶT",
            AuthStep.FINGERPRINT: "QUÉT VÂN TAY",
            AuthStep.RFID: "QUÉT THẺ TỪ",
            AuthStep.PASSCODE: "NHẬP MẬT KHẨU",
            AuthStep.ANY_AUTH: "XÁC THỰC BẤT KỲ",
            AuthStep.COMPLETED: "HOÀN THÀNH"
        }
        return step_names.get(self.step, str(self.step))

# ==== LOGGING SETUP - GIỮ NGUYÊN ====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('/home/khoi/Desktop/KHOI_LUANAN/system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

logger.info("=" * 80)
logger.info("🚀 HỆ THỐNG KHÓA BẢO MẬT v2.4.0 - VIETNAMESE SPEAKER INTEGRATION")
logger.info("📅 Started: 2025-07-06 05:52:51 UTC")
logger.info("👤 User: KHOI1235567")
logger.info("🔊 Enhancement: Vietnamese Speaker integration, voice replaces buzzer")
logger.info("=" * 80)

# ==== ENHANCED VIETNAMESE SECURITY GUI - GIỮ NGUYÊN + SPEAKER INFO ====
class VietnameseSecurityGUI:
    def __init__(self, root):
        self.root = root
        self.fps_counter = 0
        self.fps_start_time = time.time()
        self.current_fps = 0
        
        self.detection_stats = {"total": 0, "recognized": 0}
        
        self._setup_window()
        self._create_widgets()
        self._setup_bindings()
        
        logger.info("✅ VietnameseSecurityGUI khởi tạo - Enhanced interface v2.4.0 with speaker")
    
    def update_fingerprint_status(self, status_type, message, details=""):
        """Smart update cho fingerprint status"""
        colors = {
            "scanning": Colors.PRIMARY,
            "quality_issue": Colors.WARNING, 
            "not_recognized": Colors.ERROR,
            "success": Colors.SUCCESS,
            "timeout": Colors.WARNING,
            "hardware_error": Colors.ERROR
        }
        
        titles = {
            "scanning": "ĐANG QUÉT VÂN TAY",
            "quality_issue": "CHẤT LƯỢNG VÂN TAY", 
            "not_recognized": "VÂN TAY KHÔNG NHẬN DIỆN",
            "success": "VÂN TAY THÀNH CÔNG",
            "timeout": "HẾT THỜI GIAN QUÉT",
            "hardware_error": "LỖI CẢM BIẾN"
        }
        
        self.update_step(2, titles.get(status_type, "QUÉT VÂN TAY"), message, colors.get(status_type, Colors.PRIMARY))
        
        if details:
            self.update_detail(details, colors.get(status_type, Colors.TEXT_SECONDARY))
    
    def _setup_window(self):
        self.root.title("HỆ THỐNG KHÓA CỬA THÔNG MINH 4 LỚP BẢO MẬT v2.4.0 + LOA")
        self.root.geometry("1500x900")
        self.root.configure(bg=Colors.DARK_BG)
        self.root.attributes('-fullscreen', True)
        self.root.minsize(1200, 800)
    
    def _create_widgets(self):
        # Container chính - GIỮ NGUYÊN
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
        # GIỮ NGUYÊN CAMERA PANEL
        camera_panel = tk.Frame(parent, bg=Colors.CARD_BG, relief=tk.RAISED, bd=4)
        camera_panel.grid(row=0, column=0, padx=(0,10), pady=0, sticky="nsew")
        
        # Header - THÊM SPEAKER INFO
        header = tk.Frame(camera_panel, bg=Colors.PRIMARY, height=90)
        header.pack(fill=tk.X, padx=4, pady=4)
        header.pack_propagate(False)
        
        # Left side - Camera title
        header_left = tk.Frame(header, bg=Colors.PRIMARY)
        header_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        tk.Label(header_left, text="CAMERA NHẬN DIỆN + LOA",
                font=('Arial', 24, 'bold'), fg='white', bg=Colors.PRIMARY,
                anchor='w').pack(side=tk.LEFT, padx=20, expand=True, fill=tk.X)
        
        # Right side - Stats + Speaker status
        stats_frame = tk.Frame(header, bg=Colors.PRIMARY)
        stats_frame.pack(side=tk.RIGHT, padx=20)
        
        self.fps_label = tk.Label(stats_frame, text="FPS: --", 
                                 font=('Arial', 14, 'bold'), fg='white', bg=Colors.PRIMARY)
        self.fps_label.pack()
        
        self.detection_count_label = tk.Label(stats_frame, text="Nhận diện: 0", 
                                            font=('Arial', 12), fg='white', bg=Colors.PRIMARY)
        self.detection_count_label.pack()
        
        # THÊM SPEAKER STATUS DISPLAY
        self.speaker_status_label = tk.Label(stats_frame, text="🔊 Loa: --", 
                                           font=('Arial', 12, 'bold'), fg='yellow', bg=Colors.PRIMARY)
        self.speaker_status_label.pack()
        
        # GIỮ NGUYÊN CAMERA FRAME
        self.camera_frame = tk.Frame(camera_panel, bg='black', relief=tk.SUNKEN, bd=4)
        self.camera_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        self.camera_label = tk.Label(self.camera_frame, 
                                   text="Đang khởi động camera + loa...\n\nVui lòng chờ...",
                                   font=('Arial', 22), fg='white', bg='black')
        self.camera_label.pack(expand=True)
        
        # GIỮ NGUYÊN STATUS FRAME
        status_frame = tk.Frame(camera_panel, bg=Colors.CARD_BG, height=70)
        status_frame.pack(fill=tk.X, pady=10)
        status_frame.pack_propagate(False)
        
        self.face_status = tk.Label(status_frame, text="Hệ thống sẵn sàng",
                                   font=('Arial', 16, 'bold'), 
                                   fg=Colors.PRIMARY, bg=Colors.CARD_BG)
        self.face_status.pack(expand=True)
        
        self.detection_info = tk.Label(status_frame, text="Chuẩn bị nhận diện + loa",
                                      font=('Arial', 14), 
                                      fg=Colors.TEXT_SECONDARY, bg=Colors.CARD_BG)
        self.detection_info.pack()
    
    def _create_status_panel(self, parent):
        # GIỮ NGUYÊN STATUS PANEL + THÊM SPEAKER INFO
        status_panel = tk.Frame(parent, bg=Colors.CARD_BG, relief=tk.RAISED, bd=4)
        status_panel.grid(row=0, column=1, padx=(10,0), pady=0, sticky="nsew")
        
        # Header - THÊM SPEAKER INFO
        header = tk.Frame(status_panel, bg=Colors.SUCCESS, height=100)
        header.pack(fill=tk.X, padx=4, pady=4)
        header.pack_propagate(False)
        
        tk.Label(header, text="TRẠNG THÁI XÁC THỰC + LOA",
                font=('Arial', 20, 'bold'), fg='white', bg=Colors.SUCCESS).pack(pady=(15, 5))
        
        self.auth_mode_label = tk.Label(header, text="CHẾ ĐỘ: ĐANG TẢI",
                font=('Arial', 12, 'bold'), fg='white', bg=Colors.WARNING,
                relief=tk.RAISED, bd=2, padx=8, pady=1)
        self.auth_mode_label.pack(pady=(0, 10))
        
        # GIỮ NGUYÊN STEP FRAME
        self.step_frame = tk.Frame(status_panel, bg=Colors.CARD_BG)
        self.step_frame.pack(fill=tk.X, padx=25, pady=20)
        
        self.step_number = tk.Label(self.step_frame, text="1", 
                                   font=('Arial', 48, 'bold'),
                                   fg='white', bg=Colors.PRIMARY,
                                   width=2, relief=tk.RAISED, bd=5)
        self.step_number.pack(side=tk.LEFT, padx=(0,20))
        
        step_info = tk.Frame(self.step_frame, bg=Colors.CARD_BG)
        step_info.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.step_title = tk.Label(step_info, text="NHẬN DIỆN KHUÔN MẶT",
                                  font=('Arial', 26, 'bold'),
                                  fg=Colors.TEXT_PRIMARY, bg=Colors.CARD_BG,
                                  anchor='w')
        self.step_title.pack(fill=tk.X)
        
        self.step_subtitle = tk.Label(step_info, text="Hệ thống đang phân tích",
                                     font=('Arial', 16),
                                     fg=Colors.TEXT_SECONDARY, bg=Colors.CARD_BG,
                                     anchor='w')
        self.step_subtitle.pack(fill=tk.X)
        
        # GIỮ NGUYÊN PROGRESS FRAME
        progress_frame = tk.Frame(status_panel, bg=Colors.CARD_BG)
        progress_frame.pack(fill=tk.X, padx=25, pady=15)
        
        tk.Label(progress_frame, text="CÁC BƯỚC XÁC THỰC:",
                font=('Arial', 18, 'bold'),
                fg=Colors.TEXT_PRIMARY, bg=Colors.CARD_BG).pack(anchor='w')
        
        steps_frame = tk.Frame(progress_frame, bg=Colors.CARD_BG)
        steps_frame.pack(fill=tk.X, pady=10)
        
        self.step_indicators = {}
        step_names = [
            "KHUÔN MẶT",
            "VÂN TAY", 
            "THẺ TỪ",
            "MẬT KHẨU"
        ]
        
        for i, name in enumerate(step_names):
            container = tk.Frame(steps_frame, bg=Colors.CARD_BG)
            container.pack(fill=tk.X, pady=6)
            
            circle = tk.Label(container, text=f"{i+1}",
                             font=('Arial', 18, 'bold'),
                             fg='white', bg=Colors.TEXT_SECONDARY,
                             width=2, relief=tk.RAISED, bd=3)
            circle.pack(side=tk.LEFT, padx=(0,15))
            
            label = tk.Label(container, text=name,
                            font=('Arial', 16, 'bold'),
                            fg=Colors.TEXT_PRIMARY, bg=Colors.CARD_BG,
                            anchor='w')
            label.pack(side=tk.LEFT, fill=tk.X, expand=True)
            
            self.step_indicators[i+1] = {
                'circle': circle,
                'label': label
            }
        
        # GIỮ NGUYÊN MESSAGE FRAME
        msg_frame = tk.Frame(status_panel, bg=Colors.BACKGROUND, relief=tk.SUNKEN, bd=3)
        msg_frame.pack(fill=tk.X, padx=25, pady=15)
        
        tk.Label(msg_frame, text="THÔNG TIN CHI TIẾT:",
                font=('Arial', 16, 'bold'),
                fg=Colors.TEXT_PRIMARY, bg=Colors.BACKGROUND).pack(anchor='w', padx=15, pady=(12,6))
        
        self.detail_message = tk.Label(msg_frame, text="Khởi động hệ thống nhận diện + loa...",
                                      font=('Arial', 14),
                                      fg=Colors.TEXT_SECONDARY, bg=Colors.BACKGROUND,
                                      wraplength=420, justify=tk.LEFT, anchor='w')
        self.detail_message.pack(fill=tk.X, padx=15, pady=(0,12))
        
        # GIỮ NGUYÊN TIME LABEL
        self.time_label = tk.Label(status_panel, text="",
                                  font=('Arial', 14),
                                  fg=Colors.TEXT_SECONDARY, bg=Colors.CARD_BG)
        self.time_label.pack(side=tk.BOTTOM, pady=8)
        
        self._update_time()
    
    def _create_status_bar(self):
        # STATUS BAR - THÊM SPEAKER INFO
        status_bar = tk.Frame(self.root, bg=Colors.PRIMARY, height=80)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=20, pady=(0,20))
        status_bar.pack_propagate(False)
        
        self.main_status = tk.Label(status_bar, 
                                   text="HỆ THỐNG KHÓA CỬA THÔNG MINH v2.4.0 + LOA TIẾNG VIỆT - ĐANG KHỞI ĐỘNG",
                                   font=('Arial', 20, 'bold'),
                                   fg='white', bg=Colors.PRIMARY)
        self.main_status.pack(expand=True)
    
    def _setup_bindings(self):
        # GIỮ NGUYÊN BINDINGS
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
                                            "Bạn có chắc chắn muốn thoát?", 
                                            self.system_ref.buzzer,
                                            getattr(self.system_ref, 'speaker', None)):
                    self.root.quit()
    
    def _update_time(self):
        current_time = datetime.now().strftime("%H:%M:%S - %d/%m/%Y")
        self.time_label.config(text=current_time)
        self.root.after(1000, self._update_time)
    
    # ==== UPDATE METHODS - THÊM SPEAKER STATUS ====
    def update_auth_mode_display(self, auth_mode: str):
        """Cập nhật hiển thị chế độ xác thực"""
        mode_displays = {
            "sequential": ("🛡️ TUẦN TỰ", Colors.SUCCESS),
            "any": ("⚡ ĐƠN LẺ", Colors.WARNING)
        }
        
        display_text, color = mode_displays.get(auth_mode, ("❓ KHÔNG XÁC ĐỊNH", Colors.ERROR))
        
        self.auth_mode_label.config(text=display_text, bg=color)
        
        if auth_mode == "any":
            for i in range(1, 5):
                indicator = self.step_indicators[i]
                indicator['circle'].config(bg=Colors.WARNING)
                indicator['label'].config(fg=Colors.TEXT_PRIMARY)
        else:
            for i in range(1, 5):
                indicator = self.step_indicators[i]
                indicator['circle'].config(bg=Colors.TEXT_SECONDARY)
                indicator['label'].config(fg=Colors.TEXT_SECONDARY)
    
    def update_speaker_status(self, enabled, method=""):
        """NEW: Cập nhật trạng thái loa"""
        if enabled:
            status_text = f"🔊 Loa: BẬT"
            if method:
                status_text += f" ({method})"
            self.speaker_status_label.config(text=status_text, fg='lightgreen')
        else:
            self.speaker_status_label.config(text="🔇 Loa: TẮT", fg='orange')
    
    # GIỮ NGUYÊN TẤT CẢ CÁC METHODS KHÁC (update_camera, update_step, etc.)
    def update_camera(self, frame: np.ndarray, detection_result: Optional[FaceDetectionResult] = None):
        """Cập nhật hiển thị camera"""
        try:
            self.fps_counter += 1
            current_time = time.time()
            if current_time - self.fps_start_time >= 1.0:
                self.current_fps = self.fps_counter
                self.fps_counter = 0
                self.fps_start_time = current_time
                self.fps_label.config(text=f"FPS: {self.current_fps}")
            
            if detection_result:
                self.detection_stats["total"] += 1
                if detection_result.recognized:
                    self.detection_stats["recognized"] += 1
                
                self.detection_count_label.config(
                    text=f"Nhận diện: {self.detection_stats['recognized']}/{self.detection_stats['total']}"
                )
            
            height, width = frame.shape[:2]
            display_height = Config.DISPLAY_HEIGHT
            display_width = int(width * display_height / height)
            
            img = cv2.resize(frame, (display_width, display_height))
            rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            img_pil = Image.fromarray(rgb_img)
            img_tk = ImageTk.PhotoImage(img_pil)
            
            self.camera_label.config(image=img_tk, text="")
            self.camera_label.image = img_tk
            
            if detection_result:
                if detection_result.detected:
                    if detection_result.recognized:
                        self.face_status.config(
                            text=f"ĐÃ XÁC NHẬN: {detection_result.person_name}",
                            fg=Colors.SUCCESS
                        )
                        self.detection_info.config(
                            text=f"Độ chính xác: {detection_result.confidence:.1f}% - CHO PHÉP",
                            fg=Colors.SUCCESS
                        )
                    else:
                        self.face_status.config(
                            text="KHUÔN MẶT KHÔNG ĐƯỢC PHÉP",
                            fg=Colors.ERROR
                        )
                        self.detection_info.config(
                            text="Chưa được đăng ký - Từ chối truy cập",
                            fg=Colors.ERROR
                        )
                else:
                    self.face_status.config(
                        text="ĐANG QUÉT KHUÔN MẶT",
                        fg=Colors.WARNING
                    )
                    self.detection_info.config(
                        text="Tìm kiếm khuôn mặt trong khung hình",
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
        
        auth_mode = "sequential"
        if hasattr(self, 'system_ref') and hasattr(self.system_ref, 'auth_state'):
            auth_mode = self.system_ref.auth_state.auth_mode
        
        if auth_mode == "any":
            for i in range(1, 5):
                indicator = self.step_indicators[i]
                if i == step_num:
                    indicator['circle'].config(bg=color)
                    indicator['label'].config(fg=Colors.TEXT_PRIMARY)
                else:
                    indicator['circle'].config(bg=Colors.WARNING)
                    indicator['label'].config(fg=Colors.TEXT_PRIMARY)
        else:
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
        
        if len(message) > 180:
            message = message[:177] + "..."
        
        self.detail_message.config(text=message, fg=color)
    
    def set_system_reference(self, system):
        self.system_ref = system
        
        if hasattr(system, 'admin_data'):
            auth_mode = system.admin_data.get_authentication_mode()
            self.update_auth_mode_display(auth_mode)
        
        # UPDATE SPEAKER STATUS
        if hasattr(system, 'speaker') and system.speaker:
            self.update_speaker_status(system.speaker.enabled, "Google TTS")
        else:
            self.update_speaker_status(False)

# ==== VIETNAMESE SECURITY SYSTEM - THÊM SPEAKER INTEGRATION ====
class VietnameseSecuritySystem:
    
    def _init_discord_bot(self):
        """Khởi tạo Discord bot integration - GIỮ NGUYÊN"""
        try:
            logger.info("Khởi tạo Discord bot integration...")
            self.discord_bot = DiscordSecurityBot(self)
            logger.info("Discord bot integration đã sẵn sàng")
        except Exception as e:
            logger.error(f"Lỗi khởi tạo Discord bot: {e}")
            logger.info("Tiếp tục chạy mà không có Discord bot...")
            self.discord_bot = None
    
    def _send_discord_notification(self, message):
        """Helper function để gửi Discord notification - GIỮ NGUYÊN"""
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
        logger.info("🚀 Khởi tạo Hệ thống Khóa Cửa Thông minh v2.4.0 - Vietnamese Speaker")
        
        self._init_hardware()
        self._init_components()
        self._init_gui()
        self._init_discord_bot()
        
        # ENHANCED: Authentication state
        auth_mode = self.admin_data.get_authentication_mode()
        self.auth_state = AuthenticationState(auth_mode)
        
        # Legacy compatibility
        self.failed_attempts = {
            "face": 0,
            "fingerprint": 0, 
            "rfid": 0,
            "pin": 0,
            "total_today": 0
        }
        
        self.running = True
        self.face_thread = None
        
        # Any mode specific variables
        self.any_mode_active_threads = {}
        self.any_mode_lock = threading.Lock()
        
        logger.info(f"✅ Hệ thống khởi tạo thành công - Chế độ: {auth_mode.upper()}")
    
    def _init_hardware(self):
        """Khởi tạo phần cứng - GIỮ NGUYÊN"""
        try:
            logger.info("Khởi tạo phần cứng...")
            
            # Buzzer - GIỮ NGUYÊN (will be enhanced with speaker later)
            try:
                self.buzzer = EnhancedBuzzerManager(self.config.BUZZER_GPIO)
            except:
                logger.warning("Buzzer mock mode")
                self.buzzer = type('MockBuzzer', (), {'beep': lambda x, y: None})()
            
            # Camera - GIỮ NGUYÊN
            self.picam2 = Picamera2()
            if hasattr(self.picam2, 'configure'):
                self.picam2.configure(self.picam2.create_video_configuration(
                    main={"format": 'XRGB8888', "size": (self.config.CAMERA_WIDTH, self.config.CAMERA_HEIGHT)}
                ))
                self.picam2.start()
                time.sleep(2)
            
            # Relay (Door lock) - GIỮ NGUYÊN
            self.relay = LED(self.config.RELAY_GPIO)
            self.relay.on()
            
            # RFID - GIỮ NGUYÊN
            i2c = busio.I2C(board.SCL, board.SDA)
            self.pn532 = PN532_I2C(i2c, debug=False)
            self.pn532.SAM_configuration()
            
            # Fingerprint sensor - GIỮ NGUYÊN
            self.fingerprint = PyFingerprint('/dev/ttyUSB0', 57600, 0xFFFFFFFF, 0x00000000)
            if not self.fingerprint.verifyPassword():
                logger.warning("Fingerprint sensor simulation mode")
            
            logger.info("Tất cả phần cứng đã sẵn sàng")
            
        except Exception as e:
            logger.error(f"Lỗi khởi tạo phần cứng: {e}")
            logger.info("Continuing in simulation mode...")
    
    def _init_components(self):
        """Khởi tạo các thành phần hệ thống + SPEAKER"""
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
            
            # 🔊 VIETNAMESE SPEAKER INTEGRATION
            try:
                from vietnamese_speaker import VietnameseSpeaker
                speaker_enabled = self.admin_data.get_speaker_enabled()
                speaker_volume = self.admin_data.get_speaker_volume()
                
                self.speaker = VietnameseSpeaker(enabled=speaker_enabled)
                self.speaker.set_volume(speaker_volume)
                self.speaker.start_speaker_thread()
                
                # INTEGRATE SPEAKER WITH BUZZER
                self.buzzer = EnhancedBuzzerManager(self.config.BUZZER_GPIO, self.speaker)
                
                logger.info(f"✅ Vietnamese Speaker tích hợp - Enabled: {speaker_enabled}, Volume: {speaker_volume}")
            except ImportError as e:
                self.speaker = None
                logger.warning(f"⚠️ Vietnamese Speaker không khả dụng: {e}")
                logger.info("Hệ thống sẽ chạy với buzzer bình thường")
            except Exception as e:
                self.speaker = None
                logger.error(f"❌ Lỗi khởi tạo Vietnamese Speaker: {e}")
            
            logger.info("Các thành phần hệ thống đã sẵn sàng")
            
        except Exception as e:
            logger.error(f"Lỗi khởi tạo thành phần hệ thống: {e}")
            raise
    
    def _init_gui(self):
        """Khởi tạo giao diện - GIỮ NGUYÊN"""
        try:
            logger.info("Khởi tạo giao diện enhanced...")
            
            self.root = tk.Tk()
            self.gui = VietnameseSecurityGUI(self.root)
            self.gui.set_system_reference(self)
            
            # Admin GUI
            self.admin_gui = ImprovedAdminGUI(self.root, self)
            
            logger.info("Giao diện enhanced đã sẵn sàng")
            
        except Exception as e:
            logger.error(f"Lỗi khởi tạo giao diện: {e}")
            raise
    
    def _force_admin_mode(self):
        """Chế độ admin nhanh bằng phím * + VOICE"""
        # VOICE: Admin access attempt
        if self.speaker:
            self.speaker.speak("", "Truy cập quản trị")
        
        self.root.focus_force()
        self.root.update()
        
        dialog = EnhancedNumpadDialog(
            self.root, 
            "TRUY CẬP QUẢN TRỊ",
            "Nhập mật khẩu quản trị:", 
            True, 
            self.buzzer,
            self.speaker
        )
        
        if hasattr(dialog, 'dialog'):
            dialog.dialog.focus_force()
            dialog.dialog.grab_set()
            dialog.dialog.lift()
        
        password = dialog.show()
        
        if password == self.config.ADMIN_PASS:
            # Admin auth success + VOICE
            if self.speaker:
                self.speaker.speak("admin_access")
            
            self.gui.update_status("CHẾ ĐỘ QUẢN TRỊ ĐÃ KÍCH HOẠT", 'lightgreen')
            self.gui.update_detail("Xác thực quản trị thành công! Đang mở bảng điều khiển...", Colors.SUCCESS)
            self.buzzer.beep("success")
            self.admin_gui.show_admin_panel()
        elif password is not None:
            # Wrong admin password + VOICE
            if self.speaker:
                self.speaker.speak("admin_denied")
            
            self.gui.update_status("TỪ CHỐI TRUY CẬP QUẢN TRỊ", 'orange')
            self.gui.update_detail("Mật khẩu quản trị không đúng!", Colors.ERROR)
            self.buzzer.beep("error")
    
    # ==== ENHANCED AUTHENTICATION METHODS WITH VOICE ====
    
    def start_authentication(self):
        """ENHANCED: Bắt đầu quy trình xác thực với INTELLIGENT voice"""
        current_mode = self.admin_data.get_authentication_mode()
        self.auth_state.set_mode(current_mode)
        
        logger.info(f"🔄 Bắt đầu quy trình xác thực - Chế độ: {current_mode.upper()}")
        
        # 🧠 INTELLIGENT VOICE: Only announce mode if truly new session
        if hasattr(self, 'speaker') and self.speaker:
            # Check if this is a real new session (not just door reset)
            is_new_session = not hasattr(self, '_last_auth_mode') or self._last_auth_mode != current_mode
            
            if is_new_session:
                if current_mode == "sequential":
                    self.speaker.speak("mode_sequential")
                else:
                    self.speaker.speak("mode_any")
                
                self._last_auth_mode = current_mode
                time.sleep(1)
                self.speaker.speak("system_ready")
        
        self.gui.update_auth_mode_display(current_mode)
        
        if current_mode == "sequential":
            self._start_sequential_authentication()
        else:
            self._start_any_authentication()

    def _start_sequential_authentication(self):
        """Bắt đầu xác thực tuần tự với INTELLIGENT voice"""
        logger.info("🛡️ Khởi động chế độ xác thực tuần tự")
        
        # 🧠 INTELLIGENT VOICE: Only announce step if starting fresh
        if hasattr(self, 'speaker') and self.speaker:
            self.speaker.speak("step_face")
        
        self.auth_state.reset()
        
        self.gui.update_step(1, "NHẬN DIỆN KHUÔN MẶT", "Hệ thống đang phân tích", Colors.PRIMARY)
        self.gui.update_status("XÁC THỰC TUẦN TỰ - BƯỚC 1/4: PHÂN TÍCH KHUÔN MẶT", 'white')
        self.gui.update_detail("🛡️ Chế độ bảo mật cao - Tuần tự 4 lớp\nHệ thống nhận diện đang quét và phân tích khuôn mặt.\nNhìn thẳng vào camera và giữ nguyên tư thế.", Colors.PRIMARY)
        
        self.gui.detection_stats = {"total": 0, "recognized": 0}
        
        if self.face_thread and self.face_thread.is_alive():
            return
        
        self.face_thread = threading.Thread(target=self._face_recognition_loop, daemon=True)
        self.face_thread.start()

    def _start_any_authentication(self):
        """ENHANCED: Bắt đầu xác thực đơn lẻ với INTELLIGENT voice"""
        logger.info("⚡ Khởi động chế độ xác thực đơn lẻ")
        
        # 🧠 INTELLIGENT VOICE: Don't repeat mode announcement every time
        # Only announce if this is truly first time in any mode
        
        self.auth_state.reset()
        self._stop_all_auth_threads()
        
        self.gui.update_step(0, "XÁC THỰC BẤT KỲ", "Chọn phương thức xác thực", Colors.WARNING)
        self.gui.update_status("CHẾ ĐỘ TRUY CẬP NHANH - SỬ DỤNG BẤT KỲ PHƯƠNG THỨC NÀO", 'yellow')
        self.gui.update_detail("⚡ CHỌN PHƯƠNG THỨC XÁC THỰC:\n👤 KHUÔN MẶT: Nhìn vào camera\n👆 VÂN TAY: Đặt ngón tay lên cảm biến\n📱 THẺ TỪ: Đưa thẻ lại gần đầu đọc\n🔑 MẬT KHẨU: Nhấn # để nhập\n🔊 Loa sẽ thông báo khi xác thực thành công", Colors.WARNING)
        
        self.gui.detection_stats = {"total": 0, "recognized": 0}
        self._start_concurrent_authentication()
        
    def _start_concurrent_authentication(self):
        """Khởi động tất cả phương thức xác thực đồng thời với ENHANCED VOICE"""
        with self.any_mode_lock:
            try:
                # 🔊 ENHANCED VOICE: More specific guidance
                if self.speaker:
                    self.speaker.speak("", "Chọn một trong bốn phương thức xác thực")
                
                # Start face recognition
                if "face" not in self.any_mode_active_threads or not self.any_mode_active_threads["face"].is_alive():
                    self.any_mode_active_threads["face"] = threading.Thread(
                        target=self._any_mode_face_loop, daemon=True)
                    self.any_mode_active_threads["face"].start()
                    logger.debug("✅ Face recognition thread started")
                
                # Start fingerprint scanning
                if "fingerprint" not in self.any_mode_active_threads or not self.any_mode_active_threads["fingerprint"].is_alive():
                    self.any_mode_active_threads["fingerprint"] = threading.Thread(
                        target=self._any_mode_fingerprint_loop, daemon=True)
                    self.any_mode_active_threads["fingerprint"].start()
                    logger.debug("✅ Fingerprint thread started")
                
                # Start RFID scanning
                if "rfid" not in self.any_mode_active_threads or not self.any_mode_active_threads["rfid"].is_alive():
                    self.any_mode_active_threads["rfid"] = threading.Thread(
                        target=self._any_mode_rfid_loop, daemon=True)
                    self.any_mode_active_threads["rfid"].start()
                    logger.debug("✅ RFID thread started")
                
                logger.info("✅ Tất cả phương thức xác thực đã sẵn sàng trong chế độ Any")
                
                # 🎨 ENHANCED GUIDANCE MESSAGE
                guidance_message = (
                    "⚡ CHỌN PHƯƠNG THỨC XÁC THỰC:\n"
                    "👤 KHUÔN MẶT: Nhìn vào camera\n"
                    "👆 VÂN TAY: Đặt ngón tay lên cảm biến\n"
                    "📱 THẺ TỪ: Đưa thẻ lại gần đầu đọc\n"
                    "🔑 MẬT KHẨU: Nhấn # để nhập\n"
                    "🔊 Loa sẽ thông báo khi xác thực thành công"
                )
                
                self.root.after(0, lambda: self.gui.update_detail(guidance_message, Colors.SUCCESS))
                
                # Bind keyboard for passcode input
                self.root.bind('<numbersign>', self._trigger_any_mode_passcode)
                self.root.bind('<KP_Add>', self._trigger_any_mode_passcode)
                
            except Exception as e:
                logger.error(f"❌ Lỗi khởi động concurrent authentication: {e}")
                self.root.after(0, lambda: self.gui.update_detail(f"Lỗi khởi động: {str(e)}", Colors.ERROR))
    
    # GIỮ NGUYÊN TẤT CẢ CÁC METHODS AUTHENTICATION NHƯNG THÊM VOICE
    
    def _stop_all_auth_threads(self):
        """Dừng tất cả thread xác thực - GIỮ NGUYÊN"""
        try:
            with self.any_mode_lock:
                for thread_name, thread in self.any_mode_active_threads.items():
                    if thread and thread.is_alive():
                        logger.debug(f"🛑 Stopping {thread_name} thread")
                        
                self.any_mode_active_threads.clear()
                
                self.root.unbind('<numbersign>')
                self.root.unbind('<KP_Add>')
                
                logger.debug("✅ All authentication threads stopped")
        except Exception as e:
            logger.error(f"❌ Error stopping auth threads: {e}")
    
    # ==== ANY MODE AUTHENTICATION LOOPS WITH VOICE ====
    
    def _any_mode_face_loop(self):
        """Face recognition loop cho any mode + VOICE"""
        logger.debug("🎭 Any mode face loop started")
        consecutive_count = 0
        
        while (self.running and 
               self.auth_state.is_any_mode() and 
               self.auth_state.step != AuthStep.COMPLETED):
            try:
                frame = self.picam2.capture_array()
                if frame is None:
                    continue
                
                annotated_frame, result = self.face_recognizer.process_frame(frame)
                self.root.after(0, lambda: self.gui.update_camera(annotated_frame, result))
                
                if result.recognized:
                    consecutive_count += 1
                    
                    if consecutive_count >= self.config.FACE_REQUIRED_CONSECUTIVE:
                        logger.info(f"✅ Any mode face success: {result.person_name}")
                        
                        # VOICE: Success announcement
                        if self.speaker:
                            self.speaker.speak("face_success", f"Xin chào {result.person_name}")
                        
                        self._any_mode_success("face", result.person_name, f"Độ chính xác: {result.confidence:.1f}")
                        return
                    else:
                        progress = consecutive_count / self.config.FACE_REQUIRED_CONSECUTIVE * 100
                        self.root.after(0, lambda: self.gui.update_detail(
                            f"👤 KHUÔN MẶT ĐANG XÁC NHẬN: {result.person_name}\n📊 Tiến độ: {consecutive_count}/{self.config.FACE_REQUIRED_CONSECUTIVE} ({progress:.0f}%)\n🎯 Độ chính xác: {result.confidence:.1f}%\n🔊 Tiếp tục nhìn vào camera...", Colors.SUCCESS))
                else:
                    consecutive_count = 0
                
                time.sleep(self.config.FACE_DETECTION_INTERVAL)
                
            except Exception as e:
                logger.error(f"❌ Any mode face loop error: {e}")
                time.sleep(1)
        
        logger.debug("🛑 Any mode face loop ended")
    
    def _any_mode_fingerprint_loop(self):
        """Fingerprint loop cho any mode + VOICE"""
        logger.debug("👆 Any mode fingerprint loop started")
        
        while (self.running and 
               self.auth_state.is_any_mode() and 
               self.auth_state.step != AuthStep.COMPLETED):
            try:
                if self.fingerprint.readImage():
                    try:
                        self.fingerprint.convertImage(0x01)
                        result = self.fingerprint.searchTemplate()
                        
                        if result[0] != -1:
                            # SUCCESS + VOICE
                            logger.info(f"✅ Any mode fingerprint success: ID {result[0]}")
                            
                            if self.speaker:
                                self.speaker.speak("fingerprint_success")
                            
                            self._any_mode_success("fingerprint", f"ID {result[0]}", f"Template match: {result[1]}")
                            return
                        else:
                            logger.debug(f"👆 Fingerprint not recognized in any mode")
                            
                    except Exception as convert_error:
                        logger.debug(f"👆 Fingerprint quality issue: {convert_error}")
                
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"❌ Any mode fingerprint error: {e}")
                time.sleep(2)
        
        logger.debug("🛑 Any mode fingerprint loop ended")
    
    def _any_mode_rfid_loop(self):
        """RFID loop cho any mode + VOICE"""
        logger.debug("📱 Any mode RFID loop started")
        
        while (self.running and 
               self.auth_state.is_any_mode() and 
               self.auth_state.step != AuthStep.COMPLETED):
            try:
                uid = self.pn532.read_passive_target(timeout=2)
                
                if uid:
                    uid_list = list(uid)
                    logger.debug(f"📱 RFID detected in any mode: {uid_list}")
                    
                    # Check if admin card
                    if uid_list == self.config.ADMIN_UID:
                        self.root.after(0, lambda: self._admin_authentication())
                        return
                    
                    # Check if valid card
                    valid_uids = self.admin_data.get_rfid_uids()
                    if uid_list in valid_uids:
                        # SUCCESS + VOICE
                        logger.info(f"✅ Any mode RFID success: {uid_list}")
                        
                        if self.speaker:
                            self.speaker.speak("rfid_success")
                        
                        self._any_mode_success("rfid", f"UID {uid_list}", "Thẻ hợp lệ")
                        return
                    else:
                        # Invalid card + VOICE
                        logger.warning(f"📱 Invalid RFID in any mode: {uid_list}")
                        
                        if self.speaker:
                            self.speaker.speak("auth_failed", "Thẻ từ không hợp lệ")
                        
                        self.root.after(0, lambda: self.gui.update_detail(
                            f"📱 THẺ TỪ KHÔNG HỢP LỆ!\n🔍 UID phát hiện: {uid_list}\n❌ Thẻ chưa được đăng ký trong hệ thống\n⚡ Các phương thức khác vẫn hoạt động\n🔊 Thử phương thức khác", Colors.ERROR))
                
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ Any mode RFID error: {e}")
                time.sleep(3)
        
        logger.debug("🛑 Any mode RFID loop ended")
    
    def _trigger_any_mode_passcode(self, event=None):
        """Trigger passcode input trong any mode + VOICE"""
        if (self.auth_state.is_any_mode() and 
            self.auth_state.step != AuthStep.COMPLETED):
            
            logger.debug("🔑 Triggering any mode passcode input")
            
            # VOICE: Announce passcode input
            if self.speaker:
                self.speaker.speak("step_passcode")
            
            self.gui.update_detail(
                "🔑 NHẬP MẬT KHẨU - CHẾ ĐỘ NHANH\nNhập mật khẩu hệ thống để mở khóa ngay\nCác phương thức khác sẽ tạm dừng...", Colors.ACCENT)
            
            self.root.focus_force()
            self.root.update()
            
            dialog = EnhancedNumpadDialog(
                self.root, 
                "🔑 XÁC THỰC NHANH - MẬT KHẨU",
                "Nhập mật khẩu hệ thống (Chế độ đơn lẻ):", 
                True, 
                self.buzzer,
                self.speaker
            )
            
            if hasattr(dialog, 'dialog'):
                dialog.dialog.focus_force()
                dialog.dialog.grab_set()
                dialog.dialog.lift()
            
            entered_pin = dialog.show()
            
            if entered_pin is None:
                # User cancelled + VOICE
                if self.speaker:
                    self.speaker.speak("", "Hủy nhập mật khẩu")
                
                self.gui.update_detail(
                    "🔑 Nhập mật khẩu đã bị hủy\n⚡ Các phương thức khác tiếp tục hoạt động", Colors.WARNING)
                return
            
            correct_passcode = self.admin_data.get_passcode()
            
            if entered_pin == correct_passcode:
                # SUCCESS + VOICE
                logger.info("✅ Any mode passcode success")
                
                if self.speaker:
                    self.speaker.speak("passcode_success")
                
                self._any_mode_success("passcode", "Mật khẩu chính xác", f"Độ dài: {len(entered_pin)} ký tự")
            else:
                # FAILURE + VOICE
                logger.warning("❌ Any mode passcode failed")
                
                if self.speaker:
                    self.speaker.speak("auth_failed", "Mật khẩu không đúng")
                
                self.gui.update_detail(
                    f"🔑 MẬT KHẨU KHÔNG ĐÚNG!\n❌ Mật khẩu không khớp với hệ thống\n⚡ Các phương thức khác vẫn hoạt động\n🔄 Có thể thử lại bằng phím #", Colors.ERROR)
                self.buzzer.beep("error")
    
    def _any_mode_success(self, method: str, identifier: str, details: str):
        """Xử lý thành công trong any mode với ENHANCED VOICE"""
        try:
            with self.any_mode_lock:
                if self.auth_state.step == AuthStep.COMPLETED:
                    return

                self.auth_state.step = AuthStep.COMPLETED
                self.auth_state.any_mode_successes.append({
                    "method": method,
                    "identifier": identifier,
                    "details": details,
                    "timestamp": datetime.now().isoformat()
                })

            method_names = {
                "face": "👤 NHẬN DIỆN KHUÔN MẶT",
                "fingerprint": "👆 SINH TRẮC VÂN TAY",
                "rfid": "📱 THẺ TỪ RFID",
                "passcode": "🔑 MẬT KHẨU HỆ THỐNG"
            }

            method_display = method_names.get(method, method.upper())

            logger.info(f"🎉 ANY MODE SUCCESS: {method} - {identifier}")

            # 🔊 ENHANCED VOICE - More specific announcements
            if self.speaker:
                if method == "face":
                    self.speaker.speak("auth_complete", f"Xác thực khuôn mặt thành công")
                elif method == "fingerprint":
                    self.speaker.speak("auth_complete", f"Xác thực vân tay thành công")
                elif method == "rfid":
                    self.speaker.speak("auth_complete", f"Xác thực thẻ từ thành công")
                elif method == "passcode":
                    self.speaker.speak("auth_complete", f"Xác thực mật khẩu thành công")
                else:
                    self.speaker.speak("auth_complete", f"Xác thực {method_display} thành công")

            self._stop_all_auth_threads()

            # 🎨 MORE SPECIFIC STATUS MESSAGES
            specific_success_msg = {
                "face": f"XÁC THỰC KHUÔN MẶT THÀNH CÔNG - {identifier.upper()}",
                "fingerprint": f"XÁC THỰC VÂN TAY THÀNH CÔNG - {identifier.upper()}",
                "rfid": f"XÁC THỰC THẺ TỪ THÀNH CÔNG - {identifier}",
                "passcode": f"XÁC THỰC MẬT KHẨU THÀNH CÔNG - ĐÚNG"
            }

            status_message = specific_success_msg.get(method, f"XÁC THỰC {method.upper()} THÀNH CÔNG")

            self.gui.update_step(0, "XÁC THỰC THÀNH CÔNG", f"{method_display} - HOÀN TẤT", Colors.SUCCESS)
            self.gui.update_status(f"{status_message} - ĐANG MỞ KHÓA CỬA", 'lightgreen')

            # 🎨 MORE DETAILED SUCCESS MESSAGE
            detail_messages = {
                "face": f"🎉 XÁC THỰC KHUÔN MẶT THÀNH CÔNG!\n✅ Phương thức: Nhận diện AI\n👤 Danh tính: {identifier}\n📋 Chi tiết: {details}\n🔓 Đang mở khóa cửa...",
                "fingerprint": f"🎉 XÁC THỰC VÂN TAY THÀNH CÔNG!\n✅ Phương thức: Sinh trắc học\n👆 Vân tay: {identifier}\n📋 Chi tiết: {details}\n🔓 Đang mở khóa cửa...",
                "rfid": f"🎉 XÁC THỰC THẺ TỪ THÀNH CÔNG!\n✅ Phương thức: RFID/NFC\n📱 Thẻ: {identifier}\n📋 Chi tiết: {details}\n🔓 Đang mở khóa cửa...",
                "passcode": f"🎉 XÁC THỰC MẬT KHẨU THÀNH CÔNG!\n✅ Phương thức: Mã số PIN\n🔑 Trạng thái: {identifier}\n📋 Chi tiết: {details}\n🔓 Đang mở khóa cửa..."
            }

            detail_msg = detail_messages.get(method, f"🎉 XÁC THỰC THÀNH CÔNG!\n✅ Phương thức: {method_display}\n🆔 Định danh: {identifier}\n📋 Chi tiết: {details}\n🔓 Đang mở khóa cửa...")

            self.gui.update_detail(detail_msg, Colors.SUCCESS)

            self.buzzer.beep("success")

            # Enhanced Discord notification
            if self.discord_bot:
                discord_msg = f"⚡ **XÁC THỰC ĐƠN LẺ THÀNH CÔNG + VOICE**\n"
                discord_msg += f"✅ **Phương thức**: {method_display}\n"
                discord_msg += f"🆔 **Định danh**: {identifier}\n"
                discord_msg += f"📋 **Chi tiết**: {details}\n"
                discord_msg += f"🔊 **Voice**: Vietnamese specific announcements\n"
                discord_msg += f"🕐 **Thời gian**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                discord_msg += f"🔓 **Trạng thái**: Đang mở khóa cửa"

                threading.Thread(
                    target=self._send_discord_notification,
                    args=(discord_msg,),
                    daemon=True
                ).start()

            self._unlock_door()

        except Exception as e:
            logger.error(f"❌ Error in _any_mode_success: {e}")
            self.gui.update_detail(f"Lỗi xử lý thành công: {str(e)}", Colors.ERROR)
    def _face_recognition_loop(self):
        """Vòng lặp nhận diện khuôn mặt cho sequential mode + VOICE"""
        logger.info("🛡️ Bắt đầu vòng lặp nhận diện khuôn mặt - Sequential mode")
        consecutive_count = 0
        
        while self.running and self.auth_state.step == AuthStep.FACE:
            try:
                frame = self.picam2.capture_array()
                if frame is None:
                    continue
                
                annotated_frame, result = self.face_recognizer.process_frame(frame)
                self.root.after(0, lambda: self.gui.update_camera(annotated_frame, result))
                
                if result.recognized:
                    consecutive_count += 1
                    self.auth_state.consecutive_face_ok = consecutive_count
                    
                    progress = consecutive_count / self.config.FACE_REQUIRED_CONSECUTIVE * 100
                    msg = f"Đã xác nhận ({consecutive_count}/{self.config.FACE_REQUIRED_CONSECUTIVE}) - {progress:.0f}%"
                    
                    self.root.after(0, lambda: self.gui.update_step(1, "NHẬN DIỆN THÀNH CÔNG", msg, Colors.SUCCESS))
                    self.root.after(0, lambda: self.gui.update_detail(
                        f"Danh tính: {result.person_name}\nĐang xác minh... còn {self.config.FACE_REQUIRED_CONSECUTIVE - consecutive_count} lần\nĐộ chính xác: {result.confidence:.1f}/100", 
                        Colors.SUCCESS))
                    
                    if consecutive_count >= self.config.FACE_REQUIRED_CONSECUTIVE:
                        logger.info(f"✅ Sequential face success: {result.person_name}")
                        
                        # VOICE: Success announcement
                        if self.speaker:
                            self.speaker.speak("face_success", f"Xin chào {result.person_name}")
                        
                        self.buzzer.beep("success")
                        
                        # Discord success notification
                        if self.discord_bot:
                            threading.Thread(
                                target=self._send_discord_success,
                                args=("face", f"Nhận diện thành công: {result.person_name}"),
                                daemon=True
                            ).start()
                        
                        self.root.after(0, lambda: self.gui.update_status(f"✅ BƯỚC 1/4 HOÀN THÀNH: {result.person_name.upper()}!", 'lightgreen'))
                        self.root.after(1500, self._proceed_to_fingerprint)
                        break
                        
                elif result.detected:
                    consecutive_count = 0
                    self.auth_state.consecutive_face_ok = 0
                    self.root.after(0, lambda: self.gui.update_step(1, "PHÁT HIỆN KHUÔN MẶT", "Khuôn mặt chưa đăng ký", Colors.WARNING))
                    self.root.after(0, lambda: self.gui.update_detail(
                        f"Hệ thống phát hiện khuôn mặt nhưng chưa có trong cơ sở dữ liệu.\nĐộ chính xác phát hiện: {result.confidence:.1f}\nVui lòng đảm bảo bạn đã được đăng ký trong hệ thống.", 
                        Colors.WARNING))
                else:
                    consecutive_count = 0
                    self.auth_state.consecutive_face_ok = 0
                    self.root.after(0, lambda: self.gui.update_step(1, "ĐANG QUÉT", "Tìm kiếm khuôn mặt", Colors.PRIMARY))
                
                time.sleep(self.config.FACE_DETECTION_INTERVAL)
                
            except Exception as e:
                logger.error(f"❌ Sequential face loop error: {e}")
                self.root.after(0, lambda: self.gui.update_detail(f"Lỗi hệ thống: {str(e)}", Colors.ERROR))
                time.sleep(1)
    
    def _proceed_to_fingerprint(self):
        """Chuyển sang bước quét vân tay + VOICE"""
        logger.info("🛡️ Sequential mode: Chuyển sang xác thực vân tay")
        self.auth_state.step = AuthStep.FINGERPRINT
        self.auth_state.fingerprint_attempts = 0
        
        # VOICE: Announce fingerprint step
        if self.speaker:
            self.speaker.speak("step_fingerprint")
        
        self.gui.update_step(2, "QUÉT VÂN TAY", "Đặt ngón tay lên cảm biến", Colors.WARNING)
        self.gui.update_status("🛡️ BƯỚC 2/4: ĐANG CHỜ QUÉT VÂN TAY", 'yellow')
        self.gui.update_detail("Vui lòng đặt ngón tay đã đăng ký lên cảm biến sinh trắc học.\nCảm biến đã sẵn sàng để quét.\n🔊 Loa sẽ thông báo kết quả", Colors.WARNING)
        
        threading.Thread(target=self._fingerprint_loop, daemon=True).start()
    
    def _fingerprint_loop(self):
        """ENHANCED: Fingerprint loop cho sequential mode + VOICE"""
        while (self.auth_state.fingerprint_attempts < self.config.MAX_ATTEMPTS and 
            self.auth_state.step == AuthStep.FINGERPRINT):
            
            try:
                self.auth_state.fingerprint_attempts += 1
                attempt_msg = f"Lần thử {self.auth_state.fingerprint_attempts}/{self.config.MAX_ATTEMPTS}"
                
                self.root.after(0, lambda: self.gui.update_step(2, "QUÉT VÂN TAY", attempt_msg, Colors.WARNING))
                
                timeout = 10
                start_time = time.time()
                scan_success = False
                image_read_attempts = 0
                
                while time.time() - start_time < timeout:
                    try:
                        if self.fingerprint.readImage():
                            image_read_attempts += 1
                            
                            try:
                                self.fingerprint.convertImage(0x01)
                                result = self.fingerprint.searchTemplate()
                                
                                if result[0] != -1:
                                    # SUCCESS + VOICE
                                    logger.info(f"✅ Sequential fingerprint verified: ID {result[0]}")
                                    
                                    if self.speaker:
                                        self.speaker.speak("fingerprint_success")
                                    
                                    self.buzzer.beep("success")
                                    
                                    # Discord success notification
                                    if self.discord_bot:
                                        threading.Thread(
                                            target=self._send_discord_success,
                                            args=("fingerprint", f"Vân tay xác thực: ID {result[0]}"),
                                            daemon=True
                                        ).start()
                                    
                                    self.root.after(0, lambda: self.gui.update_status("✅ BƯỚC 2/4 HOÀN THÀNH: VÂN TAY ĐÃ XÁC THỰC!", 'lightgreen'))
                                    self.root.after(1500, self._proceed_to_rfid)
                                    return
                                else:
                                    # Template not found + VOICE
                                    logger.warning(f"❌ Sequential fingerprint not recognized: attempt {self.auth_state.fingerprint_attempts}")
                                    
                                    if self.speaker:
                                        self.speaker.speak("auth_failed", "Vân tay không nhận diện")
                                    
                                    details = f"Template not found | Sensor reading: {result[1]} | Sequential mode step 2"
                                    self._send_discord_failure_alert("fingerprint", self.auth_state.fingerprint_attempts, details)
                                    
                                    self.buzzer.beep("error")
                                    remaining = self.config.MAX_ATTEMPTS - self.auth_state.fingerprint_attempts
                                    if remaining > 0:
                                        self.root.after(0, lambda: self.gui.update_detail(
                                            f"Vân tay không được nhận diện!\nCòn {remaining} lần thử\nVui lòng thử lại với ngón tay đã đăng ký.", Colors.ERROR))
                                        time.sleep(2)
                                        scan_success = True
                                        break
                                    
                            except Exception as convert_error:
                                error_msg = str(convert_error)
                                
                                if "too few feature points" in error_msg.lower():
                                    logger.debug(f"Fingerprint quality issue (attempt {image_read_attempts}): {error_msg}")
                                    
                                    if image_read_attempts >= 3:
                                        logger.info(f"Skipping quality error after {image_read_attempts} attempts")
                                        continue
                                    
                                    if self.speaker:
                                        self.speaker.speak("", "Chất lượng vân tay chưa đủ tốt")
                                    
                                    self.root.after(0, lambda: self.gui.update_detail(
                                        f"Chất lượng vân tay chưa đủ tốt.\nVui lòng đặt ngón tay chắc chắn hơn.", Colors.WARNING))
                                    time.sleep(0.5)
                                    continue
                                else:
                                    logger.error(f"Real fingerprint error: {error_msg}")
                                    
                                    if self.speaker:
                                        self.speaker.speak("system_error", "Lỗi cảm biến vân tay")
                                    
                                    details = f"Hardware/processing error: {error_msg}"
                                    self._send_discord_failure_alert("fingerprint", self.auth_state.fingerprint_attempts, details)
                                    
                                    self.root.after(0, lambda: self.gui.update_detail(f"Lỗi cảm biến: {error_msg}", Colors.ERROR))
                                    time.sleep(1)
                                    break
                        
                        time.sleep(0.1)
                        
                    except Exception as read_error:
                        logger.error(f"Fingerprint read error: {read_error}")
                        break
                
                # Check timeout
                if time.time() - start_time >= timeout and not scan_success:
                    details = f"Sequential mode timeout - step 2 | Read attempts: {image_read_attempts}"
                    logger.warning(f"Sequential fingerprint timeout: attempt {self.auth_state.fingerprint_attempts}")
                    
                    # VOICE: Timeout announcement
                    if self.speaker:
                        self.speaker.speak("timeout", "Hết thời gian quét vân tay")
                    
                    self._send_discord_failure_alert("fingerprint", self.auth_state.fingerprint_attempts, details)
                    
                    remaining = self.config.MAX_ATTEMPTS - self.auth_state.fingerprint_attempts
                    if remaining > 0:
                        self.root.after(0, lambda: self.gui.update_detail(
                            f"Hết thời gian quét!\nCòn {remaining} lần thử\nVui lòng đặt ngón tay đúng cách lên cảm biến.", Colors.WARNING))
                        time.sleep(1)
                        
            except Exception as e:
                details = f"Sequential mode fingerprint error: {str(e)}"
                logger.error(f"❌ Sequential fingerprint general error: {e}")
                
                if self.speaker:
                    self.speaker.speak("system_error", "Lỗi hệ thống vân tay")
                
                self._send_discord_failure_alert("fingerprint", self.auth_state.fingerprint_attempts, details)
                
                self.root.after(0, lambda: self.gui.update_detail(f"Lỗi cảm biến: {str(e)}", Colors.ERROR))
                time.sleep(1)
        
        # Max attempts exceeded + VOICE
        if self.auth_state.fingerprint_attempts >= self.config.MAX_ATTEMPTS:
            details = f"Sequential mode - max fingerprint attempts exceeded at step 2"
            logger.critical(f"Sequential fingerprint max attempts: {self.auth_state.fingerprint_attempts}")
            
            if self.speaker:
                self.speaker.speak("max_attempts", "Hết lượt thử vân tay")
            
            self._send_discord_failure_alert("fingerprint", self.auth_state.fingerprint_attempts, details)
        
        logger.warning("Sequential fingerprint: Maximum attempts exceeded")
        self.root.after(0, lambda: self.gui.update_status("🛡️ BƯỚC 2/4 THẤT BẠI - KHỞI ĐỘNG LẠI XÁC THỰC", 'orange'))
        self.buzzer.beep("error")
        self.root.after(3000, self.start_authentication)
    
    def _proceed_to_rfid(self):
        """Chuyển sang bước quét thẻ RFID + VOICE"""
        logger.info("🛡️ Sequential mode: Chuyển sang xác thực thẻ RFID")
        self.auth_state.step = AuthStep.RFID
        self.auth_state.rfid_attempts = 0
        
        # VOICE: Announce RFID step
        if self.speaker:
            self.speaker.speak("step_rfid")
        
        self.gui.update_step(3, "QUÉT THẺ RFID", "Đưa thẻ lại gần đầu đọc", Colors.ACCENT)
        self.gui.update_status("🛡️ BƯỚC 3/4: ĐANG CHỜ THẺ RFID", 'lightblue')
        self.gui.update_detail("Vui lòng đưa thẻ RFID lại gần đầu đọc.\nĐầu đọc đang hoạt động và quét thẻ.\n🔊 Loa sẽ thông báo kết quả", Colors.ACCENT)
        
        threading.Thread(target=self._rfid_loop, daemon=True).start()
    
    def _rfid_loop(self):
        """Vòng lặp xác thực thẻ RFID cho sequential mode + VOICE"""
        while (self.auth_state.rfid_attempts < self.config.MAX_ATTEMPTS and 
            self.auth_state.step == AuthStep.RFID):
            
            try:
                self.auth_state.rfid_attempts += 1
                attempt_msg = f"Lần thử {self.auth_state.rfid_attempts}/{self.config.MAX_ATTEMPTS}"
                
                self.root.after(0, lambda: self.gui.update_step(3, "QUÉT THẺ TỪ", attempt_msg, Colors.ACCENT))
                self.root.after(0, lambda: self.gui.update_detail(
                    f"Đang quét thẻ từ... (Lần thử {self.auth_state.rfid_attempts}/{self.config.MAX_ATTEMPTS})\nGiữ thẻ trong khoảng 2-5cm từ đầu đọc.", 
                    Colors.ACCENT))
                
                uid = self.pn532.read_passive_target(timeout=8)
                
                if uid:
                    uid_list = list(uid)
                    logger.info(f"RFID detected in sequential mode: {uid_list}")
                    
                    # Check admin card
                    if uid_list == self.config.ADMIN_UID:
                        self.root.after(0, lambda: self._admin_authentication())
                        return
                    
                    # Check regular cards
                    valid_uids = self.admin_data.get_rfid_uids()
                    if uid_list in valid_uids:
                        # SUCCESS + VOICE
                        logger.info(f"✅ Sequential RFID verified: {uid_list}")
                        
                        if self.speaker:
                            self.speaker.speak("rfid_success")
                        
                        self.buzzer.beep("success")
                        
                        # Discord success notification
                        if self.discord_bot:
                            threading.Thread(
                                target=self._send_discord_success,
                                args=("rfid", f"Thẻ từ xác thực: {uid_list}"),
                                daemon=True
                            ).start()
                        
                        self.root.after(0, lambda: self.gui.update_status("✅ BƯỚC 3/4 HOÀN THÀNH: THẺ TỪ ĐÃ XÁC THỰC!", 'lightgreen'))
                        self.root.after(0, lambda: self.gui.update_detail(f"Xác thực thẻ từ thành công!\nMã thẻ: {uid_list}\nChuyển đến bước nhập mật khẩu cuối cùng.", Colors.SUCCESS))
                        self.root.after(1500, self._proceed_to_passcode)
                        return
                    else:
                        # Invalid card + VOICE
                        details = f"Sequential mode - invalid RFID | UID: {uid_list} | Step 3"
                        logger.warning(f"Sequential RFID invalid: {uid_list}")
                        
                        if self.speaker:
                            self.speaker.speak("auth_failed", "Thẻ từ không hợp lệ")
                        
                        self._send_discord_failure_alert("rfid", self.auth_state.rfid_attempts, details)
                        
                        self.buzzer.beep("error")
                        remaining = self.config.MAX_ATTEMPTS - self.auth_state.rfid_attempts
                        
                        error_msg = f"THẺ TỪ KHÔNG ĐƯỢC PHÉP!\nMã thẻ phát hiện: {uid_list}\nThẻ chưa được đăng ký trong hệ thống\n"
                        error_msg += f"Còn {remaining} lần thử" if remaining > 0 else "Hết lần thử"
                        
                        self.root.after(0, lambda: self.gui.update_detail(error_msg, Colors.ERROR))
                        
                        if remaining > 0:
                            time.sleep(3)
                        else:
                            break
                else:
                    # No card detected + VOICE
                    details = f"Sequential mode - no RFID detected | Step 3 | Timeout: 8s"
                    logger.warning(f"Sequential RFID timeout: attempt {self.auth_state.rfid_attempts}")
                    
                    if self.speaker:
                        self.speaker.speak("timeout", "Không phát hiện thẻ từ")
                    
                    self._send_discord_failure_alert("rfid", self.auth_state.rfid_attempts, details)
                    
                    remaining = self.config.MAX_ATTEMPTS - self.auth_state.rfid_attempts
                    
                    timeout_msg = f"KHÔNG PHÁT HIỆN THẺ!\nHết thời gian quét sau 8 giây\nVui lòng đưa thẻ gần đầu đọc hơn\n"
                    timeout_msg += f"Còn {remaining} lần thử" if remaining > 0 else "Hết lần thử"
                    
                    self.root.after(0, lambda: self.gui.update_detail(timeout_msg, Colors.WARNING))
                    
                    if remaining > 0:
                        time.sleep(2)
                    else:
                        break
                    
            except Exception as e:
                details = f"Sequential mode RFID hardware error: {str(e)}"
                logger.error(f"Sequential RFID error: {e}")
                
                if self.speaker:
                    self.speaker.speak("system_error", "Lỗi đầu đọc thẻ từ")
                
                self._send_discord_failure_alert("rfid", self.auth_state.rfid_attempts, details)
                
                self.root.after(0, lambda: self.gui.update_detail(f"LỖI ĐẦU ĐỌC THẺ TỪ!\n{str(e)}\nVui lòng kiểm tra kết nối phần cứng", Colors.ERROR))
                time.sleep(2)
        
        # Max attempts exceeded + VOICE
        if self.auth_state.rfid_attempts >= self.config.MAX_ATTEMPTS:
            details = f"Sequential mode - max RFID attempts exceeded at step 3"
            logger.critical(f"Sequential RFID max attempts: {self.auth_state.rfid_attempts}")
            
            if self.speaker:
                self.speaker.speak("max_attempts", "Hết lượt thử thẻ từ")
            
            self._send_discord_failure_alert("rfid", self.auth_state.rfid_attempts, details)
        
        logger.warning("Sequential RFID: Maximum attempts exceeded")
        self.root.after(0, lambda: self.gui.update_status("🛡️ BƯỚC 3/4 THẤT BẠI - KHỞI ĐỘNG LẠI XÁC THỰC", 'orange'))
        self.root.after(0, lambda: self.gui.update_detail(
            f"XÁC THỰC THẺ TỪ THẤT BẠI!\nĐã hết tất cả {self.config.MAX_ATTEMPTS} lần thử\nĐang khởi động lại toàn bộ quy trình xác thực...\nSự kiện bảo mật đã được ghi lại.", Colors.ERROR))
        self.buzzer.beep("error")
        self.root.after(4000, self.start_authentication)
    
    def _proceed_to_passcode(self):
        """Chuyển sang bước cuối - nhập mật khẩu + VOICE"""
        logger.info("🛡️ Sequential mode: Chuyển đến bước xác thực mật khẩu cuối cùng")
        self.auth_state.step = AuthStep.PASSCODE
        self.auth_state.pin_attempts = 0
        
        # VOICE: Announce final step
        if self.speaker:
            self.speaker.speak("step_passcode", "Bước cuối cùng, nhập mật khẩu")
        
        # Discord notification về bước cuối
        if self.discord_bot:
            threading.Thread(
                target=self._send_discord_notification,
                args=("🛡️ **BƯỚC XÁC THỰC CUỐI CÙNG + VOICE**\nĐang chuyển đến nhập mật khẩu\nNgười dùng đã vượt qua 3/4 lớp bảo mật sequential\n🔊 Voice guidance active",),
                daemon=True
            ).start()
        
        self.gui.update_step(4, "NHẬP MẬT KHẨU CUỐI", "Nhập mật khẩu hệ thống", Colors.SUCCESS)
        self.gui.update_status("🛡️ BƯỚC 4/4: NHẬP MẬT KHẨU CUỐI CÙNG", 'lightgreen')
        self.gui.update_detail(
            "BƯỚC XÁC THỰC CUỐI CÙNG - SEQUENTIAL MODE\n✅ Nhận diện khuôn mặt: THÀNH CÔNG\n✅ Quét vân tay: THÀNH CÔNG\n✅ Quét thẻ từ: THÀNH CÔNG\n🔄 Mật khẩu: ĐANG CHỜ NHẬP\n🔊 Loa sẽ hướng dẫn và thông báo", Colors.SUCCESS)
        
        self._request_passcode()

    def _request_passcode(self):
        """Nhập mật khẩu cho sequential mode + VOICE"""
        
        if self.auth_state.pin_attempts >= self.config.MAX_ATTEMPTS:
            details = f"Sequential mode - max passcode attempts exceeded at step 4"
            logger.critical(f"Sequential passcode max attempts: {self.auth_state.pin_attempts}")
            
            # VOICE: Max attempts
            if self.speaker:
                self.speaker.speak("max_attempts", "Hết lượt thử mật khẩu")
            
            self._send_discord_failure_alert("passcode", self.auth_state.pin_attempts, details)
            
            logger.warning("Sequential passcode: Maximum attempts exceeded")
            self.gui.update_status("🛡️ BƯỚC 4/4 THẤT BẠI - KHỞI ĐỘNG LẠI", 'orange')
            self.gui.update_detail(
                f"XÁC THỰC MẬT KHẨU THẤT BẠI!\nĐã hết tất cả {self.config.MAX_ATTEMPTS} lần thử\nNgười dùng đã vượt qua tất cả lớp bảo mật khác\nĐang khởi động lại toàn bộ quy trình...", Colors.ERROR)
            self.buzzer.beep("error")
            self.root.after(4000, self.start_authentication)
            return
        
        self.auth_state.pin_attempts += 1
        attempt_msg = f"Lần thử {self.auth_state.pin_attempts}/{self.config.MAX_ATTEMPTS}"
        
        self.gui.update_step(4, "NHẬP MẬT KHẨU", attempt_msg, Colors.SUCCESS)
        self.gui.update_detail(
            f"Nhập mật khẩu hệ thống... (Lần thử {self.auth_state.pin_attempts}/{self.config.MAX_ATTEMPTS})\n✅ Các bước trước đã hoàn thành thành công\n🎯 Sử dụng bàn phím số hoặc USB numpad\n🔊 Loa sẽ thông báo kết quả", Colors.SUCCESS)
        
        self.root.focus_force()
        self.root.update()
        
        dialog = EnhancedNumpadDialog(
            self.root, 
            "🛡️ XÁC THỰC CUỐI CÙNG - SEQUENTIAL",
            f"Nhập mật khẩu hệ thống (Lần thử {self.auth_state.pin_attempts}/{self.config.MAX_ATTEMPTS}):", 
            True, 
            self.buzzer,
            self.speaker
        )
        
        if hasattr(dialog, 'dialog'):
            dialog.dialog.focus_force()
            dialog.dialog.grab_set()
            dialog.dialog.lift()
        
        entered_pin = dialog.show()
        
        if entered_pin is None:
            logger.info("Sequential passcode cancelled by user")
            
            # VOICE: Cancel announcement
            if self.speaker:
                self.speaker.speak("", "Hủy nhập mật khẩu")
            
            self.gui.update_detail("❌ Việc nhập mật khẩu đã bị hủy\n🔄 Đang khởi động lại xác thực...", Colors.WARNING)
            self.buzzer.beep("click")
            self.root.after(2000, self.start_authentication)
            return
        
        correct_passcode = self.admin_data.get_passcode()
        
        if entered_pin == correct_passcode:
            # SUCCESS + VOICE
            logger.info("✅ Sequential passcode verified - ALL 4 LAYERS COMPLETED!")
            
            if self.speaker:
                self.speaker.speak("passcode_success")
                time.sleep(0.5)
                self.speaker.speak("auth_complete", "Hoàn thành xác thực tuần tự bốn lớp")
            
            self.gui.update_status("🛡️ XÁC THỰC 4 LỚP HOÀN TẤT! ĐANG MỞ KHÓA CỬA", 'lightgreen')
            self.gui.update_detail(
                "🎉 XÁC THỰC SEQUENTIAL THÀNH CÔNG!\n✅ Tất cả 4 lớp bảo mật đã được xác minh:\n  👤 Nhận diện khuôn mặt: THÀNH CÔNG\n  👆 Quét vân tay: THÀNH CÔNG\n  📱 Quét thẻ từ: THÀNH CÔNG\n  🔑 Mật khẩu: THÀNH CÔNG\n🔓 Đang mở khóa cửa...\n🔊 Loa đã thông báo hoàn tất", Colors.SUCCESS)
            self.buzzer.beep("success")
            
            # Discord success notification
            if self.discord_bot:
                threading.Thread(
                    target=self._send_discord_success,
                    args=("passcode", "Mật khẩu xác thực - Hoàn thành sequential mode with voice"),
                    daemon=True
                ).start()
                
                threading.Thread(
                    target=self._send_discord_notification,
                    args=("🛡️ **XÁC THỰC SEQUENTIAL + VOICE HOÀN TẤT** - Tất cả 4 lớp đã được xác minh thành công với voice guidance!",),
                    daemon=True
                ).start()
            
            self._unlock_door()
            
        else:
            # FAILURE + VOICE
            remaining = self.config.MAX_ATTEMPTS - self.auth_state.pin_attempts
            
            details = f"Sequential mode - incorrect passcode | Expected length: {len(correct_passcode)}, Got: {len(entered_pin)} | Step 4 final"
            logger.warning(f"Sequential passcode incorrect: attempt {self.auth_state.pin_attempts}")
            
            if self.speaker:
                self.speaker.speak("auth_failed", "Mật khẩu không đúng")
            
            self._send_discord_failure_alert("passcode", self.auth_state.pin_attempts, details)
            
            self.buzzer.beep("error")
            
            if remaining > 0:
                error_msg = f"MẬT KHẨU KHÔNG ĐÚNG!\n🔢 Mật khẩu không khớp với hồ sơ hệ thống\n🔄 Còn {remaining} lần thử\n⚠️ Vui lòng xác minh mật khẩu và thử lại\n🔊 Loa đã thông báo lỗi"
                
                self.gui.update_detail(error_msg, Colors.ERROR)
                self.root.after(2500, self._request_passcode)
            else:
                final_error_msg = f"🚫 XÁC THỰC MẬT KHẨU THẤT BẠI!\n❌ Đã hết tất cả {self.config.MAX_ATTEMPTS} lần thử\n⚠️ Người dùng đã hoàn thành 3/4 lớp bảo mật\n🔒 Khởi động lại toàn bộ quy trình xác thực\n📋 Sự kiện bảo mật đã được ghi lại\n🔊 Loa đã thông báo thất bại"
                
                self.gui.update_status("🛡️ MẬT KHẨU THẤT BẠI - KHỞI ĐỘNG LẠI XÁC THỰC", 'orange')
                self.gui.update_detail(final_error_msg, Colors.ERROR)
                self.root.after(4000, self.start_authentication)

    def _admin_authentication(self):
        """Xác thực quản trị nâng cao qua thẻ từ + VOICE"""
        # VOICE: Admin card detected
        if self.speaker:
            self.speaker.speak("", "Phát hiện thẻ quản trị")
        
        # Discord notification về việc truy cập admin
        if self.discord_bot:
            threading.Thread(
                target=self._send_discord_notification,
                args=("🔧 **PHÁT HIỆN THẺ QUẢN TRỊ + VOICE**\nThẻ quản trị đã được quét - yêu cầu xác thực mật khẩu\n🔊 Voice guidance active",),
                daemon=True
            ).start()
        
        # Stop all auth threads if in any mode
        if self.auth_state.is_any_mode():
            self._stop_all_auth_threads()
        
        self.root.focus_force()
        self.root.update()
        
        dialog = EnhancedNumpadDialog(
            self.root, 
            "🔧 TRUY CẬP QUẢN TRỊ VIA THẺ TỪ + LOA",
            "Đã phát hiện thẻ quản trị. Nhập mật khẩu quản trị:", 
            True, 
            self.buzzer,
            self.speaker
        )
        
        if hasattr(dialog, 'dialog'):
            dialog.dialog.focus_force()
            dialog.dialog.grab_set()
            dialog.dialog.lift()
        
        password = dialog.show()
        
        if password == self.config.ADMIN_PASS:
            # Admin auth success + VOICE
            if self.speaker:
                self.speaker.speak("admin_access", "Quyền truy cập quản trị được cấp phép")
            
            if self.discord_bot:
                threading.Thread(
                    target=self._send_discord_notification,
                    args=(f"✅ **CẤP QUYỀN TRUY CẬP QUẢN TRỊ + VOICE**\nQuản trị viên đã xác thực thành công qua thẻ từ + mật khẩu\nĐang mở bảng điều khiển quản trị với voice support\n🔊 Voice announcements active",),
                    daemon=True
                ).start()
            
            logger.info("✅ Admin authentication via RFID successful")
            self.gui.update_status("THẺ QUẢN TRỊ ĐÃ XÁC THỰC! ĐANG MỞ BẢNG ĐIỀU KHIỂN + LOA", 'lightgreen')
            self.gui.update_detail(
                "🔧 XÁC THỰC QUẢN TRỊ THÀNH CÔNG!\n✅ Thẻ từ quản trị đã được xác minh\n✅ Mật khẩu quản trị đã được xác minh\n🎛️ Đang mở bảng điều khiển với voice support\n🔊 Loa sẽ hướng dẫn trong admin panel", Colors.SUCCESS)
            self.buzzer.beep("success")
            self.admin_gui.show_admin_panel()
            
        elif password is not None:
            # Wrong admin password + VOICE
            if self.speaker:
                self.speaker.speak("admin_denied", "Từ chối truy cập quản trị")
            
            if self.discord_bot:
                threading.Thread(
                    target=self._send_discord_notification,
                    args=("❌ **TỪ CHỐI TRUY CẬP QUẢN TRỊ + VOICE**\nThẻ quản trị đúng nhưng mật khẩu sai\n⚠️ Có thể có hành vi truy cập trái phép\n🔊 Voice warning given",),
                    daemon=True
                ).start()
            
            logger.warning("❌ Admin card detected but wrong password")
            self.gui.update_status("MẬT KHẨU QUẢN TRỊ KHÔNG ĐÚNG", 'orange')
            self.gui.update_detail(
                "❌ TỪ CHỐI TRUY CẬP QUẢN TRỊ!\n✅ Thẻ từ quản trị đã được xác minh\n❌ Mật khẩu quản trị không đúng\n⚠️ Vi phạm bảo mật đã được ghi lại\n🔊 Loa đã cảnh báo từ chối truy cập", Colors.ERROR)
            self.buzzer.beep("error")
            time.sleep(3)
            self.start_authentication()
        else:
            # Admin cancelled + VOICE
            if self.speaker:
                self.speaker.speak("", "Hủy truy cập quản trị")
            
            if self.discord_bot:
                threading.Thread(
                    target=self._send_discord_notification,
                    args=("🔄 **HỦY TRUY CẬP QUẢN TRỊ + VOICE**\nQuản trị viên đã hủy việc nhập mật khẩu\nĐang quay về xác thực bình thường\n🔊 Voice guidance continues",),
                    daemon=True
                ).start()
            
            logger.info("Admin access cancelled")
            self.gui.update_detail("🔄 Truy cập quản trị đã bị hủy\nĐang quay về xác thực...", Colors.WARNING)
            self.start_authentication()
    
    # ==== ENHANCED HELPER METHODS WITH VOICE ====
    
    def _send_discord_failure_alert(self, step, attempts, details=""):
        """ENHANCED: Gửi Discord alert với voice context"""
        def send_alert():
            try:
                if self.discord_bot and self.discord_bot.bot:
                    mode_context = f"Auth Mode: {self.auth_state.auth_mode} | Voice: Active | "
                    enhanced_details = mode_context + details
                    
                    asyncio.run(
                        self.discord_bot.send_authentication_failure_alert(step, attempts, enhanced_details)
                    )
                    logger.info(f"✅ Discord failure alert sent: {step} (mode: {self.auth_state.auth_mode}) with voice context")
                else:
                    logger.warning("Discord bot not available")
            except Exception as e:
                logger.error(f"Discord alert error: {e}")
        
        threading.Thread(target=send_alert, daemon=True).start()

    def _send_discord_success(self, step, details=""):
        """Enhanced helper function để gửi Discord success notification với voice context"""
        def send_success():
            try:
                if self.discord_bot:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    loop.run_until_complete(
                        self.discord_bot.record_authentication_success(step)
                    )
                    
                    if details:
                        mode_info = f"Mode: {self.auth_state.auth_mode.upper()} + Voice"
                        success_message = f"✅ **{step.upper()} XÁC THỰC THÀNH CÔNG + VOICE**\n{details}\n🔧 {mode_info}\n🔊 Vietnamese voice announcements active"
                        loop.run_until_complete(
                            self.discord_bot.send_security_notification(success_message, "SUCCESS")
                        )
                    
                    loop.close()
                    logger.info(f"Discord success notification sent for {step} (mode: {self.auth_state.auth_mode}) with voice context")
                    
            except Exception as e:
                logger.error(f"Discord success notification error for {step}: {e}")
        
        threading.Thread(target=send_success, daemon=True).start()

    def _unlock_door(self):
        """Enhanced door unlock với voice announcements"""
        try:
            current_mode = self.auth_state.auth_mode
            logger.info(f"🔓 Đang mở khóa cửa - Mode: {current_mode} - Duration: {self.config.LOCK_OPEN_DURATION}s")
            
            # VOICE: Door opening announcement
            if self.speaker:
                self.speaker.speak("door_opening")
            
            # Enhanced Discord notification với voice info
            if self.discord_bot:
                if current_mode == "sequential":
                    unlock_message = f"🛡️ **CỬA ĐÃ MỞ KHÓA - SEQUENTIAL MODE + VOICE**\n"
                    unlock_message += f"🎉 Hoàn thành xác thực 4 lớp tuần tự:\n"
                    unlock_message += f"  ✅ Nhận diện khuôn mặt: THÀNH CÔNG\n"
                    unlock_message += f"  ✅ Quét vân tay: THÀNH CÔNG\n"
                    unlock_message += f"  ✅ Quét thẻ từ: THÀNH CÔNG\n"
                    unlock_message += f"  ✅ Mật khẩu: THÀNH CÔNG\n\n"
                    unlock_message += f"🛡️ Độ bảo mật: CAO NHẤT (4 lớp)\n"
                else:
                    unlock_message = f"⚡ **CỬA ĐÃ MỞ KHÓA - ANY MODE + VOICE**\n"
                    unlock_message += f"🎯 Xác thực đơn lẻ thành công:\n"
                    for success in self.auth_state.any_mode_successes:
                        method_name = {
                            "face": "👤 Khuôn mặt",
                            "fingerprint": "👆 Vân tay", 
                            "rfid": "📱 Thẻ từ",
                            "passcode": "🔑 Mật khẩu"
                        }.get(success["method"], success["method"])
                        unlock_message += f"  ✅ {method_name}: {success['identifier']}\n"
                    unlock_message += f"\n⚡ Độ bảo mật: TRUNG BÌNH (1 lớp)\n"
                
                unlock_message += f"🔊 Voice: Vietnamese announcements provided\n"
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
            self.relay.off()
            self.buzzer.beep("success")
            
            # VOICE: Door opened announcement
            if self.speaker:
                time.sleep(1)
                self.speaker.speak("door_opened")
            
            # Đếm ngược với voice announcements
            for i in range(self.config.LOCK_OPEN_DURATION, 0, -1):
                self.root.after((self.config.LOCK_OPEN_DURATION - i) * 1000, 
                            lambda t=i: self.gui.update_detail(
                                f"🔓 CỬA ĐANG MỞ\n⏰ Tự động khóa sau {t} giây\n🚶 Vui lòng vào và đóng cửa\n🔧 Chế độ: {current_mode.upper()}\n🔊 Loa đã thông báo mở cửa\n🛡️ Tất cả hệ thống hoạt động bình thường", Colors.SUCCESS))
                self.root.after((self.config.LOCK_OPEN_DURATION - i) * 1000,
                            lambda t=i: self.gui.update_status(f"CỬA MỞ - KHÓA SAU {t} GIÂY", 'lightgreen'))
                
                # Voice countdown cho 3 giây cuối
                if i <= 3:
                    self.root.after((self.config.LOCK_OPEN_DURATION - i) * 1000,
                                lambda: self.buzzer.beep("click"))
                    if self.speaker and i == 1:
                        self.root.after((self.config.LOCK_OPEN_DURATION - i) * 1000,
                                    lambda: self.speaker.speak("", "Cửa sắp khóa"))
            
            self.root.after(self.config.LOCK_OPEN_DURATION * 1000, self._lock_door)
            
        except Exception as e:
            logger.error(f"❌ Lỗi mở khóa cửa: {e}")
            
            # VOICE: Error announcement
            if self.speaker:
                self.speaker.speak("system_error", "Lỗi mở khóa cửa")
            
            # Enhanced error notification
            if self.discord_bot:
                error_message = f"❌ **LỖI MỞ KHÓA CỬA + VOICE**\n"
                error_message += f"🔧 Mode: {self.auth_state.auth_mode}\n"
                error_message += f"💥 Lỗi: {str(e)}\n"
                error_message += f"🔊 Voice: Error announced\n"
                error_message += f"⚠️ Có thể cần can thiệp thủ công"
                threading.Thread(
                    target=self._send_discord_notification,
                    args=(error_message,),
                    daemon=True
                ).start()
            
            self.gui.update_detail(f"🔧 LỖI MỞ KHÓA CỬA!\n{str(e)}\nVui lòng kiểm tra phần cứng", Colors.ERROR)
            self.buzzer.beep("error")

    def _lock_door(self):
        """Enhanced door lock với INTELLIGENT voice"""
        try:
            current_mode = self.auth_state.auth_mode
            logger.info(f"🔒 Đang khóa cửa và đặt lại hệ thống - Mode: {current_mode}")
            
            # Khóa cửa
            self.relay.on()
            
            # 🧠 INTELLIGENT VOICE: Only announce door locked, don't repeat mode
            if hasattr(self, 'speaker') and self.speaker:
                self.speaker.speak("door_locked")
            
            # Enhanced Discord notification
            if self.discord_bot:
                lock_message = f"🔒 **CỬA ĐÃ TỰ ĐỘNG KHÓA + INTELLIGENT VOICE**\n"
                lock_message += f"✅ Cửa đã được bảo mật sau {self.config.LOCK_OPEN_DURATION} giây\n"
                lock_message += f"🔧 Mode được sử dụng: {current_mode.upper()}\n"
                lock_message += f"🔊 Voice: Intelligent announcements\n"
                lock_message += f"🔄 Hệ thống sẵn sàng cho người dùng tiếp theo\n"
                lock_message += f"📅 Thời gian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                
                threading.Thread(
                    target=self._send_discord_notification,
                    args=(lock_message,),
                    daemon=True
                ).start()
            
            self.gui.update_status("CỬA ĐÃ KHÓA - SẴN SÀNG CHO NGƯỜI DÙNG TIẾP THEO", 'white')
            self.gui.update_detail(
                f"🔒 CỬA ĐÃ TỰ ĐỘNG KHÓA\n✅ Hệ thống bảo mật đã đặt lại\n🔧 Chế độ hiện tại: {current_mode.upper()}\n🔄 Sẵn sàng cho chu kỳ xác thực tiếp theo\n🛡️ Tất cả sensors đã sẵn sàng", Colors.SUCCESS)
            self.buzzer.beep("click")
            
            # Reset detection stats và auth state
            self.gui.detection_stats = {"total": 0, "recognized": 0}
            self.auth_state.reset()
            
            # Stop any remaining threads for any mode
            if current_mode == "any":
                self._stop_all_auth_threads()
            
            # 🧠 INTELLIGENT VOICE: DON'T announce system ready again after door lock
            # The system is just resetting, not truly starting new session
            
            # Bắt đầu chu kỳ xác thực mới NHƯNG KHÔNG RESET SESSION ANNOUNCEMENTS
            self.root.after(3000, self.start_authentication)
            
        except Exception as e:
            logger.error(f"❌ Lỗi khóa cửa: {e}")
            
            if hasattr(self, 'speaker') and self.speaker:
                self.speaker.speak("system_error", "Lỗi nghiêm trọng khóa cửa")
            
            # Enhanced critical error notification
            if self.discord_bot:
                critical_message = f"🚨 **NGHIÊM TRỌNG: LỖI KHÓA CỬA + INTELLIGENT VOICE**\n"
                critical_message += f"❌ Không thể khóa cửa: {str(e)}\n"
                critical_message += f"🔧 Mode đang chạy: {self.auth_state.auth_mode}\n"
                critical_message += f"⚠️ CẦN CAN THIỆP THỦ CÔNG NGAY LẬP TỨC"
                
                threading.Thread(
                    target=self._send_discord_notification,
                    args=(critical_message,),
                    daemon=True
                ).start()
            
            self.gui.update_detail(f"🚨 NGHIÊM TRỌNG: LỖI KHÓA CỬA!\n{str(e)}\n⚠️ Cần can thiệp thủ công", Colors.ERROR)
            self.buzzer.beep("error")

    def reset_voice_session(self):
        """🧠 RESET: Reset voice session khi thật sự cần (ví dụ: thay đổi mode)"""
        if hasattr(self, 'speaker') and self.speaker:
            self.speaker.reset_session_announcements()
            logger.info("🔄 Voice session reset - will announce mode changes again")
    
    def run(self):
        """Chạy hệ thống chính với Vietnamese Speaker integration"""
        try:
            logger.info("🚀 Đang khởi động Hệ thống Khóa Cửa Thông minh v2.4.0 + Vietnamese Speaker")

            # VOICE: System startup announcement
            if self.speaker:
                self.speaker.speak("system_start")

            if self.discord_bot:
                logger.info("Đang khởi động Discord bot...")
                if self.discord_bot.start_bot():
                    logger.info("✅ Discord bot đã khởi động thành công!")
                else:
                    logger.warning("⚠️ Không thể khởi động Discord bot")

            # Enhanced startup effects với voice
            current_mode = self.admin_data.get_authentication_mode()
            mode_display = self.admin_data.get_mode_display_name()
            
            # Update speaker status in GUI
            if self.speaker:
                self.gui.update_speaker_status(self.speaker.enabled, "Google TTS")
            else:
                self.gui.update_speaker_status(False)
            
            self.gui.update_status("HỆ THỐNG KHÓA CỬA THÔNG MINH v2.4.0 + LOA - SẴN SÀNG!", 'lightgreen')
            self.gui.update_detail(f"Hệ thống nhận diện đã tải và sẵn sàng\n🔧 Chế độ xác thực: {mode_display}\n🔊 Loa tiếng Việt: {'BẬT' if self.speaker and self.speaker.enabled else 'TẮT'}\n🛡️ Hệ thống bảo mật đa lớp đang hoạt động\n🎵 Voice announcements ready", Colors.SUCCESS)
            
            self.buzzer.beep("startup")
            
            # Enhanced system info với speaker details
            face_info = self.face_recognizer.get_database_info()
            speaker_info = "Google TTS Vietnamese" if (self.speaker and self.speaker.enabled) else "Buzzer Only"
            
            self.gui.update_detail(f"Trạng thái hệ thống v2.4.0 + Voice:\n👤 Khuôn mặt đã đăng ký: {face_info['total_people']}\n👆 Vân tay: {len(self.admin_data.get_fingerprint_ids())}\n📱 Thẻ từ: {len(self.admin_data.get_rfid_uids())}\n🔧 Chế độ: {mode_display}\n🔊 Audio: {speaker_info}\n🎯 Phiên bản: v2.4.0", Colors.PRIMARY)
            
            # Enhanced Discord startup notification với voice info
            if self.discord_bot:
                startup_msg = f"🚀 **HỆ THỐNG KHÓA CỬA v2.4.0 + VIETNAMESE SPEAKER ĐÃ KHỞI ĐỘNG**\n"
                startup_msg += f"🔧 **Chế độ xác thực**: {mode_display}\n"
                startup_msg += f"👤 **Khuôn mặt**: {face_info['total_people']} người\n"
                startup_msg += f"👆 **Vân tay**: {len(self.admin_data.get_fingerprint_ids())} mẫu\n"
                startup_msg += f"📱 **Thẻ từ**: {len(self.admin_data.get_rfid_uids())} thẻ\n"
                startup_msg += f"🔊 **Vietnamese Speaker**: {'✅ Active (Google TTS)' if (self.speaker and self.speaker.enabled) else '❌ Disabled'}\n"
                startup_msg += f"🕐 **Thời gian**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                startup_msg += f"🛡️ **Trạng thái**: Sẵn sàng hoạt động với voice guidance\n"
                startup_msg += f"🎵 **Audio Features**: Natural Vietnamese announcements for all actions"
                
                threading.Thread(
                    target=self._send_discord_notification,
                    args=(startup_msg,),
                    daemon=True
                ).start()
            
            # VOICE: System ready announcement
            if self.speaker:
                time.sleep(2)
                self.speaker.speak("system_ready")
            
            # Bắt đầu xác thực sau 3 giây
            self.root.after(3000, self.start_authentication)
            
            # Setup cleanup
            self.root.protocol("WM_DELETE_WINDOW", self.cleanup)
            
            # Enhanced log
            logger.info(f"✅ Main loop starting - Mode: {current_mode} + Voice: {'Active' if (self.speaker and self.speaker.enabled) else 'Inactive'}")
            
            # Bắt đầu main loop
            self.root.mainloop()
            
        except KeyboardInterrupt:
            logger.info("Hệ thống dừng theo yêu cầu người dùng")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Enhanced cleanup với Vietnamese Speaker support"""
        logger.info("🧹 Đang dọn dẹp tài nguyên hệ thống v2.4.0 + Speaker...")
        self.running = False
        
        try:
            # VOICE: Shutdown announcement
            if hasattr(self, 'speaker') and self.speaker:
                try:
                    self.speaker.speak("system_shutdown")
                    time.sleep(1.5)
                except:
                    pass
            
            # Stop all auth threads
            if hasattr(self, 'auth_state') and self.auth_state.is_any_mode():
                self._stop_all_auth_threads()
            
            # CLEANUP DISCORD BOT
            if hasattr(self, 'discord_bot') and self.discord_bot:
                if self.discord_bot.bot:
                    shutdown_msg = f"🔴 **HỆ THỐNG v2.4.0 + VOICE ĐANG TẮT**\n"
                    shutdown_msg += f"🕐 Thời gian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    shutdown_msg += f"🔧 Chế độ cuối: {getattr(self.auth_state, 'auth_mode', 'unknown')}\n"
                    shutdown_msg += f"🔊 Voice: {'Active' if (hasattr(self, 'speaker') and self.speaker and self.speaker.enabled) else 'Inactive'}\n"
                    shutdown_msg += f"📊 Phiên làm việc: Kết thúc với voice support\n"
                    shutdown_msg += f"🔒 Trạng thái cửa: Đã khóa an toàn"
                    
                    try:
                        threading.Thread(
                            target=self._send_discord_notification,
                            args=(shutdown_msg,),
                            daemon=True
                        ).start()
                        time.sleep(1)
                    except:
                        pass
                
                self.discord_bot.stop_bot()
                logger.info("Discord bot đã dừng")
            
            # CLEANUP VIETNAMESE SPEAKER
            if hasattr(self, 'speaker') and self.speaker:
                try:
                    self.speaker.cleanup()
                    logger.info("Vietnamese Speaker đã dừng")
                except Exception as e:
                    logger.error(f"Lỗi cleanup speaker: {e}")
            
            if hasattr(self, 'picam2'):
                self.picam2.stop()
                logger.info("Camera đã dừng")
                
            if hasattr(self, 'relay'):
                self.relay.on()
                logger.info("Cửa đã khóa")
                
            if hasattr(self, 'buzzer') and hasattr(self.buzzer, 'buzzer') and self.buzzer.buzzer:
                self.buzzer.buzzer.off()
                logger.info("Buzzer đã dừng")
                
        except Exception as e:
            logger.error(f"❌ Lỗi cleanup: {e}")
        
        if hasattr(self, 'root'):
            self.root.quit()
        
        logger.info("✅ Cleanup hoàn tất - Vietnamese Speaker system shutdown complete")

# ==== MAIN EXECUTION WITH VOICE INTEGRATION ====
if __name__ == "__main__":
    try:
        print("=" * 100)
        print("HỆ THỐNG KHÓA CỬA THÔNG MINH 4 LỚP BẢO MẬT v2.4.0 + VIETNAMESE SPEAKER")
        print("   👤 Tác giả: Khoi - Luận án tốt nghiệp")
        print("   📅 Ngày cập nhật: 2025-07-06 06:01:40 UTC")
        print("   🧑‍💻 Cập nhật bởi: KHOI1235567")
        print("   🔊 Nâng cấp: Tích hợp loa tiếng Việt thật, voice thay thế buzzer")
        print("=" * 100)
        print()
        print("🔊 VIETNAMESE SPEAKER INTEGRATION HOÀN THÀNH:")
        print("   ✓ PHẦN 1: vietnamese_speaker.py - Google TTS engine")
        print("   ✓ PHẦN 2: enhanced_components.py - Admin Option 7 + Voice support")
        print("   ✓ PHẦN 3: KETHOP2_AI_ENHANCED.py - Full system integration")
        print("   ✓ Voice announcements for all authentication steps")
        print("   ✓ Voice feedback in admin panel và dialogs")
        print("   ✓ Voice replaces buzzer patterns seamlessly")
        print("   ✓ Backward compatibility 100% maintained")
        print("   ✓ Thread-safe voice operations")
        print()
        print("🔧 TECHNICAL ENHANCEMENTS:")
        print("   ✓ Google TTS Vietnamese voice engine")
        print("   ✓ Pygame audio system với MP3 support")
        print("   ✓ Enhanced buzzer manager với speaker integration")
        print("   ✓ Voice-enabled dialogs (numpad, message boxes)")
        print("   ✓ Admin panel Option 7: Speaker settings")
        print("   ✓ Real-time speaker status display")
        print("   ✓ Enhanced Discord notifications với voice context")
        print("   ✓ Voice announcements cho all system events")
        print()
        print("4 LỚP BẢO MẬT (Sequential Mode) + VOICE:")
        print("   1. 👤 Nhận diện khuôn mặt (Camera AI) + Voice guidance")
        print("   2. 👆 Sinh trắc học vân tay (AS608) + Voice feedback")
        print("   3. 📱 Thẻ từ/NFC (PN532) + Voice confirmations")
        print("   4. 🔑 Mật khẩu số (Numpad) + Voice prompts")
        print()
        print("⚡ XÁC THỰC ĐƠN LẺ (Any Mode) + VOICE:")
        print("   • Bất kỳ 1 trong 4 phương thức thành công → Mở khóa ngay")
        print("   • Tất cả sensors hoạt động đồng thời")
        print("   • Voice guidance cho từng phương thức")
        print("   • Real-time voice announcements")
        print()
        print("ĐIỀU KHIỂN NÂNG CAO + VOICE:")
        print("   * hoặc KP_* = Chế độ quản trị (voice guided)")
        print("   # hoặc KP_+ = Bắt đầu xác thực (voice announced)")
        print("   # (trong Any mode) = Nhập mật khẩu nhanh (voice prompted)")
        print("   ESC = Thoát hệ thống (voice confirmed)")
        print("   F11 = Chuyển đổi toàn màn hình")
        print("   Admin Option 7 = Cài đặt loa tiếng Việt")
        print()
        print("🔊 VOICE FEATURES:")
        print("   🎵 Natural Vietnamese voice using Google TTS")
        print("   📢 All authentication steps announced")
        print("   🔔 Success/failure messages spoken")
        print("   🎯 Admin actions với voice feedback")
        print("   🚪 Door operations announced")
        print("   ⚠️ Error messages và warnings")
        print("   🔄 System status updates")
        print("   🎛️ Mode changes announced")
        print()
        print("KIỂM TRA PHẦN CỨNG + AUDIO:")
        
        hardware_components = [
            ("CAM", "Camera Raspberry Pi Module 2"),
            ("VT", "Cảm biến vân tay AS608 (USB/UART)"),
            ("THẺ", "Đầu đọc thẻ từ PN532 (I2C)"),
            ("KHÓA", "Khóa điện từ + Relay 4 kênh"),
            ("BUZZER", "Buzzer nâng cao (GPIO PWM)"),
            ("PHÍM", "Bàn phím số USB"),
            ("🔊 LOA", "Loa/Audio Output (USB/3.5mm) - NEW"),
            ("🎵 TTS", "Google Text-to-Speech engine - NEW"),
            ("GUI", "Enhanced interface v2.4.0 - Voice integrated"),
            ("AI", "Database khuôn mặt + authentication mode + voice")
        ]
        
        for prefix, component in hardware_components:
            print(f"   {prefix}: {component}")
            time.sleep(0.15)
        
        print()
        print("📦 SOFTWARE DEPENDENCIES + VOICE:")
        dependencies = [
            "gtts (Google Text-to-Speech)",
            "pygame (Audio playback)",
            "mpg123 (Audio player fallback)",
            "espeak/espeak-ng (TTS fallback)",
            "opencv-python (Computer vision)",
            "picamera2 (Camera interface)",
            "gpiozero (GPIO control)",
            "pyfingerprint (Fingerprint sensor)",
            "adafruit-circuitpython-pn532 (RFID)",
            "tkinter (GUI framework)",
            "discord.py (Discord integration)",
            "python-dotenv (Environment variables)"
        ]
        
        for dep in dependencies:
            print(f"   📦 {dep}")
            time.sleep(0.1)
        
        print()
        print("ĐANG KHỞI TẠO HỆ THỐNG v2.4.0 + VIETNAMESE SPEAKER ...")
        print("=" * 100)
        
        # Khởi tạo và chạy hệ thống
        system = VietnameseSecuritySystem()
        
        print()
        print("✅ TẤT CẢ THÀNH PHẦN ĐÃ SẴN SÀNG!")
        print("✅ Enhanced GUI interface loaded!")
        print("✅ Kết nối phần cứng thành công!")
        print("✅ Mô hình AI và cấu hình mode đã được tải!")
        print("✅ Discord integration active!")
        print("✅ Vietnamese optimization complete!")
        print("🔊 VIETNAMESE SPEAKER READY!")
        print("🎵 Google TTS Vietnamese voice active!")
        print("🔧 Admin Option 7: Speaker settings available!")
        print("🎯 Voice announcements for all system actions!")
        print("=" * 100)
        print("🚀 HỆ THỐNG v2.4.0 + LOA TIẾNG VIỆT SẴN SÀNG! BẮT ĐẦU SỬ DỤNG...")
        print("=" * 100)
        
        system.run()
        
    except Exception as e:
        print()
        print("=" * 100)
        print(f"❌ LỖI KHỞI ĐỘNG NGHIÊM TRỌNG v2.4.0 + VOICE: {e}")
        print()
        print("DANH SÁCH KIỂM TRA KHẮC PHỤC + VOICE:")
        
        troubleshooting_items = [
            ("HW", "Kiểm tra kết nối phần cứng và nguồn điện"),
            ("MODEL", "Đảm bảo các file mô hình AI tồn tại trong thư mục models/"),
            ("DATA", "Kiểm tra quyền truy cập thư mục face_data/ và admin_data.json"),
            ("CAM", "Xác minh camera module được kết nối đúng"),
            ("VT", "Cảm biến vân tay AS608 trên cổng USB/UART"),
            ("THẺ", "Đầu đọc PN532 trên I2C (SCL/SDA)"),
            ("KHÓA", "Relay module và khóa điện từ"),
            ("BUZZER", "Buzzer PWM trên GPIO 17"),
            ("🔊 AUDIO", "USB/3.5mm audio output for speaker - NEW"),
            ("🎵 TTS", "Google TTS dependencies: gtts, pygame - NEW"),
            ("NET", "Kết nối mạng cho Discord integration và Google TTS"),
            ("MODE", "Cấu hình authentication mode trong admin_data.json"),
            ("GUI", "Tkinter và PIL dependencies cho enhanced interface"),
            ("PERM", "Quyền sudo cho GPIO và hardware access"),
            ("LIB", "Thư viện Python: opencv, picamera2, gpiozero, pyfingerprint..."),
            ("🔊 VOICE", "Audio system configuration và speaker test - NEW")
        ]
        
        for prefix, item in troubleshooting_items:
            print(f"   [{prefix}] {item}")
        
        print()
        print("🔧 HƯỚNG DẪN KHẮC PHỤC + VOICE:")
        print("   1. Chạy: sudo python3 -m pip install gtts pygame")
        print("   2. Test speaker: python3 vietnamese_speaker.py")
        print("   3. Kiểm tra: sudo raspi-config → Interface Options → Enable I2C, SPI, Camera")
        print("   4. Audio: sudo raspi-config → Advanced Options → Audio → Force 3.5mm")
        print("   5. Phần cứng: Đảm bảo tất cả module được kết nối đúng và có nguồn")
        print("   6. Quyền: Chạy với sudo hoặc thêm user vào group gpio, i2c, audio")
        print("   7. Cấu hình: Kiểm tra file admin_data.json có authentication_mode")
        print("   8. GUI: Verify tkinter và PIL dependencies")
        print("   9. Voice: Test audio output với 'speaker-test -t wav'")
        print("   10. TTS: Test Google TTS với internet connection")
        print()
        print("📞 HỖ TRỢ + VOICE:")
        print("   📧 Email: support@khoisecurity.local")
        print("   💬 Discord: Check system logs và Discord bot status")
        print("   📝 Logs: /home/khoi/Desktop/KHOI_LUANAN/system.log")
        print("   🐛 Debug: Chạy với logging.DEBUG để xem chi tiết")
        print("   🎨 GUI: Enhanced interface v2.4.0 troubleshooting")
        print("   🔊 Voice: Vietnamese speaker troubleshooting guide")
        print()
        print("🔄 THỬ LẠI:")
        print("   • Khởi động lại Raspberry Pi")
        print("   • Chạy: sudo systemctl restart khoi-security")
        print("   • Hoặc: python3 KETHOP2_AI_ENHANCED.py (manual)")
        print("   • Test GUI: python3 -c \"import tkinter; tkinter.Tk().mainloop()\"")
        print("   • Test Voice: python3 vietnamese_speaker.py")
        print("   • Test Audio: speaker-test -t wav -c 2")
        print()
        
        import traceback
        print("STACK TRACE CHI TIẾT:")
        print("-" * 80)
        traceback.print_exc()
        print("-" * 80)
        
        print()
        print("❌ HỆ THỐNG v2.4.0 + VOICE KHÔNG THỂ KHỞI ĐỘNG!")
        print("⚠️ Vui lòng kiểm tra và khắc phục các lỗi trên trước khi thử lại.")
        print("🎨 Enhanced GUI interface có thể cần dependencies bổ sung.")
        print("🔊 Vietnamese Speaker cần gtts và pygame packages.")
        print("=" * 100)
        
        # Enhanced error logging với voice context
        logger.error(f"💥 CRITICAL SYSTEM STARTUP FAILURE v2.4.0 + VOICE: {e}")
        logger.error("🔧 Enhanced GUI + Vietnamese Speaker system failed to initialize")
        logger.error(f"📅 Failure timestamp: 2025-07-06 06:01:40 UTC")
        logger.error(f"👤 User context: KHOI1235567")
        logger.error("📊 Error context: Enhanced GUI dual authentication mode + voice system")
        logger.error("🔊 Voice context: Vietnamese Speaker integration failure")
        
        # Try to send Discord error notification if possible
        try:
            if 'system' in locals() and hasattr(system, 'discord_bot') and system.discord_bot:
                error_msg = f"💥 **CRITICAL SYSTEM FAILURE v2.4.0 + VOICE**\n"
                error_msg += f"❌ **Error**: {str(e)}\n"
                error_msg += f"🕐 **Time**: 2025-07-06 06:01:40 UTC\n"
                error_msg += f"👤 **User**: KHOI1235567\n"
                error_msg += f"🔧 **Context**: Enhanced GUI dual auth mode + Vietnamese Speaker\n"
                error_msg += f"🎨 **GUI**: v2.4.0 interface initialization failure\n"
                error_msg += f"🔊 **Voice**: Vietnamese Speaker integration failure\n"
                error_msg += f"⚠️ **Status**: System offline - manual intervention required"
                
                # Try emergency Discord notification
                import asyncio
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(
                        system.discord_bot.send_security_notification(error_msg, "CRITICAL")
                    )
                    loop.close()
                    print("📱 Emergency Discord notification sent")
                except:
                    print("📱 Could not send Discord emergency notification")
        except:
            pass
        
        exit(1)
    
    except KeyboardInterrupt:
        print()
        print("=" * 100)
        print("🛑 HỆ THỐNG v2.4.0 + VOICE DỪNG THEO YÊU CẦU NGƯỜI DÙNG")
        print("📅 Thời gian dừng: 2025-07-06 06:01:40 UTC")
        print("👤 Người dùng: KHOI1235567")
        print("🔧 Trạng thái: Tắt an toàn - Enhanced GUI + Vietnamese Speaker")
        print("=" * 100)
        
        # Graceful shutdown logging với voice context
        logger.info("🛑 User requested system shutdown via KeyboardInterrupt")
        logger.info("✅ Enhanced GUI + Vietnamese Speaker graceful shutdown sequence initiated")
        
        # Try to send shutdown notification
        try:
            if 'system' in locals() and hasattr(system, 'discord_bot') and system.discord_bot:
                shutdown_msg = f"🛑 **HỆ THỐNG DỪNG AN TOÀN v2.4.0 + VOICE**\n"
                shutdown_msg += f"👤 **Người dùng**: KHOI1235567\n"
                shutdown_msg += f"🕐 **Thời gian**: 2025-07-06 06:01:40 UTC\n"
                shutdown_msg += f"🔧 **Lý do**: Manual shutdown (Ctrl+C)\n"
                shutdown_msg += f"🎨 **GUI**: Enhanced interface v2.4.0\n"
                shutdown_msg += f"🔊 **Voice**: Vietnamese Speaker integrated\n"
                shutdown_msg += f"✅ **Trạng thái**: Clean shutdown - Không mất dữ liệu"
                
                import asyncio
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(
                        system.discord_bot.send_security_notification(shutdown_msg, "INFO")
                    )
                    loop.close()
                    print("📱 Shutdown notification sent to Discord")
                except:
                    pass
        except:
            pass
        
        print("✅ Tắt hệ thống enhanced GUI + Vietnamese Speaker hoàn tất an toàn!")
        exit(0)
    
    finally:
        # Final cleanup regardless of how program exits
        try:
            if 'system' in locals():
                print("🧹 Thực hiện cleanup cuối cùng enhanced GUI + Voice...")
                system.cleanup()
                print("✅ Enhanced GUI + Vietnamese Speaker cleanup hoàn tất")
        except:
            pass
        
        print()
        print("=" * 100)
        print("🏁 HỆ THỐNG KHÓA CỬA THÔNG MINH v2.4.0 + VIETNAMESE SPEAKER - KẾT THÚC")
        print("   📅 Kết thúc: 2025-07-06 06:01:40 UTC")
        print("   👤 Session user: KHOI1235567")
        print("   🔧 Version: Enhanced GUI Dual Authentication Mode + Vietnamese Speaker")
        print("   🎨 Interface: Vietnamese Optimized v2.4.0")
        print("   🔊 Audio: Google TTS Vietnamese Voice Integration")
        print("   📊 Status: Program terminated với voice support")
        print("=" * 100)
        print("🙏 Cảm ơn bạn đã sử dụng hệ thống bảo mật Enhanced GUI + Voice của Khoi!")
        print("📧 Phản hồi và góp ý: support@khoisecurity.local")
        print("🎓 Luận án tốt nghiệp - Đại học Công nghệ Thông tin")
        print("🎨 Enhanced GUI Interface - Optimized for Vietnamese users")
        print("🔊 Vietnamese Speaker - Natural voice announcements")
        print("🎵 Google TTS Integration - Real Vietnamese voice experience")
        print("=" * 100)
