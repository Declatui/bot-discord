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
    
    # Render tự cấp biến môi trường PORT, nếu chạy local sẽ dùng cổng 8080
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
        self.tree = app_commands.CommandTree(self)
        
        # Lấy Token từ biến môi trường của Render (Bảo mật tuyệt đối)
        self.TOKEN = os.getenv('BOT_TOKEN')
        
        # ID Guild chứa các emoji bạn muốn random khi ping bot
        self.TARGET_EMOJI_GUILD_ID = 1503922700408586240
        
        self.server_configs = {}
        self.birthdays = {}
        self.verify_codes = {}

    async def setup_hook(self):
        # Khởi động Web Server chạy ngầm song song với Bot Discord
        self.loop.create_terask = asyncio.create_task(start_web_server())
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

        await interaction.response.send_message(
            f"✅ **Đã lưu cài đặt Welcome thành công!**\n- **Kênh:** {target_channel.mention}\n- **Ảnh đính kèm:** {'Có' if self.image_url_input.value.strip() else 'Không'}",
            ephemeral=True
        )


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
            return await interaction.response.send_message(
                f"❌ Không tìm thấy Role nào có tên hoặc ID là **`{role_text}`** trong server này!",
                ephemeral=True
            )

        bot.server_configs[guild_id]["verify_role"] = found_role.id

        await interaction.response.send_message(
            f"✅ **Đã cài đặt thành công Role Verify!** Khi người dùng verify xong sẽ nhận role: {found_role.mention}",
            ephemeral=True
        )


class SetupBuongBanModal(discord.ui.Modal, title="Cài đặt Kênh Buông Bàn"):
    channel_input = discord.ui.TextInput(
        label="Nhập Tên Kênh hoặc ID Kênh Buông Bàn",
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
            return await interaction.response.send_message(
                f"❌ Không tìm thấy kênh văn bản nào có tên hoặc ID là **`{chan_text}`** trong server này!",
                ephemeral=True
            )

        bot.server_configs[guild_id]["buongban_channel"] = found_chan.id

        await interaction.response.send_message(
            f"✅ **Đã cài đặt thành công kênh Buông Bàn!** Các thông báo sản phẩm sẽ được gửi tới: {found_chan.mention}",
            ephemeral=True
        )


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
            return await interaction.response.send_message(
                "❌ Server chưa cài đặt kênh Buông Bàn! Admin vui lòng dùng lệnh `/setup-buong-ban` trước.",
                ephemeral=True
            )
            
        channel = interaction.guild.get_channel(channel_id)
        if not channel:
            return await interaction.response.send_message("❌ Không tìm thấy kênh Buông Bàn đã cài đặt!", ephemeral=True)

        price_text = self.item_price.value.strip()
        bank_desc = self.bank_info.value.strip()
        product_name = self.item_name.value.strip()

        # Thông báo yêu cầu người bán gửi ảnh QR trong vòng 60 giây
        await interaction.response.send_message(
            "📸 **Vui lòng tải lên (upload) ảnh mã QR ngân hàng của bạn vào kênh chat này ngay bây giờ!**\n*(Bạn có 60 giây để gửi ảnh, bot sẽ tự động hoàn tất bài đăng)*",
            ephemeral=True
        )

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
            return await interaction.followup.send(
                "⏰ Đã quá thời gian 60 giây mà không thấy bạn gửi ảnh QR. Đã hủy lệnh đăng bán!",
                ephemeral=True
            )

        # Tạo Embed hiển thị sản phẩm ra kênh Buông Bàn
        embed = discord.Embed(
            title="🛍️ SẢN PHẨM / DỊCH VỤ MỚI",
            description=f"• **Tên sản phẩm:** {product_name}\n• **Giá thành:** 💰 `{price_text} VNĐ`\n• **Người bán:** {interaction.user.mention}\n• **Thanh toán:** `{bank_desc}`",
            color=discord.Color.orange()
        )
        embed.set_image(url=qr_image_url)
        embed.set_footer(text="Quét mã QR trên để thanh toán và nhấn nút 'Mua ngay' bên dưới để nhận thông tin riêng tư!")
        embed.timestamp = datetime.now()

        view = BuyItemView(secret_data=self.secret_content.value, seller=interaction.user)
        await channel.send(embed=embed, view=view)

        await interaction.followup.send(
            f"✅ **Đã đăng bán sản phẩm thành công kèm ảnh QR của bạn** vào kênh {channel.mention}!",
            ephemeral=True
        )


# ================= GIAO DIỆN NÚT MUA HÀNG =================
class BuyItemView(discord.ui.View):
    def __init__(self, secret_data: str, seller: discord.Member):
        super().__init__(timeout=None)
        self.secret_data = secret_data
        self.seller = seller

    @discord.ui.button(label="🛒 Mua Ngay & Nhận Hàng", style=discord.ButtonStyle.green, emoji="⚡", custom_id="buy_item_button")
    async def buy_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user == self.seller:
            return await interaction.response.send_message("⚠️ Bạn không thể tự mua sản phẩm của chính mình tạo ra!", ephemeral=True)

        await interaction.response.send_message(
            f"🎉 **Xác nhận giao dịch thành công!** (Hãy chắc chắn bạn đã quét mã QR chuyển khoản cho người bán).\n\n🔒 **Nội dung/Tài khoản riêng tư của bạn:**\n```text\n{self.secret_data}\n```",
            ephemeral=True
        )


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
        title="🛡️ Xác thực Thành viên (Verify)",
        description="Nhấn vào nút bên dưới để nhận mã xác thực ngẫu nhiên và mở bảng nhập.",
        color=discord.Color.green()
    )
    view = VerifyRegisterView()
    await target_channel.send(embed=embed, view=view)
    
    await interaction.response.send_message(
        f"✅ **Đã cài đặt và gửi bảng Verify thành công!** Kênh Verify: {target_channel.mention}",
        ephemeral=True
    )

@bot.tree.command(name="setup-verify-role", description="Mở bảng cài đặt Role sẽ được cấp sau khi Verify thành công")
@app_commands.checks.has_permissions(administrator=True)
async def setup_verify_role(interaction: discord.Interaction):
    await interaction.response.send_modal(SetupVerifyRoleModal())

@bot.tree.command(name="setup-buong-ban", description="Mở bảng cài đặt kênh Buông Bàn")
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
    
    await interaction.response.send_message(
        f"✅ **Đã cài đặt thành công kênh thông báo sinh nhật!** Các lời chúc sẽ được gửi vào: {target_channel.mention}",
        ephemeral=True
    )

@bot.tree.command(name="setup-dangky-sinhnhat", description="Gửi bảng nút bấm đăng ký ngày sinh vào kênh")
@app_commands.describe(kenh="Chọn kênh để gửi bảng đăng ký (Bỏ trống sẽ lấy kênh hiện tại)")
@app_commands.checks.has_permissions(administrator=True)
async def setup_dangky_sinhnhat(interaction: discord.Interaction, kenh: discord.TextChannel = None):
    target_channel = kenh if kenh else interaction.channel
    
    embed = discord.Embed(
        title="🎂 Đăng ký Ngày Sinh Nhật (Bảo mật tuyệt đối)",
        description="Nhấn vào nút bên dưới để lưu ngày sinh của bạn.\n*Lưu ý: Ngày sinh của bạn sẽ được giữ kín hoàn toàn, bot chỉ dùng để chúc mừng đúng ngày chứ không hiển thị ngày sinh ra công khai.*",
        color=discord.Color.pink()
    )
    view = BirthdayRegisterView()
    await target_channel.send(embed=embed, view=view)
    
    await interaction.response.send_message(
        f"✅ **Đã gửi bảng đăng ký sinh nhật thành công** vào kênh {target_channel.mention}!",
        ephemeral=True
    )

@setup_welcome.error
@setup_verify.error
@setup_verify_role.error
@setup_buong_ban.error
@setup_sinhnhat.error
@setup_dangky_sinhnhat.error
async def slash_command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message("❌ Bạn cần có quyền Quản trị viên (Administrator) để dùng lệnh này!", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ Đã xảy ra lỗi: {error}", ephemeral=True)


# ================= CÁC LỆNH PREFIX COMMANDS =================

@bot.command(name="mute", description="Cấm ngôn thành viên")
@commands.has_permissions(moderate_members=True)
async def mute(ctx, member: discord.Member, minutes: int, *, reason: str = "Không có lý do"):
    if minutes <= 0:
        return await ctx.send("❌ Thời gian mute phải lớn hơn 0 phút!")
    
    duration = timedelta(minutes=minutes)
    try:
        await member.timeout(duration, reason=reason)
        await ctx.send(f"🔇 Đã cấm ngôn thành công **{member.mention}** trong **{minutes} phút**.\n📝 **Lý do:** {reason}")
    except Exception as e:
        await ctx.send(f"❌ Không thể mute thành viên này. Lỗi: {e}")

@bot.command(name="ban", description="Cấm vĩnh viễn thành viên")
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason: str = "Không có lý do"):
    try:
        await member.ban(reason=reason)
        await ctx.send(f"🔨 Đã ban thành công **{member.mention}** khỏi server.\n📝 **Lý do:** {reason}")
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
            return await interaction.response.send_message("❌ **Mã xác thực không chính xác!** Vui lòng bấm nút Verify lại để lấy mã mới.", ephemeral=True)
        
        config = bot.server_configs.get(interaction.guild_id, {})
        role_id = config.get("verify_role")
        
        if not role_id:
            return await interaction.response.send_message("❌ Server chưa cài đặt Role Verify! Hãy bảo Admin dùng lệnh `/setup-verify-role` trước.", ephemeral=True)
            
        role = interaction.guild.get_role(role_id)
        if not role:
            return await interaction.response.send_message("❌ Không tìm thấy Role Verify trong server này!", ephemeral=True)
            
        if role in interaction.user.roles:
            return await interaction.response.send_message("ℹ️ Bạn đã xác thực từ trước rồi!", ephemeral=True)
        
        try:
            await interaction.user.add_roles(role)
            bot.verify_codes.pop(interaction.user.id, None)
            await interaction.response.send_message("✅ **Xác thực thành công!** Bạn đã được cấp role và quyền tham gia server.", ephemeral=True)
        except Exception as e:
            print(e)
            await interaction.response.send_message("❌ Đã xảy ra lỗi khi cấp quyền xác thực (Bot có thể thiếu quyền Quản lý vai trò).", ephemeral=True)

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
            return await interaction.response.send_message("❌ Định dạng không hợp lệ! Vui lòng nhập đúng định dạng `DD/MM` (Ví dụ: `25/12`).", ephemeral=True)
        bot.birthdays[interaction.user.id] = date_str
        await interaction.response.send_message("🎂 Đã lưu thông tin sinh nhật của bạn thành công! Ngày sinh sẽ được giữ bảo mật hoàn toàn.", ephemeral=True)

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
            title="👋 Chào mừng đến với Server!",
            description=custom_msg,
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        if img_url:
            embed.set_image(url=img_url)
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
                                    description=f"Hôm nay là một ngày đặc biệt vô cùng! Chúc mừng sinh nhật thành viên <@{user_id}>! 🎈\n\nChúc bạn tuổi mới luôn tràn đầy niềm vui, sức khỏe dồi dào, học tập/làm việc phát tài và mọi ước mơ đều trở thành hiện thực! 🎁✨",
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