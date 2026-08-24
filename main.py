import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import asyncio
import re
import random
import string
import os
from aiohttp import web  # Thêm thư viện dựng Web Server

# ================= WEB SERVER PHỤ CHO RENDER =================
async def handle_ping(request):
    return web.Response(text="Bot is running and alive!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"🌐 Web Server đã mở thành công trên cổng {port} để phục vụ Render!")

# ================= CẤU HÌNH BOT DISCORD =================
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=":", intents=intents)
        
        self.TOKEN = os.getenv('BOT_TOKEN') #[cite: 1]
        self.TARGET_EMOJI_GUILD_ID = 1503922700408586240 #[cite: 1]
        
        self.server_configs = {}
        self.birthdays = {}
        self.verify_codes = {}

    async def setup_hook(self):
        asyncio.create_task(start_web_server())
        await self.tree.sync()
        print("Đã đồng bộ Slash Commands và khởi động Bot thành công!")

bot = MyBot()

@bot.event
async def on_ready():
    print(f'Bot đã đăng nhập thành công với tên: {bot.user.tag}')
    bot.loop.create_task(check_birthdays_loop())


# ================= TÍNH NĂNG: PING BOT ĐỂ RANDOM EMOJI =================
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        await bot.process_commands(message)
        return

    if bot.user in message.mentions:
        emoji_guild = bot.get_guild(bot.TARGET_EMOJI_GUILD_ID)
        
        random_emoji = ""
        if emoji_guild and emoji_guild.emojis:
            chosen_emoji = random.choice(emoji_guild.emojis)
            random_emoji = str(chosen_emoji)
        
        await message.reply(f"Hé lô bạn! {random_emoji} (Gõ `:mute` hoặc `:ban` hoặc dùng các lệnh `/setup-...` để quản lý nhé!)")

    await bot.process_commands(message)


# ================= GIAO DIỆN BẢNG SETUP (MODALS) =================

class SetupWelcomeModal(discord.ui.Modal, title="Cài đặt Chào mừng (Welcome)"):
    channel_id_input = discord.ui.TextInput(
        label="ID Kênh hoặc Tên Kênh (hoặc để trống lấy hiện tại)",
        placeholder="Nhập ID kênh gửi tin nhắn chào mừng...",
        required=False,
        max_length=50
    )
    
    message_input = discord.ui.TextInput(
        label="Nội dung chào mừng tùy chỉnh",
        style=discord.TextStyle.paragraph,
        placeholder="Dùng {member} để nhắc tên thành viên...",
        default="Xin chào {member}, chúc bạn có những phút giây vui vẻ tại server!",
        required=True
    )
    
    image_url_input = discord.ui.TextInput(
        label="Link ảnh Banner/Thumbnail (Tùy chọn)",
        placeholder="Dán link ảnh (https://...) vào đây...",
        required=False,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        if guild_id not in bot.server_configs:
            bot.server_configs[guild_id] = {}
            
        target_channel = interaction.channel
        chan_text = self.channel_id_input.value.strip()
        if chan_text:
            if chan_text.isdigit():
                found_chan = interaction.guild.get_channel(int(chan_text))
                if found_chan:
                    target_channel = found_chan
            else:
                found_chan = discord.utils.get(interaction.guild.text_channels, name=chan_text)
                if found_chan:
                    target_channel = found_chan

        bot.server_configs[guild_id]["welcome_channel"] = target_channel.id
        bot.server_configs[guild_id]["welcome_msg"] = self.message_input.value
        bot.server_configs[guild_id]["welcome_img"] = self.image_url_input.value.strip()

        embed = discord.Embed(
            title="✨ Thiết Lập Chào Mừng Thành Công",
            description="Hệ thống đã lưu cấu hình tin nhắn chào mừng mới cho server của bạn.",
            color=discord.Color.brand_green()
        )
        embed.add_field(name="📂 Kênh áp dụng", value=target_channel.mention, inline=False)
        embed.add_field(name="💬 Nội dung mẫu", value=f"```text\n{self.message_input.value}\n```", inline=False)
        embed.add_field(name="🖼️ Ảnh đính kèm", value="Có hình ảnh" if self.image_url_input.value.strip() else "Không sử dụng", inline=True)
        embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
        embed.timestamp = datetime.now()

        await interaction.response.send_message(embed=embed, ephemeral=True)


class SetupVerifyRoleModal(discord.ui.Modal, title="Cài đặt Role Verify"):
    role_input = discord.ui.TextInput(
        label="Nhập Tên Role hoặc ID của Role",
        placeholder="Ví dụ: Thanh Vien hoặc 123456789...",
        required=True,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        if guild_id not in bot.server_configs:
            bot.server_configs[guild_id] = {}

        role_text = self.role_input.value.strip()
        found_role = None

        if role_text.isdigit():
            found_role = interaction.guild.get_role(int(role_text))
        else:
            found_role = discord.utils.get(interaction.guild.roles, name=role_text)

        if not found_role:
            err_embed = discord.Embed(
                title="❌ Thất Bại",
                description=f"Không tìm thấy Role nào có tên hoặc ID là **`{role_text}`** trong server này!",
                color=discord.Color.brand_red()
            )
            return await interaction.response.send_message(embed=err_embed, ephemeral=True)

        bot.server_configs[guild_id]["verify_role"] = found_role.id

        embed = discord.Embed(
            title="🛡️ Đã Cài Đặt Role Verify",
            description=f"Thành viên hoàn thành xác thực sẽ tự động nhận vai trò: {found_role.mention}",
            color=discord.Color.brand_green()
        )
        embed.timestamp = datetime.now()
        await interaction.response.send_message(embed=embed, ephemeral=True)


class SetupBuongBanModal(discord.ui.Modal, title="Cài đặt Kênh Buông Bán"):
    channel_input = discord.ui.TextInput(
        label="Nhập Tên Kênh hoặc ID Kênh Buông Bán",
        placeholder="Ví dụ: buong-ban hoặc 123456789...",
        required=True,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        if guild_id not in bot.server_configs:
            bot.server_configs[guild_id] = {}

        chan_text = self.channel_input.value.strip()
        found_chan = None

        if chan_text.isdigit():
            found_chan = interaction.guild.get_channel(int(chan_text))
        else:
            found_chan = discord.utils.get(interaction.guild.text_channels, name=chan_text)

        if not found_chan:
            err_embed = discord.Embed(
                title="❌ Thất Bại",
                description=f"Không tìm thấy kênh văn bản nào có tên hoặc ID là **`{chan_text}`**!",
                color=discord.Color.brand_red()
            )
            return await interaction.response.send_message(embed=err_embed, ephemeral=True)

        bot.server_configs[guild_id]["buongban_channel"] = found_chan.id

        embed = discord.Embed(
            title="🛍️ Đã Thiết Lập Kênh Buông Bán",
            description=f"Các thông báo sản phẩm và dịch vụ sẽ được chuyển đến kênh: {found_chan.mention}",
            color=discord.Color.orange()
        )
        embed.timestamp = datetime.now()
        await interaction.response.send_message(embed=embed, ephemeral=True)


class SellItemModal(discord.ui.Modal, title="Đăng Bán Sản Phẩm"):
    item_name = discord.ui.TextInput(
        label="Tên sản phẩm",
        placeholder="Ví dụ: Acc Roblox VIP, Key bản quyền...",
        required=True,
        max_length=100
    )
    item_price = discord.ui.TextInput(
        label="Giá tiền (Chỉ nhập số, ví dụ: 50000)",
        placeholder="50000",
        required=True,
        max_length=20
    )
    bank_info = discord.ui.TextInput(
        label="Thông tin Ngân hàng & STK",
        placeholder="Ví dụ: MB Bank - 123456789 - Chủ TK: Nguyen Van A",
        required=True,
        max_length=100
    )
    secret_content = discord.ui.TextInput(
        label="Nội dung/Tài khoản ẩn (Chỉ người mua thấy)",
        style=discord.TextStyle.paragraph,
        placeholder="Nhập tài khoản, mật khẩu, link tải hoặc thông tin bí mật ở đây...",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        config = bot.server_configs.get(interaction.guild_id, {})
        channel_id = config.get("buongban_channel")
        
        if not channel_id:
            err_embed = discord.Embed(
                title="⚠️ Chưa Cài Đặt Kênh",
                description="Server chưa thiết lập kênh Buông Bán! Admin vui lòng dùng lệnh `/setup-buong-ban` trước.",
                color=discord.Color.gold()
            )
            return await interaction.response.send_message(embed=err_embed, ephemeral=True)
            
        channel = interaction.guild.get_channel(channel_id)
        if not channel:
            return await interaction.response.send_message("❌ Không tìm thấy kênh Buông Bán đã cài đặt!", ephemeral=True)

        price_text = self.item_price.value.strip()
        bank_desc = self.bank_info.value.strip()
        product_name = self.item_name.value.strip()

        prompt_embed = discord.Embed(
            title="📸 Tải Lên Mã QR Thanh Toán",
            description="**Vui lòng gửi ảnh mã QR ngân hàng của bạn vào kênh chat này ngay bây giờ!**\n*(Bạn có 60 giây để tải ảnh lên, bot sẽ tự động hủy nếu quá hạn)*",
            color=discord.Color.blurple()
        )
        await interaction.response.send_message(embed=prompt_embed, ephemeral=True)

        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel and len(m.attachments) > 0

        try:
            msg = await bot.wait_for('message', timeout=60.0, check=check)
            qr_image_url = msg.attachments[0].url
            try:
                await msg.delete()
            except:
                pass
        except asyncio.TimeoutError:
            timeout_embed = discord.Embed(
                title="⏰ Hết Thời Gian",
                description="Không nhận được ảnh QR trong 60 giây. Đã hủy lệnh đăng bán sản phẩm!",
                color=discord.Color.brand_red()
            )
            return await interaction.followup.send(embed=timeout_embed, ephemeral=True)

        embed = discord.Embed(
            title="🌟 SẢN PHẨM / DỊCH VỤ MỚI MỞ BÁN",
            description=f"• **Tên sản phẩm:** **{product_name}**\n• **Giá thành:** 💰 `{price_text} VNĐ`\n• **Người bán:** {interaction.user.mention}\n• **Thanh toán:** `{bank_desc}`",
            color=discord.Color.orange()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_image(url=qr_image_url)
        embed.set_footer(text="Quét mã QR trên để chuyển khoản và bấm nút 'Mua Ngay' bên dưới để nhận tài khoản/thông tin riêng tư!")
        embed.timestamp = datetime.now()

        view = BuyItemView(secret_data=self.secret_content.value, seller=interaction.user)
        await channel.send(embed=embed, view=view)

        success_embed = discord.Embed(
            title="✅ Đăng Bán Thành Công",
            description=f"Bài đăng của bạn đã được xuất bản hoàn tất tại kênh {channel.mention}!",
            color=discord.Color.brand_green()
        )
        await interaction.followup.send(embed=success_embed, ephemeral=True)


# ================= GIAO DIỆN NÚT MUA HÀNG =================
class BuyItemView(discord.ui.View):
    def __init__(self, secret_data: str, seller: discord.Member):
        super().__init__(timeout=None)
        self.secret_data = secret_data
        self.seller = seller

    @discord.ui.button(label="🛒 Mua Ngay & Nhận Hàng", style=discord.ButtonStyle.green, emoji="⚡", custom_id="buy_item_button")
    async def buy_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user == self.seller:
            return await interaction.response.send_message("⚠️ Bạn không thể tự mua sản phẩm do chính mình tạo ra!", ephemeral=True)

        success_embed = discord.Embed(
            title="🎉 Giao Dịch Thành Công!",
            description=f"*(Hãy đảm bảo bạn đã quét mã QR chuyển khoản chính xác cho người bán [{self.seller.mention}])*\n\n🔒 **Nội dung / Tài khoản riêng tư của bạn:**\n```text\n{self.secret_data}\n```",
            color=discord.Color.brand_green()
        )
        success_embed.set_footer(text="Cảm ơn bạn đã tin tưởng và ủng hộ giao dịch qua hệ thống!")
        await interaction.response.send_message(embed=success_embed, ephemeral=True)


# ================= CÁC LỆNH SLASH COMMANDS =================

@bot.tree.command(name="setup-welcome", description="Mở bảng cài đặt tin nhắn chào mừng thành viên mới")
@app_commands.checks.has_permissions(administrator=True)
async def setup_welcome(interaction: discord.Interaction):
    await interaction.response.send_modal(SetupWelcomeModal())

@bot.tree.command(name="setup-verify", description="Cài đặt kênh gửi bảng nút bấm xác thực (Verify)")
@app_commands.describe(kenh="Chọn kênh verify (Bỏ trống sẽ lấy kênh hiện tại)")
@app_commands.checks.has_permissions(administrator=True)
async def setup_verify(interaction: discord.Interaction, kenh: discord.TextChannel = None):
    target_channel = kenh if kenh else interaction.channel
    
    if interaction.guild_id not in bot.server_configs:
        bot.server_configs[interaction.guild_id] = {}
        
    bot.server_configs[interaction.guild_id]["verify_channel"] = target_channel.id
    
    embed = discord.Embed(
        title="🛡️ HỆ THỐNG XÁC THỰC THÀNH VIÊN (VERIFY)",
        description="Chào mừng bạn đến với server! Để mở khóa toàn bộ các kênh trò chuyện và truy cập đầy đủ tính năng, vui lòng nhấn vào nút **Xác thực (Verify)** màu xanh bên dưới.\n\n*Hệ thống sẽ gửi mã xác nhận ngẫu nhiên nhằm đảm bảo an toàn tuyệt đối cho cộng đồng.*",
        color=discord.Color.brand_green()
    )
    embed.set_footer(text="Bảo mật & Tự động hóa hệ thống")
    view = VerifyRegisterView()
    await target_channel.send(embed=embed, view=view)
    
    res_embed = discord.Embed(
        title="✅ Kích Hoạt Thành Công",
        description=f"Đã gửi giao diện bảng Verify ra kênh: {target_channel.mention}",
        color=discord.Color.brand_green()
    )
    await interaction.response.send_message(embed=res_embed, ephemeral=True)

@bot.tree.command(name="setup-verify-role", description="Mở bảng cài đặt Role sẽ được cấp sau khi Verify thành công")
@app_commands.checks.has_permissions(administrator=True)
async def setup_verify_role(interaction: discord.Interaction):
    await interaction.response.send_modal(SetupVerifyRoleModal())

@bot.tree.command(name="setup-buong-ban", description="Mở bảng cài đặt kênh Buông Bán")
@app_commands.checks.has_permissions(administrator=True)
async def setup_buong_ban(interaction: discord.Interaction):
    await interaction.response.send_modal(SetupBuongBanModal())

@bot.tree.command(name="dang-ban", description="Mở bảng điền thông tin sản phẩm để đăng bán")
async def dang_ban(interaction: discord.Interaction):
    await interaction.response.send_modal(SellItemModal())

@bot.tree.command(name="setup-sinhnhat", description="Cài đặt kênh nhận thông báo chúc mừng sinh nhật")
@app_commands.describe(kenh="Chọn kênh thông báo sinh nhật (Bỏ trống sẽ lấy kênh hiện tại)")
@app_commands.checks.has_permissions(administrator=True)
async def setup_sinhnhat(interaction: discord.Interaction, kenh: discord.TextChannel = None):
    target_channel = kenh if kenh else interaction.channel
    
    if interaction.guild_id not in bot.server_configs:
        bot.server_configs[interaction.guild_id] = {}
        
    bot.server_configs[interaction.guild_id]["birthday_channel"] = target_channel.id
    
    embed = discord.Embed(
        title="🎂 Đã Cài Đặt Kênh Sinh Nhật",
        description=f"Các lời chúc mừng sinh nhật thành viên tự động sẽ được gửi vào kênh: {target_channel.mention}",
        color=discord.Color.pink()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="setup-dangky-sinhnhat", description="Gửi bảng nút bấm đăng ký ngày sinh vào kênh")
@app_commands.describe(kenh="Chọn kênh để gửi bảng đăng ký (Bỏ trống sẽ lấy kênh hiện tại)")
@app_commands.checks.has_permissions(administrator=True)
async def setup_dangky_sinhnhat(interaction: discord.Interaction, kenh: discord.TextChannel = None):
    target_channel = kenh if kenh else interaction.channel
    
    embed = discord.Embed(
        title="🎈 ĐĂNG KÝ NGÀY SINH NHẬT CÁ NHÂN",
        description="Hãy chia sẻ ngày sinh nhật của bạn với chúng tôi để nhận những lời chúc tốt đẹp nhất vào ngày đặc biệt!\n\n🔒 **Bảo mật tuyệt đối:** Ngày sinh của bạn được lưu trữ hoàn toàn riêng tư, bot chỉ dùng để gửi lời chúc mừng đúng ngày chứ **không** hiển thị ra công khai ngoài cộng đồng.",
        color=discord.Color.pink()
    )
    embed.set_footer(text="Hệ thống Chúc mừng Tự động")
    view = BirthdayRegisterView()
    await target_channel.send(embed=embed, view=view)
    
    res_embed = discord.Embed(
        title="✅ Gửi Thành Công",
        description=f"Đã phát hành bảng đăng ký sinh nhật tới kênh {target_channel.mention}!",
        color=discord.Color.brand_green()
    )
    await interaction.response.send_message(embed=res_embed, ephemeral=True)

@setup_welcome.error
@setup_verify.error
@setup_verify_role.error
@setup_buong_ban.error
@setup_sinhnhat.error
@setup_dangky_sinhnhat.error
async def slash_command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.errors.MissingPermissions):
        embed = discord.Embed(title="⛔ Từ Chối Truy Cập", description="Bạn cần có quyền Quản trị viên (`Administrator`) để sử dụng lệnh hệ thống này!", color=discord.Color.brand_red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        embed = discord.Embed(title="❌ Đã Xảy Ra Lỗi", description=f"Chi tiết lỗi: `{error}`", color=discord.Color.brand_red())
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ================= CÁC LỆNH PREFIX COMMANDS =================

@bot.command(name="mute", description="Cấm ngôn thành viên")
@commands.has_permissions(moderate_members=True)
async def mute(ctx, member: discord.Member, minutes: int, *, reason: str = "Không có lý do"):
    if minutes <= 0:
        return await ctx.send("❌ Thời gian mute phải lớn hơn 0 phút!")
    
    duration = timedelta(minutes=minutes)
    try:
        await member.timeout(duration, reason=reason)
        embed = discord.Embed(
            title="🔇 THÀNH VIÊN BỊ CẤM NGÔN (TIMEOUT)",
            description=f"• **Thành viên:** {member.mention}\n• **Thời hạn:** `{minutes} phút`\n• **Lý do:** `{reason}`",
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"Người thực hiện: {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ Không thể mute thành viên này. Lỗi: {e}")

@bot.command(name="ban", description="Cấm vĩnh viễn thành viên")
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason: str = "Không có lý do"):
    try:
        await member.ban(reason=reason)
        embed = discord.Embed(
            title="🔨 THÀNH VIÊN BỊ TRỤC XUẤT (BAN)",
            description=f"• **Thành viên:** {member.mention}\n• **Hình thức:** Cấm vĩnh viễn\n• **Lý do:** `{reason}`",
            color=discord.Color.brand_red()
        )
        embed.set_footer(text=f"Người thực hiện: {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ Không thể ban thành viên này. Lỗi: {e}")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Bạn không có quyền sử dụng lệnh này!", delete_after=5)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Thiếu thông số! Cú pháp đúng: `:mute @User [phút] [lý do]` hoặc `:ban @User [lý do]`", delete_after=5)
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        print(f"Lỗi lệnh prefix: {error}")


# ================= GIAO DIỆN (UI) NÚT BẤM & MODAL =================

class VerifyModal(discord.ui.Modal):
    def __init__(self, correct_code: str):
        super().__init__(title="Xác thực Mã Ngẫu Nhiên")
        self.correct_code = correct_code
        self.code_input = discord.ui.TextInput(
            label=f"Nhập chính xác mã: [ {correct_code} ]",
            placeholder="Nhập lại mã ở trên vào đây...",
            min_length=4, max_length=4, required=True
        )
        self.add_item(self.code_input)

    async def on_submit(self, interaction: discord.Interaction):
        user_input = self.code_input.value.strip()
        if user_input != self.correct_code:
            err_embed = discord.Embed(title="❌ Xác Thực Thất Bại", description="Mã xác thực không chính xác! Vui lòng bấm nút Verify lại để nhận mã mới.", color=discord.Color.brand_red())
            return await interaction.response.send_message(embed=err_embed, ephemeral=True)
        
        config = bot.server_configs.get(interaction.guild_id, {})
        role_id = config.get("verify_role")
        
        if not role_id:
            err_embed = discord.Embed(title="⚠️ Chưa Cài Đặt", description="Server chưa thiết lập Role Verify! Vui lòng liên hệ Quản trị viên.", color=discord.Color.gold())
            return await interaction.response.send_message(embed=err_embed, ephemeral=True)
            
        role = interaction.guild.get_role(role_id)
        if not role:
            return await interaction.response.send_message("❌ Không tìm thấy Role Verify cấu hình trong server này!", ephemeral=True)
            
        if role in interaction.user.roles:
            info_embed = discord.Embed(title="ℹ️ Thông Báo", description="Bạn đã thực hiện xác thực từ trước rồi!", color=discord.Color.blurple())
            return await interaction.response.send_message(embed=info_embed, ephemeral=True)
        
        try:
            await interaction.user.add_roles(role)
            bot.verify_codes.pop(interaction.user.id, None)
            
            success_embed = discord.Embed(
                title="✅ Xác Thực Thành Công!",
                description=f"Chúc mừng bạn đã hoàn thành xác thực. Hệ thống đã cấp vai trò {role.mention} cho bạn.",
                color=discord.Color.brand_green()
            )
            await interaction.response.send_message(embed=success_embed, ephemeral=True)
        except Exception as e:
            print(e)
            await interaction.response.send_message("❌ Đã xảy ra lỗi khi cấp quyền xác thực (Bot có thể thiếu quyền quản lý vai trò hoặc Role nằm cao hơn Role của Bot).", ephemeral=True)

class VerifyRegisterView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Xác thực (Verify)", style=discord.ButtonStyle.success, emoji="✅", custom_id="verify_modal_btn")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        random_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        bot.verify_codes[interaction.user.id] = random_code
        await interaction.response.send_modal(VerifyModal(random_code))


class BirthdayModal(discord.ui.Modal, title="Đăng ký Sinh nhật (Riêng tư)"):
    bday_input = discord.ui.TextInput(
        label="Nhập ngày sinh của bạn (Định dạng DD/MM)",
        placeholder="Ví dụ: 25/12", min_length=5, max_length=5, required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        date_str = self.bday_input.value.strip()
        date_regex = r"^(0[1-9]|[12][0-9]|3[01])\/(0[1-9]|1[0-2])$"
        if not re.match(date_regex, date_str):
            err_embed = discord.Embed(title="❌ Lỗi Định Dạng", description="Vui lòng nhập đúng cú pháp `DD/MM` (Ví dụ: `25/12`).", color=discord.Color.brand_red())
            return await interaction.response.send_message(embed=err_embed, ephemeral=True)
            
        bot.birthdays[interaction.user.id] = date_str
        
        success_embed = discord.Embed(
            title="🎂 Đăng Ký Sinh Nhật Thành Công",
            description="Thông tin ngày sinh của bạn đã được lưu trữ bảo mật tuyệt đối!",
            color=discord.Color.pink()
        )
        await interaction.response.send_message(embed=success_embed, ephemeral=True)

class BirthdayRegisterView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Đăng ký Sinh nhật", style=discord.ButtonStyle.primary, emoji="🎂", custom_id="birthday_register_btn")
    async def birthday_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BirthdayModal())


# ================= SỰ KIỆN WELCOME & SINH NHẬT =================
@bot.event
async def on_member_join(member):
    config = bot.server_configs.get(member.guild.id)
    if not config or not config.get("welcome_channel"):
        return
    
    channel = member.guild.get_channel(config["welcome_channel"])
    if channel:
        custom_msg = config.get("welcome_msg", "Xin chào {member}!").replace("{member}", member.mention)
        img_url = config.get("welcome_img", "")
        
        embed = discord.Embed(
            title="👋 CHÀO MỪNG THÀNH VIÊN MỚI",
            description=custom_msg,
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        if img_url:
            embed.set_image(url=img_url)
        embed.set_footer(text=f"Thứ hạng thành viên: #{len(member.guild.members)}")
        embed.timestamp = datetime.now()
        
        await channel.send(embed=embed)


async def check_birthdays_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        now = datetime.now()
        current_day = now.strftime("%d/%m")
        
        for user_id, bday in list(bot.birthdays.items()):
            if bday == current_day:
                for guild_id, config in bot.server_configs.items():
                    if config.get("birthday_channel"):
                        guild = bot.get_guild(guild_id)
                        if guild:
                            channel = guild.get_channel(config["birthday_channel"])
                            if channel:
                                member = guild.get_member(user_id)
                                avatar_url = member.display_avatar.url if member else None

                                bday_embed = discord.Embed(
                                    title="🎉 CHÚC MỪNG SINH NHẬT! 🎂",
                                    description=f"Hôm nay là một ngày vô cùng đặc biệt! Chúc mừng sinh nhật thành viên <@{user_id}>! 🎈\n\nChúc bạn tuổi mới luôn tràn đầy niềm vui, sức khỏe dồi dào, học tập và mọi dự định đều thành công rực rỡ! 🎁✨",
                                    color=discord.Color.gold()
                                )
                                if avatar_url:
                                    bday_embed.set_thumbnail(url=avatar_url)
                                bday_embed.set_footer(text="Hệ thống Chúc mừng Sinh nhật Tự động")
                                bday_embed.timestamp = datetime.now()

                                await channel.send(content=f"🎉 Chúc mừng sinh nhật <@{user_id}>! 🥳", embeds=[bday_embed])
                                
                bot.birthdays.pop(user_id, None)
                
        await asyncio.sleep(86400)

bot.run(bot.TOKEN)