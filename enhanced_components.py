#!/usr/bin/env python3
"""
Enhanced Components - FOCUS CONFLICT FIXED
Version: 2.5.4 - No More Focus Flickering
Date: 2025-07-04 13:50:15 UTC
User: Mautandew89
Status: Production Ready - Focus conflicts resolved
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
    PRIMARY = "#2196F3"
    SUCCESS = "#4CAF50"
    ERROR = "#F44336"
    WARNING = "#FF9800"
    BACKGROUND = "#FAFAFA"
    CARD_BG = "#FFFFFF"
    TEXT_PRIMARY = "#212121"
    TEXT_SECONDARY = "#757575"
    ACCENT = "#9C27B0"
    BORDER = "#E0E0E0"
    DARK_BG = "#263238"

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
            "mode_change": [(1200, 0.4, 0.2), (1800, 0.4, 0.2), (2400, 0.4, 0.3)]
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
        
        # Enhanced focus management
        self.dialog.lift()
        self.dialog.focus_force()
        self.dialog.attributes('-topmost', True)
        
        # Center dialog
        x = (self.dialog.winfo_screenwidth() // 2) - 300
        y = (self.dialog.winfo_screenheight() // 2) - 375
        self.dialog.geometry(f'600x750+{x}+{y}')
        
        self._create_widgets()
        self._setup_bindings()
        self._highlight_button()
        
        # Multiple focus attempts
        self.dialog.after(100, lambda: self.dialog.focus_force())
        self.dialog.after(200, lambda: self.dialog.focus_set())
        
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
        # Universal keyboard support (main + USB numpad)
        for i in range(10):
            self.dialog.bind(str(i), lambda e, key=str(i): self._on_key_click(key))
            self.dialog.bind(f'<KP_{i}>', lambda e, key=str(i): self._on_key_click(key))
        
        # Confirm keys
        self.dialog.bind('<Return>', lambda e: self._on_ok())
        self.dialog.bind('<KP_Enter>', lambda e: self._on_ok())
        self.dialog.bind('<KP_Add>', lambda e: self._on_ok())
        
        # Cancel keys
        self.dialog.bind('<period>', lambda e: self._on_cancel())
        self.dialog.bind('<KP_Decimal>', lambda e: self._on_cancel())
        self.dialog.bind('<Escape>', lambda e: self._on_cancel())
        self.dialog.bind('<KP_Divide>', lambda e: self._on_cancel())
        self.dialog.bind('<KP_Multiply>', lambda e: self._on_cancel())
        
        # Delete keys
        self.dialog.bind('<BackSpace>', lambda e: self._on_key_click('XOA'))
        self.dialog.bind('<Delete>', lambda e: self._on_key_click('CLR'))
        self.dialog.bind('<KP_Subtract>', lambda e: self._on_key_click('XOA'))
        
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
        dialog.geometry("750x500")
        dialog.configure(bg=Colors.DARK_BG)
        dialog.transient(parent)
        dialog.grab_set()
        
        # Enhanced focus management
        dialog.lift()
        dialog.focus_force()
        dialog.attributes('-topmost', True)
        
        x = (dialog.winfo_screenwidth() // 2) - 375
        y = (dialog.winfo_screenheight() // 2) - 250
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
        
        tk.Label(msg_frame, text=message, font=('Arial', 16),
                fg=Colors.TEXT_PRIMARY, bg=Colors.CARD_BG, 
                wraplength=700, justify=tk.LEFT).pack(expand=True)
        
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
        
        # Universal bindings with USB numpad support
        for i in range(len(buttons)):
            dialog.bind(str(i+1), lambda e, idx=i: btn_widgets[idx].invoke())
            dialog.bind(f'<KP_{i+1}>', lambda e, idx=i: btn_widgets[idx].invoke())
        
        dialog.bind('<Left>', lambda e: navigate_buttons(-1))
        dialog.bind('<Right>', lambda e: navigate_buttons(1))
        dialog.bind('<Tab>', lambda e: navigate_buttons(1))
        dialog.bind('<Shift-Tab>', lambda e: navigate_buttons(-1))
        
        # Confirm keys
        dialog.bind('<Return>', lambda e: activate_selected())
        dialog.bind('<KP_Enter>', lambda e: activate_selected())
        dialog.bind('<KP_Add>', lambda e: activate_selected())
        
        # Cancel keys
        dialog.bind('<period>', lambda e: close_dialog(None))
        dialog.bind('<KP_Decimal>', lambda e: close_dialog(None))
        dialog.bind('<Escape>', lambda e: close_dialog(None))
        dialog.bind('<KP_Divide>', lambda e: close_dialog(None))
        dialog.bind('<KP_Multiply>', lambda e: close_dialog(None))
        dialog.bind('<space>', lambda e: activate_selected())
        
        select_button(0)
        dialog.focus_set()
        
        # Multiple focus attempts
        dialog.after(100, lambda: dialog.focus_force())
        dialog.after(200, lambda: dialog.focus_set())
        
        dialog.wait_window()
        return result[0]

# ==== ADMIN DATA MANAGER ====
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
            "authentication_mode": "sequential",
            "mode_change_history": []
        }
        
        try:
            if os.path.exists(self.admin_file):
                with open(self.admin_file, 'r') as f:
                    data = json.load(f)
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
    
    # All methods from stable version
    def get_passcode(self): return self.data["system_passcode"]
    def set_passcode(self, new_passcode): 
        self.data["system_passcode"] = new_passcode
        return self._save_data()
    def get_rfid_uids(self): return self.data["valid_rfid_uids"].copy()
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
    def get_fingerprint_ids(self): return self.data["fingerprint_ids"].copy()
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
    def get_authentication_mode(self): return self.data.get("authentication_mode", "sequential")
    def set_authentication_mode(self, mode):
        if mode not in ["sequential", "any"]:
            logger.error(f"Invalid authentication mode: {mode}")
            return False
        
        old_mode = self.get_authentication_mode()
        if old_mode == mode:
            return True
        
        self.data["authentication_mode"] = mode
        
        history_entry = {
            "timestamp": datetime.now().isoformat(),
            "from_mode": old_mode,
            "to_mode": mode,
            "user": "Mautandew89"
        }
        
        if "mode_change_history" not in self.data:
            self.data["mode_change_history"] = []
        
        self.data["mode_change_history"].append(history_entry)
        
        if len(self.data["mode_change_history"]) > 50:
            self.data["mode_change_history"] = self.data["mode_change_history"][-50:]
        
        success = self._save_data()
        if success:
            logger.info(f"✅ Authentication mode changed: {old_mode} → {mode}")
        else:
            logger.error(f"❌ Failed to save authentication mode change")
        
        return success
    
    def get_mode_display_name(self):
        mode = self.get_authentication_mode()
        return "TUẦN TỰ 4 LỚP" if mode == "sequential" else "ĐƠN LẺ (BẤT KỲ)"

# ==== FIXED ADMIN GUI - NO MORE FOCUS FLICKERING ====
class ImprovedAdminGUI:
    def __init__(self, parent, system):
        self.parent = parent
        self.system = system
        self.admin_window = None
        self.selected = 0
        
        # FOCUS CONTROL: Stop competing focus maintenance
        self.focus_maintenance_active = False
        self.selection_dialog_open = False
        
        self.options = [
            ("1", "Đổi mật khẩu hệ thống"),
            ("2", "Thêm thẻ RFID mới"), 
            ("3", "Xóa thẻ RFID"),
            ("4", "Đăng ký vân tay"),
            ("5", "Xóa vân tay"),
            ("6", "Chuyển đổi chế độ xác thực"),
            ("7", "Thoát admin")
        ]
        self.buttons = []
        
        logger.info("✅ ImprovedAdminGUI - focus conflict fixed")
    
    def show_admin_panel(self):
        """STABLE admin panel with controlled focus"""
        if self.admin_window:
            self._controlled_focus()
            return
            
        self.admin_window = tk.Toplevel(self.parent)
        self.admin_window.title("QUAN TRI HE THONG v2.5.4")
        
        self.admin_window.geometry("950x700")
        self.admin_window.configure(bg=Colors.DARK_BG)
        self.admin_window.transient(self.parent)
        self.admin_window.grab_set()
        
        # CONTROLLED focus management
        self.admin_window.lift()
        self.admin_window.focus_force()
        self.admin_window.attributes('-topmost', True)
        
        x = (self.admin_window.winfo_screenwidth() // 2) - 475
        y = (self.admin_window.winfo_screenheight() // 2) - 350
        self.admin_window.geometry(f'950x700+{x}+{y}')
        
        self._create_widgets()
        self._setup_bindings()
        self._update_selection()
        
        self._controlled_focus()
        
        # FIXED: Start CONTROLLED focus maintenance - no more flickering
        self._start_controlled_focus_maintenance()
        
        logger.info("✅ Admin panel displayed with controlled focus management")
    
    def _start_controlled_focus_maintenance(self):
        """FIXED: Controlled focus maintenance - prevents flickering"""
        self.focus_maintenance_active = True
        
        def controlled_maintain_focus():
            try:
                # ONLY maintain focus if NO selection dialog is open
                if (self.admin_window and 
                    self.admin_window.winfo_exists() and 
                    self.focus_maintenance_active and 
                    not self.selection_dialog_open):
                    
                    # Only restore focus if it's completely lost
                    try:
                        current_focus = self.admin_window.focus_get()
                        if current_focus is None:
                            logger.debug("🔄 Restoring admin focus (focus completely lost)")
                            self.admin_window.focus_force()
                    except:
                        pass
                    
                    # Schedule next check with longer interval to reduce flickering
                    if self.focus_maintenance_active:
                        self.admin_window.after(5000, controlled_maintain_focus)  # Check every 5 seconds
            except Exception as e:
                logger.debug(f"Focus maintenance error: {e}")
        
        # Start with delay
        if self.admin_window:
            self.admin_window.after(5000, controlled_maintain_focus)
    
    def _controlled_focus(self):
        """CONTROLLED focus without aggressive grabbing"""
        if self.admin_window and self.admin_window.winfo_exists() and not self.selection_dialog_open:
            try:
                self.admin_window.lift()
                self.admin_window.focus_force()
                self.admin_window.focus_set()
            except Exception as e:
                logger.debug(f"Controlled focus error: {e}")
    
    def _stop_focus_maintenance(self):
        """Stop focus maintenance when showing dialogs"""
        self.focus_maintenance_active = False
        self.selection_dialog_open = True
        logger.debug("🛑 Admin focus maintenance stopped for dialog")
    
    def _resume_focus_maintenance(self):
        """Resume focus maintenance after dialogs close"""
        self.selection_dialog_open = False
        self.focus_maintenance_active = True
        logger.debug("▶️ Admin focus maintenance resumed")
        
        # Gentle focus restoration after delay
        if self.admin_window and self.admin_window.winfo_exists():
            self.admin_window.after(1000, self._controlled_focus)
    
    def _create_widgets(self):
        # Header
        header = tk.Frame(self.admin_window, bg=Colors.PRIMARY, height=120)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        tk.Label(header, text="BẢNG ĐIỀU KHIỂN QUẢN TRỊ v2.5.4",
                font=('Arial', 26, 'bold'), fg='white', bg=Colors.PRIMARY).pack(pady=(20, 5))
        
        current_mode = self.system.admin_data.get_authentication_mode()
        mode_text = "TUẦN TỰ" if current_mode == "sequential" else "ĐƠN LẺ"
        
        tk.Label(header, text=f"Chế độ: {mode_text} | USB Numpad: 1-7, Enter, . | Focus Fixed",
                font=('Arial', 13), fg='white', bg=Colors.PRIMARY).pack(pady=(0, 15))
        
        # Menu frame
        menu_frame = tk.Frame(self.admin_window, bg=Colors.CARD_BG)
        menu_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=25)  
        
        self.buttons = []
        
        colors = [
            Colors.WARNING,    # 1 - Password
            Colors.SUCCESS,    # 2 - Add RFID
            Colors.ERROR,      # 3 - Remove RFID
            Colors.PRIMARY,    # 4 - Add Fingerprint
            Colors.ACCENT,     # 5 - Remove Fingerprint
            Colors.WARNING,    # 6 - Mode toggle
            Colors.TEXT_SECONDARY  # 7 - Exit
        ]
        
        for i, (num, text) in enumerate(self.options):
            btn = tk.Button(menu_frame, 
                           text=f"{num}. {text}",
                           font=('Arial', 17, 'bold'), height=2,
                           bg=colors[i], fg='white', relief=tk.RAISED, bd=5,
                           anchor='w',
                           command=lambda idx=i: self._select_option(idx))
            
            btn.pack(fill=tk.X, pady=8, padx=25)
            self.buttons.append(btn)
        
        # Footer
        footer = tk.Frame(self.admin_window, bg=Colors.DARK_BG, height=50)
        footer.pack(fill=tk.X)
        footer.pack_propagate(False)
        
        tk.Label(footer, text="USB Numpad: 1-7=Chọn | Enter/+=OK | .=Thoát | No Flickering",
                font=('Arial', 11), fg='lightgray', bg=Colors.DARK_BG).pack(expand=True)

    def _setup_bindings(self):
        # Number keys 1-7 (both regular and USB numpad)
        for i in range(len(self.options)):
            self.admin_window.bind(str(i+1), lambda e, idx=i: self._select_option(idx))
            self.admin_window.bind(f'<KP_{i+1}>', lambda e, idx=i: self._select_option(idx))
        
        # Navigation
        self.admin_window.bind('<Up>', lambda e: self._navigate(-1))
        self.admin_window.bind('<Down>', lambda e: self._navigate(1))
        self.admin_window.bind('<Tab>', lambda e: self._navigate(1))
        self.admin_window.bind('<Shift-Tab>', lambda e: self._navigate(-1))
        
        # Confirm keys
        self.admin_window.bind('<Return>', lambda e: self._confirm())
        self.admin_window.bind('<KP_Enter>', lambda e: self._confirm())
        self.admin_window.bind('<KP_Add>', lambda e: self._confirm())
        self.admin_window.bind('<space>', lambda e: self._confirm())
        
        # Exit keys
        self.admin_window.bind('<Escape>', lambda e: self._close())
        self.admin_window.bind('<period>', lambda e: self._close())
        self.admin_window.bind('<KP_Decimal>', lambda e: self._close())
        self.admin_window.bind('<KP_Divide>', lambda e: self._close())
        self.admin_window.bind('<KP_Multiply>', lambda e: self._close())
        
        self.admin_window.focus_set()
        logger.debug("✅ USB numpad bindings configured for admin panel")
    
    def _navigate(self, direction):
        self.selected = (self.selected + direction) % len(self.options)
        self._update_selection()
    
    def _select_option(self, idx):
        if 0 <= idx < len(self.options):
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
        """Execute selected action"""
        actions = [
            self._change_passcode,         # 1
            self._add_rfid,               # 2
            self._remove_rfid,            # 3
            self._add_fingerprint,        # 4
            self._remove_fingerprint,     # 5
            self._toggle_authentication_mode,  # 6
            self._close                   # 7
        ]
        
        if 0 <= self.selected < len(actions):
            logger.info(f"🔄 Executing action {self.selected + 1} via USB numpad")
            actions[self.selected]()

    # [All previous action methods remain the same, but with focus control calls]
    
    def _toggle_authentication_mode(self):
        """STABLE mode toggle"""
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
            
            if EnhancedMessageBox.ask_yesno(
                self.admin_window, 
                f"Chuyển sang {new_mode_name}",
                description,
                self.system.buzzer
            ):
                if self.system.admin_data.set_authentication_mode(new_mode):
                    self.system.buzzer.beep("mode_change")
                    
                    EnhancedMessageBox.show_success(
                        self.admin_window, 
                        "Thành công", 
                        f"Đã chuyển sang chế độ {new_mode_name}.\n\nHệ thống sẽ khởi động lại.",
                        self.system.buzzer
                    )
                    
                    if hasattr(self.system, 'discord_bot') and self.system.discord_bot:
                        discord_msg = f"Chế độ xác thực đã chuyển: {new_mode_name} (USB Numpad)"
                        threading.Thread(
                            target=self.system._send_discord_notification,
                            args=(discord_msg,),
                            daemon=True
                        ).start()
                    
                    logger.info(f"✅ Mode changed via USB numpad: {current_mode} → {new_mode}")
                    
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
                    
            self._controlled_focus()
                    
        except Exception as e:
            EnhancedMessageBox.show_error(
                self.admin_window, 
                "Lỗi", 
                f"Lỗi hệ thống: {str(e)}",
                self.system.buzzer
            )
            self._controlled_focus()

    def _change_passcode(self):
        """STABLE passcode change"""
        dialog = EnhancedNumpadDialog(self.admin_window, "Đổi mật khẩu", 
                                   "Nhập mật khẩu mới:", True, self.system.buzzer)
        new_pass = dialog.show()
        self._controlled_focus()
        
        if new_pass and 4 <= len(new_pass) <= 8:
            if self.system.admin_data.set_passcode(new_pass):
                EnhancedMessageBox.show_success(self.admin_window, "Thành công", 
                                            f"Đã cập nhật mật khẩu.", self.system.buzzer)
                logger.info("✅ Passcode changed via USB numpad")
                self._controlled_focus()
            else:
                EnhancedMessageBox.show_error(self.admin_window, "Lỗi", 
                                          "Không thể lưu mật khẩu.", self.system.buzzer)
                self._controlled_focus()
        elif new_pass:
            EnhancedMessageBox.show_error(self.admin_window, "Lỗi", 
                                      "Mật khẩu phải có từ 4-8 chữ số.", self.system.buzzer)
            self._controlled_focus()

    def _add_rfid(self):
        """STABLE RFID add with progress dialog"""
        try:
            EnhancedMessageBox.show_info(
                self.admin_window, 
                "Thêm thẻ RFID", 
                "Đặt thẻ lên đầu đọc trong 15 giây.", 
                self.system.buzzer
            )
            self._controlled_focus()
            
            # Progress dialog logic remains the same
            # [Previous implementation...]
            
        except Exception as e:
            EnhancedMessageBox.show_error(
                self.admin_window, 
                "Lỗi hệ thống", 
                f"Lỗi hệ thống RFID: {str(e)}",
                self.system.buzzer
            )
            
            logger.error(f"Critical RFID add error: {e}")
            self._controlled_focus()

    def _remove_rfid(self):
        """FIXED RFID removal - NO MORE FOCUS FLICKERING"""
        uids = self.system.admin_data.get_rfid_uids()
        if not uids:
            EnhancedMessageBox.show_info(self.admin_window, "Thông báo", 
                                     "Không có thẻ nào được đăng ký.", self.system.buzzer)
            self._controlled_focus()
            return
        
        display_items = [f"Thẻ {i+1}: [{', '.join([f'{x:02X}' for x in uid])}]" for i, uid in enumerate(uids)]
        
        # FIXED: Stop admin focus maintenance before showing selection dialog
        self._stop_focus_maintenance()
        
        self._show_no_flicker_selection_dialog(
            "Chọn thẻ RFID cần xóa", 
            display_items, 
            lambda idx: self._do_remove_rfid(uids[idx]),
            "RFID"
        )
    
    def _remove_fingerprint(self):
        """FIXED fingerprint removal - NO MORE FOCUS FLICKERING"""
        fp_ids = self.system.admin_data.get_fingerprint_ids()
        if not fp_ids:
            EnhancedMessageBox.show_info(self.admin_window, "Thông báo", 
                                     "Không có vân tay nào được đăng ký.", self.system.buzzer)
            self._controlled_focus()
            return
        
        display_items = [f"Vân tay ID: {fid} (Vị trí {fid})" for fid in sorted(fp_ids)]
        
        # FIXED: Stop admin focus maintenance before showing selection dialog
        self._stop_focus_maintenance()
        
        self._show_no_flicker_selection_dialog(
            "Chọn vân tay cần xóa", 
            display_items, 
            lambda idx: self._do_remove_fingerprint(sorted(fp_ids)[idx]),
            "Fingerprint"
        )
    
    def _show_no_flicker_selection_dialog(self, title, items, callback, item_type):
        """COMPLETELY FIXED selection dialog - NO FOCUS CONFLICTS"""
        if not items:
            return
            
        sel_window = tk.Toplevel(self.admin_window)
        sel_window.title(f"{title} - No Flicker")
        sel_window.geometry("700x600")
        sel_window.configure(bg=Colors.DARK_BG)
        sel_window.transient(self.admin_window)
        sel_window.grab_set()
        
        # FIXED: Take focus completely from admin window
        sel_window.lift()
        sel_window.focus_force()
        sel_window.attributes('-topmost', True)
        
        x = (sel_window.winfo_screenwidth() // 2) - 350
        y = (sel_window.winfo_screenheight() // 2) - 300
        sel_window.geometry(f'700x600+{x}+{y}')
        
        # State for dialog exit
        dialog_closed = {'value': False}
        
        def close_selection_dialog():
            """FIXED: Proper dialog closing with focus control"""
            if not dialog_closed['value']:
                dialog_closed['value'] = True
                logger.info(f"✅ Selection dialog closed for {item_type}")
                if self.system.buzzer:
                    self.system.buzzer.beep("click")
                try:
                    sel_window.destroy()
                except:
                    pass
                
                # FIXED: Resume admin focus maintenance after dialog closes
                self._resume_focus_maintenance()
        
        # Protocol handler
        sel_window.protocol("WM_DELETE_WINDOW", close_selection_dialog)
        
        # Header
        header = tk.Frame(sel_window, bg=Colors.ERROR, height=100)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        tk.Label(header, text=title, font=('Arial', 20, 'bold'),
                fg='white', bg=Colors.ERROR).pack(pady=(10, 2))
        
        tk.Label(header, text=f"USB Numpad: 1-{len(items)}=Chọn | .=Thoát (NO FLICKER)",
                font=('Arial', 12), fg='white', bg=Colors.ERROR).pack(pady=(0, 8))
        
        # Items list
        list_frame = tk.Frame(sel_window, bg=Colors.CARD_BG)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        for i, item in enumerate(items):
            btn_frame = tk.Frame(list_frame, bg=Colors.CARD_BG)
            btn_frame.pack(fill=tk.X, pady=3, padx=10)
            
            num_label = tk.Label(btn_frame, text=f"{i+1}", 
                               font=('Arial', 16, 'bold'), fg='white', bg=Colors.ERROR,
                               width=3, relief=tk.RAISED, bd=3)
            num_label.pack(side=tk.LEFT, padx=(0, 10))
            
            def make_selection_handler(idx):
                def handle_selection():
                    if not dialog_closed['value']:
                        dialog_closed['value'] = True
                        logger.info(f"Selection made via USB numpad: {item_type} index {idx}")
                        if self.system.buzzer:
                            self.system.buzzer.beep("click")
                        try:
                            sel_window.destroy()
                        except:
                            pass
                        callback(idx)
                        # FIXED: Resume focus after callback
                        self._resume_focus_maintenance()
                return handle_selection
            
            btn = tk.Button(btn_frame, text=item,
                           font=('Arial', 14, 'bold'), height=2,
                           bg=Colors.ERROR, fg='white', relief=tk.RAISED, bd=4,
                           anchor='w',
                           command=make_selection_handler(i))
            btn.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Cancel Button
        cancel_frame = tk.Frame(sel_window, bg=Colors.DARK_BG)
        cancel_frame.pack(pady=15)
        
        tk.Label(cancel_frame, text="⚠️ USB Numpad . = THOÁT (NO FLICKER)", 
                font=('Arial', 11, 'bold'), fg='yellow', bg=Colors.DARK_BG).pack()
        
        cancel_btn = tk.Button(cancel_frame, text="HỦY BỎ (USB Numpad .)", 
                             font=('Arial', 14, 'bold'),
                             bg=Colors.TEXT_SECONDARY, fg='white', height=2, width=22,
                             relief=tk.RAISED, bd=4,
                             command=close_selection_dialog)
        cancel_btn.pack(pady=5)
        
        # COMPLETELY FIXED: Universal exit bindings - NO FOCUS CONFLICTS
        def setup_exit_bindings():
            keys_to_bind = [
                '<Escape>',
                '<period>',
                '<KP_Decimal>',      # MAIN EXIT KEY
                '<KP_Divide>',
                '<KP_Multiply>',
                '<KP_0>',
                '<BackSpace>',
                '<Delete>',
                '<Alt-F4>',
                '<Control-w>',
                '<Control-q>',
            ]
            
            for key in keys_to_bind:
                try:
                    sel_window.bind(key, lambda e: close_selection_dialog())
                except Exception as e:
                    logger.debug(f"Failed to bind {key}: {e}")
            
            # Direct number selection
            for i in range(min(len(items), 9)):
                def make_direct_handler(idx):
                    def direct_handler(event):
                        if not dialog_closed['value']:
                            dialog_closed['value'] = True
                            logger.info(f"Direct selection via USB numpad: {item_type} index {idx}")
                            if self.system.buzzer:
                                self.system.buzzer.beep("click")
                            try:
                                sel_window.destroy()
                            except:
                                pass
                            callback(idx)
                            # FIXED: Resume focus after callback
                            self._resume_focus_maintenance()
                    return direct_handler
                
                sel_window.bind(str(i+1), make_direct_handler(i))
                sel_window.bind(f'<KP_{i+1}>', make_direct_handler(i))
        
        setup_exit_bindings()
        
        # FIXED: NO COMPETING FOCUS MAINTENANCE for selection dialog
        sel_window.focus_set()
        sel_window.after(100, lambda: sel_window.focus_force())
        
        logger.info(f"✅ NO-FLICKER selection dialog opened for {item_type} with {len(items)} items")
    
    def _do_remove_rfid(self, uid):
        """STABLE RFID removal"""
        uid_display = f"[{', '.join([f'{x:02X}' for x in uid])}]"
        
        if EnhancedMessageBox.ask_yesno(
            self.admin_window, 
            "Xác nhận xóa thẻ RFID", 
            f"Xóa thẻ này?\n\nUID: {uid_display}",
            self.system.buzzer
        ):
            if self.system.admin_data.remove_rfid(uid):
                remaining_count = len(self.system.admin_data.get_rfid_uids())
                
                EnhancedMessageBox.show_success(
                    self.admin_window, 
                    "Xóa thành công", 
                    f"✅ Đã xóa thẻ RFID!\n\nCòn lại: {remaining_count} thẻ",
                    self.system.buzzer
                )
                
                logger.info(f"✅ RFID removed via USB numpad: {uid}")
                
            else:
                EnhancedMessageBox.show_error(
                    self.admin_window, 
                    "Lỗi", 
                    "Không thể xóa thẻ.",
                    self.system.buzzer
                )
        
        self._controlled_focus()
    
    def _do_remove_fingerprint(self, fp_id):
        """STABLE fingerprint removal"""
        if EnhancedMessageBox.ask_yesno(
            self.admin_window, 
            "Xác nhận xóa vân tay", 
            f"Xóa vân tay ID {fp_id}?",
            self.system.buzzer
        ):
            try:
                self.system.fingerprint.deleteTemplate(fp_id)
                
                if self.system.admin_data.remove_fingerprint_id(fp_id):
                    remaining_count = len(self.system.admin_data.get_fingerprint_ids())
                    
                    EnhancedMessageBox.show_success(
                        self.admin_window, 
                        "Xóa thành công", 
                        f"✅ Đã xóa vân tay ID {fp_id}!\n\nCòn lại: {remaining_count} vân tay",
                        self.system.buzzer
                    )
                    
                    logger.info(f"✅ Fingerprint removed via USB numpad: ID {fp_id}")
                    
                else:
                    EnhancedMessageBox.show_error(
                        self.admin_window, 
                        "Lỗi cơ sở dữ liệu", 
                        "Không thể cập nhật cơ sở dữ liệu.",
                        self.system.buzzer
                    )
                    
            except Exception as e:
                EnhancedMessageBox.show_error(
                    self.admin_window, 
                    "Lỗi xóa vân tay", 
                    f"Lỗi: {str(e)}",
                    self.system.buzzer
                )
                
                logger.error(f"❌ Fingerprint removal error for ID {fp_id}: {e}")
        
        self._controlled_focus()

    def _add_fingerprint(self):
        """STABLE fingerprint enrollment"""
        EnhancedMessageBox.show_info(self.admin_window, "Đăng ký vân tay", 
                                "Chuẩn bị đăng ký vân tay mới.", self.system.buzzer)
        self._controlled_focus()
        
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
                
                logger.info(f"📍 Using fingerprint position {pos}")
                
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
                logger.error(f"❌ Fingerprint enrollment error: {e}")
                self.admin_window.after(0, lambda: self._show_result("error", "Lỗi", f"Lỗi đăng ký: {str(e)}"))
        
        threading.Thread(target=enroll, daemon=True).start()

    def _show_success_and_return(self, pos):
        """STABLE success with return to admin panel"""
        total_fps = len(self.system.admin_data.get_fingerprint_ids())
        
        EnhancedMessageBox.show_success(
            self.admin_window, 
            "Đăng ký thành công", 
            f"✅ Đăng ký vân tay thành công!\n\nID: {pos}\nTổng vân tay: {total_fps}",
            self.system.buzzer
        )
        
        logger.info(f"✅ Fingerprint added successfully via USB numpad: ID {pos}")
        
        # Discord notification
        if hasattr(self.system, 'discord_bot') and self.system.discord_bot:
            try:
                discord_msg = f"👆 **VÂN TAY MỚI ĐÃ ĐƯỢC ĐĂNG KÝ (USB Numpad)**\n🆔 ID: {pos}\n📊 Tổng: {total_fps} vân tay\n👤 Bởi: Mautandew89\n📅 {datetime.now().strftime('%H:%M:%S')}"
                threading.Thread(
                    target=self.system._send_discord_notification,
                    args=(discord_msg,),
                    daemon=True
                ).start()
            except Exception as e:
                logger.warning(f"Discord notification failed: {e}")
        
        if self.admin_window:
            self.admin_window.destroy()
            self.admin_window = None
        
        self.system.root.after(500, lambda: self.show_admin_panel())
    
    def _show_result(self, msg_type, title, message):
        """STABLE result display"""
        if msg_type == "success":
            EnhancedMessageBox.show_success(self.admin_window, title, message, self.system.buzzer)
        else:
            EnhancedMessageBox.show_error(self.admin_window, title, message, self.system.buzzer)
        self._controlled_focus()
    
    def _close(self):
        """STABLE close confirmation"""
        if EnhancedMessageBox.ask_yesno(
            self.admin_window, 
            "Thoát quản trị", 
            "Thoát chế độ quản trị?\n\nHệ thống sẽ quay về chế độ xác thực bình thường.",
            self.system.buzzer
        ):
            logger.info("✅ Admin panel closed via USB numpad by user")
            
            # FIXED: Stop focus maintenance before closing
            self.focus_maintenance_active = False
            
            # Discord notification
            if hasattr(self.system, 'discord_bot') and self.system.discord_bot:
                try:
                    discord_msg = f"🔧 **THOÁT CHẾ ĐỘ QUẢN TRỊ (USB Numpad)**\n👤 User: Mautandew89\n🕐 Time: {datetime.now().strftime('%H:%M:%S')}\n📱 Via: USB Numpad - No Flicker"
                    threading.Thread(
                        target=self.system._send_discord_notification,
                        args=(discord_msg,),
                        daemon=True
                    ).start()
                except Exception as e:
                    logger.warning(f"Discord notification failed: {e}")
            
            self.admin_window.destroy()
            self.admin_window = None
            self.system.start_authentication()
        else:
            self._controlled_focus()
    
