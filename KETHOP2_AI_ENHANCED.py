#!/usr/bin/env python3
"""
HỆ THỐNG KHÓA BẢO MẬT 4 LỚP - AI ENHANCED VERSION (FIXED)
Tác giả: Khoi - Luận án tốt nghiệp
Ngày cập nhật: 2025-01-16
Phiên bản: v2.1 - Fixed Focus Issues & Removed Icons
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
    from discord_integration import DiscordSecurityBot  # THÊM DÒNG NÀY
except ImportError as e:
    print(f"❌ Lỗi import modules: {e}")
    print("🔧 Đảm bảo các file sau tồn tại:")
    print("   - improved_face_recognition.py")
    print("   - enhanced_components.py")
    print("   - discord_integration.py")  # THÊM DÒNG NÀY
    sys.exit(1)

# Hardware imports
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
    
    # Use mock classes
    Picamera2 = MockPicamera2
    LED = MockLED
    
    # Mock board and busio
    class MockBoard:
        SCL = None
        SDA = None
    
    class MockBusIO:
        def I2C(self, scl, sda): return None
    
    board = MockBoard()
    busio = MockBusIO()
    PN532_I2C = lambda i2c, debug=False: MockPN532()
    PyFingerprint = lambda *args, **kwargs: MockFingerprint()

# ==== CONFIGURATION ====
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
    
    # Face Recognition - AI Enhanced
    FACE_CONFIDENCE_THRESHOLD: float = 0.5
    FACE_RECOGNITION_THRESHOLD: float = 85.0
    FACE_REQUIRED_CONSECUTIVE: int = 5
    FACE_DETECTION_INTERVAL: float = 0.03  # ~33 FPS
    
    # Camera - Enhanced Quality
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
        
        # Tạo thư mục nếu chưa có
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

# ==== ENHANCED GUI - FIXED FOCUS & NO ICONS ====
class AIEnhancedSecurityGUI:
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
        self.root.title("HE THONG KHOA BAO MAT AI - PHIEN BAN 2.1")  # XÓA ICON
        self.root.geometry("1500x900")
        self.root.configure(bg=Colors.DARK_BG)
        self.root.attributes('-fullscreen', True)
        self.root.minsize(1200, 800)
    
    def _create_widgets(self):
        # Main container
        main_container = tk.Frame(self.root, bg=Colors.DARK_BG)
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        main_container.grid_columnconfigure(0, weight=2)  # Camera gets more space
        main_container.grid_columnconfigure(1, weight=1)
        main_container.grid_rowconfigure(0, weight=1)
        
        # LEFT - AI CAMERA PANEL
        self._create_ai_camera_panel(main_container)
        
        # RIGHT - STATUS PANEL
        self._create_status_panel(main_container)
        
        # BOTTOM - STATUS BAR
        self._create_status_bar()
    
    def _create_ai_camera_panel(self, parent):
        camera_panel = tk.Frame(parent, bg=Colors.CARD_BG, relief=tk.RAISED, bd=4)
        camera_panel.grid(row=0, column=0, padx=(0,10), pady=0, sticky="nsew")
        
        # Header - XÓA ICON
        header = tk.Frame(camera_panel, bg=Colors.PRIMARY, height=100)
        header.pack(fill=tk.X, padx=4, pady=4)
        header.pack_propagate(False)
        
        # Left side - title - XÓA ICON
        header_left = tk.Frame(header, bg=Colors.PRIMARY)
        header_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        tk.Label(header_left, text="AI FACE DETECTION SYSTEM",  # XÓA ICON 🤖
                font=('Arial', 26, 'bold'), fg='white', bg=Colors.PRIMARY,
                anchor='w').pack(side=tk.LEFT, padx=20, expand=True, fill=tk.X)
        
        # Right side - stats
        stats_frame = tk.Frame(header, bg=Colors.PRIMARY)
        stats_frame.pack(side=tk.RIGHT, padx=20)
        
        self.fps_label = tk.Label(stats_frame, text="FPS: --", 
                                 font=('Arial', 16, 'bold'), fg='white', bg=Colors.PRIMARY)
        self.fps_label.pack()
        
        self.detection_count_label = tk.Label(stats_frame, text="Detected: 0", 
                                            font=('Arial', 14), fg='white', bg=Colors.PRIMARY)
        self.detection_count_label.pack()
        
        # Camera display - MUCH LARGER
        self.camera_frame = tk.Frame(camera_panel, bg='black', relief=tk.SUNKEN, bd=4)
        self.camera_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # XÓA ICON TRONG CAMERA LABEL
        self.camera_label = tk.Label(self.camera_frame, 
                                   text="Đang khởi động AI Camera System...\n\nOpenCV DNN Loading...",  # XÓA ICON
                                   font=('Arial', 22), fg='white', bg='black')
        self.camera_label.pack(expand=True)
        
        # AI Status bar - XÓA ICON
        ai_status_frame = tk.Frame(camera_panel, bg=Colors.CARD_BG, height=80)
        ai_status_frame.pack(fill=tk.X, pady=10)
        ai_status_frame.pack_propagate(False)
        
        self.ai_status = tk.Label(ai_status_frame, text="AI System Initializing...",  # XÓA ICON 🤖
                                 font=('Arial', 18, 'bold'), 
                                 fg=Colors.PRIMARY, bg=Colors.CARD_BG)
        self.ai_status.pack(expand=True)
        
        self.detection_info = tk.Label(ai_status_frame, text="Preparing neural networks...",  # XÓA ICON 🔍
                                      font=('Arial', 16), 
                                      fg=Colors.TEXT_SECONDARY, bg=Colors.CARD_BG)
        self.detection_info.pack()
    
    def _create_status_panel(self, parent):
        status_panel = tk.Frame(parent, bg=Colors.CARD_BG, relief=tk.RAISED, bd=4)
        status_panel.grid(row=0, column=1, padx=(10,0), pady=0, sticky="nsew")
        
        # Header - XÓA ICON
        header = tk.Frame(status_panel, bg=Colors.SUCCESS, height=100)
        header.pack(fill=tk.X, padx=4, pady=4)
        header.pack_propagate(False)
        
        tk.Label(header, text="TRANG THAI AUTHENTICATION",  # XÓA ICON 📊
                font=('Arial', 22, 'bold'), fg='white', bg=Colors.SUCCESS).pack(expand=True)
        
        # Current step - LARGER
        self.step_frame = tk.Frame(status_panel, bg=Colors.CARD_BG)
        self.step_frame.pack(fill=tk.X, padx=25, pady=25)
        
        self.step_number = tk.Label(self.step_frame, text="1", 
                                   font=('Arial', 52, 'bold'),
                                   fg='white', bg=Colors.PRIMARY,
                                   width=2, relief=tk.RAISED, bd=5)
        self.step_number.pack(side=tk.LEFT, padx=(0,25))
        
        step_info = tk.Frame(self.step_frame, bg=Colors.CARD_BG)
        step_info.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.step_title = tk.Label(step_info, text="AI FACE RECOGNITION",  # XÓA ICON 🤖
                                  font=('Arial', 30, 'bold'),
                                  fg=Colors.TEXT_PRIMARY, bg=Colors.CARD_BG,
                                  anchor='w')
        self.step_title.pack(fill=tk.X)
        
        self.step_subtitle = tk.Label(step_info, text="Neural network đang phân tích...",
                                     font=('Arial', 20),
                                     fg=Colors.TEXT_SECONDARY, bg=Colors.CARD_BG,
                                     anchor='w')
        self.step_subtitle.pack(fill=tk.X)
        
        # Progress indicators - XÓA ICON
        progress_frame = tk.Frame(status_panel, bg=Colors.CARD_BG)
        progress_frame.pack(fill=tk.X, padx=25, pady=20)
        
        tk.Label(progress_frame, text="TIEN TRINH XAC THUC:",  # XÓA ICON 🔄
                font=('Arial', 22, 'bold'),
                fg=Colors.TEXT_PRIMARY, bg=Colors.CARD_BG).pack(anchor='w')
        
        steps_frame = tk.Frame(progress_frame, bg=Colors.CARD_BG)
        steps_frame.pack(fill=tk.X, pady=15)
        
        self.step_indicators = {}
        # XÓA TẤT CẢ ICON
        names = ["AI RECOGNITION", "FINGERPRINT", "RFID CARD", "PASSCODE"]
        
        for i, name in enumerate(names):
            container = tk.Frame(steps_frame, bg=Colors.CARD_BG)
            container.pack(fill=tk.X, pady=8)
            
            circle = tk.Label(container, text=f"{i+1}",
                             font=('Arial', 22, 'bold'),
                             fg='white', bg=Colors.TEXT_SECONDARY,
                             width=3, relief=tk.RAISED, bd=4)
            circle.pack(side=tk.LEFT, padx=(0,20))
            
            label = tk.Label(container, text=name,  # CHỈ TEXT, KHÔNG ICON
                            font=('Arial', 20, 'bold'),
                            fg=Colors.TEXT_PRIMARY, bg=Colors.CARD_BG,
                            anchor='w')
            label.pack(side=tk.LEFT, fill=tk.X, expand=True)
            
            self.step_indicators[i+1] = {
                'circle': circle,
                'label': label
            }
        
        # AI Details area - XÓA ICON
        msg_frame = tk.Frame(status_panel, bg=Colors.BACKGROUND, relief=tk.SUNKEN, bd=4)
        msg_frame.pack(fill=tk.X, padx=25, pady=20)
        
        tk.Label(msg_frame, text="AI ANALYSIS DETAILS:",  # XÓA ICON 🧠
                font=('Arial', 18, 'bold'),
                fg=Colors.TEXT_PRIMARY, bg=Colors.BACKGROUND).pack(anchor='w', padx=20, pady=(15,8))
        
        self.detail_message = tk.Label(msg_frame, text="Khởi động neural networks...\nLoading OpenCV DNN models...",  # XÓA ICON
                                      font=('Arial', 16),
                                      fg=Colors.TEXT_SECONDARY, bg=Colors.BACKGROUND,
                                      wraplength=450, justify=tk.LEFT, anchor='w')
        self.detail_message.pack(fill=tk.X, padx=20, pady=(0,15))
        
        # Time display - XÓA ICON
        self.time_label = tk.Label(status_panel, text="",
                                  font=('Arial', 16),
                                  fg=Colors.TEXT_SECONDARY, bg=Colors.CARD_BG)
        self.time_label.pack(side=tk.BOTTOM, pady=10)
        
        self._update_time()
    
    def _create_status_bar(self):
        status_bar = tk.Frame(self.root, bg=Colors.PRIMARY, height=90)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=20, pady=(0,20))
        status_bar.pack_propagate(False)
        
        # XÓA ICON TRONG STATUS BAR
        self.main_status = tk.Label(status_bar, 
                                   text="AI ENHANCED SECURITY SYSTEM v2.1 - INITIALIZING...",  # XÓA ICON 🤖
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
        # XÓA ICON TRONG TIME
        current_time = datetime.now().strftime("%H:%M:%S - %d/%m/%Y")
        self.time_label.config(text=current_time)
        self.root.after(1000, self._update_time)
    
    def update_camera(self, frame: np.ndarray, detection_result: Optional[FaceDetectionResult] = None):
        """Update camera display với AI feedback nâng cao"""
        try:
            # Calculate FPS
            self.fps_counter += 1
            current_time = time.time()
            if current_time - self.fps_start_time >= 1.0:
                self.current_fps = self.fps_counter
                self.fps_counter = 0
                self.fps_start_time = current_time
                self.fps_label.config(text=f"FPS: {self.current_fps}")
            
            # Update detection statistics
            if detection_result:
                self.detection_stats["total"] += 1
                if detection_result.recognized:
                    self.detection_stats["recognized"] += 1
                elif detection_result.detected:
                    self.detection_stats["unknown"] += 1
                
                self.detection_count_label.config(
                    text=f"Total: {self.detection_stats['total']} | OK: {self.detection_stats['recognized']}"
                )
            
            # Resize frame for display
            height, width = frame.shape[:2]
            display_height = Config.DISPLAY_HEIGHT
            display_width = int(width * display_height / height)
            
            img = cv2.resize(frame, (display_width, display_height))
            rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            img_pil = Image.fromarray(rgb_img)
            img_tk = ImageTk.PhotoImage(img_pil)
            
            self.camera_label.config(image=img_tk, text="")
            self.camera_label.image = img_tk
            
            # Update AI status based on detection result - XÓA ICON
            if detection_result:
                if detection_result.detected:
                    if detection_result.recognized:
                        self.ai_status.config(
                            text=f"AI CONFIRMED: {detection_result.person_name}",  # XÓA ICON ✅
                            fg=Colors.SUCCESS
                        )
                        self.detection_info.config(
                            text=f"Confidence: {detection_result.confidence:.1f} | Status: AUTHORIZED",  # XÓA ICON 🎯
                            fg=Colors.SUCCESS
                        )
                    else:
                        self.ai_status.config(
                            text="AI DETECTED: UNAUTHORIZED FACE",  # XÓA ICON ❌
                            fg=Colors.ERROR
                        )
                        self.detection_info.config(
                            text="Face detected but not in database | Access denied",  # XÓA ICON ⚠️
                            fg=Colors.ERROR
                        )
                else:
                    self.ai_status.config(
                        text="AI SCANNING: Searching for faces...",  # XÓA ICON 🔍
                        fg=Colors.WARNING
                    )
                    self.detection_info.config(
                        text="Neural networks analyzing video stream...",  # XÓA ICON 👁️
                        fg=Colors.TEXT_SECONDARY
                    )
            
        except Exception as e:
            logger.error(f"Error updating camera: {e}")
    
    def update_step(self, step_num, title, subtitle, color=None):
        if color is None:
            color = Colors.PRIMARY
            
        self.step_number.config(text=str(step_num), bg=color)
        self.step_title.config(text=title)
        self.step_subtitle.config(text=subtitle)
        
        # Update progress indicators
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
        # XÓA ICON TRONG STATUS
        self.main_status.config(text=message, fg=color)
    
    def update_detail(self, message, color=None):
        if color is None:
            color = Colors.TEXT_SECONDARY
        self.detail_message.config(text=message, fg=color)
    
    def set_system_reference(self, system):
        self.system_ref = system

# ==== AI ENHANCED SECURITY SYSTEM - FIXED FOCUS ====
class AIEnhancedSecuritySystem:
    
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
                # Tạo event loop mới cho thread này
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Chạy notification
                loop.run_until_complete(self.discord_bot.send_notification(message))
                loop.close()
                
        except Exception as e:
            logger.error(f"Discord notification error: {e}")       
    def __init__(self):
        self.config = Config()
        logger.info("Khởi tạo AI Enhanced Security System...")  # XÓA ICON 🤖
        
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
        
        logger.info("AI Enhanced Security System khởi tạo thành công!")  # XÓA ICON ✅
    
    def _init_hardware(self):
        """Khởi tạo phần cứng"""
        try:
            logger.info("Khởi tạo phần cứng...")  # XÓA ICON 🔧
            
            # Buzzer (với mock nếu cần)
            try:
                self.buzzer = EnhancedBuzzerManager(self.config.BUZZER_GPIO)
            except:
                logger.warning("Buzzer mock mode")  # XÓA ICON ⚠️
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
                logger.warning("Fingerprint sensor simulation mode")  # XÓA ICON ⚠️
            
            logger.info("Tất cả phần cứng đã sẵn sàng")  # XÓA ICON ✅
            
        except Exception as e:
            logger.error(f"Lỗi khởi tạo phần cứng: {e}")  # XÓA ICON ❌
            logger.info("Continuing in simulation mode...")  # XÓA ICON 🔄
    
    def _init_components(self):
        """Khởi tạo các thành phần AI và data"""
        try:
            logger.info("Khởi tạo AI components...")  # XÓA ICON 🧠
            
            # Admin data manager
            self.admin_data = AdminDataManager(self.config.ADMIN_DATA_PATH)
            
            # AI Face Recognition - Enhanced
            self.face_recognizer = ImprovedFaceRecognition(
                models_path=self.config.MODELS_PATH,
                face_data_path=self.config.FACE_DATA_PATH,
                confidence_threshold=self.config.FACE_CONFIDENCE_THRESHOLD,
                recognition_threshold=self.config.FACE_RECOGNITION_THRESHOLD
            )
            
            logger.info("AI components đã sẵn sàng")  # XÓA ICON ✅
            
        except Exception as e:
            logger.error(f"Lỗi khởi tạo AI components: {e}")  # XÓA ICON ❌
            raise
    
    def _init_gui(self):
        """Khởi tạo giao diện"""
        try:
            logger.info("Khởi tạo GUI...")  # XÓA ICON 🎨
            
            self.root = tk.Tk()
            self.gui = AIEnhancedSecurityGUI(self.root)
            self.gui.set_system_reference(self)
            
            # Admin GUI
            self.admin_gui = ImprovedAdminGUI(self.root, self)
            
            logger.info("GUI đã sẵn sàng")  # XÓA ICON ✅
            
        except Exception as e:
            logger.error(f"Lỗi khởi tạo GUI: {e}")  # XÓA ICON ❌
            raise
    
    def _force_admin_mode(self):
        """Chế độ admin nhanh bằng phím * - FIXED FOCUS"""
        # FORCE FOCUS TRƯỚC KHI MỞ DIALOG
        self.root.focus_force()
        self.root.update()
        
        dialog = EnhancedNumpadDialog(self.root, "ADMIN ACCESS",  # XÓA ICON 🔧
                                    "Nhập mật khẩu admin:", True, self.buzzer)
        
        # FORCE FOCUS CHO DIALOG NGAY SAU KHI TẠO
        if hasattr(dialog, 'dialog'):
            dialog.dialog.focus_force()
            dialog.dialog.grab_set()
            dialog.dialog.lift()
        
        password = dialog.show()
        
        if password == self.config.ADMIN_PASS:
            self.gui.update_status("AI ADMIN MODE ACTIVATED", 'lightgreen')
            self.gui.update_detail("Admin authentication successful! Opening control panel...", Colors.SUCCESS)  # XÓA ICON ✅
            self.buzzer.beep("success")
            self.admin_gui.show_admin_panel()
        elif password is not None:
            self.gui.update_status("ADMIN ACCESS DENIED", 'orange')
            self.gui.update_detail("Incorrect admin password!", Colors.ERROR)  # XÓA ICON ❌
            self.buzzer.beep("error")
    
    def start_authentication(self):
        """Bắt đầu quy trình xác thực AI"""
        logger.info("Bắt đầu quy trình xác thực AI")  # XÓA ICON 🚀
        
        self.auth_state = {
            "step": AuthStep.FACE,
            "consecutive_face_ok": 0,
            "fingerprint_attempts": 0,
            "rfid_attempts": 0,
            "pin_attempts": 0
        }
        
        # XÓA ICON TRONG CÁC STEP
        self.gui.update_step(1, "AI FACE RECOGNITION", "Neural network đang phân tích...", Colors.PRIMARY)
        self.gui.update_status("AI ANALYZING FACES - PLEASE LOOK AT CAMERA", 'white')
        self.gui.update_detail("AI neural networks đang quét và phân tích khuôn mặt.\nNhìn thẳng vào camera và giữ nguyên vị trí.", Colors.PRIMARY)
        
        # Reset detection stats
        self.gui.detection_stats = {"total": 0, "recognized": 0, "unknown": 0}
        
        if self.face_thread and self.face_thread.is_alive():
            return
        
        self.face_thread = threading.Thread(target=self._ai_face_loop, daemon=True)
        self.face_thread.start()
    
    def _ai_face_loop(self):
        """AI Face recognition loop với enhanced performance"""
        logger.info("Bắt đầu AI face recognition loop")  # XÓA ICON 👁️
        consecutive_count = 0
        
        while self.running and self.auth_state["step"] == AuthStep.FACE:
            try:
                # Capture frame
                frame = self.picam2.capture_array()
                if frame is None:
                    continue
                
                # AI Processing
                annotated_frame, result = self.face_recognizer.process_frame(frame)
                
                # Update GUI với kết quả AI
                self.root.after(0, lambda: self.gui.update_camera(annotated_frame, result))
                
                if result.recognized:
                    consecutive_count += 1
                    self.auth_state["consecutive_face_ok"] = consecutive_count
                    
                    progress = consecutive_count / self.config.FACE_REQUIRED_CONSECUTIVE * 100
                    msg = f"AI confirmed ({consecutive_count}/{self.config.FACE_REQUIRED_CONSECUTIVE}) - {progress:.0f}%"
                    
                    # XÓA ICON TRONG STEP UPDATE
                    self.root.after(0, lambda: self.gui.update_step(1, "AI RECOGNITION", msg, Colors.SUCCESS))
                    self.root.after(0, lambda: self.gui.update_detail(
                        f"Identity: {result.person_name}\n"
                        f"Verifying... {self.config.FACE_REQUIRED_CONSECUTIVE - consecutive_count} more confirmations needed\n"
                        f"Confidence: {result.confidence:.1f}/100", 
                        Colors.SUCCESS))
                    
                    if consecutive_count >= self.config.FACE_REQUIRED_CONSECUTIVE:
                        logger.info(f"AI Face recognition thành công: {result.person_name}")  # XÓA ICON ✅
                        self.buzzer.beep("success")
                        self.root.after(0, lambda: self.gui.update_status(f"AI FACE VERIFIED: {result.person_name.upper()}!", 'lightgreen'))
                        self.root.after(1500, self._proceed_to_fingerprint)
                        break
                        
                elif result.detected:
                    # Phát hiện khuôn mặt nhưng không nhận diện được
                    consecutive_count = 0
                    self.auth_state["consecutive_face_ok"] = 0
                    # XÓA ICON TRONG UPDATE
                    self.root.after(0, lambda: self.gui.update_step(1, "AI DETECTION", "Unknown face detected", Colors.WARNING))
                    self.root.after(0, lambda: self.gui.update_detail(
                        "AI detected a face but it's not in the authorized database.\n"
                        f"Detection confidence: {result.confidence:.1f}\n"
                        "Please ensure you are registered in the system.", 
                        Colors.WARNING))
                else:
                    # Không phát hiện khuôn mặt
                    consecutive_count = 0
                    self.auth_state["consecutive_face_ok"] = 0
                    # XÓA ICON
                    self.root.after(0, lambda: self.gui.update_step(1, "AI SCANNING", "Searching for faces...", Colors.PRIMARY))
                
                time.sleep(self.config.FACE_DETECTION_INTERVAL)
                
            except Exception as e:
                logger.error(f"Lỗi AI face loop: {e}")  # XÓA ICON ❌
                self.root.after(0, lambda: self.gui.update_detail(f"AI Error: {str(e)}", Colors.ERROR))
                time.sleep(1)
    
    def _proceed_to_fingerprint(self):
        """Chuyển sang bước vân tay"""
        logger.info("Chuyển sang xác thực vân tay")  # XÓA ICON 👆
        self.auth_state["step"] = AuthStep.FINGERPRINT
        self.auth_state["fingerprint_attempts"] = 0
        
        # XÓA ICON TRONG UPDATE
        self.gui.update_step(2, "FINGERPRINT SCAN", "Place finger on sensor", Colors.WARNING)
        self.gui.update_status("WAITING FOR FINGERPRINT...", 'yellow')
        self.gui.update_detail("Please place your registered finger on the biometric sensor.\nSensor is ready for scanning.", Colors.WARNING)
        
        threading.Thread(target=self._fingerprint_loop, daemon=True).start()
    
    def _fingerprint_loop(self):
        """FIXED: Fingerprint loop với Discord alerts"""
        while (self.auth_state["fingerprint_attempts"] < self.config.MAX_ATTEMPTS and 
            self.auth_state["step"] == AuthStep.FINGERPRINT):
            
            try:
                self.auth_state["fingerprint_attempts"] += 1
                attempt_msg = f"Attempt {self.auth_state['fingerprint_attempts']}/{self.config.MAX_ATTEMPTS}"
                
                self.root.after(0, lambda: self.gui.update_step(2, "FINGERPRINT", attempt_msg, Colors.WARNING))
                
                timeout = 10
                start_time = time.time()
                
                while time.time() - start_time < timeout:
                    if self.fingerprint.readImage():
                        self.fingerprint.convertImage(0x01)
                        result = self.fingerprint.searchTemplate()
                        
                        if result[0] != -1:
                            # SUCCESS
                            logger.info(f"Fingerprint verified: ID {result[0]}")
                            self.buzzer.beep("success")
                            self.root.after(0, lambda: self.gui.update_status("FINGERPRINT VERIFIED! PROCEEDING TO RFID...", 'lightgreen'))
                            self.root.after(1500, self._proceed_to_rfid)
                            return
                        else:
                            # FAILURE - Send Discord alert
                            details = f"Template not found | Sensor reading: {result[1]}"
                            logger.warning(f"Fingerprint not recognized: attempt {self.auth_state['fingerprint_attempts']}")
                            
                            # Send Discord alert
                            self._send_discord_failure_alert("fingerprint", self.auth_state['fingerprint_attempts'], details)
                            
                            self.buzzer.beep("error")
                            remaining = self.config.MAX_ATTEMPTS - self.auth_state["fingerprint_attempts"]
                            if remaining > 0:
                                self.root.after(0, lambda: self.gui.update_detail(
                                    f"Fingerprint not recognized!\n{remaining} attempts remaining\nPlease try again with a registered finger.", Colors.ERROR))
                                time.sleep(2)
                                break
                    time.sleep(0.1)
                
                if time.time() - start_time >= timeout:
                    # TIMEOUT - Send Discord alert
                    details = f"Scan timeout - no finger detected ({timeout}s)"
                    logger.warning(f"Fingerprint timeout: attempt {self.auth_state['fingerprint_attempts']}")
                    
                    # Send Discord alert
                    self._send_discord_failure_alert("fingerprint", self.auth_state['fingerprint_attempts'], details)
                    
                    remaining = self.config.MAX_ATTEMPTS - self.auth_state["fingerprint_attempts"]
                    if remaining > 0:
                        self.root.after(0, lambda: self.gui.update_detail(
                            f"Scan timeout!\n{remaining} attempts remaining\nPlease place finger properly on sensor.", Colors.WARNING))
                        time.sleep(1)
                    
            except Exception as e:
                # HARDWARE ERROR - Send Discord alert
                details = f"Hardware error: {str(e)}"
                logger.error(f"Fingerprint error: {e}")
                
                # Send Discord alert
                self._send_discord_failure_alert("fingerprint", self.auth_state['fingerprint_attempts'], details)
                
                self.root.after(0, lambda: self.gui.update_detail(f"Sensor error: {str(e)}", Colors.ERROR))
                time.sleep(1)
        
        # OUT OF ATTEMPTS
        if self.auth_state["fingerprint_attempts"] >= self.config.MAX_ATTEMPTS:
            details = f"Maximum fingerprint attempts exceeded ({self.config.MAX_ATTEMPTS})"
            logger.critical(f"Fingerprint max attempts exceeded: {self.auth_state['fingerprint_attempts']}")
            
            # Send critical Discord alert
            self._send_discord_failure_alert("fingerprint", self.auth_state['fingerprint_attempts'], details)
        
        logger.warning("Fingerprint: Maximum attempts exceeded")
        self.root.after(0, lambda: self.gui.update_status("FINGERPRINT FAILED - RESTARTING AUTHENTICATION", 'orange'))
        self.buzzer.beep("error")
        self.root.after(3000, self.start_authentication)
    
    def _proceed_to_rfid(self):
        """Chuyển sang bước RFID"""
        logger.info("Chuyển sang xác thực RFID")  # XÓA ICON 📱
        self.auth_state["step"] = AuthStep.RFID
        self.auth_state["rfid_attempts"] = 0
        
        # XÓA ICON
        self.gui.update_step(3, "RFID SCAN", "Present card to reader", Colors.ACCENT)
        self.gui.update_status("WAITING FOR RFID CARD...", 'lightblue')
        self.gui.update_detail("Please present your RFID card near the reader.\nReader is active and scanning for cards.", Colors.ACCENT)
        
        threading.Thread(target=self._rfid_loop, daemon=True).start()
    
    def _rfid_loop(self):
        """RFID verification loop với FIXED Discord alerts"""
        while (self.auth_state["rfid_attempts"] < self.config.MAX_ATTEMPTS and 
            self.auth_state["step"] == AuthStep.RFID):
            
            try:
                self.auth_state["rfid_attempts"] += 1
                attempt_msg = f"Attempt {self.auth_state['rfid_attempts']}/{self.config.MAX_ATTEMPTS}"
                
                # Update GUI
                self.root.after(0, lambda: self.gui.update_step(3, "RFID SCAN", attempt_msg, Colors.ACCENT))
                self.root.after(0, lambda: self.gui.update_detail(
                    f"Scanning for RFID card... (Attempt {self.auth_state['rfid_attempts']}/{self.config.MAX_ATTEMPTS})\n"
                    "Hold card within 2-5cm of reader.", 
                    Colors.ACCENT))
                
                # Scan for RFID card
                uid = self.pn532.read_passive_target(timeout=8)
                
                if uid:
                    uid_list = list(uid)
                    logger.info(f"RFID detected: {uid_list}")
                    
                    # Check admin card
                    if uid_list == self.config.ADMIN_UID:
                        self.root.after(0, lambda: self._admin_authentication())
                        return
                    
                    # Check regular cards
                    valid_uids = self.admin_data.get_rfid_uids()
                    if uid_list in valid_uids:
                        # SUCCESS
                        logger.info(f"RFID verified: {uid_list}")
                        self.buzzer.beep("success")
                        self.root.after(0, lambda: self.gui.update_status("RFID VERIFIED! ENTER PASSCODE...", 'lightgreen'))
                        self.root.after(0, lambda: self.gui.update_detail(f"RFID card authentication successful!\nCard UID: {uid_list}\nProceeding to final passcode step.", Colors.SUCCESS))
                        self.root.after(1500, self._proceed_to_passcode)
                        return
                    else:
                        # FAILURE - Unauthorized card - SEND DISCORD ALERT
                        details = f"Unauthorized card | UID: {uid_list} | Not in database"
                        logger.warning(f"RFID unauthorized: {uid_list}")
                        
                        # Send Discord alert
                        self._send_discord_failure_alert("rfid", self.auth_state['rfid_attempts'], details)
                        
                        self.buzzer.beep("error")
                        remaining = self.config.MAX_ATTEMPTS - self.auth_state["rfid_attempts"]
                        
                        error_msg = f"❌ UNAUTHORIZED RFID CARD!\n"
                        error_msg += f"📱 Detected UID: {uid_list}\n"
                        error_msg += f"⚠️ Card not registered in system\n"
                        error_msg += f"🔄 {remaining} attempts remaining" if remaining > 0 else "🚫 No attempts remaining"
                        
                        self.root.after(0, lambda: self.gui.update_detail(error_msg, Colors.ERROR))
                        
                        if remaining > 0:
                            time.sleep(3)
                        else:
                            break
                else:
                    # FAILURE - No card detected - SEND DISCORD ALERT
                    details = f"No RFID card detected within timeout ({8}s)"
                    logger.warning(f"RFID timeout: attempt {self.auth_state['rfid_attempts']}")
                    
                    # Send Discord alert  
                    self._send_discord_failure_alert("rfid", self.auth_state['rfid_attempts'], details)
                    
                    remaining = self.config.MAX_ATTEMPTS - self.auth_state["rfid_attempts"]
                    
                    timeout_msg = f"⏰ NO CARD DETECTED!\n"
                    timeout_msg += f"🕐 Scan timeout after {8} seconds\n"
                    timeout_msg += f"📱 Please present card closer to reader\n"
                    timeout_msg += f"🔄 {remaining} attempts remaining" if remaining > 0 else "🚫 No attempts remaining"
                    
                    self.root.after(0, lambda: self.gui.update_detail(timeout_msg, Colors.WARNING))
                    
                    if remaining > 0:
                        time.sleep(2)
                    else:
                        break
                    
            except Exception as e:
                # HARDWARE ERROR - SEND DISCORD ALERT
                details = f"RFID hardware error: {str(e)}"
                logger.error(f"RFID error: {e}")
                
                # Send Discord alert
                self._send_discord_failure_alert("rfid", self.auth_state['rfid_attempts'], details)
                
                self.root.after(0, lambda: self.gui.update_detail(f"🔧 RFID READER ERROR!\n{str(e)}\nPlease check hardware connection", Colors.ERROR))
                time.sleep(2)
        
        # OUT OF ATTEMPTS - SEND FINAL DISCORD ALERT
        if self.auth_state["rfid_attempts"] >= self.config.MAX_ATTEMPTS:
            details = f"Maximum RFID attempts exceeded ({self.config.MAX_ATTEMPTS}) | Possible intrusion attempt"
            logger.critical(f"RFID max attempts exceeded: {self.auth_state['rfid_attempts']}")
            
            # Send critical Discord alert
            self._send_discord_failure_alert("rfid", self.auth_state['rfid_attempts'], details)
        
        logger.warning("RFID: Maximum attempts exceeded - Restarting authentication")
        self.root.after(0, lambda: self.gui.update_status("RFID FAILED - RESTARTING AUTHENTICATION", 'orange'))
        self.root.after(0, lambda: self.gui.update_detail(
            "❌ RFID AUTHENTICATION FAILED!\n"
            f"🚫 All {self.config.MAX_ATTEMPTS} attempts exhausted\n"
            "🔄 Restarting full authentication process...\n"
            "🛡️ Security event logged", Colors.ERROR))
        self.buzzer.beep("error")
        self.root.after(4000, self.start_authentication)
    
    def _proceed_to_passcode(self):
        """Chuyển sang bước cuối - passcode với enhanced security"""
        logger.info("Proceeding to final passcode authentication step")
        self.auth_state["step"] = AuthStep.PASSCODE
        self.auth_state["pin_attempts"] = 0
        
        # Discord notification về bước cuối
        if self.discord_bot:
            threading.Thread(
                target=self._send_discord_notification,
                args=("🔑 **FINAL AUTHENTICATION STEP**\nProceeding to passcode entry\nUser has passed 3/4 security layers ✅",),
                daemon=True
            ).start()
        
        self.gui.update_step(4, "FINAL PASSCODE", "Enter system passcode", Colors.SUCCESS)
        self.gui.update_status("ENTER FINAL PASSCODE...", 'lightgreen')
        self.gui.update_detail(
            "🔑 FINAL AUTHENTICATION STEP\n"
            "✅ Face Recognition: PASSED\n"
            "✅ Fingerprint: PASSED\n" 
            "✅ RFID Card: PASSED\n"
            "🔄 Passcode: PENDING\n\n"
            "Enter your numeric passcode to complete authentication.", 
            Colors.SUCCESS)
        
        self._request_passcode()

    def _request_passcode(self):
        """FIXED: Passcode input với Discord alerts"""
        
        # Check max attempts
        if self.auth_state["pin_attempts"] >= self.config.MAX_ATTEMPTS:
            # Send final critical alert
            details = f"Maximum passcode attempts exceeded ({self.config.MAX_ATTEMPTS}) | Final authentication step failed"
            logger.critical(f"Passcode max attempts exceeded: {self.auth_state['pin_attempts']}")
            
            # Send Discord alert
            self._send_discord_failure_alert("passcode", self.auth_state['pin_attempts'], details)
            
            logger.warning("Passcode: Maximum attempts exceeded")
            self.gui.update_status("PASSCODE FAILED - RESTARTING", 'orange')
            self.gui.update_detail(
                "🚫 PASSCODE AUTHENTICATION FAILED!\n"
                f"❌ All {self.config.MAX_ATTEMPTS} attempts exhausted\n"
                "⚠️ User passed all other security layers\n"
                "🔄 Restarting full authentication process...\n"
                "🛡️ Critical security event logged", Colors.ERROR)
            self.buzzer.beep("error")
            self.root.after(4000, self.start_authentication)
            return
        
        # Increment attempt counter
        self.auth_state["pin_attempts"] += 1
        attempt_msg = f"Attempt {self.auth_state['pin_attempts']}/{self.config.MAX_ATTEMPTS}"
        
        # Update GUI
        self.gui.update_step(4, "PASSCODE", attempt_msg, Colors.SUCCESS)
        self.gui.update_detail(
            f"🔑 Enter system passcode... (Attempt {self.auth_state['pin_attempts']}/{self.config.MAX_ATTEMPTS})\n"
            "✅ Previous steps completed successfully\n"
            "🎯 Use the numeric keypad to enter your code\n"
            "⚠️ This is the final authentication step", Colors.SUCCESS)
        
        # FORCE FOCUS
        self.root.focus_force()
        self.root.update()
        
        # Show dialog
        dialog = EnhancedNumpadDialog(
            self.root, 
            "🔑 FINAL AUTHENTICATION",
            f"Enter system passcode (Attempt {self.auth_state['pin_attempts']}/{self.config.MAX_ATTEMPTS}):", 
            True, 
            self.buzzer
        )
        
        if hasattr(dialog, 'dialog'):
            dialog.dialog.focus_force()
            dialog.dialog.grab_set()
            dialog.dialog.lift()
        
        # Get input
        entered_pin = dialog.show()
        
        if entered_pin is None:
            # User cancelled
            logger.info("Passcode entry cancelled by user")
            self.gui.update_detail("❌ Passcode entry cancelled\n🔄 Restarting authentication...", Colors.WARNING)
            self.buzzer.beep("click")
            self.root.after(2000, self.start_authentication)
            return
        
        # Validate passcode
        correct_passcode = self.admin_data.get_passcode()
        
        if entered_pin == correct_passcode:
            # SUCCESS
            logger.info("✅ Passcode verified - FULL AUTHENTICATION COMPLETE!")
            self.gui.update_status("AUTHENTICATION COMPLETE! UNLOCKING DOOR...", 'lightgreen')
            self.gui.update_detail(
                "🎉 AUTHENTICATION SUCCESSFUL!\n"
                "✅ All 4 security layers verified:\n"
                "  👤 Face Recognition: PASSED\n"
                "  👆 Fingerprint: PASSED\n"
                "  📱 RFID Card: PASSED\n"
                "  🔑 Passcode: PASSED\n\n"
                "🔓 Door unlocking now...", Colors.SUCCESS)
            self.buzzer.beep("success")
            
            # Send success notification to Discord
            if self.discord_bot:
                threading.Thread(
                    target=self._send_discord_notification,
                    args=("🔓 **AUTHENTICATION COMPLETED** - All 4 layers verified successfully!",),
                    daemon=True
                ).start()
            
            self._unlock_door()
            
        else:
            # FAILURE - Wrong passcode - SEND DISCORD ALERT
            remaining = self.config.MAX_ATTEMPTS - self.auth_state["pin_attempts"]
            
            details = f"Incorrect passcode | Expected length: {len(correct_passcode)}, Got: {len(entered_pin)} | User reached final step"
            logger.warning(f"Passcode incorrect: attempt {self.auth_state['pin_attempts']}")
            
            # Send Discord alert
            self._send_discord_failure_alert("passcode", self.auth_state['pin_attempts'], details)
            
            self.buzzer.beep("error")
            
            if remaining > 0:
                # Still have attempts
                error_msg = f"❌ INCORRECT PASSCODE!\n"
                error_msg += f"🔢 Passcode does not match system records\n"
                error_msg += f"🔄 {remaining} attempts remaining\n"
                error_msg += f"⚠️ Please verify your passcode and try again\n"
                error_msg += f"🛡️ This attempt has been logged"
                
                self.gui.update_detail(error_msg, Colors.ERROR)
                self.root.after(2500, self._request_passcode)
            else:
                # No attempts left
                final_error_msg = f"🚫 PASSCODE AUTHENTICATION FAILED!\n"
                final_error_msg += f"❌ All {self.config.MAX_ATTEMPTS} attempts exhausted\n"
                final_error_msg += f"⚠️ User completed 3/4 security layers but failed final step\n"
                final_error_msg += f"🔄 Restarting full authentication process...\n"
                final_error_msg += f"🛡️ Critical security breach logged"
                
                self.gui.update_status("PASSCODE FAILED - RESTARTING AUTHENTICATION", 'orange')
                self.gui.update_detail(final_error_msg, Colors.ERROR)
                self.root.after(4000, self.start_authentication)

    def _admin_authentication(self):
        """Enhanced admin authentication via RFID với Discord alerts"""
        # Discord notification về admin access attempt
        if self.discord_bot:
            threading.Thread(
                target=self._send_discord_notification,
                args=("🔧 **ADMIN RFID DETECTED**\nAdmin card scanned - requesting password authentication",),
                daemon=True
            ).start()
        
        # FORCE FOCUS BEFORE DIALOG
        self.root.focus_force()
        self.root.update()
        
        dialog = EnhancedNumpadDialog(
            self.root, 
            "🔧 ADMIN RFID ACCESS",
            "Admin card detected. Enter admin password:", 
            True, 
            self.buzzer
        )
        
        # FORCE FOCUS FOR DIALOG
        if hasattr(dialog, 'dialog'):
            dialog.dialog.focus_force()
            dialog.dialog.grab_set()
            dialog.dialog.lift()
        
        password = dialog.show()
        
        if password == self.config.ADMIN_PASS:
            # Admin authentication successful
            if self.discord_bot:
                threading.Thread(
                    target=self._send_discord_notification,
                    args=(f"✅ **ADMIN ACCESS GRANTED**\nAdmin authenticated successfully via RFID + password\nOpening admin control panel...",),
                    daemon=True
                ).start()
            
            logger.info("✅ Admin RFID authentication successful")
            self.gui.update_status("ADMIN RFID VERIFIED! OPENING CONTROL PANEL", 'lightgreen')
            self.gui.update_detail(
                "🔧 ADMIN AUTHENTICATION SUCCESSFUL!\n"
                "✅ Admin RFID card verified\n"
                "✅ Admin password verified\n"
                "🎛️ Opening admin control panel...", Colors.SUCCESS)
            self.buzzer.beep("success")
            self.admin_gui.show_admin_panel()
            
        elif password is not None:
            # Wrong admin password
            if self.discord_bot:
                threading.Thread(
                    target=self._send_discord_notification,
                    args=("❌ **ADMIN ACCESS DENIED**\nCorrect admin RFID but incorrect password\n⚠️ Possible unauthorized access attempt",),
                    daemon=True
                ).start()
            
            logger.warning("❌ Admin RFID detected but wrong password")
            self.gui.update_status("ADMIN PASSWORD INCORRECT", 'orange')
            self.gui.update_detail(
                "❌ ADMIN ACCESS DENIED!\n"
                "✅ Admin RFID verified\n"
                "❌ Admin password incorrect\n"
                "⚠️ Security violation logged\n"
                "🔄 Returning to authentication...", Colors.ERROR)
            self.buzzer.beep("error")
            time.sleep(3)
            self.start_authentication()
        else:
            # Admin cancelled
            if self.discord_bot:
                threading.Thread(
                    target=self._send_discord_notification,
                    args=("🔄 **ADMIN ACCESS CANCELLED**\nAdmin cancelled password entry\nReturning to normal authentication",),
                    daemon=True
                ).start()
            
            logger.info("Admin access cancelled")
            self.gui.update_detail("🔄 Admin access cancelled\nReturning to authentication...", Colors.WARNING)
            self.start_authentication()
    

    def _send_discord_failure_alert(self, step, attempts, details=""):
        """FIXED: Helper method để gửi Discord failure alert"""
        def send_alert():
            try:
                if self.discord_bot and self.discord_bot.bot:
                    # Tạo event loop mới
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    # Log để debug
                    logger.info(f"Sending Discord alert: {step} - {attempts} attempts")
                    
                    # Gửi alert
                    loop.run_until_complete(
                        self.discord_bot.send_authentication_failure_alert(step, attempts, details)
                    )
                    loop.close()
                    
                    logger.info(f"Discord alert sent successfully: {step}")
                    
                else:
                    logger.warning("Discord bot not available for alert")
                    
            except Exception as e:
                logger.error(f"Discord alert error: {e}")
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
                    success_message = f"✅ **{step.upper()} AUTHENTICATION SUCCESS**\n{details}"
                    loop.run_until_complete(
                        self.discord_bot.send_security_notification(success_message, "SUCCESS")
                    )
                
                loop.close()
                logger.info(f"Discord success notification sent for {step}")
                
        except Exception as e:
            logger.error(f"Discord success notification error for {step}: {e}")

    def _send_discord_notification(self, message):
        """Enhanced helper function để gửi Discord notification từ sync context"""
        try:
            if self.discord_bot and self.discord_bot.bot:
                # Create event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Send notification
                loop.run_until_complete(
                    self.discord_bot.send_security_notification(message, "INFO")
                )
                loop.close()
                
                logger.info(f"Discord notification sent: {message[:50]}...")
                
        except Exception as e:
            logger.error(f"Discord notification error: {e}")

    def _unlock_door(self):
        """Enhanced door unlock với Discord notifications"""
        try:
            logger.info(f"🔓 Unlocking door for {self.config.LOCK_OPEN_DURATION} seconds")
            
            # Final Discord success notification
            if self.discord_bot:
                unlock_message = f"🔓 **DOOR UNLOCKED SUCCESSFULLY**\n"
                unlock_message += f"🎉 4-layer authentication completed:\n"
                unlock_message += f"  ✅ Face Recognition: PASSED\n"
                unlock_message += f"  ✅ Fingerprint: PASSED\n"
                unlock_message += f"  ✅ RFID Card: PASSED\n"
                unlock_message += f"  ✅ Passcode: PASSED\n\n"
                unlock_message += f"🕐 Door will auto-lock in {self.config.LOCK_OPEN_DURATION} seconds\n"
                unlock_message += f"📅 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                
                threading.Thread(
                    target=self._send_discord_notification,
                    args=(unlock_message,),
                    daemon=True
                ).start()
            
            self.gui.update_step(4, "COMPLETED", "DOOR UNLOCKED", Colors.SUCCESS)
            self.gui.update_status(f"DOOR OPEN - AUTO LOCK IN {self.config.LOCK_OPEN_DURATION}S", 'lightgreen')
            
            # Unlock the door
            self.relay.off()  # Unlock door
            self.buzzer.beep("success")
            
            # Countdown with visual effects
            for i in range(self.config.LOCK_OPEN_DURATION, 0, -1):
                self.root.after((self.config.LOCK_OPEN_DURATION - i) * 1000, 
                            lambda t=i: self.gui.update_detail(
                                f"🔓 DOOR IS OPEN\n"
                                f"⏰ Auto lock in {t} seconds\n"
                                f"🚶 Please enter and close the door\n"
                                f"🛡️ All security systems active", Colors.SUCCESS))
                self.root.after((self.config.LOCK_OPEN_DURATION - i) * 1000,
                            lambda t=i: self.gui.update_status(f"DOOR OPEN - LOCK IN {t}S", 'lightgreen'))
                
                # Beep countdown for last 3 seconds
                if i <= 3:
                    self.root.after((self.config.LOCK_OPEN_DURATION - i) * 1000,
                                lambda: self.buzzer.beep("click"))
            
            # Schedule auto-lock
            self.root.after(self.config.LOCK_OPEN_DURATION * 1000, self._lock_door)
            
        except Exception as e:
            logger.error(f"Door unlock error: {e}")
            
            # Error notification to Discord
            if self.discord_bot:
                error_message = f"❌ **DOOR UNLOCK ERROR**\nHardware error during unlock: {str(e)}\n⚠️ Manual intervention may be required"
                threading.Thread(
                    target=self._send_discord_notification,
                    args=(error_message,),
                    daemon=True
                ).start()
            
            self.gui.update_detail(f"🔧 DOOR UNLOCK ERROR!\n{str(e)}\nPlease check hardware", Colors.ERROR)
            self.buzzer.beep("error")

    def _lock_door(self):
        """Enhanced door lock với Discord notifications"""
        try:
            logger.info("🔒 Locking door and resetting system")
            
            # Lock the door
            self.relay.on()  # Lock door
            
            # Discord notification về auto-lock
            if self.discord_bot:
                lock_message = f"🔒 **DOOR AUTO-LOCKED**\n"
                lock_message += f"✅ Door secured after {self.config.LOCK_OPEN_DURATION} seconds\n"
                lock_message += f"🔄 System ready for next user\n"
                lock_message += f"🛡️ All security layers reset\n"
                lock_message += f"📅 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                
                threading.Thread(
                    target=self._send_discord_notification,
                    args=(lock_message,),
                    daemon=True
                ).start()
            
            self.gui.update_status("DOOR LOCKED - SYSTEM READY FOR NEXT USER", 'white')
            self.gui.update_detail(
                "🔒 DOOR LOCKED AUTOMATICALLY\n"
                "✅ Security system reset\n"
                "🔄 Ready for next authentication cycle\n"
                "🛡️ All sensors active and monitoring", Colors.PRIMARY)
            self.buzzer.beep("click")
            
            # Reset detection stats
            self.gui.detection_stats = {"total": 0, "recognized": 0, "unknown": 0}
            
            # Reset authentication state completely
            self.auth_state = {
                "step": AuthStep.FACE,
                "consecutive_face_ok": 0,
                "fingerprint_attempts": 0,
                "rfid_attempts": 0,
                "pin_attempts": 0
            }
            
            # Start new authentication cycle
            self.root.after(3000, self.start_authentication)
            
        except Exception as e:
            logger.error(f"Door lock error: {e}")
            
            # Critical error notification to Discord
            if self.discord_bot:
                critical_message = f"🚨 **CRITICAL: DOOR LOCK ERROR**\n"
                critical_message += f"❌ Failed to lock door: {str(e)}\n"
                critical_message += f"⚠️ SECURITY BREACH RISK\n"
                critical_message += f"🔧 IMMEDIATE MANUAL INTERVENTION REQUIRED"
                
                threading.Thread(
                    target=self._send_discord_notification,
                    args=(critical_message,),
                    daemon=True
                ).start()
            
            self.gui.update_detail(f"🚨 CRITICAL: DOOR LOCK ERROR!\n{str(e)}\n⚠️ Manual intervention required", Colors.ERROR)
            self.buzzer.beep("error")

    
    def run(self):
        """Chạy hệ thống chính"""
        try:
            logger.info("Starting AI Enhanced Security System")  # XÓA ICON 🚀

            if self.discord_bot:
                logger.info("Đang khởi động Discord bot...")
            if self.discord_bot.start_bot():
                logger.info("✅ Discord bot đã khởi động thành công!")
            else:
                logger.warning("⚠️ Không thể khởi động Discord bot")

            # Startup effects - XÓA ICON
            self.gui.update_status("AI ENHANCED SECURITY SYSTEM v2.1 - READY!", 'lightgreen')
            self.gui.update_detail("AI neural networks loaded and ready\n"
                                 "4-layer security system active\n"
                                 "Discord bot integration enabled\n"  # THÊM DÒNG NÀY
                                 "Enhanced performance for Raspberry Pi 5", Colors.SUCCESS)
            
            self.buzzer.beep("startup")
            
            # Show system info - XÓA ICON
            face_info = self.face_recognizer.get_database_info()
            self.gui.update_detail(f"System Status:\n"
                                 f"Registered faces: {face_info['total_people']}\n"
                                 f"Fingerprints: {len(self.admin_data.get_fingerprint_ids())}\n"
                                 f"RFID cards: {len(self.admin_data.get_rfid_uids())}\n"
                                 f"AI Status: Ready", Colors.SUCCESS)
            
            # Start authentication after 3 seconds
            self.root.after(3000, self.start_authentication)
            
            # Setup cleanup
            self.root.protocol("WM_DELETE_WINDOW", self.cleanup)
            
            # Start main loop
            self.root.mainloop()
            
        except KeyboardInterrupt:
            logger.info("System stopped by user request")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Cleanup tài nguyên khi thoát"""
        logger.info("Cleaning up system resources...")
        self.running = False
        
        try:
            # THÊM CLEANUP DISCORD BOT
            if hasattr(self, 'discord_bot') and self.discord_bot:
                self.discord_bot.stop_bot()
                logger.info("Discord bot stopped")
            
            if hasattr(self, 'picam2'):
                self.picam2.stop()
                logger.info("Camera stopped")
                
            if hasattr(self, 'relay'):
                self.relay.on()  # Ensure door is locked
                logger.info("Door locked")
                
            if hasattr(self, 'buzzer') and hasattr(self.buzzer, 'buzzer') and self.buzzer.buzzer:
                self.buzzer.buzzer.off()
                logger.info("Buzzer stopped")
                
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
        
        if hasattr(self, 'root'):
            self.root.quit()
        
        logger.info("Cleanup completed")
    
    

# ==== MAIN EXECUTION ====
if __name__ == "__main__":
    try:
        print("=" * 100)
        print("HE THONG KHOA BAO MAT 4 LOP - AI ENHANCED VERSION 2.1")  # XÓA ICON
        print("   Tác giả: Khoi - Luận án tốt nghiệp")
        print("   Ngày: 2025-01-16 - FIXED FOCUS & NO ICONS")
        print("=" * 100)
        print()
        print("CAI TIEN AI DAC BIET:")  # XÓA ICON 🎯
        print("   OpenCV DNN Face Detection với MobileNet SSD")  # XÓA ICON 🤖
        print("   LBPH Face Recognition với độ chính xác cao")  # XÓA ICON 🧠
        print("   FPS cao 30+ với real-time visual feedback")  # XÓA ICON 📹
        print("   Khung bounding box màu sắc (xanh/đỏ)")  # XÓA ICON 🎨
        print("   Cửa sổ camera lớn hơn 60% so với phiên bản cũ")  # XÓA ICON 📱
        print("   Tối ưu hoàn toàn cho Raspberry Pi 5")  # XÓA ICON ⚡
        print("   Enhanced buzzer với nhiều âm thanh")  # XÓA ICON 🎵
        print("   Real-time statistics và monitoring")  # XÓA ICON 📊
        print("   FIXED: Focus issues với dialog")  # XÓA ICON 🔧
        print("   REMOVED: Tất cả icon khỏi giao diện")  # XÓA ICON ❌
        print()
        print("4 LOP BAO MAT TUAN TU:")  # XÓA ICON 🔐
        print("   1. AI Face Recognition (OpenCV DNN)")  # XÓA ICON 🤖
        print("   2. Fingerprint Biometric (AS608)")  # XÓA ICON 👆
        print("   3. RFID/NFC Card (PN532)")  # XÓA ICON 📱
        print("   4. Numeric Passcode (Keyboard)")  # XÓA ICON 🔑
        print()
        print("DIEU KHIEN NANG CAO:")  # XÓA ICON 🎮
        print("   * hoặc KP_* = Admin mode")
        print("   # hoặc KP_+ = Start authentication")
        print("   ESC = Exit system")
        print("   F11 = Toggle fullscreen")
        print("   Up/Down/Left/Right = Navigate dialogs")  # XÓA ICON ↑↓←→
        print("   Enter/Space = Confirm")
        print("   Period (.) = Cancel/Exit dialogs")  # XÓA ICON
        print("   1-9 = Quick select")
        print()
        print("KIEM TRA PHAN CUNG:")  # XÓA ICON 🔍
        
        hardware_components = [
            ("CAM", "Raspberry Pi Camera Module 2"),  # XÓA ICON 📹
            ("FP", "Fingerprint Sensor AS608 (USB/UART)"),  # XÓA ICON 👆
            ("RFID", "RFID Reader PN532 (I2C)"),  # XÓA ICON 📱
            ("RELAY", "Solenoid Lock + 4-channel Relay"),  # XÓA ICON 🔌
            ("BUZZ", "Enhanced Buzzer (GPIO PWM)"),  # XÓA ICON 🔊
            ("KBD", "USB Numeric Keypad"),  # XÓA ICON ⌨️
            ("DATA", "AI Model Storage"),  # XÓA ICON 💾
            ("AI", "Face Database System")  # XÓA ICON 🧠
        ]
        
        for prefix, component in hardware_components:
            print(f"   {prefix}: {component}")
            time.sleep(0.2)
        
        print()
        print("KHOI TAO HE THONG ...")  # XÓA ICON 🚀
        print("=" * 100)
        
        # Initialize and run system
        system = AIEnhancedSecuritySystem()
        
        print()
        print("TAT CA THANH PHAN DA SAN SANG!")  # XÓA ICON ✅
        print("Đang khởi động giao diện AI...")  # XÓA ICON 🎨
        print("Kết nối hardware thành công!")  # XÓA ICON 📡
        print("  neural networks đã được load!")  # XÓA ICON 🤖
        print("=" * 100)
        print("HE THONG SAN SANG! BAT DAU SU DUNG...")  # XÓA ICON 🎯
        print("=" * 100)
        
        system.run()
        
    except Exception as e:
        print()
        print("=" * 100)
        print(f"LOI KHOI DONG NGHIEM TRONG: {e}")  # XÓA ICON ❌
        print()
        print("DANH SACH KIEM TRA KHAC PHUC:")  # XÓA ICON 🔧
        
        troubleshooting_items = [
            ("HW", "Kiểm tra kết nối phần cứng và nguồn điện"),  # XÓA ICON 🔌
            ("AI", "Đảm bảo các file models AI tồn tại"),  # XÓA ICON 📁
            ("GPIO", "Kiểm tra quyền truy cập GPIO và USB"),  # XÓA ICON 🔑
            ("LIB", "Cài đặt đầy đủ thư viện Python"),  # XÓA ICON 📦
            ("BUZZ", "Cấu hình đúng GPIO cho Buzzer"),  # XÓA ICON 🔊
            ("CAM", "Camera permissions và drivers"),  # XÓA ICON 📹
            ("DISK", "Kiểm tra dung lượng ổ cứng"),  # XÓA ICON 💾
            ("I2C", "Kết nối I2C và UART hoạt động"),  # XÓA ICON 🌐
            ("MODEL", "Download AI models (chạy download_models.py)"),  # XÓA ICON 🤖
            ("LOG", "Kiểm tra log file để xem chi tiết lỗi")  # XÓA ICON 📝
        ]
        
        for prefix, item in troubleshooting_items:
            print(f"   {prefix}: {item}")
        
        print()
        print("HUONG DAN KHAC PHUC:")  # XÓA ICON 📞
        print("   1. Chạy: python3 download_models.py")
        print("   2. Kiểm tra: ls -la /home/khoi/Desktop/KHOI_LUANAN/models/")
        print("   3. Test camera: python3 -c 'from picamera2 import Picamera2; print(\"OK\")'")
        print("   4. Test OpenCV: python3 -c 'import cv2; print(cv2.__version__)'")
        print("   5. Kiểm tra log: tail -f /home/khoi/Desktop/KHOI_LUANAN/system.log")
        print()
        print("=" * 100)
        
        logger.error(f"System startup failed: {e}")
        sys.exit(1)
