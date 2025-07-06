#!/usr/bin/env python3
"""
Vietnamese Speaker - OPTIMIZED INTELLIGENT VERSION
Version: 3.1 - 2025-07-06 06:17:53 UTC
User: KHOI1235567
Status: PRODUCTION READY - Intelligent Voice Logic
"""

import threading
import time
import logging
import queue
from typing import Optional
import subprocess
import os
import tempfile

# GOOGLE TTS INTEGRATION
try:
    from gtts import gTTS
    import pygame
    GTTS_AVAILABLE = True
    PYGAME_AVAILABLE = True
except ImportError:
    try:
        from gtts import gTTS
        GTTS_AVAILABLE = True
        PYGAME_AVAILABLE = False
    except ImportError:
        GTTS_AVAILABLE = False
        PYGAME_AVAILABLE = False

logger = logging.getLogger(__name__)

class VietnameseSpeaker:
    """OPTIMIZED Vietnamese Speaker - Intelligent Voice Logic"""
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.volume = 0.8
        self.voice_speed = 1.0
        
        # Thread-safe message queue
        self.message_queue = queue.Queue(maxsize=3)  # Giảm queue size
        self.speaker_thread = None
        self.running = False
        
        # Audio system
        self.pygame_initialized = False
        self.tts_method = self._detect_best_method()
        
        # 🧠 INTELLIGENT VOICE CONTROL
        self.last_spoken_message = None
        self.last_spoken_time = 0
        self.message_cooldown = {}  # Cooldown cho từng loại message
        self.session_announced = {
            "mode_sequential": False,
            "mode_any": False,
            "system_ready": False
        }
        
        # OPTIMIZED VIETNAMESE MESSAGES - Shortened and more natural
        self.messages = {
            # System - SHORTENED
            "system_ready": "Sẵn sàng",
            "system_start": "Khởi động",
            "system_error": "Lỗi hệ thống",
            "system_shutdown": "Tắt máy",
            
            # Authentication steps - MORE NATURAL
            "step_face": "Nhìn vào camera",
            "step_fingerprint": "Đặt ngón tay", 
            "step_rfid": "Đưa thẻ lại gần",
            "step_passcode": "Nhập mật khẩu",
            
            # Success messages - SHORTER
            "face_success": "Nhận diện thành công",
            "fingerprint_success": "Vân tay hợp lệ",
            "rfid_success": "Thẻ hợp lệ",
            "passcode_success": "Mật khẩu đúng",
            "auth_complete": "Hoàn tất",
            
            # Door control - CONCISE
            "door_opening": "Mở cửa",
            "door_opened": "Đã mở",
            "door_locked": "Đã khóa",
            
            # Failure messages - BRIEF
            "auth_failed": "Thất bại",
            "try_again": "Thử lại",
            "max_attempts": "Hết lượt",
            "timeout": "Hết thời gian",
            
            # Admin messages - SIMPLIFIED
            "admin_mode": "Chế độ quản trị",
            "admin_access": "Truy cập được cấp",
            "admin_denied": "Truy cập bị từ chối",
            
            # Mode changes - ONLY ANNOUNCE ONCE
            "mode_sequential": "Chế độ tuần tự",
            "mode_any": "Chế độ đơn lẻ",
            
            # Buzzer patterns as voice - MINIMAL
            "success": "",  # REMOVE SUCCESS SOUND - TOO FREQUENT
            "error": "Lỗi",
            "click": "",    # REMOVE CLICK SOUND - TOO FREQUENT
            "warning": "Xác nhận",
            "startup": "",  # REMOVE STARTUP SOUND
            "mode_change": ""  # HANDLE BY SPECIFIC MODE MESSAGES
        }
        
        # COOLDOWN TIMES (seconds)
        self.cooldown_times = {
            "step_face": 30,        # Chỉ thông báo 30s một lần
            "step_fingerprint": 20,  # Chỉ thông báo 20s một lần
            "step_rfid": 20,
            "step_passcode": 20,
            "auth_failed": 5,       # Lỗi có thể nói 5s một lần
            "system_ready": 60,     # System ready 60s một lần
            "mode_sequential": 300, # Mode announcement 5 phút một lần
            "mode_any": 300,
            "door_opening": 10,     # Door operation 10s một lần
            "door_opened": 10,
            "door_locked": 15
        }
        
        if enabled:
            self._init_audio_system()
        
        logger.info(f"  Vietnamese Speaker v3.1 - Intelligent Voice Logic")
    
    def _detect_best_method(self):
        """Detect best TTS method"""
        if GTTS_AVAILABLE and PYGAME_AVAILABLE:
            return "gtts_pygame"
        elif GTTS_AVAILABLE:
            return "gtts_system" 
        else:
            return "espeak"
    
    def _init_audio_system(self):
        """Initialize audio system"""
        try:
            if self.tts_method == "gtts_pygame" and PYGAME_AVAILABLE:
                import pygame
                pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
                self.pygame_initialized = True
                logger.info("  Pygame audio system ready")
        except Exception as e:
            logger.warning(f"Pygame init failed: {e}")
            self.pygame_initialized = False
    
    def start_speaker_thread(self):
        """Start speaker thread"""
        if self.speaker_thread and self.speaker_thread.is_alive():
            return
        
        self.running = True
        self.speaker_thread = threading.Thread(target=self._speaker_worker, daemon=True)
        self.speaker_thread.start()
        logger.info("🔊 Vietnamese speaker thread started")
    
    def stop_speaker_thread(self):
        """Stop speaker thread"""
        self.running = False
        if self.speaker_thread:
            self.speaker_thread.join(timeout=2)
        logger.info("🔇 Vietnamese speaker thread stopped")
    
    def _speaker_worker(self):
        """Worker thread for Vietnamese voice"""
        while self.running:
            try:
                try:
                    message = self.message_queue.get(timeout=1)
                except queue.Empty:
                    continue
                
                self._speak_vietnamese(message)
                self.message_queue.task_done()
                
            except Exception as e:
                logger.error(f"Vietnamese speaker worker error: {e}")
                time.sleep(0.5)
    
    def _speak_vietnamese(self, message: str):
        """Speak Vietnamese using best available method"""
        if not self.enabled or not message:
            return
        
        try:
            logger.debug(f"🇻🇳 Speaking: {message}")
            
            # METHOD 1: Google TTS + Pygame (BEST)
            if self.tts_method == "gtts_pygame" and self._speak_with_gtts_pygame(message):
                return
            
            # METHOD 2: Google TTS + System player
            if self.tts_method == "gtts_system" and self._speak_with_gtts_system(message):
                return
            
            # METHOD 3: espeak fallback
            self._speak_with_espeak(message)
            
        except Exception as e:
            logger.error(f"Vietnamese speech error: {e}")
    
    def _speak_with_gtts_pygame(self, message: str):
        """Google TTS + Pygame - BEST quality"""
        try:
            if not GTTS_AVAILABLE or not self.pygame_initialized:
                return False
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
                temp_filename = temp_file.name
            
            try:
                # Generate Vietnamese speech
                tts = gTTS(text=message, lang='vi', slow=False, tld='com')
                tts.save(temp_filename)
                
                # Play with pygame
                import pygame
                pygame.mixer.music.load(temp_filename)
                pygame.mixer.music.set_volume(self.volume)
                pygame.mixer.music.play()
                
                # Wait for playback
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)
                
                logger.debug("  Google TTS Vietnamese played")
                return True
                
            finally:
                try:
                    os.unlink(temp_filename)
                except:
                    pass
                
        except Exception as e:
            logger.debug(f"Google TTS + Pygame failed: {e}")
            return False
    
    def _speak_with_gtts_system(self, message: str):
        """Google TTS + System player"""
        try:
            if not GTTS_AVAILABLE:
                return False
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
                temp_filename = temp_file.name
            
            try:
                tts = gTTS(text=message, lang='vi', slow=False, tld='com')
                tts.save(temp_filename)
                
                # Try mpg123 first
                if os.path.exists('/usr/bin/mpg123'):
                    subprocess.run(['/usr/bin/mpg123', '-q', temp_filename], 
                                 check=True, timeout=10)
                else:
                    return False
                
                logger.debug("  Google TTS Vietnamese (system)")
                return True
                
            finally:
                try:
                    os.unlink(temp_filename)
                except:
                    pass
                
        except Exception as e:
            logger.debug(f"Google TTS + System failed: {e}")
            return False
    
    def _speak_with_espeak(self, message: str):
        """espeak Vietnamese fallback"""
        try:
            subprocess.run([
                'espeak', '-v', 'vi', '-s', '150', '-p', '50', '-a', '70', message
            ], capture_output=True, timeout=5)
            logger.debug("  espeak Vietnamese fallback")
        except Exception as e:
            logger.debug(f"espeak failed: {e}")
    
    # ==== 🧠 INTELLIGENT PUBLIC METHODS ====
    
    def _should_speak(self, message_key: str, custom_message: str = None) -> bool:
        """🧠 INTELLIGENT: Decide if should speak based on cooldown and logic"""
        if not self.enabled:
            return False
        
        current_time = time.time()
        
        # 1. CHECK EMPTY MESSAGES - DON'T SPEAK
        message = custom_message if custom_message else self.messages.get(message_key, message_key)
        if not message or message.strip() == "":
            return False
        
        # 2. CHECK COOLDOWN
        if message_key in self.cooldown_times:
            cooldown_time = self.cooldown_times[message_key]
            last_time = self.message_cooldown.get(message_key, 0)
            
            if current_time - last_time < cooldown_time:
                logger.debug(f"🔇 Cooldown active for {message_key}: {current_time - last_time:.1f}s < {cooldown_time}s")
                return False
        
        # 3. CHECK SESSION ANNOUNCEMENTS - ONLY ONCE PER SESSION
        if message_key in self.session_announced:
            if self.session_announced[message_key]:
                logger.debug(f"🔇 Already announced in session: {message_key}")
                return False
        
        # 4. AVOID DUPLICATE MESSAGES
        if (self.last_spoken_message == message and 
            current_time - self.last_spoken_time < 3):  # 3 seconds duplicate protection
            logger.debug(f"🔇 Duplicate message blocked: {message}")
            return False
        
        return True
    
    def speak(self, message_key: str, custom_message: str = None):
        """🧠 INTELLIGENT: Speak Vietnamese - smart logic"""
        if not self._should_speak(message_key, custom_message):
            return
        
        message = custom_message if custom_message else self.messages.get(message_key, message_key)
        current_time = time.time()
        
        # Update tracking
        self.last_spoken_message = message
        self.last_spoken_time = current_time
        self.message_cooldown[message_key] = current_time
        
        # Mark session announcements
        if message_key in self.session_announced:
            self.session_announced[message_key] = True
        
        try:
            # Clear queue if full to prevent backlog
            if self.message_queue.qsize() >= 2:
                try:
                    self.message_queue.get_nowait()
                    self.message_queue.task_done()
                except:
                    pass
            
            self.message_queue.put(message, block=False)
            logger.debug(f"🔊 Queued: {message_key} -> {message}")
        except queue.Full:
            logger.debug(f"🔇 Queue full, skipping: {message_key}")
    
    def speak_immediate(self, message_key: str, custom_message: str = None):
        """🧠 INTELLIGENT: Speak immediately but still check logic"""
        if not self._should_speak(message_key, custom_message):
            return
        
        message = custom_message if custom_message else self.messages.get(message_key, message_key)
        
        # Update tracking
        current_time = time.time()
        self.last_spoken_message = message
        self.last_spoken_time = current_time
        self.message_cooldown[message_key] = current_time
        
        # Mark session announcements
        if message_key in self.session_announced:
            self.session_announced[message_key] = True
        
        def immediate_speak():
            self._speak_vietnamese(message)
        
        threading.Thread(target=immediate_speak, daemon=True).start()
        logger.debug(f"🔊 Immediate: {message_key} -> {message}")
    
    def beep(self, pattern: str):
        """🧠 INTELLIGENT: Compatibility with buzzer interface - filtered"""
        # FILTER OUT FREQUENT PATTERNS
        if pattern in ["success", "click", "startup", "mode_change"]:
            return  # DON'T SPEAK THESE - TOO FREQUENT
        
        self.speak(pattern)
    
    def reset_session_announcements(self):
        """🧠 RESET: Reset session announcements - call when truly starting new session"""
        logger.info("  Resetting voice session announcements")
        self.session_announced = {
            "mode_sequential": False,
            "mode_any": False,
            "system_ready": False
        }
        # Also reset some cooldowns for new session
        for key in ["system_ready", "mode_sequential", "mode_any"]:
            if key in self.message_cooldown:
                del self.message_cooldown[key]
    
    def force_speak(self, message_key: str, custom_message: str = None):
        """🚨 FORCE: Force speak without any checks - use sparingly"""
        message = custom_message if custom_message else self.messages.get(message_key, message_key)
        if message and message.strip():
            try:
                self.message_queue.put(message, block=False)
                logger.debug(f"🚨 Forced: {message_key} -> {message}")
            except queue.Full:
                logger.debug(f"🔇 Queue full, force failed: {message_key}")
    
    def set_enabled(self, enabled: bool):
        """Enable/disable speaker"""
        old_enabled = self.enabled
        self.enabled = enabled
        
        if enabled and not old_enabled:
            self._init_audio_system()
            self.start_speaker_thread()
            time.sleep(0.5)
            self.force_speak("system_ready")  # Force announce enable
        elif not enabled and old_enabled:
            try:
                while not self.message_queue.empty():
                    self.message_queue.get_nowait()
                    self.message_queue.task_done()
            except:
                pass
        
        logger.info(f"🇻🇳 Vietnamese speaker enabled: {enabled}")
    
    def set_volume(self, volume: float):
        """Set volume"""
        self.volume = max(0.0, min(1.0, volume))
        logger.info(f"🔊 Volume: {self.volume:.1f}")
    
    def test_speaker(self):
        """Test speaker"""
        try:
            self.force_speak("system_ready", "Kiểm tra loa tiếng Việt thành công")
            return True
        except Exception as e:
            logger.error(f"Test speaker error: {e}")
            return False
    
    def cleanup(self):
        """Cleanup"""
        logger.info("🧹 Cleaning up Vietnamese Speaker...")
        
        if self.enabled:
            try:
                self.force_speak("system_shutdown")
                time.sleep(1.5)
            except:
                pass
        
        self.running = False
        self.stop_speaker_thread()
        
        if self.pygame_initialized:
            try:
                import pygame
                pygame.mixer.quit()
            except:
                pass
        
        logger.info("  Vietnamese Speaker cleanup complete")

# Compatibility
LoaTiengViet = VietnameseSpeaker

if __name__ == "__main__":
    print("🇻🇳 Testing OPTIMIZED Vietnamese Speaker v3.1...")
    
    speaker = VietnameseSpeaker(enabled=True)
    speaker.start_speaker_thread()
    
    # Test intelligent logic
    test_sequence = [
        ("system_start", "Khởi động"),
        ("system_ready", "Sẵn sàng lần 1"),
        ("system_ready", "Sẵn sàng lần 2 - SHOULD BE BLOCKED"),
        ("step_face", "Bước mặt lần 1"),
        ("step_face", "Bước mặt lần 2 - SHOULD BE BLOCKED"),
        ("face_success", "Thành công"),
        ("success", "Success pattern - SHOULD BE BLOCKED"),
        ("click", "Click pattern - SHOULD BE BLOCKED"),
        ("door_opening", "Mở cửa"),
        ("door_opened", "Đã mở"),
        ("system_shutdown", "Tắt máy")
    ]
    
    for msg_key, description in test_sequence:
        print(f"🔊 Testing: {description}")
        speaker.speak(msg_key)
        time.sleep(2)
    
    speaker.cleanup()
    print("  OPTIMIZED integration test complete!")
