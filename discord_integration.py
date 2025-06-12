#!/usr/bin/env python3
"""
Discord Integration cho hệ thống khóa bảo mật - Updated Version
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
        security_system: Reference đến AIEnhancedSecuritySystem
        """
        self.security_system = security_system
        self.authenticated_users = set()
        self.bot_thread = None
        self.bot = None
        self.failed_attempts_count = 0  # Đếm số lần thất bại
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
        
        @self.bot.command(name='menu')
        async def menu(ctx):
            await self._handle_menu(ctx)
        
        @self.bot.command(name='ping')
        async def ping(ctx):
            latency = round(self.bot.latency * 1000)
            embed = discord.Embed(title="🏓 PONG!", description=f"Latency: {latency}ms", color=0x00ff00)
            await ctx.send(embed=embed)
    
    async def _send_startup_message(self):
        """Gửi thông báo khởi động"""
        channel = self.bot.get_channel(CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title="🔐 SECURITY SYSTEM DISCORD BOT",
                description="✅ Đã kết nối với hệ thống khóa bảo mật!",
                color=0x00ff00,
                timestamp=datetime.now()
            )
            embed.add_field(name="🤖 Bot Status", value="Online", inline=True)
            embed.add_field(name="🔒 Security System", value="Connected", inline=True)
            embed.add_field(name="📱 Commands", value="!menu", inline=True)
            embed.add_field(name="🛡️ Security Alert", value="Active Monitoring", inline=True)
            await channel.send(embed=embed)
    
    async def _handle_login(self, ctx, password):
        """Xử lý đăng nhập"""
        user_id = ctx.author.id
        
        if password != BOT_PASSWORD:
            embed = discord.Embed(
                title="❌ XÁC THỰC THẤT BẠI",
                description="Mật khẩu không chính xác!\nSử dụng: `!login khoi2025`",
                color=0xff0000
            )
            await ctx.send(embed=embed)
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
        
        await ctx.send(embed=embed)
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
        await ctx.send(embed=embed)
    
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
        
        await ctx.send(embed=embed)
    
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
        await ctx.send(embed=embed)
        
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
                await ctx.send(embed=error_embed)
        else:
            # Simulation mode
            await asyncio.sleep(1)
            success_embed = discord.Embed(
                title="🔓 MỞ KHÓA THÀNH CÔNG",
                description="Cửa sẽ tự động khóa sau 3 giây (SIMULATION)",
                color=0x00ff00
            )
            await ctx.send(embed=success_embed)
    
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
        await ctx.send(embed=embed)
        
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
                await ctx.send(embed=error_embed)
    
    async def _handle_system_info(self, ctx):
        """Thông tin chi tiết hệ thống"""
        if not self._check_auth(ctx.author.id):
            await self._send_auth_required(ctx)
            return
        
        embed = discord.Embed(
            title="🔍 THÔNG TIN HỆ THỐNG CHI TIẾT",
            color=0x9932cc,
            timestamp=datetime.now()
        )
        
        if self.security_system:
            try:
                # Lấy thông tin từ face recognizer
                face_info = self.security_system.face_recognizer.get_database_info()
                fp_count = len(self.security_system.admin_data.get_fingerprint_ids())
                rfid_count = len(self.security_system.admin_data.get_rfid_uids())
                
                embed.add_field(name="🤖 AI Face Recognition", value=f"{face_info['total_people']} người đã đăng ký", inline=True)
                embed.add_field(name="👆 Fingerprint Database", value=f"{fp_count} vân tay", inline=True)  
                embed.add_field(name="📱 RFID Cards", value=f"{rfid_count} thẻ", inline=True)
                
                embed.add_field(name="🧠 AI Model Status", value="✅ Loaded", inline=True)
                embed.add_field(name="📹 Camera Status", value="✅ Active", inline=True)
                embed.add_field(name="🔊 Hardware Status", value="✅ Connected", inline=True)
                
                embed.add_field(name="⚠️ Security Alerts", value=f"{self.failed_attempts_count} failed attempts today", inline=True)
                embed.add_field(name="🛡️ Monitoring", value="Real-time Active", inline=True)
                
            except Exception as e:
                embed.add_field(name="⚠️ System Error", value=str(e), inline=False)
        else:
            embed.add_field(name="⚠️ Status", value="Simulation Mode", inline=False)
        
        await ctx.send(embed=embed)
    
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
            ("🔍 !system_info", "Thông tin chi tiết hệ thống")
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
        embed.set_footer(text="Security System Discord Bot v2.0")
        await ctx.send(embed=embed)
    
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
        await ctx.send(embed=embed)
    
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
        
        await ctx.send(embed=success_embed)
        
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
        await ctx.send(embed=lock_embed)
    
    async def send_security_notification(self, message, alert_type="INFO"):
        """Gửi thông báo bảo mật với các mức độ khác nhau"""
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
            title=f"{icons.get(alert_type, 'ℹ️')} SECURITY ALERT - {alert_type}",
            description=message,
            color=colors.get(alert_type, 0x0099ff),
            timestamp=datetime.now()
        )
        
        embed.add_field(name="🕐 Time", value=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), inline=True)
        embed.add_field(name="📍 Source", value="AI Security System", inline=True)
        
        if alert_type in ["DANGER", "CRITICAL"]:
            embed.add_field(name="🔔 Action Required", value="Check system immediately!", inline=False)
        
        await channel.send(embed=embed)
    
    async def send_failed_attempt_alert(self, step, attempts_count, total_failed_today):
        """Gửi cảnh báo khi có lỗi xác thực nhiều lần"""
        self.failed_attempts_count = total_failed_today
        
        if attempts_count >= 3:
            alert_type = "CRITICAL"
            message = f"🚨 **CRITICAL SECURITY BREACH ATTEMPT**\n"
            message += f"Step: {step}\n"
            message += f"Consecutive failures: {attempts_count}\n"
            message += f"Total failed today: {total_failed_today}\n"
            message += f"**POSSIBLE INTRUSION ATTEMPT!**"
        elif attempts_count >= 2:
            alert_type = "DANGER"  
            message = f"🔴 **MULTIPLE FAILED ATTEMPTS**\n"
            message += f"Step: {step}\n"
            message += f"Consecutive failures: {attempts_count}\n"
            message += f"Total failed today: {total_failed_today}"
        else:
            alert_type = "WARNING"
            message = f"⚠️ **AUTHENTICATION FAILED**\n"
            message += f"Step: {step}\n"
            message += f"Failed attempts: {attempts_count}\n"
            message += f"Total failed today: {total_failed_today}"
        
        await self.send_security_notification(message, alert_type)
    
    async def send_success_notification(self, step_info="4-layer authentication completed"):
        """Gửi thông báo khi mở khóa thành công"""
        message = f"🔓 **DOOR UNLOCKED SUCCESSFULLY**\n"
        message += f"Authentication: {step_info}\n"
        message += f"Time: {datetime.now().strftime('%H:%M:%S')}\n"
        message += f"All security layers verified ✅"
        
        await self.send_security_notification(message, "SUCCESS")
    
    def start_bot(self):
        """Khởi động bot trong thread riêng"""
        if self.bot_thread and self.bot_thread.is_alive():
            return False
        
        def run_bot():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.bot.start(TOKEN))
            except Exception as e:
                logger.error(f"Discord bot error: {e}")
        
        self.bot_thread = threading.Thread(target=run_bot, daemon=True)
        self.bot_thread.start()
        return True
    
    def stop_bot(self):
        """Dừng bot"""
        if self.bot:
            asyncio.create_task(self.bot.close())
