import json
import os
from datetime import datetime
import discord
from discord import app_commands
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

ROLE_ID = 1535266021462511737         # ยศพันมิตรสำหรับสมาชิก
ADMIN_ROLE_ID = 1535263803548110908   # ยศแอดมินหลังบ้าน
SCRIM_SCHEDULE_CHANNEL_ID = 1544949197520764972 # ไอดีห้องกำหนดการกระชับมิตร

def load_json(filename):
    if not os.path.exists(filename):
        return {} if any(k in filename for k in ["warnings", "attendance", "scrim"]) else []
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {} if any(k in filename for k in ["warnings", "attendance", "scrim"]) else []

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def check_admin(interaction: discord.Interaction) -> bool:
    try:
        if interaction.user.guild_permissions.administrator:
            return True
        if isinstance(interaction.user, discord.Member):
            return any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles)
        return False
    except Exception as e:
        print(f"Error in check_admin: {e}")
        return False


# --- 🪖 ระบบยืนยันกิลด์พันมิตร ---
class GuildModal(discord.ui.Modal, title="ยืนยันกิลด์พันมิตร ROV"):
    guild_input = discord.ui.TextInput(
        label="ชื่อกิลด์หรือชื่อย่อพันมิตร",
        placeholder="พิมพ์ชื่อกิลด์หรือชื่อย่อ เช่น DragonMind หรือ DM",
        required=True,
    )
    custom_nickname = discord.ui.TextInput(
        label="ชื่อเล่นของคุณ (สำหรับต่อท้ายชื่อย่อ)",
        placeholder="พิมพ์ชื่อเล่นของคุณที่นี่...",
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        user_input = self.guild_input.value.strip().lower()
        suffix = self.custom_nickname.value.strip()
        guilds = load_json("guilds.json")

        matched_guild = None
        for g in guilds:
            if user_input == g["name"].lower() or user_input == g["abbr"].lower():
                matched_guild = g
                break

        if matched_guild:
            role = interaction.guild.get_role(ROLE_ID)
            if not role:
                await interaction.response.send_message("❌ เกิดข้อผิดพลาด: ไม่พบยศนี้ในระบบ", ephemeral=True)
                return

            abbr = matched_guild["abbr"]
            full_name = matched_guild["name"]
            new_nickname = f"[{abbr}] {suffix}"

            try:
                await interaction.user.edit(nick=new_nickname)
                await interaction.user.add_roles(role)
                await interaction.response.send_message(
                    f"✅ ยืนยันสำเร็จ! กิลด์ **{full_name}**\nระบบเปลี่ยนชื่อเป็น **{new_nickname}** เรียบร้อย",
                    ephemeral=True,
                )
            except discord.Forbidden:
                await interaction.response.send_message("⚠️ บอทไม่มีสิทธิ์เปลี่ยนชื่อหรือเพิ่มยศให้คุณ", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ เกิดข้อผิดพลาด: {e}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ ชื่อกิลด์หรือชื่อย่อไม่ถูกต้อง", ephemeral=True)


class AddGuildModal(discord.ui.Modal, title="เพิ่มกิลด์พันมิตรใหม่"):
    guild_name = discord.ui.TextInput(label="ชื่อเต็มกิลด์", placeholder="เช่น DragonMind", required=True)
    guild_abbr = discord.ui.TextInput(label="ชื่อย่อกิลด์", placeholder="เช่น DM", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        name = self.guild_name.value.strip()
        abbr = self.guild_abbr.value.strip().upper()
        guilds = load_json("guilds.json")

        for g in guilds:
            if g["name"].lower() == name.lower() or g["abbr"].lower() == abbr.lower():
                await interaction.response.send_message("⚠️ มีชื่อกิลด์หรือชื่อย่อนี้ในระบบอยู่แล้ว", ephemeral=True)
                return

        guilds.append({"name": name, "abbr": abbr})
        save_json("guilds.json", guilds)
        await interaction.response.send_message(f"✅ เพิ่มกิลด์ **{name}** เรียบร้อยแล้ว!", ephemeral=True)


class RemoveGuildModal(discord.ui.Modal, title="ลบกิลด์พันมิตร"):
    target_query = discord.ui.TextInput(label="ชื่อกิลด์หรือชื่อย่อที่ต้องการลบ", placeholder="พิมพ์ชื่อหรือชื่อย่อ...", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        query = self.target_query.value.strip().lower()
        guilds = load_json("guilds.json")
        updated_guilds = [g for g in guilds if g["name"].lower() != query and g["abbr"].lower() != query]

        if len(guilds) == len(updated_guilds):
            await interaction.response.send_message("❌ ไม่พบกิลด์ที่ต้องการลบ", ephemeral=True)
            return

        save_json("guilds.json", updated_guilds)
        await interaction.response.send_message("🗑️ ลบกิลด์พันมิตรเรียบร้อยแล้ว", ephemeral=True)


class GuildView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🪖 ยืนยันกิลด์พันมิตร", style=discord.ButtonStyle.green, custom_id="verify_guild_btn")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GuildModal())


class AdminDashboardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="➕ เพิ่มกิลด์", style=discord.ButtonStyle.blurple, custom_id="admin_add_guild")
    async def add_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not check_admin(interaction):
            await interaction.response.send_message("❌ สำหรับแอดมินเท่านั้น", ephemeral=True)
            return
        await interaction.response.send_modal(AddGuildModal())

    @discord.ui.button(label="📋 ดูรายชื่อกิลด์", style=discord.ButtonStyle.gray, custom_id="admin_list_guild")
    async def list_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not check_admin(interaction):
            await interaction.response.send_message("❌ สำหรับแอดมินเท่านั้น", ephemeral=True)
            return
        guilds = load_json("guilds.json")
        if not guilds:
            await interaction.response.send_message("📂 ยังไม่มีรายชื่อกิลด์", ephemeral=True)
            return
        guild_list_str = "\n".join([f"- **{g['name']}** (`{g['abbr']}`)" for g in guilds])
        await interaction.response.send_message(f"📋 **รายชื่อกิลด์:**\n{guild_list_str}", ephemeral=True)

    @discord.ui.button(label="🗑️ ลบกิลด์", style=discord.ButtonStyle.red, custom_id="admin_remove_guild")
    async def remove_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not check_admin(interaction):
            await interaction.response.send_message("❌ สำหรับแอดมินเท่านั้น", ephemeral=True)
            return
        await interaction.response.send_modal(RemoveGuildModal())


# --- 🎙️ ระบบเช็คชื่อห้องเสียง ---
class AttendanceView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎙️ สแกนเช็คชื่อห้องเสียง", style=discord.ButtonStyle.green, custom_id="scan_attendance_btn")
    async def scan_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not check_admin(interaction):
            await interaction.response.send_message("❌ สำหรับแอดมินเท่านั้น", ephemeral=True)
            return
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("❌ คุณต้องเข้าไปอยู่ในห้องเสียงก่อนกดสแกน!", ephemeral=True)
            return

        vc = interaction.user.voice.channel
        members = [member.display_name for member in vc.members if not member.bot]

        if not members:
            await interaction.response.send_message(f"⚠️ ไม่พบสมาชิกในห้องเสียง **{vc.name}**", ephemeral=True)
            return

        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        record_key = f"ประชุมกิลด์วันที่ {date_str}"

        logs = load_json("attendance_logs.json")
        logs[record_key] = {
            "channel_name": vc.name,
            "total": len(members),
            "members": members
        }
        save_json("attendance_logs.json", logs)

        member_list_str = "\n".join([f"{i+1}. {name}" for i, name in enumerate(members)])
        embed = discord.Embed(
            title=f"✅ บันทึก: {record_key}",
            description=f"🎙️ ห้อง: **{vc.name}**\n👥 มาทั้งหมด: **{len(members)}** คน",
            color=discord.Color.green()
        )
        embed.add_field(name="รายชื่อผู้เข้าร่วม:", value=member_list_str[:1024], inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="📊 ดูประวัติการประชุม", style=discord.ButtonStyle.secondary, custom_id="view_attendance_btn")
    async def view_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not check_admin(interaction):
            await interaction.response.send_message("❌ สำหรับแอดมินเท่านั้น", ephemeral=True)
            return

        logs = load_json("attendance_logs.json")
        if not logs:
            await interaction.response.send_message("📂 ยังไม่มีประวัติการเช็คชื่อ", ephemeral=True)
            return

        embed = discord.Embed(title="📋 ประวัติการเช็คชื่อย้อนหลังทั้งหมด", color=discord.Color.blue())
        for record_key, data in list(logs.items())[-5:]:
            embed.add_field(
                name=f"📌 {record_key}",
                value=f"🎙️ ห้อง: {data['channel_name']} | 👥 มา {data['total']} คน\nรายชื่อ: {', '.join(data['members'][:5])}{' ...' if data['total'] > 5 else ''}",
                inline=False
            )
        embed.set_footer(text="แสดงประวัติการประชุมล่าสุด 5 รอบ")
        await interaction.response.send_message(embed=embed, ephemeral=True)


# --- 📊 กระดานสถิติพันมิตร ---
def create_stats_embed(guild):
    guilds = load_json("guilds.json")
    stats = {g["abbr"].upper(): {"name": g["name"], "count": 0} for g in guilds}
    total_members = 0

    for member in guild.members:
        display_name = member.display_name.upper()
        for abbr, data in stats.items():
            if display_name.startswith(f"[{abbr}]"):
                data["count"] += 1
                total_members += 1
                break

    embed = discord.Embed(title="📊 สถิติกิลด์พันมิตร", description=f"รวมทั้งหมด: **{total_members}** คน", color=discord.Color.blue())
    for abbr, data in stats.items():
        embed.add_field(name=f"{data['name']} (`{abbr}`)", value=f"👥 **{data['count']}** คน", inline=False)
    embed.set_footer(text="กดปุ่มรีเฟรชด้านล่าง")
    return embed


class StatsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔄 รีเฟรชข้อมูล", style=discord.ButtonStyle.secondary, custom_id="refresh_stats_btn")
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = create_stats_embed(interaction.guild)
        await interaction.message.edit(embed=embed, view=self)


# --- 🚨 บอร์ดประกาศรายชื่อผู้ทำผิดกฎ ---
def create_warnings_embed():
    warnings = load_json("warnings.json")
    embed = discord.Embed(
        title="🚨 บอร์ดประกาศรายชื่อผู้ทำผิดกฎ (Penalty Board)",
        description="แสดงประวัติใบเหลืองและใบแดงของสมาชิกในเซิร์ฟเวอร์",
        color=discord.Color.dark_red()
    )

    if not warnings:
        embed.add_field(name="สถานะ", value="🎉 เยี่ยมมาก! ยังไม่มีสมาชิกทำผิดกฎในระบบ", inline=False)
        embed.set_footer(text="กดปุ่ม '🔄 รีเฟรชข้อมูล' ด้านล่างเพื่ออัปเดตสถานะล่าสุด")
        return embed

    count = 0
    for user_id, data in warnings.items():
        yellows = data.get("yellow_cards", [])
        reds = data.get("red_cards", [])

        if not yellows and not reds:
            continue

        y_text = f"🟨 ใบเหลือง: {len(yellows)} ใบ"
        r_text = f"🟥 ใบแดง: {len(reds)} ใบ"

        details = []
        for y in yellows:
            details.append(f"• [เหลือง] {y['date']} - เหตุผล: {y['reason']}")
        for r in reds:
            details.append(f"• [แดง] {r['date']} - เหตุผล: {r['reason']}")

        val = f"{y_text} | {r_text}\n" + "\n".join(details[:3])
        if len(details) > 3:
            val += f"\n... และอื่นๆ อีก {len(details)-3} รายการ"

        embed.add_field(
            name=f"👤 สมาชิก: <@{user_id}>",
            value=val,
            inline=False
        )
        count += 1
        if count >= 25:
            break

    if count == 0:
        embed.add_field(name="สถานะ", value="🎉 เยี่ยมมาก! ยังไม่มีสมาชิกทำผิดกฎในระบบ", inline=False)

    embed.set_footer(text="กดปุ่ม '🔄 รีเฟรชข้อมูล' ด้านล่างเพื่ออัปเดตสถานะล่าสุด")
    return embed


class WarningsBoardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔄 รีเฟรชข้อมูล", style=discord.ButtonStyle.secondary, custom_id="refresh_warnings_board_btn")
    async def refresh_warnings_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = create_warnings_embed()
        await interaction.message.edit(embed=embed, view=self)


# --- ⚔️ ระบบนัดกระชับมิตร (Scrim Negotiation System) ---
class ScheduleControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="❌ ยกเลิกการแข่งขัน (แอดมิน)", style=discord.ButtonStyle.red, custom_id="cancel_schedule_match_btn")
    async def cancel_match(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not check_admin(interaction):
            await interaction.response.send_message("❌ ปุ่มนี้สำหรับแอดมินฝั่งเราเท่านั้น", ephemeral=True)
            return

        if not interaction.message.embeds:
            await interaction.response.send_message("❌ ไม่พบข้อมูลการแข่งขันนี้", ephemeral=True)
            return

        embed = interaction.message.embeds[0]
        embed.title = "❌ แมตช์การแข่งขันนี้ถูกยกเลิกแล้ว"
        embed.color = discord.Color.red()
        embed.set_footer(text=f"ถูกยกเลิกการแข่งขันโดยแอดมิน: {interaction.user.display_name}")

        for child in self.children:
            child.disabled = True

        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.send_message(f"🗑️ แอดมิน {interaction.user.mention} ทำการยกเลิกการแข่งขันนี้เรียบร้อยแล้ว", ephemeral=True)


class ScrimFormModal(discord.ui.Modal, title="กรอกฟอร์มนัดกระชับมิตร"):
    guild_fullname = discord.ui.TextInput(label="ชื่อเต็มกิลด์", placeholder="", required=True)
    guild_abbr = discord.ui.TextInput(label="ชื่อย่อกิลด์", placeholder="", required=True, max_length=10)
    scrim_datetime = discord.ui.TextInput(label="วันที่และเวลา", placeholder="", required=True)
    rules_text = discord.ui.TextInput(label="รายละเอียดและกฎการแข่ง", placeholder="เช่น BO3, NO Toxic, ห้ามเล่นตัวซ้ำ", style=discord.TextStyle.paragraph, required=True)
    discord_arena = discord.ui.TextInput(label="ดิสสนามแข่งขัน", placeholder="", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        scrim_data = load_json("scrim_sessions.json")
        thread_id = str(interaction.channel.id)

        scrim_data[thread_id] = {
            "fullname": self.guild_fullname.value.strip(),
            "abbr": self.guild_abbr.value.strip(),
            "datetime": self.scrim_datetime.value.strip(),
            "rules": self.rules_text.value.strip(),
            "arena": self.discord_arena.value.strip(),
            "requester": str(interaction.user.id),
            "host_confirmed": False,
            "guest_confirmed": False
        }
        save_json("scrim_sessions.json", scrim_data)

        embed = discord.Embed(
            title="💖 กระชับมิตร 💖",
            description=(
                f"💖 ชื่อเต็ม: **{scrim_data[thread_id]['fullname']}**\n"
                f"🧡 ชื่อย่อ: **{scrim_data[thread_id]['abbr']}**\n"
                f"📅 วันที่: **{scrim_data[thread_id]['datetime']}**\n\n"
                f"{scrim_data[thread_id]['rules']}\n"
                f"ดิสสนาม: **{scrim_data[thread_id]['arena']}**\n\n"
                f"🛡️ สถานะแอดมินฝั่งเรา: ❌ ยังไม่ยืนยัน\n"
                f"⚔️ สถานะฝั่งคู่กรณี: ❌ ยังไม่ยืนยัน"
            ),
            color=discord.Color.pink()
        )
        embed.set_footer(text="รอการตรวจสอบและกดยืนยันจากทั้ง 2 ฝั่ง")

        await interaction.response.send_message(
            "✅ บันทึกฟอร์มเรียบร้อย! กรุณากดยืนยันเวลาด้านล่างเมื่อพร้อม",
            embed=embed,
            view=ScrimControlView(),
            ephemeral=False
        )


class ScrimControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✅ ยืนยันฝั่งเรา (Host)", style=discord.ButtonStyle.green, custom_id="scrim_confirm_host")
    async def confirm_host(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not check_admin(interaction):
            await interaction.response.send_message("❌ ปุ่มนี้สำหรับแอดมินฝั่งเราเท่านั้น", ephemeral=True)
            return

        scrim_data = load_json("scrim_sessions.json")
        thread_id = str(interaction.channel.id)
        if thread_id not in scrim_data:
            await interaction.response.send_message("❌ ไม่พบข้อมูลการนัดหมายในห้องนี้", ephemeral=True)
            return

        scrim_data[thread_id]["host_confirmed"] = True
        save_json("scrim_sessions.json", scrim_data)
        
        await self.update_embed_status(interaction, scrim_data[thread_id])
        await interaction.response.send_message("✅ บันทึกการยืนยันฝั่งเราเรียบร้อย", ephemeral=True)
        await self.check_and_publish(interaction)

    @discord.ui.button(label="✅ ยืนยันฝั่งคู่กรณี", style=discord.ButtonStyle.blurple, custom_id="scrim_confirm_guest")
    async def confirm_guest(self, interaction: discord.Interaction, button: discord.ui.Button):
        scrim_data = load_json("scrim_sessions.json")
        thread_id = str(interaction.channel.id)
        if thread_id not in scrim_data:
            await interaction.response.send_message("❌ ไม่พบข้อมูลการนัดหมายในห้องนี้", ephemeral=True)
            return

        scrim_data[thread_id]["guest_confirmed"] = True
        save_json("scrim_sessions.json", scrim_data)
        
        await self.update_embed_status(interaction, scrim_data[thread_id])
        await interaction.response.send_message("✅ บันทึกการยืนยันฝั่งคู่กรณีเรียบร้อย", ephemeral=True)
        await self.check_and_publish(interaction)

    @discord.ui.button(label="🔄 แก้ไขเวลา/ข้อมูล", style=discord.ButtonStyle.secondary, custom_id="scrim_edit")
    async def edit_scrim(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ScrimFormModal())

    @discord.ui.button(label="❌ ยกเลิกการเจรจา (ปิดห้อง)", style=discord.ButtonStyle.red, custom_id="scrim_cancel")
    async def cancel_scrim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not check_admin(interaction) and interaction.user.id != int(load_json("scrim_sessions.json").get(str(interaction.channel.id), {}).get("requester", 0)):
            await interaction.response.send_message("❌ คุณไม่มีสิทธิ์ยกเลิกการเจรจานี้", ephemeral=True)
            return

        scrim_data = load_json("scrim_sessions.json")
        thread_id = str(interaction.channel.id)
        if thread_id in scrim_data:
            del scrim_data[thread_id]
            save_json("scrim_sessions.json", scrim_data)

        await interaction.response.send_message("🗑️ ทำการยกเลิกการเจรจาและกำลังลบห้องเธรดนี้...", ephemeral=True)
        
        if isinstance(interaction.channel, discord.Thread):
            try:
                await interaction.channel.delete()
            except Exception:
                await interaction.channel.edit(archived=True, locked=True)

    async def update_embed_status(self, interaction: discord.Interaction, data: dict):
        try:
            host_status = "✅ ยืนยันแล้ว" if data["host_confirmed"] else "❌ ยังไม่ยืนยัน"
            guest_status = "✅ ยืนยันแล้ว" if data["guest_confirmed"] else "❌ ยังไม่ยืนยัน"

            if interaction.message and interaction.message.embeds:
                embed = interaction.message.embeds[0]
                embed.description = (
                    f"💖 ชื่อเต็ม: **{data['fullname']}**\n"
                    f"🧡 ชื่อย่อ: **{data['abbr']}**\n"
                    f"📅 วันที่: **{data['datetime']}**\n\n"
                    f"{data['rules']}\n"
                    f"ดิสสนาม: **{data['arena']}**\n\n"
                    f"🛡️ สถานะแอดมินฝั่งเรา: {host_status}\n"
                    f"⚔️ สถานะฝั่งคู่กรณี: {guest_status}"
                )
                await interaction.message.edit(embed=embed)
        except Exception as e:
            print(f"Error updating embed: {e}")

    async def check_and_publish(self, interaction: discord.Interaction):
        scrim_data = load_json("scrim_sessions.json")
        thread_id = str(interaction.channel.id)
        data = scrim_data.get(thread_id)

        if data and data["host_confirmed"] and data["guest_confirmed"]:
            embed = discord.Embed(
                title="💖 กระชับมิตร 💖",
                description=(
                    f"💖 ชื่อเต็ม: **{data['fullname']}**\n"
                    f"🧡 ชื่อย่อ: **{data['abbr']}**\n"
                    f"📅 วันที่: **{data['datetime']}**\n\n"
                    f"{data['rules']}\n"
                    f"ดิสสนาม: **{data['arena']}**"
                ),
                color=discord.Color.pink()
            )
            embed.set_footer(text="✅ นัดหมายสำเร็จและได้รับการยืนยันจากทั้ง 2 ฝั่งเรียบร้อย")

            schedule_channel = interaction.guild.get_channel(SCRIM_SCHEDULE_CHANNEL_ID)
            
            if schedule_channel:
                await schedule_channel.send(embed=embed, view=ScheduleControlView())
            else:
                print("⚠️ ไม่พบห้องกำหนดการตาม ID ที่ระบุ")

            if thread_id in scrim_data:
                del scrim_data[thread_id]
                save_json("scrim_sessions.json", scrim_data)

            if isinstance(interaction.channel, discord.Thread):
                try:
                    await interaction.channel.delete()
                except Exception:
                    await interaction.channel.edit(archived=True, locked=True)


class ScrimSetupView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="⚔️ แจ้งขอติดต่อกระชับมิตร", style=discord.ButtonStyle.green, custom_id="start_scrim_thread_btn")
    async def start_scrim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("❌ กดปุ่มนี้ในห้องติดต่อกระชับมิตรเท่านั้น", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        thread = await interaction.channel.create_thread(
            name=f"scrim-{interaction.user.name}",
            type=discord.ChannelType.private_thread,
            auto_archive_duration=1440
        )
        await thread.add_user(interaction.user)

        instructions = (
            f"👋 สวัสดีคุณ {interaction.user.mention}!\n"
            "กรุณากดปุ่ม **'📝 กรอกฟอร์มรายละเอียด'** ด้านล่างเพื่อกรอกข้อมูลการแข่ง"
        )

        class InitialView(discord.ui.View):
            @discord.ui.button(label="📝 กรอกฟอร์มรายละเอียด", style=discord.ButtonStyle.blurple)
            async def open_modal(self, btn_interaction: discord.Interaction, btn: discord.ui.Button):
                await btn_interaction.response.send_modal(ScrimFormModal())

        await thread.send(instructions, view=InitialView())
        await interaction.followup.send(f"✅ เปิดห้องเจรจานัดหมายส่วนตัวให้แล้วครับ: {thread.mention}", ephemeral=True)


# --- ⚠️ ระบบคลิกขวาออกใบเตือน ---
class WarnModal(discord.ui.Modal, title="ระบบออกใบเตือนสมาชิก"):
    def __init__(self, target_member: discord.Member):
        super().__init__()
        self.target_member = target_member

    card_type_input = discord.ui.TextInput(label="ประเภทโทษ (พิมพ์คำว่า เหลือง หรือ แดง)", placeholder="พิมพ์ 'เหลือง' หรือ 'แดง'", required=True, max_length=6)
    reason_input = discord.ui.TextInput(label="เหตุผลในการทำผิดกฎ", placeholder="เช่น พิมพ์ด่าทอ, เปิดไมค์ช็อต, ฯลฯ", style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            card_input = self.card_type_input.value.strip().lower()
            reason = self.reason_input.value.strip()

            if card_input not in ["เหลือง", "แดง", "yellow", "red"]:
                await interaction.response.send_message("❌ กรุณาพิมพ์ประเภทโทษให้ถูกต้อง ('เหลือง' หรือ 'แดง')", ephemeral=True)
                return

            is_red = card_input in ["แดง", "red"]
            warnings = load_json("warnings.json")
            user_id_str = str(self.target_member.id)

            if user_id_str not in warnings:
                warnings[user_id_str] = {
                    "username": self.target_member.display_name,
                    "yellow_cards": [],
                    "red_cards": []
                }

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            record = {
                "reason": reason,
                "date": timestamp,
                "admin": interaction.user.display_name
            }

            embed = discord.Embed(title="⚠️ บันทึกบทลงโทษสมาชิก", color=discord.Color.gold() if not is_red else discord.Color.red())
            embed.add_field(name="สมาชิกผู้กระทำผิด", value=self.target_member.mention, inline=False)
            embed.add_field(name="ผู้ดำเนินการ (Admin)", value=interaction.user.mention, inline=False)
            embed.add_field(name="เหตุผล", value=reason, inline=False)

            if not is_red:
                warnings[user_id_str]["yellow_cards"].append(record)
                total_yellow = len(warnings[user_id_str]["yellow_cards"])
                embed.title = "🟨 ออกใบเหลือง (ตักเตือน)"
                embed.add_field(name="สถานะใบเหลือง", value=f"สะสมแล้ว **{total_yellow} / 2** ใบ", inline=False)

                if total_yellow >= 2:
                    embed.add_field(name="🚨 แจ้งเตือนจากระบบ", value="**สมาชิกคนนี้สะสมใบเหลืองครบ 2 ใบแล้ว! แนะนำให้ทำการแบนถาวรตามกฎ**", inline=False)
            else:
                warnings[user_id_str]["red_cards"].append(record)
                embed.title = "🟥 ออกใบแดง (แบนถาวรทันที)"
                try:
                    await self.target_member.ban(reason=f"ใบแดง: {reason}")
                    embed.add_field(name="สถานะการแบน", value="✅ บอทแบนสมาชิกออกจากเซิร์ฟเวอร์เรียบร้อย", inline=False)
                except Exception:
                    embed.add_field(name="สถานะการแบน", value="⚠️ บอทไม่สามารถแบนได้ (โปรดแบนด้วยมือ)", inline=False)

            save_json("warnings.json", warnings)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            print(f"Error in WarnModal on_submit: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ เกิดข้อผิดพลาด: {e}", ephemeral=True)


@bot.tree.context_menu(name="จัดการใบเตือน")
async def warn_context_menu(interaction: discord.Interaction, member: discord.Member):
    try:
        if not check_admin(interaction):
            await interaction.response.send_message("❌ เมนูนี้สำหรับแอดมินที่มีสิทธิ์เท่านั้น", ephemeral=True)
            return
        await interaction.response.send_modal(WarnModal(target_member=member))
    except Exception as e:
        print(f"Error in warn_context_menu: {e}")
        if not interaction.response.is_done():
            await interaction.response.send_message(f"❌ เกิดข้อผิดพลาด: {e}", ephemeral=True)


@bot.event
async def on_ready():
    bot.add_view(GuildView())
    bot.add_view(AdminDashboardView())
    bot.add_view(AttendanceView())
    bot.add_view(StatsView())
    bot.add_view(WarningsBoardView())
    bot.add_view(ScrimSetupView())
    bot.add_view(ScrimControlView())
    bot.add_view(ScheduleControlView())
    
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands successfully.")
    except Exception as e:
        print(f"Sync error: {e}")


@bot.tree.command(name="setup", description="ส่งปุ่มยืนยันกิลด์")
@app_commands.default_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    await interaction.channel.send("📜 **ยืนยันตัวตนกิลด์พันมิตร**", view=GuildView())
    await interaction.response.send_message("สร้างปุ่มสมาชิกเรียบร้อย!", ephemeral=True)


@bot.tree.command(name="admindash", description="แผงควบคุมจัดการกิลด์")
@app_commands.default_permissions(administrator=True)
async def admindash(interaction: discord.Interaction):
    await interaction.channel.send("🛠️ **แผงควบคุมแอดมิน (จัดการกิลด์)**", view=AdminDashboardView())
    await interaction.response.send_message("สร้างแดชบอร์ดกิลด์แล้ว!", ephemeral=True)


@bot.tree.command(name="attendance", description="แผงเช็คชื่อประชุมห้องเสียงสำหรับแอดมิน")
@app_commands.default_permissions(administrator=True)
async def attendance(interaction: discord.Interaction):
    await interaction.channel.send("🎙️ **ระบบเช็คชื่อประชุมห้องเสียง**", view=AttendanceView())
    await interaction.response.send_message("สร้างแผงเช็คชื่อแล้ว!", ephemeral=True)


@bot.tree.command(name="statsboard", description="กระดานสถิติพันมิตร")
@app_commands.default_permissions(administrator=True)
async def statsboard(interaction: discord.Interaction):
    embed = create_stats_embed(interaction.guild)
    await interaction.channel.send(embed=embed, view=StatsView())
    await interaction.response.send_message("สร้างกระดานสถิติแล้ว!", ephemeral=True)


@bot.tree.command(name="warningsboard", description="สร้างกระดานบอร์ดใบเหลือง-ใบแดงสาธารณะสำหรับทุกคน")
@app_commands.default_permissions(administrator=True)
async def warningsboard(interaction: discord.Interaction):
    embed = create_warnings_embed()
    await interaction.channel.send(embed=embed, view=WarningsBoardView())
    await interaction.response.send_message("สร้างบอร์ดใบเตือนสาธารณะเรียบร้อยแล้ว!", ephemeral=True)


@bot.tree.command(name="scrimsetup", description="ส่งปุ่มติดต่อกระชับมิตร")
@app_commands.default_permissions(administrator=True)
async def scrimsetup(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📥 ระบบติดต่อขอแข่งขันกระชับมิตร",
        description="คลิกปุ่ม **'⚔️ แจ้งขอติดต่อกระชับมิตร'** ด้านล่างเพื่อเปิดห้องเจรจาส่วนตัวกับทีมงานครับ",
        color=discord.Color.blue()
    )
    await interaction.channel.send(embed=embed, view=ScrimSetupView())
    await interaction.response.send_message("สร้างปุ่มติดต่อกระชับมิตรเรียบร้อยแล้ว!", ephemeral=True)


bot.run(os.getenv("TOKEN"))