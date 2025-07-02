#!/usr/bin/env python3
"""
Enhanced Components for Vietnamese Security System
Nâng cấp: Thêm chức năng chuyển đổi chế độ xác thực
Version: 2.3 - Dual Authentication Mode
Date: 2025-07-02
"""

import cv2
import time
import json
import os
import logging
import threading
import tkinter as tk
from tkinter import ttk, font
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import numpy as np

try:
    from gpiozero import LED, PWMOutputDevice
    from pyfingerprint.pyfingerprint import PyFingerprint
    import board
    import busio
    from adafruit_pn532.i2c import PN532_I2C
except ImportError as e:
    logging.error(f"Không thể import thư viện phần cứng: {e}")

logger = logging.getLogger(__name__)

# ==== COLOR SCHEME ====
class Colors:
    PRIMARY = "#2196F3"      # Blue
    SUCCESS = "#4CAF50"      # Green  
    ERROR = "#F44336"        # Red
    WARNING = "#FF9800"      # Orange
    BACKGROUND = "#FAFAFA"   # Light Gray
    CARD_BG = "#FFFFFF"      # White
    TEXT_PRIMARY = "#212121" # Dark Gray
    TEXT_SECONDARY = "#757575" # Medium Gray
    ACCENT = "#9C27B0"       # Purple
    BORDER = "#E0E0E0"       # Light Border
    DARK_BG = "#263238"      # Dark Background

# ==== ENHANCED BUZZER ====
class EnhancedBuzzerManager:
    def __init__(self, gpio_pin: int):
        try:
            self.buzzer = PWMOutputDevice(gpio_pin)
            self.buzzer.off()
            logger.info(f"✅ Buzzer khởi tạo thành công trên GPIO {gpio_pin}")
        except Exception as e:
            logger.error(f"❌ Lỗi khởi tạo buzzer: {e}")
            self.buzzer = None
    
    def beep(self, pattern: str):
        if self.buzzer is None:
            return
            
        patterns = {
            "success": [(2000, 0.5, 0.3), (2500, 0.5, 0.3)],
            "error": [(400, 0.8, 0.8)],
            "click": [(1500, 0.3, 0.1)],
            "warning": [(800, 0.6, 0.2), (600, 0.6, 0.2)],
            "startup": [(1000, 0.4, 0.2), (1500, 0.4, 0.2), (2000, 0.4, 0.3)],
            "mode_change": [(1200, 0.4, 0.2), (1800, 0.4, 0.2), (2400, 0.4, 0.3)]  # NEW
        }
        
        if pattern in patterns:
            def beep_thread():
                try:
                    for freq, volume, duration in patterns[pattern]:
                        if self.buzzer:
                            self.buzzer.frequency = freq
                            self.buzzer.value = volume
                            time.sleep(duration)
                            self.buzzer.off()
                            time.sleep(0.05)
                except Exception as e:
                    logger.error(f"Lỗi buzzer: {e}")
            
            threading.Thread(target=beep_thread, daemon=True).start()
    # ==== ENHANCED NUMPAD DIALOG ====
class EnhancedNumpadDialog:
    def __init__(self, parent, title, prompt, is_password=False, buzzer=None):
        self.parent = parent
        self.title = title
        self.prompt = prompt
        self.is_password = is_password
        self.buzzer = buzzer
        self.result = None
        self.input_text = ""
        self.selected_row = 1
        self.selected_col = 1
        self.button_widgets = {}
        
    def show(self) -> Optional[str]:
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title(self.title)
        self.dialog.geometry("600x750")
        self.dialog.configure(bg=Colors.DARK_BG)
        self.dialog.resizable(False, False)
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # Focus management
        self.dialog.lift()
        self.dialog.focus_force()
        
        # Center dialog
        x = (self.dialog.winfo_screenwidth() // 2) - 300
        y = (self.dialog.winfo_screenheight() // 2) - 375
        self.dialog.geometry(f'600x750+{x}+{y}')
        
        self._create_widgets()
        self._setup_bindings()
        self._highlight_button()
        
        # Multiple focus attempts
        self.dialog.after(100, lambda: self.dialog.focus_force())
        
        self.dialog.wait_window()
        return self.result
    
    def _create_widgets(self):
        # Header
        header_frame = tk.Frame(self.dialog, bg=Colors.PRIMARY, height=100)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text=self.title, 
                font=('Arial', 26, 'bold'), fg='white', bg=Colors.PRIMARY).pack(expand=True)
        
        if self.prompt:
            tk.Label(header_frame, text=self.prompt,
                    font=('Arial', 18), fg='white', bg=Colors.PRIMARY).pack()
        
        # Display
        display_frame = tk.Frame(self.dialog, bg=Colors.CARD_BG, height=140)
        display_frame.pack(fill=tk.X, padx=25, pady=25)
        display_frame.pack_propagate(False)
        
        self.display_var = tk.StringVar()
        self.display_label = tk.Label(display_frame, textvariable=self.display_var,
                font=('Courier New', 36, 'bold'), fg=Colors.SUCCESS, bg=Colors.CARD_BG,
                relief=tk.SUNKEN, bd=4)
        self.display_label.pack(expand=True, fill=tk.BOTH, padx=18, pady=18)
        
        # Numpad
        numpad_frame = tk.Frame(self.dialog, bg=Colors.DARK_BG)
        numpad_frame.pack(padx=25, pady=20)
        
        buttons_layout = [
            ['1', '2', '3'],
            ['4', '5', '6'], 
            ['7', '8', '9'],
            ['CLR', '0', 'XOA']
        ]
        
        for i, row in enumerate(buttons_layout):
            for j, text in enumerate(row):
                color = Colors.ERROR if text in ['CLR', 'XOA'] else Colors.PRIMARY
                btn = tk.Button(numpad_frame, text=text, font=('Arial', 22, 'bold'),
                              bg=color, fg='white', width=6, height=2,
                              relief=tk.RAISED, bd=5,
                              command=lambda t=text: self._on_key_click(t))
                btn.grid(row=i, column=j, padx=10, pady=10)
                self.button_widgets[(i, j)] = btn
        
        # Control buttons
        control_frame = tk.Frame(self.dialog, bg=Colors.DARK_BG)
        control_frame.pack(pady=30)
        
        self.ok_btn = tk.Button(control_frame, text="XAC NHAN", font=('Arial', 20, 'bold'),
                 bg=Colors.SUCCESS, fg='white', width=14, height=2,
                 relief=tk.RAISED, bd=5,
                 command=self._on_ok)
        self.ok_btn.pack(side=tk.LEFT, padx=20)
        
        self.cancel_btn = tk.Button(control_frame, text="HUY", font=('Arial', 20, 'bold'),
                 bg=Colors.ACCENT, fg='white', width=14, height=2,
                 relief=tk.RAISED, bd=5,
                 command=self._on_cancel)
        self.cancel_btn.pack(side=tk.RIGHT, padx=20)
        
        self.button_widgets[(-1, 0)] = self.ok_btn
        self.button_widgets[(-1, 1)] = self.cancel_btn
        
        self._update_display()
    
    def _setup_bindings(self):
        # Universal keyboard support (main + wireless numpad)
        for i in range(10):
            self.dialog.bind(str(i), lambda e, key=str(i): self._on_key_click(key))
            self.dialog.bind(f'<KP_{i}>', lambda e, key=str(i): self._on_key_click(key))
        
        # Special keys
        self.dialog.bind('<Return>', lambda e: self._on_ok())
        self.dialog.bind('<KP_Enter>', lambda e: self._on_ok())
        self.dialog.bind('<period>', lambda e: self._on_cancel())
        self.dialog.bind('<KP_Decimal>', lambda e: self._on_cancel())
        self.dialog.bind('<Escape>', lambda e: self._on_cancel())
        self.dialog.bind('<BackSpace>', lambda e: self._on_key_click('XOA'))
        self.dialog.bind('<Delete>', lambda e: self._on_key_click('CLR'))
        
        # Navigation
        self.dialog.bind('<Up>', lambda e: self._navigate(-1, 0))
        self.dialog.bind('<Down>', lambda e: self._navigate(1, 0))
        self.dialog.bind('<Left>', lambda e: self._navigate(0, -1))
        self.dialog.bind('<Right>', lambda e: self._navigate(0, 1))
        self.dialog.bind('<space>', lambda e: self._activate_selected())
        
        self.dialog.focus_set()
    
    def _navigate(self, row_delta, col_delta):
        new_row = self.selected_row + row_delta
        new_col = self.selected_col + col_delta
        
        if 0 <= new_row <= 3 and 0 <= new_col <= 2:
            self.selected_row = new_row
            self.selected_col = new_col
        elif new_row == -1 and 0 <= new_col <= 1:
            self.selected_row = -1
            self.selected_col = new_col
        elif new_row > 3:
            self.selected_row = -1
            self.selected_col = 0
        elif new_row < -1:
            self.selected_row = 3
            self.selected_col = 1
        elif new_col > 2:
            self.selected_col = 0
        elif new_col < 0:
            self.selected_col = 2
        
        self._highlight_button()
    
    def _highlight_button(self):
        for pos, btn in self.button_widgets.items():
            btn.config(relief=tk.RAISED, bd=5)
        
        if (self.selected_row, self.selected_col) in self.button_widgets:
            btn = self.button_widgets[(self.selected_row, self.selected_col)]
            btn.config(relief=tk.SUNKEN, bd=7)
    
    def _activate_selected(self):
        if (self.selected_row, self.selected_col) in self.button_widgets:
            btn = self.button_widgets[(self.selected_row, self.selected_col)]
            btn.invoke()
    
    def _on_key_click(self, key):
        if self.buzzer:
            self.buzzer.beep("click")
            
        if key.isdigit():
            self.input_text += key
        elif key == 'XOA' and self.input_text:
            self.input_text = self.input_text[:-1]
        elif key == 'CLR':
            self.input_text = ""
        
        self._update_display()
    
    def _update_display(self):
        if self.is_password:
            display = '●' * len(self.input_text)
        else:
            display = self.input_text
        
        if len(display) == 0:
            display = "___"
        
        self.display_var.set(display)
        
        if len(self.input_text) >= 4:
            self.display_label.config(fg=Colors.SUCCESS)
        elif len(self.input_text) > 0:
            self.display_label.config(fg=Colors.WARNING)
        else:
            self.display_label.config(fg=Colors.TEXT_SECONDARY)
    
    def _on_ok(self):
        if len(self.input_text) >= 1:
            if self.buzzer:
                self.buzzer.beep("success")
            self.result = self.input_text
            self.dialog.destroy()
    
    def _on_cancel(self):
        if self.buzzer:
            self.buzzer.beep("click")
        self.result = None
        self.dialog.destroy()

# ==== ENHANCED MESSAGE BOX ====
class EnhancedMessageBox:
    @staticmethod
    def show_info(parent, title, message, buzzer=None):
        return EnhancedMessageBox._show(parent, title, message, "info", ["OK"], buzzer)
    
    @staticmethod
    def show_error(parent, title, message, buzzer=None):
        return EnhancedMessageBox._show(parent, title, message, "error", ["OK"], buzzer)
    
    @staticmethod
    def show_success(parent, title, message, buzzer=None):
        return EnhancedMessageBox._show(parent, title, message, "success", ["OK"], buzzer)
    
    @staticmethod
    def ask_yesno(parent, title, message, buzzer=None):
        return EnhancedMessageBox._show(parent, title, message, "question", ["CO", "KHONG"], buzzer) == "CO"
    
    @staticmethod
    def _show(parent, title, message, msg_type, buttons, buzzer=None):
        dialog = tk.Toplevel(parent)
        dialog.title(title)
        # Enlarged để chứa longer messages
        dialog.geometry("750x500")  # Tăng từ 650x400
        dialog.configure(bg=Colors.DARK_BG)
        dialog.transient(parent)
        dialog.grab_set()
        
        # Focus management
        dialog.lift()
        dialog.focus_force()
        
        x = (dialog.winfo_screenwidth() // 2) - 375  # 750/2
        y = (dialog.winfo_screenheight() // 2) - 250  # 500/2
        dialog.geometry(f'750x500+{x}+{y}')
        
        result = [None]
        selected = [0]
        btn_widgets = []
        
        # Header
        colors = {
            "info": Colors.PRIMARY,
            "error": Colors.ERROR, 
            "success": Colors.SUCCESS,
            "question": Colors.WARNING
        }
        color = colors.get(msg_type, Colors.PRIMARY)
        
        header = tk.Frame(dialog, bg=color, height=90)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        tk.Label(header, text=title, font=('Arial', 24, 'bold'),
                fg='white', bg=color).pack(expand=True)
        
        # Message
        msg_frame = tk.Frame(dialog, bg=Colors.CARD_BG)
        msg_frame.pack(fill=tk.BOTH, expand=True, padx=25, pady=25)
        
        tk.Label(msg_frame, text=message, font=('Arial', 16),  # Giảm font để fit nhiều text
                fg=Colors.TEXT_PRIMARY, bg=Colors.CARD_BG, 
                wraplength=700, justify=tk.LEFT).pack(expand=True)  # Tăng wraplength
        
        # Buttons
        btn_frame = tk.Frame(dialog, bg=Colors.DARK_BG)
        btn_frame.pack(pady=30)
        
        btn_colors = [Colors.SUCCESS, Colors.ERROR]
        
        def close_dialog(text):
            if buzzer:
                buzzer.beep("click")
            result[0] = text
            dialog.destroy()
        
        for i, btn_text in enumerate(buttons):
            bg_color = btn_colors[i] if i < len(btn_colors) else Colors.PRIMARY
            btn = tk.Button(btn_frame, text=btn_text, font=('Arial', 18, 'bold'),
                          bg=bg_color, fg='white', width=12, height=2,
                          relief=tk.RAISED, bd=5,
                          command=lambda t=btn_text: close_dialog(t))
            btn.pack(side=tk.LEFT, padx=25)
            btn_widgets.append(btn)
        
        # Navigation functions
        def select_button(idx):
            for j, btn in enumerate(btn_widgets):
                if j == idx:
                    btn.config(relief=tk.SUNKEN, bd=7)
                else:
                    btn.config(relief=tk.RAISED, bd=5)
            selected[0] = idx
        
        def navigate_buttons(direction):
            new_idx = (selected[0] + direction) % len(btn_widgets)
            select_button(new_idx)
        
        def activate_selected():
            btn_widgets[selected[0]].invoke()
        
        # Universal bindings
        for i in range(len(buttons)):
            dialog.bind(str(i+1), lambda e, idx=i: btn_widgets[idx].invoke())
            dialog.bind(f'<KP_{i+1}>', lambda e, idx=i: btn_widgets[idx].invoke())
        
        dialog.bind('<Left>', lambda e: navigate_buttons(-1))
        dialog.bind('<Right>', lambda e: navigate_buttons(1))
        dialog.bind('<Tab>', lambda e: navigate_buttons(1))
        dialog.bind('<Shift-Tab>', lambda e: navigate_buttons(-1))
        dialog.bind('<Return>', lambda e: activate_selected())
        dialog.bind('<KP_Enter>', lambda e: activate_selected())
        dialog.bind('<period>', lambda e: close_dialog(None))
        dialog.bind('<KP_Decimal>', lambda e: close_dialog(None))
        dialog.bind('<Escape>', lambda e: close_dialog(None))
        dialog.bind('<space>', lambda e: activate_selected())
        
        select_button(0)
        dialog.focus_set()
        
        # Multiple focus attempts
        dialog.after(100, lambda: dialog.focus_force())
        
        dialog.wait_window()
        return result[0]
    # ==== ADMIN DATA MANAGER - ENHANCED WITH DUAL AUTH MODE ====
class AdminDataManager:
    def __init__(self, data_path: str):
        self.data_path = data_path
        self.admin_file = os.path.join(data_path, "admin_data.json")
        self.data = self._load_data()
        logger.info(f"✅ AdminDataManager khởi tạo - Mode: {self.get_authentication_mode()}")
    
    def _load_data(self):
        default_data = {
            "system_passcode": "1234",
            "valid_rfid_uids": [[0x1b, 0x93, 0xf2, 0x3c]],
            "fingerprint_ids": [1, 2, 3],
            "authentication_mode": "sequential",  # NEW: "sequential" hoặc "any"
            "mode_change_history": []  # NEW: Lịch sử thay đổi chế độ
        }
        
        try:
            if os.path.exists(self.admin_file):
                with open(self.admin_file, 'r') as f:
                    data = json.load(f)
                    # Ensure all default keys exist
                    for key, value in default_data.items():
                        if key not in data:
                            data[key] = value
                            logger.info(f"Added missing key: {key} = {value}")
                    return data
            else:
                os.makedirs(os.path.dirname(self.admin_file), exist_ok=True)
                self._save_data(default_data)
                logger.info("Created new admin_data.json with defaults")
                return default_data
        except Exception as e:
            logger.error(f"Lỗi load admin data: {e}")
            return default_data
    
    def _save_data(self, data=None):
        try:
            if data is None:
                data = self.data
            with open(self.admin_file, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Lỗi save admin data: {e}")
            return False
    
    # ==== EXISTING METHODS - UNCHANGED ====
    def get_passcode(self):
        return self.data["system_passcode"]
    
    def set_passcode(self, new_passcode):
        self.data["system_passcode"] = new_passcode
        return self._save_data()
    
    def get_rfid_uids(self):
        return self.data["valid_rfid_uids"].copy()
    
    def add_rfid(self, uid_list):
        if uid_list not in self.data["valid_rfid_uids"]:
            self.data["valid_rfid_uids"].append(uid_list)
            return self._save_data()
        return False
    
    def remove_rfid(self, uid_list):
        if uid_list in self.data["valid_rfid_uids"]:
            self.data["valid_rfid_uids"].remove(uid_list)
            return self._save_data()
        return False
    
    def get_fingerprint_ids(self):
        return self.data["fingerprint_ids"].copy()
    
    def add_fingerprint_id(self, fp_id):
        if fp_id not in self.data["fingerprint_ids"]:
            self.data["fingerprint_ids"].append(fp_id)
            return self._save_data()
        return False
    
    def remove_fingerprint_id(self, fp_id):
        if fp_id in self.data["fingerprint_ids"]:
            self.data["fingerprint_ids"].remove(fp_id)
            return self._save_data()
        return False
    
    # ==== NEW AUTHENTICATION MODE METHODS ====
    def get_authentication_mode(self):
        """Lấy chế độ xác thực hiện tại"""
        return self.data.get("authentication_mode", "sequential")
    
    def set_authentication_mode(self, mode):
        """Đặt chế độ xác thực: 'sequential' hoặc 'any'"""
        if mode not in ["sequential", "any"]:
            logger.error(f"Invalid authentication mode: {mode}")
            return False
        
        old_mode = self.get_authentication_mode()
        if old_mode == mode:
            return True  # No change needed
        
        # Update mode
        self.data["authentication_mode"] = mode
        
        # Log history
        history_entry = {
            "timestamp": datetime.now().isoformat(),
            "from_mode": old_mode,
            "to_mode": mode,
            "user": "admin"  # Could be enhanced to track specific user
        }
        
        if "mode_change_history" not in self.data:
            self.data["mode_change_history"] = []
        
        self.data["mode_change_history"].append(history_entry)
        
        # Keep only last 50 entries
        if len(self.data["mode_change_history"]) > 50:
            self.data["mode_change_history"] = self.data["mode_change_history"][-50:]
        
        success = self._save_data()
        if success:
            logger.info(f"✅ Authentication mode changed: {old_mode} → {mode}")
        else:
            logger.error(f"❌ Failed to save authentication mode change")
        
        return success
    
    def is_sequential_mode(self):
        """Kiểm tra có phải chế độ tuần tự không"""
        return self.get_authentication_mode() == "sequential"
    
    def is_any_mode(self):
        """Kiểm tra có phải chế độ đơn lẻ không"""
        return self.get_authentication_mode() == "any"
    
    def get_mode_display_name(self):
        """Lấy tên hiển thị của chế độ hiện tại"""
        mode = self.get_authentication_mode()
        return "TUẦN TỰ 4 LỚP" if mode == "sequential" else "ĐƠN LẺ (BẤT KỲ)"
    
    def get_mode_description(self):
        """Lấy mô tả chi tiết của chế độ hiện tại"""
        mode = self.get_authentication_mode()
        if mode == "sequential":
            return """Chế độ bảo mật cao:
• Phải vượt qua TẤT CẢ 4 lớp
• Khuôn mặt → Vân tay → Thẻ từ → Mật khẩu
• Thất bại bất kỳ lớp nào → Khởi động lại"""
        else:
            return """Chế độ truy cập nhanh:
• Chỉ cần 1 trong 4 lớp thành công
• Bất kỳ sensor nào đúng → Mở khóa ngay
• Độ bảo mật thấp hơn"""
    
    def get_mode_change_history(self, limit=10):
        """Lấy lịch sử thay đổi chế độ"""
        history = self.data.get("mode_change_history", [])
        return history[-limit:] if history else []
    
    def validate_mode_configuration(self):
        """Kiểm tra tính hợp lệ của cấu hình chế độ"""
        mode = self.get_authentication_mode()
        
        # Basic validation
        if mode not in ["sequential", "any"]:
            logger.error(f"Invalid mode in config: {mode}")
            return False
        
        # Check if we have at least one authentication method configured
        has_face = True  # Face recognition always available
        has_fingerprint = len(self.get_fingerprint_ids()) > 0
        has_rfid = len(self.get_rfid_uids()) > 0
        has_passcode = len(self.get_passcode()) >= 4
        
        auth_methods = sum([has_face, has_fingerprint, has_rfid, has_passcode])
        
        if mode == "any" and auth_methods < 1:
            logger.warning("No authentication methods configured for 'any' mode")
            return False
        
        if mode == "sequential" and auth_methods < 4:
            logger.warning(f"Only {auth_methods}/4 authentication methods configured for sequential mode")
            # Still valid, but suboptimal
        
        return True
    # ==== IMPROVED ADMIN GUI - ENHANCED WITH DUAL AUTH MODE ====
# ==== IMPROVED ADMIN GUI - SIMPLIFIED & CLEAN ====
class ImprovedAdminGUI:
    def __init__(self, parent, system):
        self.parent = parent
        self.system = system
        self.admin_window = None
        self.selected = 0
        
        # CLEAN options - no unnecessary icons
        self.options = [
            ("1", "Đổi mật khẩu hệ thống"),
            ("2", "Thêm thẻ RFID mới"), 
            ("3", "Xóa thẻ RFID"),
            ("4", "Đăng ký vân tay"),
            ("5", "Xóa vân tay"),
            ("6", "Chuyển đổi chế độ xác thực"),
            ("7", "Xem thống kê hệ thống"),
            ("8", "Thoát admin")
        ]
        self.buttons = []
        
        logger.info("✅ ImprovedAdminGUI khởi tạo - simplified interface")
    
    def show_admin_panel(self):
        """Show admin panel - clean and focused"""
        if self.admin_window:
            self._force_focus()
            return
            
        self.admin_window = tk.Toplevel(self.parent)
        self.admin_window.title("QUAN TRI HE THONG")
        
        # Enlarged size for 8 options
        self.admin_window.geometry("950x750")
        self.admin_window.configure(bg=Colors.DARK_BG)
        self.admin_window.transient(self.parent)
        self.admin_window.grab_set()
        
        # Focus management
        self.admin_window.lift()
        self.admin_window.focus_force()
        
        # Centered position
        x = (self.admin_window.winfo_screenwidth() // 2) - 475
        y = (self.admin_window.winfo_screenheight() // 2) - 375
        self.admin_window.geometry(f'950x750+{x}+{y}')
        
        self._create_widgets()
        self._setup_bindings()
        self._update_selection()
        
        self._force_focus()
        
        logger.info("✅ Admin panel displayed - clean interface")
    
    def _force_focus(self):
        """Force focus về admin window"""
        if self.admin_window and self.admin_window.winfo_exists():
            self.admin_window.lift()
            self.admin_window.focus_force()
            self.admin_window.grab_set()
            self.admin_window.after(50, lambda: self.admin_window.focus_set())
    
    def _create_widgets(self):
        # CLEAN Header
        header = tk.Frame(self.admin_window, bg=Colors.PRIMARY, height=120)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        # Main title only
        tk.Label(header, text="BẢNG ĐIỀU KHIỂN QUẢN TRỊ",
                font=('Arial', 26, 'bold'), fg='white', bg=Colors.PRIMARY).pack(pady=(20, 10))
        
        # SIMPLE mode indicator - no fancy styling
        current_mode = self.system.admin_data.get_authentication_mode()
        mode_text = "TUẦN TỰ" if current_mode == "sequential" else "ĐƠN LẺ"
        
        tk.Label(header, text=f"Chế độ: {mode_text}",
                font=('Arial', 16), fg='white', bg=Colors.PRIMARY).pack(pady=(0, 15))
        
        # CLEAN Menu frame
        menu_frame = tk.Frame(self.admin_window, bg=Colors.CARD_BG)
        menu_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=25)  
        
        self.buttons = []
        
        # SIMPLE colors - no special highlighting
        colors = [
            Colors.WARNING,    # 1
            Colors.SUCCESS,    # 2
            Colors.ERROR,      # 3
            Colors.PRIMARY,    # 4
            Colors.ACCENT,     # 5
            Colors.WARNING,    # 6 - mode toggle
            Colors.PRIMARY,    # 7
            Colors.TEXT_SECONDARY  # 8
        ]
        
        for i, (num, text) in enumerate(self.options):
            btn = tk.Button(menu_frame, 
                           text=f"{num}. {text}",  # NO ICONS
                           font=('Arial', 17, 'bold'), height=2,
                           bg=colors[i], fg='white', relief=tk.RAISED, bd=5,
                           anchor='w',
                           command=lambda idx=i: self._select_option(idx))
            
            btn.pack(fill=tk.X, pady=8, padx=25)
            self.buttons.append(btn)
        
        # SIMPLE footer
        footer = tk.Frame(self.admin_window, bg=Colors.DARK_BG, height=50)
        footer.pack(fill=tk.X)
        footer.pack_propagate(False)
        
        tk.Label(footer, text="Phím 1-8: Chọn | Enter: Xác nhận | Esc: Thoát",
                font=('Arial', 12), fg='lightgray', bg=Colors.DARK_BG).pack(expand=True)

    def _setup_bindings(self):
        """Clean keyboard bindings"""
        # Number keys 1-8
        for i in range(len(self.options)):
            self.admin_window.bind(str(i+1), lambda e, idx=i: self._select_option(idx))
            self.admin_window.bind(f'<KP_{i+1}>', lambda e, idx=i: self._select_option(idx))
        
        # Navigation
        self.admin_window.bind('<Up>', lambda e: self._navigate(-1))
        self.admin_window.bind('<Down>', lambda e: self._navigate(1))
        self.admin_window.bind('<Tab>', lambda e: self._navigate(1))
        self.admin_window.bind('<Shift-Tab>', lambda e: self._navigate(-1))
        
        # Action keys
        self.admin_window.bind('<Return>', lambda e: self._confirm())
        self.admin_window.bind('<KP_Enter>', lambda e: self._confirm())
        self.admin_window.bind('<space>', lambda e: self._confirm())
        self.admin_window.bind('<Escape>', lambda e: self._close())
        
        self.admin_window.focus_set()
        logger.debug("✅ Clean admin bindings configured")
    
    def _navigate(self, direction):
        """Simple navigation"""
        self.selected = (self.selected + direction) % len(self.options)
        self._update_selection()
    
    def _select_option(self, idx):
        """Clean option selection"""
        if 0 <= idx < len(self.options):
            self.selected = idx
            self._update_selection()
            self.admin_window.after(300, self._confirm)
    
    def _update_selection(self):
        """Simple selection update"""
        for i, btn in enumerate(self.buttons):
            if i == self.selected:
                btn.config(relief=tk.SUNKEN, bd=7)
            else:
                btn.config(relief=tk.RAISED, bd=5)
    
    def _confirm(self):
        """Execute selected action"""
        actions = [
            self._change_passcode,
            self._add_rfid,
            self._remove_rfid,
            self._add_fingerprint,
            self._remove_fingerprint,
            self._toggle_authentication_mode,
            self._show_statistics,
            self._close
        ]
        
        if 0 <= self.selected < len(actions):
            actions[self.selected]()

    # ==== SIMPLIFIED MODE TOGGLE ====
    def _toggle_authentication_mode(self):
        """SIMPLIFIED mode toggle - no lengthy descriptions"""
        try:
            current_mode = self.system.admin_data.get_authentication_mode()
            
            if current_mode == "sequential":
                new_mode = "any"
                new_mode_name = "ĐƠN LẺ"
                description = "Chuyển sang chế độ đơn lẻ?\n\nBất kỳ sensor nào đúng sẽ mở khóa ngay."
            else:
                new_mode = "sequential"
                new_mode_name = "TUẦN TỰ"
                description = "Chuyển sang chế độ tuần tự?\n\nPhải vượt qua tất cả 4 lớp theo thứ tự."
            
            # SIMPLE confirmation
            if EnhancedMessageBox.ask_yesno(
                self.admin_window, 
                f"Chuyển sang {new_mode_name}",
                description,
                self.system.buzzer
            ):
                if self.system.admin_data.set_authentication_mode(new_mode):
                    self.system.buzzer.beep("mode_change")
                    
                    # SIMPLE success message
                    EnhancedMessageBox.show_success(
                        self.admin_window, 
                        "Thành công", 
                        f"Đã chuyển sang chế độ {new_mode_name}.\n\nHệ thống sẽ khởi động lại.",
                        self.system.buzzer
                    )
                    
                    # Discord notification - simple
                    if self.system.discord_bot:
                        discord_msg = f"Chế độ xác thực đã chuyển: {new_mode_name}"
                        threading.Thread(
                            target=self.system._send_discord_notification,
                            args=(discord_msg,),
                            daemon=True
                        ).start()
                    
                    logger.info(f"✅ Mode changed: {current_mode} → {new_mode}")
                    
                    # Close and restart
                    self.admin_window.destroy()
                    self.admin_window = None
                    
                    self.system.gui.update_status(f"Chế độ: {new_mode_name} - Đang khởi động lại", 'lightblue')
                    self.system.root.after(3000, self.system.start_authentication)
                    
                else:
                    EnhancedMessageBox.show_error(
                        self.admin_window, 
                        "Lỗi", 
                        "Không thể thay đổi chế độ.",
                        self.system.buzzer
                    )
                    
            # Always return focus
            self._force_focus()
                    
        except Exception as e:
            EnhancedMessageBox.show_error(
                self.admin_window, 
                "Lỗi", 
                f"Lỗi hệ thống: {str(e)}",
                self.system.buzzer
            )
            self._force_focus()

    # ==== SIMPLIFIED STATISTICS ====
    def _show_statistics(self):
        """CLEAN statistics display"""
        try:
            face_info = self.face_recognizer.get_database_info()
            rfid_count = len(self.system.admin_data.get_rfid_uids())
            fp_count = len(self.system.admin_data.get_fingerprint_ids())
            current_mode = self.system.admin_data.get_authentication_mode()
            mode_display = "TUẦN TỰ" if current_mode == "sequential" else "ĐƠN LẺ"
            
            # SIMPLE stats text
            stats_text = f"""THỐNG KÊ HỆ THỐNG

NHẬN DIỆN KHUÔN MẶT:
Số người đã đăng ký: {face_info['total_people']}
Tổng ảnh training: {sum(p['face_count'] for p in face_info['people'].values())}

VÂN TAY:
Số vân tay đã lưu: {fp_count}

RFID:
Số thẻ hợp lệ: {rfid_count}

CHẾ ĐỘ XÁC THỰC:
Hiện tại: {mode_display}

TRẠNG THÁI:
Discord Bot: {'Online' if self.system.discord_bot else 'Offline'}
Phiên bản: v2.3"""
            
            EnhancedMessageBox.show_info(self.admin_window, "Thống kê", stats_text, self.system.buzzer)
            self._force_focus()
            
        except Exception as e:
            EnhancedMessageBox.show_error(self.admin_window, "Lỗi", f"Lỗi lấy thống kê: {str(e)}", self.system.buzzer)
            self._force_focus()
    
    # ==== EXISTING METHODS - KEEP AS IS ====
    def _change_passcode(self):
        dialog = EnhancedNumpadDialog(self.admin_window, "Đổi mật khẩu", 
                                   "Nhập mật khẩu mới:", True, self.system.buzzer)
        new_pass = dialog.show()
        self._force_focus()
        
        if new_pass and 4 <= len(new_pass) <= 8:
            if self.system.admin_data.set_passcode(new_pass):
                EnhancedMessageBox.show_success(self.admin_window, "Thành công", 
                                            f"Đã cập nhật mật khẩu.", self.system.buzzer)
                self._force_focus()
            else:
                EnhancedMessageBox.show_error(self.admin_window, "Lỗi", 
                                          "Không thể lưu mật khẩu.", self.system.buzzer)
                self._force_focus()
        elif new_pass:
            EnhancedMessageBox.show_error(self.admin_window, "Lỗi", 
                                      "Mật khẩu phải có từ 4-8 chữ số.", self.system.buzzer)
            self._force_focus()
    
    def _add_rfid(self):
        EnhancedMessageBox.show_info(self.admin_window, "Thêm thẻ RFID", 
                                 "Đặt thẻ lên đầu đọc trong 10 giây.", self.system.buzzer)
        self._force_focus()
        
        def scan():
            try:
                uid = self.system.pn532.read_passive_target(timeout=10)
                if uid:
                    uid_list = list(uid)
                    if self.system.admin_data.add_rfid(uid_list):
                        self.admin_window.after(0, lambda: self._show_result("success", "Thành công", "Thẻ đã được thêm."))
                    else:
                        self.admin_window.after(0, lambda: self._show_result("error", "Lỗi", "Thẻ đã tồn tại."))
                else:
                    self.admin_window.after(0, lambda: self._show_result("error", "Lỗi", "Không phát hiện thẻ."))
            except Exception as e:
                self.admin_window.after(0, lambda: self._show_result("error", "Lỗi", f"Lỗi đọc thẻ: {str(e)}"))
        
        threading.Thread(target=scan, daemon=True).start()
    
    def _show_result(self, msg_type, title, message):
        """Simple result display"""
        if msg_type == "success":
            EnhancedMessageBox.show_success(self.admin_window, title, message, self.system.buzzer)
        else:
            EnhancedMessageBox.show_error(self.admin_window, title, message, self.system.buzzer)
        self._force_focus()
    
    def _remove_rfid(self):
        uids = self.system.admin_data.get_rfid_uids()
        if not uids:
            EnhancedMessageBox.show_info(self.admin_window, "Thông báo", 
                                     "Không có thẻ nào.", self.system.buzzer)
            self._force_focus()
            return
        
        self._show_selection_dialog("Chọn thẻ cần xóa", 
                                   [f"Thẻ {i+1}: {uid}" for i, uid in enumerate(uids)], 
                                   lambda idx: self._do_remove_rfid(uids[idx]))
    
    def _add_fingerprint(self):
        EnhancedMessageBox.show_info(self.admin_window, "Đăng ký vân tay", 
                                "Chuẩn bị đăng ký vân tay mới.", self.system.buzzer)
        self._force_focus()
        
        def enroll():
            try:
                # Find empty position
                pos = None
                for i in range(1, 200):
                    try:
                        self.system.fingerprint.loadTemplate(i, 0x01)
                    except:
                        pos = i
                        break
                
                if pos is None:
                    self.admin_window.after(0, lambda: self._show_result("error", "Lỗi", "Bộ nhớ vân tay đã đầy."))
                    return
                
                # Step 1
                self.admin_window.after(0, lambda: EnhancedMessageBox.show_info(
                    self.admin_window, "Bước 1", "Đặt ngón tay lần đầu.", self.system.buzzer))
                
                timeout = 15
                start_time = time.time()
                
                while not self.system.fingerprint.readImage():
                    if time.time() - start_time > timeout:
                        self.admin_window.after(0, lambda: self._show_result("error", "Hết thời gian", "Hết thời gian quét."))
                        return
                    time.sleep(0.1)
                
                self.system.fingerprint.convertImage(0x01)
                self.system.buzzer.beep("click")
                
                # Step 2
                self.admin_window.after(0, lambda: EnhancedMessageBox.show_info(
                    self.admin_window, "Bước 2", "Nhấc tay rồi đặt lại.", self.system.buzzer))
                
                while self.system.fingerprint.readImage():
                    time.sleep(0.1)
                time.sleep(1)
                
                start_time = time.time()
                while not self.system.fingerprint.readImage():
                    if time.time() - start_time > timeout:
                        self.admin_window.after(0, lambda: self._show_result("error", "Hết thời gian", "Hết thời gian quét lần 2."))
                        return
                    time.sleep(0.1)
                
                self.system.fingerprint.convertImage(0x02)
                self.system.buzzer.beep("click")
                
                # Create and store
                self.system.fingerprint.createTemplate()
                self.system.fingerprint.storeTemplate(pos, 0x01)
                
                if self.system.admin_data.add_fingerprint_id(pos):
                    self.admin_window.after(0, lambda: self._show_success_and_return(pos))
                else:
                    self.admin_window.after(0, lambda: self._show_result("error", "Lỗi", "Không thể lưu vào database."))
                
            except Exception as e:
                self.admin_window.after(0, lambda: self._show_result("error", "Lỗi", f"Lỗi đăng ký: {str(e)}"))
        
        threading.Thread(target=enroll, daemon=True).start()

    def _show_success_and_return(self, pos):
        """Simple success and return"""
        EnhancedMessageBox.show_success(self.admin_window, "Thành công", f"Đã đăng ký vân tay tại vị trí {pos}.", self.system.buzzer)
        
        if self.admin_window:
            self.admin_window.destroy()
            self.admin_window = None
        
        self.system.root.after(500, lambda: self.show_admin_panel())
    
    def _remove_fingerprint(self):
        fp_ids = self.system.admin_data.get_fingerprint_ids()
        if not fp_ids:
            EnhancedMessageBox.show_info(self.admin_window, "Thông báo", 
                                     "Không có vân tay nào.", self.system.buzzer)
            self._force_focus()
            return
        
        self._show_selection_dialog("Chọn vân tay cần xóa", 
                                   [f"Vân tay ID: {fid}" for fid in fp_ids], 
                                   lambda idx: self._do_remove_fingerprint(fp_ids[idx]))
    
    def _show_selection_dialog(self, title, items, callback):
        """SIMPLIFIED selection dialog"""
        sel_window = tk.Toplevel(self.admin_window)
        sel_window.title(title)
        sel_window.geometry("600x500")
        sel_window.configure(bg=Colors.DARK_BG)
        sel_window.transient(self.admin_window)
        sel_window.grab_set()
        
        sel_window.lift()
        sel_window.focus_force()
        
        x = (sel_window.winfo_screenwidth() // 2) - 300
        y = (sel_window.winfo_screenheight() // 2) - 250
        sel_window.geometry(f'600x500+{x}+{y}')
        
        selected = [0]
        buttons = []
        
        # Simple header
        header = tk.Frame(sel_window, bg=Colors.ERROR, height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        tk.Label(header, text=title, font=('Arial', 18, 'bold'),
                fg='white', bg=Colors.ERROR).pack(expand=True)
        
        # Simple list
        list_frame = tk.Frame(sel_window, bg=Colors.CARD_BG)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        for i, item in enumerate(items):
            btn = tk.Button(list_frame, text=f"{i+1}. {item}",
                           font=('Arial', 14, 'bold'), height=2,
                           bg=Colors.ERROR, fg='white', relief=tk.RAISED, bd=4,
                           command=lambda idx=i: self._handle_selection_callback(callback, idx, sel_window))
            btn.pack(fill=tk.X, pady=5, padx=10)
            buttons.append(btn)
        
        # Cancel button
        cancel_btn = tk.Button(sel_window, text="Hủy bỏ", font=('Arial', 14, 'bold'),
                 bg=Colors.TEXT_SECONDARY, fg='white', height=2,
                 command=lambda: self._handle_selection_cancel(sel_window))
        cancel_btn.pack(pady=15)
        buttons.append(cancel_btn)
        
        # Simple navigation
        def update_selection():
            for i, btn in enumerate(buttons):
                if i == selected[0]:
                    btn.config(relief=tk.SUNKEN, bd=6)
                else:
                    btn.config(relief=tk.RAISED, bd=4)
        
        def navigate(direction):
            selected[0] = (selected[0] + direction) % len(buttons)
            update_selection()
        
        def activate():
            buttons[selected[0]].invoke()
        
        # Simple bindings
        for i in range(min(len(items), 9)):
            sel_window.bind(str(i+1), lambda e, idx=i: buttons[idx].invoke())
        
        sel_window.bind('<Up>', lambda e: navigate(-1))
        sel_window.bind('<Down>', lambda e: navigate(1))
        sel_window.bind('<Return>', lambda e: activate())
        sel_window.bind('<Escape>', lambda e: sel_window.destroy())
        
        update_selection()
        sel_window.focus_set()
    
    def _handle_selection_callback(self, callback, idx, window):
        window.destroy()
        callback(idx)
        self._force_focus()
    
    def _handle_selection_cancel(self, window):
        window.destroy()
        self._force_focus()
    
    def _do_remove_rfid(self, uid):
        if EnhancedMessageBox.ask_yesno(self.admin_window, "Xác nhận", 
                                    f"Xóa thẻ RFID?\n\nUID: {uid}", self.system.buzzer):
            if self.system.admin_data.remove_rfid(uid):
                EnhancedMessageBox.show_success(self.admin_window, "Thành công", "Đã xóa thẻ RFID.", self.system.buzzer)
            else:
                EnhancedMessageBox.show_error(self.admin_window, "Lỗi", "Không thể xóa thẻ.", self.system.buzzer)
        self._force_focus()
    
    def _do_remove_fingerprint(self, fp_id):
        if EnhancedMessageBox.ask_yesno(self.admin_window, "Xác nhận", 
                                    f"Xóa vân tay ID: {fp_id}?", self.system.buzzer):
            try:
                self.system.fingerprint.deleteTemplate(fp_id)
                self.system.admin_data.remove_fingerprint_id(fp_id)
                EnhancedMessageBox.show_success(self.admin_window, "Thành công", "Đã xóa vân tay.", self.system.buzzer)
            except Exception as e:
                EnhancedMessageBox.show_error(self.admin_window, "Lỗi", f"Lỗi xóa: {str(e)}", self.system.buzzer)
        self._force_focus()
    
    def _close(self):
        """Simple close confirmation"""
        if EnhancedMessageBox.ask_yesno(self.admin_window, "Thoát", 
                                    "Thoát chế độ quản trị?", self.system.buzzer):
            logger.info("Admin panel closed")
            self.admin_window.destroy()
            self.admin_window = None
            self.system.start_authentication()
        else:
            self._force_focus()
    # ==== MAIN ENTRY POINT ====
if __name__ == "__main__":
    print("🔧 ENHANCED COMPONENTS v2.3 - DUAL AUTHENTICATION MODE")
    print("=" * 80)
    print("✅ AdminDataManager với dual authentication mode support")
    print("✅ ImprovedAdminGUI với 8 options và mode toggle")
    print("✅ Enhanced UI/UX với better focus management")
    print("✅ Discord integration cho mode changes")
    print("✅ Comprehensive error handling")
    print("✅ Universal keyboard support")
    print("✅ Backward compatibility 100%")
    print()
    print("🆕 NEW FEATURES:")
    print("   🔄 Authentication Mode Toggle:")
    print("      • Sequential: 4-layer security (Face→Finger→RFID→PIN)")
    print("      • Any: Single-layer access (any sensor success = unlock)")
    print("   📊 Enhanced Statistics với mode history")
    print("   🎨 Enlarged admin panel (1000x800)")
    print("   🔊 Mode change sound patterns")
    print("   📱 Discord notifications cho mode switches")
    print()
    print("⌨️  KEYBOARD SHORTCUTS:")
    print("   1-8: Quick option selection")
    print("   F1: Quick mode toggle")
    print("   ↑↓: Navigate options")
    print("   Enter/Space: Confirm")
    print("   Esc/.: Cancel/Exit")
    print()
    print("🔧 CONFIGURATION:")
    print(f"   📁 Default config file: admin_data.json")
    print(f"   🔧 Default mode: sequential")
    print(f"   📝 Mode history: Last 50 changes")
    print(f"   🔄 Auto-restart: After mode change")
    print()
    print("=" * 80)
    print("🚀 Ready for integration with main security system!")
    print("=" * 80)
