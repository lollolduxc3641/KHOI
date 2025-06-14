#!/usr/bin/env python3
"""
Discord Integration FIXED - Hoàn toàn không có timeout errors
Version: 2.2 - 2025-06-14
"""

import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio
import threading
from datetime import datetime
import logging
from typing import Optional
import concurrent.futures

# Load environment
load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID'))
ADMIN_USER_IDS = [int(id.strip()) for id in os.getenv('ADMIN_USER_IDS', '').split(',') if id.strip()]
BOT_PASSWORD = os.getenv('BOT_PASSWORD')

logger = logging.getLogger(__name__)

class DiscordSecurityBot:
    def __init__(self, security_system=None):
        """
        security_system: Reference đến VietnameseSecuritySystem
        """
        self.security_system = security_system
        self.authenticated_users = set()
        self.bot_thread = None
        self.bot = None
        self.failed_attempts_count = 0
        self.loop = None
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self._setup_bot()
    
    def _setup_bot(self):
        """Thiết lập Discord bot"""
        intents = discord.Intents.default()
        intents.message_content = True
        self.bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)
        
        # Bot events
        @self.bot.event
        async def on_ready():
            print(f'🤖 Discord Bot connected: {self.bot.user}')
            await self._send_startup_message()
        
        # Commands
        @self.bot.command(name='login')
        async def login(ctx, password=None):
            await self._handle_login(ctx, password)
        
        @self.bot.command(name='logout')  
        async def logout(ctx):
            await self._handle_logout(ctx)
        
        @self.bot.command(name='status')
        async def status(ctx):
            await self._handle_status(ctx)
        
        @self.bot.command(name='unlock')
        async def unlock(ctx):
            await self._handle_unlock(ctx)
        
        @self.bot.command(name='start_auth')
        async def start_auth(ctx):
            await self._handle_start_auth(ctx)
        
        @self.bot.command(name='system_info')
        async def system_info(ctx):
            await self._handle_system_info(ctx)
        
        @self.bot.command(name='live_info')
        async def live_info(ctx):
            await self._handle_live_info(ctx)
        
        @self.bot.command(name='menu')
        async def menu(ctx):
            await self._handle_menu(ctx)
        
        @self.bot.command(name='ping')
        async def ping(ctx):
            latency = round(self.bot.latency * 1000)
            embed = discord.Embed(title="🏓 PONG!", description=f"Latency: {latency}ms", color=0x00ff00)
            await self._safe_send(ctx.send, embed=embed)
    
    async def _safe_send(self, send_func, **kwargs):
        """ULTRA SIMPLE: Gửi message không có bất kỳ timeout nào"""
        try:
            # Đơn giản nhất - chỉ gửi trực tiếp
            return await send_func(**kwargs)
        except Exception as e:
            # Chỉ log lỗi, không raise exception
            logger.warning(f"Discord send failed: {e}")
            return None
    
    async def _send_startup_message(self):
        """Gửi thông báo khởi động"""
        channel = self.bot.get_channel(CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title="🔐 HỆ THỐNG KHÓA CỬA THÔNG MINH",
                description="✅ Đã kết nối với hệ thống bảo mật!",
                color=0x00ff00,
                timestamp=datetime.now()
            )
            embed.add_field(name="🤖 Bot Status", value="Online", inline=True)
            embed.add_field(name="🔒 Security System", value="Connected", inline=True)
            embed.add_field(name="📱 Commands", value="!menu", inline=True)
            embed.add_field(name="🛡️ Security Alert", value="Active Monitoring", inline=True)
            await self._safe_send(channel.send, embed=embed)
    
    async def _handle_login(self, ctx, password):
        """Xử lý đăng nhập"""
        user_id = ctx.author.id
        
        if password != BOT_PASSWORD:
            embed = discord.Embed(
                title="❌ XÁC THỰC THẤT BẠI",
                description="Mật khẩu không chính xác!\nSử dụng: `!login khoi2025`",
                color=0xff0000
            )
            await self._safe_send(ctx.send, embed=embed)
            return
        
        self.authenticated_users.add(user_id)
        
        embed = discord.Embed(
            title="✅ XÁC THỰC THÀNH CÔNG",
            description=f"Chào mừng {ctx.author.mention}!\nBạn có thể điều khiển hệ thống bảo mật.",
            color=0x00ff00,
            timestamp=datetime.now()
        )
        embed.add_field(name="👤 User", value=ctx.author.name, inline=True)
        embed.add_field(name="🔑 Access Level", value="Authorized", inline=True)
        
        await self._safe_send(ctx.send, embed=embed)
        await self.send_security_notification(f"🔓 User {ctx.author.name} đã đăng nhập Discord bot", "INFO")
    
    async def _handle_logout(self, ctx):
        """Xử lý đăng xuất"""
        user_id = ctx.author.id
        self.authenticated_users.discard(user_id)
        
        embed = discord.Embed(
            title="👋 ĐĂNG XUẤT THÀNH CÔNG",
            description="Bạn đã đăng xuất khỏi hệ thống!",
            color=0xffa500
        )
        await self._safe_send(ctx.send, embed=embed)
    
    async def _handle_status(self, ctx):
        """Xử lý lệnh status"""
        if not self._check_auth(ctx.author.id):
            await self._send_auth_required(ctx)
            return
        
        # Lấy thông tin từ hệ thống chính
        system_status = "UNKNOWN"
        door_status = "UNKNOWN"
        
        if self.security_system:
            try:
                system_status = "READY" if self.security_system.running else "STOPPED"
                door_status = "LOCKED" if self.security_system.relay.value else "UNLOCKED"
            except:
                pass
        
        embed = discord.Embed(
            title="📊 TRẠNG THÁI HỆ THỐNG BẢO MẬT",
            color=0x0099ff,
            timestamp=datetime.now()
        )
        
        embed.add_field(name="🤖 Discord Bot", value="✅ Online", inline=True)
        embed.add_field(name="🔒 Security System", value=f"🟢 {system_status}", inline=True)
        embed.add_field(name="🚪 Door Lock", value=f"{'🔒' if door_status == 'LOCKED' else '🔓'} {door_status}", inline=True)
        
        embed.add_field(name="👥 Discord Users", value=f"{len(self.authenticated_users)} logged in", inline=True)
        embed.add_field(name="⚠️ Failed Attempts", value=f"{self.failed_attempts_count} today", inline=True)
        embed.add_field(name="⏱️ Last Update", value=datetime.now().strftime("%H:%M:%S"), inline=True)
        
        await self._safe_send(ctx.send, embed=embed)
    
    async def _handle_unlock(self, ctx):
        """Xử lý lệnh mở khóa"""
        if not self._check_auth(ctx.author.id):
            await self._send_auth_required(ctx)
            return
        
        embed = discord.Embed(
            title="🔓 YÊU CẦU MỞ KHÓA",
            description="Đang gửi lệnh mở khóa đến hệ thống...",
            color=0xffa500
        )
        await self._safe_send(ctx.send, embed=embed)
        
        # Gửi lệnh đến hệ thống chính
        if self.security_system:
            try:
                await self._unlock_via_system(ctx)
            except Exception as e:
                error_embed = discord.Embed(
                    title="❌ LỖI MỞ KHÓA",
                    description=f"Không thể thực hiện: {str(e)}",
                    color=0xff0000
                )
                await self._safe_send(ctx.send, embed=error_embed)
        else:
            # Simulation mode
            await asyncio.sleep(1)
            success_embed = discord.Embed(
                title="🔓 MỞ KHÓA THÀNH CÔNG",
                description="Cửa sẽ tự động khóa sau 3 giây (SIMULATION)",
                color=0x00ff00
            )
            await self._safe_send(ctx.send, embed=success_embed)
    
    async def _handle_start_auth(self, ctx):
        """Khởi động quy trình xác thực"""
        if not self._check_auth(ctx.author.id):
            await self._send_auth_required(ctx)
            return
        
        embed = discord.Embed(
            title="🚀 KHỞI ĐỘNG XÁC THỰC",
            description="Đang khởi động quy trình xác thực 4 lớp...",
            color=0x00ff00
        )
        await self._safe_send(ctx.send, embed=embed)
        
        if self.security_system:
            try:
                self.security_system.root.after(0, self.security_system.start_authentication)
                await self.send_security_notification(f"🔄 {ctx.author.name} đã khởi động quy trình xác thực từ Discord", "INFO")
            except Exception as e:
                error_embed = discord.Embed(
                    title="❌ LỖI KHỞI ĐỘNG",
                    description=f"Không thể khởi động: {str(e)}",
                    color=0xff0000
                )
                await self._safe_send(ctx.send, embed=error_embed)
    
    async def _handle_system_info(self, ctx):
        """FIXED: Thông tin chi tiết hệ thống REAL-TIME"""
        if not self._check_auth(ctx.author.id):
            await self._send_auth_required(ctx)
            return
        
        embed = discord.Embed(
            title="🔍 THÔNG TIN HỆ THỐNG THỜI GIAN THỰC",
            color=0x9932cc,
            timestamp=datetime.now()
        )
        
        if self.security_system:
            try:
                # Real-time system status
                current_time = datetime.now().strftime("%H:%M:%S")
                system_status = "🟢 ĐANG CHẠY" if self.security_system.running else "🔴 DỪNG"
                
                # Real-time door status
                try:
                    door_status = "🔒 KHÓA" if self.security_system.relay.value else "🔓 MỞ"
                except:
                    door_status = "❓ KHÔNG XÁC ĐỊNH"
                
                # Real-time authentication state
                current_step = getattr(self.security_system.auth_state, 'step', 'Unknown')
                step_names = {
                    'face': 'Nhận diện khuôn mặt',
                    'fingerprint': 'Vân tay',
                    'rfid': 'Thẻ từ',
                    'passcode': 'Mật khẩu'
                }
                current_step_vn = step_names.get(str(current_step).split('.')[-1].lower(), str(current_step))
                
                # Hardware status check
                try:
                    # Test camera
                    frame = self.security_system.picam2.capture_array()
                    camera_status = "✅ HOẠT ĐỘNG" if frame is not None else "❌ LỖI"
                except:
                    camera_status = "❌ KHÔNG KẾT NỐI"
                
                # Database info
                face_info = self.security_system.face_recognizer.get_database_info()
                fp_count = len(self.security_system.admin_data.get_fingerprint_ids())
                rfid_count = len(self.security_system.admin_data.get_rfid_uids())
                
                # Current attempts info
                face_attempts = getattr(self.security_system.auth_state, 'consecutive_face_ok', 0)
                fp_attempts = getattr(self.security_system.auth_state, 'fingerprint_attempts', 0)
                rfid_attempts = getattr(self.security_system.auth_state, 'rfid_attempts', 0)
                pin_attempts = getattr(self.security_system.auth_state, 'pin_attempts', 0)
                
                # System info fields
                embed.add_field(name="🕐 Thời gian hiện tại", value=current_time, inline=True)
                embed.add_field(name="⚡ Trạng thái hệ thống", value=system_status, inline=True)
                embed.add_field(name="🚪 Trạng thái cửa", value=door_status, inline=True)
                
                embed.add_field(name="🔄 Bước xác thực hiện tại", value=current_step_vn, inline=True)
                embed.add_field(name="📹 Trạng thái camera", value=camera_status, inline=True)
                embed.add_field(name="⚠️ Lỗi hôm nay", value=f"{self.failed_attempts_count} lần", inline=True)
                
                # Database info
                embed.add_field(name="👤 Khuôn mặt đã đăng ký", value=f"{face_info['total_people']} người", inline=True)
                embed.add_field(name="👆 Vân tay đã đăng ký", value=f"{fp_count} vân tay", inline=True)  
                embed.add_field(name="📱 Thẻ từ đã đăng ký", value=f"{rfid_count} thẻ", inline=True)
                
                # Current session attempts
                attempt_info = f"👤 Khuôn mặt: {face_attempts}/{self.security_system.config.FACE_REQUIRED_CONSECUTIVE}\n"
                attempt_info += f"👆 Vân tay: {fp_attempts}/5\n"
                attempt_info += f"📱 Thẻ từ: {rfid_attempts}/5\n" 
                attempt_info += f"🔑 Mật khẩu: {pin_attempts}/5"
                
                embed.add_field(name="📊 Phiên xác thực hiện tại", value=attempt_info, inline=False)
                
                # Memory and performance
                try:
                    import psutil
                    cpu_percent = psutil.cpu_percent()
                    memory_percent = psutil.virtual_memory().percent
                    
                    perf_info = f"🖥️ CPU: {cpu_percent:.1f}%\n💾 RAM: {memory_percent:.1f}%"
                    embed.add_field(name="⚡ Hiệu suất hệ thống", value=perf_info, inline=True)
                except:
                    embed.add_field(name="⚡ Hiệu suất hệ thống", value="Không có dữ liệu", inline=True)
                    
            except Exception as e:
                embed.add_field(name="⚠️ Lỗi hệ thống", value=f"```{str(e)[:200]}```", inline=False)
        else:
            embed.add_field(name="⚠️ Trạng thái", value="🔶 Chế độ mô phỏng", inline=False)
        
        embed.set_footer(text=f"Cập nhật: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Gửi với _safe_send mới
        await self._safe_send(ctx.send, embed=embed)
    
    async def _handle_live_info(self, ctx):
        """Live updating system info"""
        if not self._check_auth(ctx.author.id):
            await self._send_auth_required(ctx)
            return
        
        # Gửi message ban đầu
        embed = discord.Embed(title="🔄 ĐANG TẢI THÔNG TIN THỜI GIAN THỰC...", color=0xffa500)
        message = await self._safe_send(ctx.send, embed=embed)
        
        if message:
            # Update 3 lần với interval 3 giây
            for i in range(3):
                await asyncio.sleep(3)
                
                # Tạo embed mới với thông tin real-time
                updated_embed = await self._create_realtime_embed()
                
                try:
                    await message.edit(embed=updated_embed)
                except:
                    # Nếu edit thất bại, gửi message mới
                    await self._safe_send(ctx.send, embed=updated_embed)
                    break

    async def _create_realtime_embed(self):
        """Tạo embed với thông tin real-time"""
        embed = discord.Embed(
            title="📊 THÔNG TIN THỜI GIAN THỰC",
            color=0x00ff00,
            timestamp=datetime.now()
        )
        
        if self.security_system:
            # Thời gian thực
            embed.add_field(
                name="🕐 Thời gian", 
                value=datetime.now().strftime("%H:%M:%S"), 
                inline=True
            )
            
            # Trạng thái cửa real-time
            try:
                door_status = "🔒 KHÓA" if self.security_system.relay.value else "🔓 MỞ"
            except:
                door_status = "❓ KHÔNG RÕ"
            
            embed.add_field(name="🚪 Cửa", value=door_status, inline=True)
            
            # Bước xác thực hiện tại
            try:
                step = str(self.security_system.auth_state['step']).split('.')[-1]
                step_vn = {
                    'FACE': '👤 Khuôn mặt',
                    'FINGERPRINT': '👆 Vân tay', 
                    'RFID': '📱 Thẻ từ',
                    'PASSCODE': '🔑 Mật khẩu'
                }.get(step.upper(), step)
                
                embed.add_field(name="🔄 Đang xác thực", value=step_vn, inline=True)
            except:
                embed.add_field(name="🔄 Đang xác thực", value="❓ Không rõ", inline=True)
        
        embed.set_footer(text="Auto-refresh mỗi 3 giây")
        return embed
    
    async def _handle_menu(self, ctx):
        """Menu lệnh"""
        embed = discord.Embed(
            title="📖 MENU ĐIỀU KHIỂN HỆ THỐNG BẢO MẬT",
            description="Danh sách lệnh có sẵn:",
            color=0x9932cc
        )
        
        basic_commands = [
            ("🔑 !login <password>", "Đăng nhập Discord bot"),
            ("👋 !logout", "Đăng xuất"),
            ("📊 !status", "Trạng thái hệ thống"),
            ("🏓 !ping", "Test kết nối")
        ]
        
        auth_commands = [
            ("🔓 !unlock", "Mở khóa cửa từ xa"),
            ("🚀 !start_auth", "Bắt đầu xác thực 4 lớp"),
            ("🔍 !system_info", "Thông tin chi tiết hệ thống"),
            ("📊 !live_info", "Thông tin real-time (auto-update)")
        ]
        
        for cmd, desc in basic_commands:
            embed.add_field(name=cmd, value=desc, inline=False)
        
        if self._check_auth(ctx.author.id):
            embed.add_field(name="\n🔒 **LỆNH YÊU CẦU XÁC THỰC:**", value="━━━━━━━━━━━━━━━━━━", inline=False)
            for cmd, desc in auth_commands:
                embed.add_field(name=cmd, value=desc, inline=False)
        else:
            embed.add_field(name="\n⚠️ **Cần đăng nhập:**", value="Sử dụng `!login khoi2025` để truy cập thêm lệnh", inline=False)
        
        embed.add_field(name="\n🛡️ **BẢO MẬT:**", value="Bot sẽ thông báo mọi hoạt động bất thường", inline=False)
        embed.set_footer(text="Security System Discord Bot v2.2")
        await self._safe_send(ctx.send, embed=embed)
    
    def _check_auth(self, user_id):
        """Kiểm tra xác thực"""
        return user_id in self.authenticated_users
    
    async def _send_auth_required(self, ctx):
        """Gửi thông báo cần xác thực"""
        embed = discord.Embed(
            title="🔒 YÊU CẦU XÁC THỰC",
            description="Bạn cần đăng nhập trước!\nSử dụng: `!login khoi2025`",
            color=0xff0000
        )
        await self._safe_send(ctx.send, embed=embed)
    
    async def _unlock_via_system(self, ctx):
        """Mở khóa qua hệ thống chính"""
        # Simulate unlock process
        self.security_system.relay.off()  # Unlock
        
        success_embed = discord.Embed(
            title="🔓 CỬA ĐÃ MỞ",
            description="Cửa sẽ tự động khóa sau 3 giây",
            color=0x00ff00,
            timestamp=datetime.now()
        )
        success_embed.add_field(name="👤 Authorized by", value=ctx.author.name, inline=True)
        success_embed.add_field(name="📱 Via", value="Discord Remote", inline=True)
        
        await self._safe_send(ctx.send, embed=success_embed)
        
        # Gửi thông báo bảo mật
        await self.send_security_notification(
            f"🔓 **REMOTE UNLOCK** - Cửa được mở từ xa bởi {ctx.author.name} qua Discord", 
            "SUCCESS"
        )
        
        # Auto lock sau 3 giây
        await asyncio.sleep(3)
        self.security_system.relay.on()  # Lock
        
        lock_embed = discord.Embed(
            title="🔒 CỬA ĐÃ KHÓA LẠI",
            description="Tự động khóa",
            color=0xffa500
        )
        await self._safe_send(ctx.send, embed=lock_embed)
    
    # ===== FIXED NOTIFICATION METHODS =====
    
    async def send_notification(self, message):
        """FIXED: Method bị thiếu - Gửi notification đơn giản"""
        await self.send_security_notification(message, "INFO")
    
    async def send_security_notification(self, message, alert_type="INFO"):
        """FIXED: Gửi thông báo bảo mật không có timeout errors"""
        if not self.bot:
            return
            
        channel = self.bot.get_channel(CHANNEL_ID)
        if not channel:
            return
        
        # Màu sắc theo mức độ cảnh báo
        colors = {
            "SUCCESS": 0x00ff00,    # Xanh lá - Thành công
            "INFO": 0x0099ff,       # Xanh dương - Thông tin
            "WARNING": 0xffa500,    # Cam - Cảnh báo
            "DANGER": 0xff0000,     # Đỏ - Nguy hiểm
            "CRITICAL": 0x8b0000    # Đỏ đậm - Nghiêm trọng
        }
        
        # Icon theo mức độ
        icons = {
            "SUCCESS": "✅",
            "INFO": "ℹ️",  
            "WARNING": "⚠️",
            "DANGER": "🚨",
            "CRITICAL": "🔴"
        }
        
        embed = discord.Embed(
            title=f"{icons.get(alert_type, 'ℹ️')} CẢNH BÁO BẢO MẬT - {alert_type}",
            description=message,
            color=colors.get(alert_type, 0x0099ff),
            timestamp=datetime.now()
        )
        
        embed.add_field(name="🕐 Thời gian", value=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), inline=True)
        embed.add_field(name="📍 Nguồn", value="Hệ thống bảo mật", inline=True)
        
        if alert_type in ["DANGER", "CRITICAL"]:
            embed.add_field(name="🔔 Cần hành động", value="Kiểm tra hệ thống ngay!", inline=False)
        
        # FIXED: Không dùng timeout để tránh context manager error
        await self._safe_send(channel.send, embed=embed)
    
    async def send_authentication_failure_alert(self, step, attempts, details=""):
        """ULTRA SIMPLE: Gửi alert không có timeout context"""
        try:
            if not self.bot:
                return
                
            channel = self.bot.get_channel(CHANNEL_ID)
            if not channel:
                return
            
            # Xác định mức độ cảnh báo
            if attempts >= 3:
                title = "🚨 VI PHẠM BẢO MẬT NGHIÊM TRỌNG"
                color = 0x8b0000
            elif attempts >= 2:
                title = "🔴 NHIỀU LẦN THẤT BẠI"
                color = 0xff0000
            else:
                title = "⚠️ XÁC THỰC THẤT BẠI"
                color = 0xffa500
            
            embed = discord.Embed(title=title, color=color, timestamp=datetime.now())
            
            # Việt hóa step names
            step_names = {
                'face': 'Nhận diện khuôn mặt',
                'fingerprint': 'Vân tay',
                'rfid': 'Thẻ từ', 
                'passcode': 'Mật khẩu'
            }
            
            embed.add_field(name="🔍 Bước thất bại", value=step_names.get(step, step).upper(), inline=True)
            embed.add_field(name="🔢 Lần thử", value=f"{attempts}/5", inline=True)
            embed.add_field(name="⏰ Thời gian", value=datetime.now().strftime("%H:%M:%S"), inline=True)
            
            if details:
                embed.add_field(name="📋 Chi tiết", value=details[:500], inline=False)
            
            if attempts >= 3:
                embed.add_field(name="🚨 CẢNH BÁO", value="Có thể có hành vi xâm nhập!", inline=False)
            
            # SIMPLEST: Chỉ gửi trực tiếp
            await channel.send(embed=embed)
            logger.info(f"✅ Discord alert sent: {step} - attempt {attempts}")
            
        except Exception as e:
            logger.error(f"Discord send failed: {e}")
            # KHÔNG raise exception

    async def record_authentication_success(self, step):
        """Ghi lại thành công xác thực"""
        step_names = {
            'face': 'Nhận diện khuôn mặt',
            'fingerprint': 'Vân tay', 
            'rfid': 'Thẻ từ',
            'passcode': 'Mật khẩu'
        }
        
        message = f"✅ **{step_names.get(step, step).upper()} THÀNH CÔNG**\nBước xác thực hoàn tất thành công"
        await self.send_security_notification(message, "SUCCESS")
    
    # ===== FIXED BOT MANAGEMENT =====
    
    def start_bot(self):
        """FIXED: Khởi động bot trong thread riêng"""
        if self.bot_thread and self.bot_thread.is_alive():
            return False
        
        def run_bot():
            try:
                # Tạo event loop mới cho thread này
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
                
                # Chạy bot
                self.loop.run_until_complete(self.bot.start(TOKEN))
            except Exception as e:
                logger.error(f"Discord bot error: {e}")
            finally:
                if self.loop and not self.loop.is_closed():
                    self.loop.close()
        
        self.bot_thread = threading.Thread(target=run_bot, daemon=True)
        self.bot_thread.start()
        return True
    
    def stop_bot(self):
        """FIXED: Dừng bot với proper async cleanup"""
        try:
            if self.bot and self.loop:
                # Đóng bot trong loop của nó
                if not self.loop.is_closed():
                    # Schedule bot.close() trong loop của bot
                    future = asyncio.run_coroutine_threadsafe(self.bot.close(), self.loop)
                    # Đợi tối đa 3 giây
                    future.result(timeout=3)
            
            # Đợi thread dừng
            if self.bot_thread and self.bot_thread.is_alive():
                self.bot_thread.join(timeout=3)
                
            # Đóng executor
            if hasattr(self, 'executor'):
                self.executor.shutdown(wait=False)
                
            logger.info("Discord bot stopped successfully")
            
        except Exception as e:
            logger.error(f"Error stopping Discord bot: {e}")
