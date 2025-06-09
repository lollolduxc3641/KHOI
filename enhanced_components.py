#!/usr/bin/env python3
"""
Enhanced Components cho hệ thống khóa bảo mật
Phiên bản tối ưu - Loại bỏ icon và cải thiện logic
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
            "startup": [(1000, 0.4, 0.2), (1500, 0.4, 0.2), (2000, 0.4, 0.3)]
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
        
        # Center dialog
        x = (self.dialog.winfo_screenwidth() // 2) - 300
        y = (self.dialog.winfo_screenheight() // 2) - 375
        self.dialog.geometry(f'600x750+{x}+{y}')
        
        self._create_widgets()
        self._setup_bindings()
        self._highlight_button()
        
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
        # Số từ bàn phím
        for i in range(10):
            self.dialog.bind(str(i), lambda e, key=str(i): self._on_key_click(key))
            self.dialog.bind(f'<KP_{i}>', lambda e, key=str(i): self._on_key_click(key))
        
        # Phím đặc biệt - ĐÃ TỐI ƯU
        self.dialog.bind('<Return>', lambda e: self._on_ok())
        self.dialog.bind('<KP_Enter>', lambda e: self._on_ok())
        self.dialog.bind('<period>', lambda e: self._on_cancel())  # Dấu "." để thoát
        self.dialog.bind('<KP_Decimal>', lambda e: self._on_cancel())  # Dấu "." trên keypad
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

# ==== ENHANCED MESSAGE BOX - TỐI ƯU ====
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
        dialog.geometry("650x400")
        dialog.configure(bg=Colors.DARK_BG)
        dialog.transient(parent)
        dialog.grab_set()
        
        x = (dialog.winfo_screenwidth() // 2) - 325
        y = (dialog.winfo_screenheight() // 2) - 200
        dialog.geometry(f'650x400+{x}+{y}')
        
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
        
        tk.Label(msg_frame, text=message, font=('Arial', 18),
                fg=Colors.TEXT_PRIMARY, bg=Colors.CARD_BG, 
                wraplength=600, justify=tk.CENTER).pack(expand=True)
        
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
        
        # TỐI ƯU BINDINGS
        for i in range(len(buttons)):
            dialog.bind(str(i+1), lambda e, idx=i: btn_widgets[idx].invoke())
        
        dialog.bind('<Left>', lambda e: navigate_buttons(-1))
        dialog.bind('<Right>', lambda e: navigate_buttons(1))
        dialog.bind('<Tab>', lambda e: navigate_buttons(1))
        dialog.bind('<Shift-Tab>', lambda e: navigate_buttons(-1))
        dialog.bind('<Return>', lambda e: activate_selected())  # Enter để xác nhận
        dialog.bind('<KP_Enter>', lambda e: activate_selected())
        dialog.bind('<period>', lambda e: close_dialog(None))  # Dấu "." để thoát
        dialog.bind('<KP_Decimal>', lambda e: close_dialog(None))
        dialog.bind('<Escape>', lambda e: close_dialog(None))
        dialog.bind('<space>', lambda e: activate_selected())
        
        select_button(0)
        dialog.focus_set()
        dialog.wait_window()
        return result[0]

# ==== ADMIN DATA MANAGER ====
class AdminDataManager:
    def __init__(self, data_path: str):
        self.data_path = data_path
        self.admin_file = os.path.join(data_path, "admin_data.json")
        self.data = self._load_data()
    
    def _load_data(self):
        default_data = {
            "system_passcode": "1234",
            "valid_rfid_uids": [[0x1b, 0x93, 0xf2, 0x3c]],
            "fingerprint_ids": [1, 2, 3]
        }
        
        try:
            if os.path.exists(self.admin_file):
                with open(self.admin_file, 'r') as f:
                    data = json.load(f)
                    for key, value in default_data.items():
                        if key not in data:
                            data[key] = value
                    return data
            else:
                os.makedirs(os.path.dirname(self.admin_file), exist_ok=True)
                self._save_data(default_data)
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

# ==== IMPROVED ADMIN GUI - ĐÃ TỐI ƯU ====
class ImprovedAdminGUI:
    def __init__(self, parent, system):
        self.parent = parent
        self.system = system
        self.admin_window = None
        self.selected = 0
        # ĐÃ XÓA CHỨC NĂNG THÊM KHUÔN MẶT
        self.options = [
            ("1", "Đổi mật khẩu hệ thống"),
            ("2", "Thêm thẻ RFID mới"), 
            ("3", "Xóa thẻ RFID"),
            ("4", "Đăng ký vân tay"),
            ("5", "Xóa vân tay"),
            ("6", "Xem thống kê hệ thống"),
            ("7", "Thoát admin")
        ]
        self.buttons = []
    
    def show_admin_panel(self):
        if self.admin_window:
            return
            
        self.admin_window = tk.Toplevel(self.parent)
        self.admin_window.title("QUAN TRI HE THONG")
        self.admin_window.geometry("800x650")
        self.admin_window.configure(bg=Colors.DARK_BG)
        self.admin_window.transient(self.parent)
        self.admin_window.grab_set()
        
        x = (self.admin_window.winfo_screenwidth() // 2) - 400
        y = (self.admin_window.winfo_screenheight() // 2) - 325
        self.admin_window.geometry(f'800x650+{x}+{y}')
        
        self._create_widgets()
        self._setup_bindings()
        self._update_selection()
    
    def _create_widgets(self):
        # Header
        header = tk.Frame(self.admin_window, bg=Colors.PRIMARY, height=100)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        tk.Label(header, text="BANG DIEU KHIEN ADMIN",
                font=('Arial', 28, 'bold'), fg='white', bg=Colors.PRIMARY).pack(expand=True)
        
        # Menu
        menu_frame = tk.Frame(self.admin_window, bg=Colors.CARD_BG)
        menu_frame.pack(fill=tk.BOTH, expand=True, padx=25, pady=25)  
        
        self.buttons = []
        colors = [Colors.WARNING, Colors.SUCCESS, Colors.ERROR, Colors.PRIMARY, 
                 Colors.ACCENT, Colors.PRIMARY, Colors.TEXT_SECONDARY]
        
        for i, (num, text) in enumerate(self.options):
            # CHỈ HIỂN THỊ SỐ VÀ TEXT
            btn = tk.Button(menu_frame, text=f"{num}. {text}",
                           font=('Arial', 20, 'bold'), height=2,
                           bg=colors[i % len(colors)], fg='white', relief=tk.RAISED, bd=5,
                           anchor='w',
                           command=lambda idx=i: self._select_option(idx))
            btn.pack(fill=tk.X, pady=8, padx=20)
            self.buttons.append(btn)
    
    def _setup_bindings(self):
        # Number keys
        for i in range(len(self.options)):
            self.admin_window.bind(str(i+1), lambda e, idx=i: self._select_option(idx))
        
        # Navigation
        self.admin_window.bind('<Up>', lambda e: self._navigate(-1))
        self.admin_window.bind('<Down>', lambda e: self._navigate(1))
        self.admin_window.bind('<Tab>', lambda e: self._navigate(1))
        self.admin_window.bind('<Shift-Tab>', lambda e: self._navigate(-1))
        
        # Action keys - TỐI ƯU
        self.admin_window.bind('<Return>', lambda e: self._confirm())
        self.admin_window.bind('<KP_Enter>', lambda e: self._confirm())
        self.admin_window.bind('<space>', lambda e: self._confirm())
        self.admin_window.bind('<period>', lambda e: self._close())  # Dấu "." để thoát
        self.admin_window.bind('<KP_Decimal>', lambda e: self._close())
        self.admin_window.bind('<Escape>', lambda e: self._close())
        
        self.admin_window.focus_set()
    
    def _navigate(self, direction):
        self.selected = (self.selected + direction) % len(self.options)
        self._update_selection()
    
    def _select_option(self, idx):
        self.selected = idx
        self._update_selection()
        self.admin_window.after(300, self._confirm)
    
    def _update_selection(self):
        for i, btn in enumerate(self.buttons):
            if i == self.selected:
                btn.config(relief=tk.SUNKEN, bd=7)
            else:
                btn.config(relief=tk.RAISED, bd=5)
    
    def _confirm(self):
        actions = [
            self._change_passcode,
            self._add_rfid,
            self._remove_rfid, 
            self._add_fingerprint,
            self._remove_fingerprint,
            self._show_statistics,   # Chỉ còn 6 chức năng
            self._close
        ]
        
        if 0 <= self.selected < len(actions):
            actions[self.selected]()
    
    def _change_passcode(self):
        dialog = EnhancedNumpadDialog(self.admin_window, "Đổi mật khẩu", 
                                   "Nhập mật khẩu mới (4-8 số):", True, self.system.buzzer)
        new_pass = dialog.show()
        if new_pass and 4 <= len(new_pass) <= 8:
            if self.system.admin_data.set_passcode(new_pass):
                EnhancedMessageBox.show_success(self.admin_window, "Thành công", 
                                            f"Đã cập nhật mật khẩu!\nMật khẩu mới: {new_pass}", self.system.buzzer)
            else:
                EnhancedMessageBox.show_error(self.admin_window, "Lỗi", 
                                          "Không thể lưu mật khẩu!", self.system.buzzer)
        elif new_pass:
            EnhancedMessageBox.show_error(self.admin_window, "Lỗi", 
                                      "Mật khẩu phải có từ 4-8 chữ số!", self.system.buzzer)
    
    def _add_rfid(self):
        EnhancedMessageBox.show_info(self.admin_window, "Thêm thẻ RFID", 
                                 "Đặt thẻ RFID lên đầu đọc trong 10 giây...", self.system.buzzer)
        
        def scan():
            try:
                uid = self.system.pn532.read_passive_target(timeout=10)
                if uid:
                    uid_list = list(uid)
                    if self.system.admin_data.add_rfid(uid_list):
                        self.admin_window.after(0, lambda: EnhancedMessageBox.show_success(
                            self.admin_window, "Thành công", 
                            f"Thêm thẻ RFID thành công!\nUID: {uid_list}", self.system.buzzer))
                    else:
                        self.admin_window.after(0, lambda: EnhancedMessageBox.show_error(
                            self.admin_window, "Lỗi", 
                            f"Thẻ đã tồn tại!\nUID: {uid_list}", self.system.buzzer))
                else:
                    self.admin_window.after(0, lambda: EnhancedMessageBox.show_error(
                        self.admin_window, "Lỗi", 
                        "Không phát hiện thẻ RFID!", self.system.buzzer))
            except Exception as e:
                self.admin_window.after(0, lambda: EnhancedMessageBox.show_error(
                    self.admin_window, "Lỗi", f"Lỗi đọc thẻ: {str(e)}", self.system.buzzer))
        
        threading.Thread(target=scan, daemon=True).start()
    
    def _remove_rfid(self):
        uids = self.system.admin_data.get_rfid_uids()
        if not uids:
            EnhancedMessageBox.show_info(self.admin_window, "Thông báo", 
                                     "Không có thẻ RFID nào trong hệ thống!", self.system.buzzer)
            return
        
        self._show_selection_dialog("Chọn thẻ cần xóa", 
                                   [f"Thẻ {i+1}: {uid}" for i, uid in enumerate(uids)], 
                                   lambda idx: self._do_remove_rfid(uids[idx]))
    

    def _add_fingerprint(self):
        EnhancedMessageBox.show_info(self.admin_window, "Đăng ký vân tay", 
                                "Chuẩn bị đăng ký vân tay mới...", self.system.buzzer)
        
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
                    self.admin_window.after(0, lambda: EnhancedMessageBox.show_error(
                        self.admin_window, "Lỗi", "Bộ nhớ vân tay đã đầy!", self.system.buzzer))
                    return
                
                # Step 1
                self.admin_window.after(0, lambda: EnhancedMessageBox.show_info(
                    self.admin_window, "Bước 1/2", "Đặt ngón tay lần đầu...", self.system.buzzer))
                
                # Wait for first scan
                scan_timeout = 15  # 15 seconds timeout
                start_time = time.time()
                
                while not self.system.fingerprint.readImage():
                    if time.time() - start_time > scan_timeout:
                        self.admin_window.after(0, lambda: EnhancedMessageBox.show_error(
                            self.admin_window, "Hết thời gian", 
                            "Hết thời gian chờ quét vân tay!\nVui lòng thử lại.", self.system.buzzer))
                        return
                    time.sleep(0.1)
                
                self.system.fingerprint.convertImage(0x01)
                self.system.buzzer.beep("click")
                
                # Step 2
                self.admin_window.after(0, lambda: EnhancedMessageBox.show_info(
                    self.admin_window, "Bước 2/2", "Nhấc tay rồi đặt lại...", self.system.buzzer))
                
                # Wait for finger to be removed
                while self.system.fingerprint.readImage():
                    time.sleep(0.1)
                
                time.sleep(1)  # Short pause
                
                # Wait for second scan
                start_time = time.time()
                while not self.system.fingerprint.readImage():
                    if time.time() - start_time > scan_timeout:
                        self.admin_window.after(0, lambda: EnhancedMessageBox.show_error(
                            self.admin_window, "Hết thời gian", 
                            "Hết thời gian chờ quét lần 2!\nVui lòng thử lại.", self.system.buzzer))
                        return
                    time.sleep(0.1)
                
                self.system.fingerprint.convertImage(0x02)
                self.system.buzzer.beep("click")
                
                # Create and store template
                self.system.fingerprint.createTemplate()
                self.system.fingerprint.storeTemplate(pos, 0x01)
                
                # Save to admin data
                if self.system.admin_data.add_fingerprint_id(pos):
                    # SUCCESS - HIỂN THỊ THÔNG BÁO VÀ QUAY VỀ MENU
                    self.admin_window.after(0, lambda: self._show_success_and_return(pos))
                else:
                    self.admin_window.after(0, lambda: EnhancedMessageBox.show_error(
                        self.admin_window, "Lỗi", 
                        f"Không thể lưu vân tay vào database!\nVị trí: {pos}", self.system.buzzer))
                
            except Exception as e:
                self.admin_window.after(0, lambda: EnhancedMessageBox.show_error(
                    self.admin_window, "Lỗi", f"Lỗi đăng ký: {str(e)}", self.system.buzzer))
        
        # Chạy enrollment trong thread riêng
        threading.Thread(target=enroll, daemon=True).start()

    def _show_success_and_return(self, pos):
        """Hiển thị thông báo thành công và quay về menu admin"""
        # Hiển thị thông báo thành công
        EnhancedMessageBox.show_success(
            self.admin_window, 
            "Thành công", 
            f"Đăng ký vân tay thành công!\n\nVị trí lưu: {pos}\nTrạng thái: Đã thêm vào hệ thống\n\nQuay về menu admin...", 
            self.system.buzzer
        )
        
        # ĐÓNG CỬA SỔ ADMIN HIỆN TẠI VÀ MỞ LẠI MENU
        if self.admin_window:
            self.admin_window.destroy()
            self.admin_window = None
        
        # Delay ngắn rồi mở lại admin panel
        self.system.root.after(500, self.show_admin_panel)
    
    def _remove_fingerprint(self):
        fp_ids = self.system.admin_data.get_fingerprint_ids()
        if not fp_ids:
            EnhancedMessageBox.show_info(self.admin_window, "Thông báo", 
                                     "Không có vân tay nào trong hệ thống!", self.system.buzzer)
            return
        
        self._show_selection_dialog("Chọn vân tay cần xóa", 
                                   [f"Vân tay ID: {fid}" for fid in fp_ids], 
                                   lambda idx: self._do_remove_fingerprint(fp_ids[idx]))
    
    def _show_statistics(self):
        """Hiển thị thống kê hệ thống - CẢI THIỆN"""
        try:
            # Get stats
            face_info = self.system.face_recognizer.get_database_info()
            rfid_count = len(self.system.admin_data.get_rfid_uids())
            fp_count = len(self.system.admin_data.get_fingerprint_ids())
            
            stats_text = f"""THỐNG KÊ HỆ THỐNG:
            
AI Face Recognition:
   - Tổng số người: {face_info['total_people']}
   - Tổng ảnh training: {sum(p['face_count'] for p in face_info['people'].values())}

Vân tay:
   - Số vân tay đã đăng ký: {fp_count}

RFID:
   - Số thẻ hợp lệ: {rfid_count}

Bảo mật:
   - Trạng thái: Hoạt động tốt
   - Phiên bản: AI Enhanced v2.0"""
            
            EnhancedMessageBox.show_info(self.admin_window, "Thống kê", stats_text, self.system.buzzer)
            
        except Exception as e:
            EnhancedMessageBox.show_error(self.admin_window, "Lỗi", 
                                        f"Không thể lấy thống kê: {e}", self.system.buzzer)
    
    def _show_selection_dialog(self, title, items, callback):
        """Dialog chọn item - ĐÃ TỐI ƯU"""
        sel_window = tk.Toplevel(self.admin_window)
        sel_window.title(title)
        sel_window.geometry("600x500")
        sel_window.configure(bg=Colors.DARK_BG)
        sel_window.transient(self.admin_window)
        sel_window.grab_set()
        
        x = (sel_window.winfo_screenwidth() // 2) - 300
        y = (sel_window.winfo_screenheight() // 2) - 250
        sel_window.geometry(f'600x500+{x}+{y}')
        
        selected = [0]
        buttons = []
        
        # Header
        header = tk.Frame(sel_window, bg=Colors.ERROR, height=80)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        tk.Label(header, text=title, font=('Arial', 22, 'bold'),
                fg='white', bg=Colors.ERROR).pack(expand=True)
        
        # List frame
        list_frame = tk.Frame(sel_window, bg=Colors.CARD_BG)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=25, pady=25)
        
        # Buttons - CHỈ SỐ VÀ TEXT
        for i, item in enumerate(items):
            btn = tk.Button(list_frame, text=f"{i+1}. {item}",
                           font=('Arial', 18, 'bold'), height=2,
                           bg=Colors.ERROR, fg='white', relief=tk.RAISED, bd=5,
                           command=lambda idx=i: [callback(idx), sel_window.destroy()])
            btn.pack(fill=tk.X, pady=10, padx=15)
            buttons.append(btn)
        
        # Cancel button
        cancel_btn = tk.Button(sel_window, text="Hủy bỏ", font=('Arial', 18, 'bold'),
                 bg=Colors.TEXT_SECONDARY, fg='white', height=2,
                 command=sel_window.destroy)
        cancel_btn.pack(pady=20)
        buttons.append(cancel_btn)
        
        # Navigation
        def update_selection():
            for i, btn in enumerate(buttons):
                if i == selected[0]:
                    btn.config(relief=tk.SUNKEN, bd=7)
                else:
                    btn.config(relief=tk.RAISED, bd=5)
        
        def navigate(direction):
            selected[0] = (selected[0] + direction) % len(buttons)
            update_selection()
        
        def activate():
            buttons[selected[0]].invoke()
        
        # Bindings - TỐI ƯU
        for i in range(len(items)):
            sel_window.bind(str(i+1), lambda e, idx=i: buttons[idx].invoke())
        
        sel_window.bind('<Up>', lambda e: navigate(-1))
        sel_window.bind('<Down>', lambda e: navigate(1))
        sel_window.bind('<Tab>', lambda e: navigate(1))
        sel_window.bind('<Shift-Tab>', lambda e: navigate(-1))
        sel_window.bind('<Return>', lambda e: activate())
        sel_window.bind('<KP_Enter>', lambda e: activate())
        sel_window.bind('<space>', lambda e: activate())
        sel_window.bind('<period>', lambda e: sel_window.destroy())  # Dấu "." để thoát
        sel_window.bind('<KP_Decimal>', lambda e: sel_window.destroy())
        sel_window.bind('<Escape>', lambda e: sel_window.destroy())
        
        update_selection()
        sel_window.focus_set()
    
    def _do_remove_rfid(self, uid):
        if EnhancedMessageBox.ask_yesno(self.admin_window, "Xác nhận", 
                                    f"Xóa thẻ RFID?\nUID: {uid}", self.system.buzzer):
            if self.system.admin_data.remove_rfid(uid):
                EnhancedMessageBox.show_success(self.admin_window, "Thành công", 
                                              "Đã xóa thẻ!", self.system.buzzer)
            else:
                EnhancedMessageBox.show_error(self.admin_window, "Lỗi", 
                                            "Không thể xóa!", self.system.buzzer)
    
    def _do_remove_fingerprint(self, fp_id):
        if EnhancedMessageBox.ask_yesno(self.admin_window, "Xác nhận", 
                                    f"Xóa vân tay ID: {fp_id}?", self.system.buzzer):
            try:
                self.system.fingerprint.deleteTemplate(fp_id)
                self.system.admin_data.remove_fingerprint_id(fp_id)
                EnhancedMessageBox.show_success(self.admin_window, "Thành công", 
                                              "Đã xóa vân tay!", self.system.buzzer)
            except Exception as e:
                EnhancedMessageBox.show_error(self.admin_window, "Lỗi", 
                                            f"Lỗi: {str(e)}", self.system.buzzer)
    
    def _close(self):
        if EnhancedMessageBox.ask_yesno(self.admin_window, "Thoát Admin", 
                                    "Thoát chế độ quản trị?", self.system.buzzer):
            self.admin_window.destroy()
            self.admin_window = None
            self.system.start_authentication()
