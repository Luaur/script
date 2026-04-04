import discord
from discord.ext import commands
import io
import aiohttp
import asyncio
from datetime import datetime, timezone, timedelta
import re
import os
import sys
import time
import platform
import traceback
import subprocess

TOKEN = ""
OWNER_ID = 1463723091489194150
VERSION = "v1.5.3"

CAT_NAME, CMD_CH, RES_CH, MEDIA_CH = "PROFILER SYSTEM", "cmd-profiler", "result-profiler", "media-profiler"
LOG_CH = "server-logs"
ROLE_MEM, ROLE_STF = "Member", "Staff"

BADGES = {
    "staff": "Discord Staff", "partner": "Partnered Server Owner", "hypesquad": "HypeSquad Events",
    "bug_hunter": "Bug Hunter L1", "hypesquad_bravery": "House Bravery", "hypesquad_brilliance": "House Brilliance",
    "hypesquad_balance": "House Balance", "early_supporter": "Early Supporter", "bug_hunter_level_2": "Bug Hunter L2",
    "verified_bot_developer": "Verified Bot Dev", "discord_certified_moderator": "Certified Mod", "active_developer": "Active Dev"
}

def parse_dt(dt_str, fmt="%Y-%m-%dT%H:%M:%S.%fZ"):
    try: return datetime.strptime(dt_str, fmt).replace(tzinfo=timezone.utc)
    except: return datetime.now(timezone.utc)

class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Setuju & Verifikasi", style=discord.ButtonStyle.success, custom_id="verify_gatekeeper")
    async def verify_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = discord.utils.get(interaction.guild.roles, name=ROLE_MEM)
        if not role:
            return await interaction.response.send_message("Sistem error: Role akses tidak ditemukan.", ephemeral=True)
        if role in interaction.user.roles:
            await interaction.response.send_message("Anda sudah terverifikasi dalam sistem.", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("Verifikasi berhasil! Hak akses telah diberikan.", ephemeral=True)

class MasterBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all(), help_command=None, owner_id=OWNER_ID)

    async def setup_hook(self):
        self.add_view(VerifyView())
        await self.add_cog(SystemCog(self))

    async def on_ready(self):
        try: owner = await self.fetch_user(self.owner_id)
        except: return
        for g in self.guilds:
            ow = {
                g.default_role: discord.PermissionOverwrite(read_messages=False),
                owner: discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True),
                g.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True, attach_files=True)
            }
            cat = discord.utils.get(g.categories, name=CAT_NAME) or await g.create_category(CAT_NAME, overwrites=ow)
            for ch in [CMD_CH, RES_CH, MEDIA_CH]:
                if not discord.utils.get(g.text_channels, name=ch, category=cat): await g.create_text_channel(ch, category=cat)

class SystemCog(commands.Cog):
    def __init__(self, bot):
        self.bot, self.session = bot, None
        self.temp_vcs = set()

    async def cog_load(self): self.session = aiohttp.ClientSession()
    async def cog_unload(self): await self.session.close() if self.session else None
    
    async def cog_command_error(self, ctx, error):
        if isinstance(error, (commands.NotOwner, commands.CheckFailure, commands.CommandNotFound)): 
            return

        await ctx.send("Terjadi kesalahan sistem. Log diagnostik telah dikirimkan kepada Owner.", delete_after=5)
        
        owner = await self.bot.fetch_user(self.bot.owner_id)
        if owner:
            tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
            e = discord.Embed(title="Log Diagnostik Sistem", color=0xFF0000, timestamp=datetime.now(timezone.utc))
            e.add_field(name="Perintah", value=ctx.command.name if ctx.command else "Unknown", inline=True)
            e.add_field(name="Lokasi", value=ctx.channel.name, inline=True)
            
            if len(tb) > 2000:
                await owner.send(embed=e, file=discord.File(io.BytesIO(tb.encode('utf-8')), filename="error_log.txt"))
            else:
                e.description = f"```python\n{tb}\n```"
                await owner.send(embed=e)

    async def _fetch(self, url, method="GET", json=None, is_json=True):
        try:
            async with self.session.request(method, url, json=json, timeout=10) as r:
                if r.status in [200, 204]: return await r.json() if is_json else io.BytesIO(await r.read())
        except: pass
        return None

    def _build_embed(self, title, url, color, fields, desc=None):
        e = discord.Embed(title=title, url=url, color=color, description=desc)
        for n, v, i in fields: e.add_field(name=n, value=v, inline=i)
        return e

    async def _log_mod(self, guild, title, desc, color):
        ch = discord.utils.get(guild.text_channels, name=LOG_CH)
        if ch: await ch.send(embed=discord.Embed(title=title, description=desc, color=color, timestamp=datetime.now(timezone.utc)))

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot: return
        await self._log_mod(message.guild, "Log Penghapusan Pesan", f"**Pengguna:** {message.author.mention}\n**Saluran:** {message.channel.mention}\n**Isi Teks:** {message.content[:3000]}", 0xFF0000)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot or before.content == after.content: return
        e = discord.Embed(title="Log Modifikasi Pesan", description=f"**Pengguna:** {before.author.mention}\n**Saluran:** {before.channel.mention}", color=0xFFFF00, timestamp=datetime.now(timezone.utc))
        e.add_field(name="Teks Asli", value=before.content[:1024] or "Tidak terdeteksi", inline=False)
        e.add_field(name="Teks Modifikasi", value=after.content[:1024] or "Tidak terdeteksi", inline=False)
        ch = discord.utils.get(before.guild.text_channels, name=LOG_CH)
        if ch: await ch.send(embed=e)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if after.channel and after.channel.name == "Join to Create":
            cat = after.channel.category
            ow = {
                after.channel.guild.default_role: discord.PermissionOverwrite(connect=True),
                member: discord.PermissionOverwrite(manage_channels=True, manage_permissions=True, connect=True, speak=True)
            }
            temp_vc = await after.channel.guild.create_voice_channel(f"{member.display_name}'s Session", category=cat, overwrites=ow)
            self.temp_vcs.add(temp_vc.id)
            try: await member.move_to(temp_vc)
            except: 
                await temp_vc.delete()
                self.temp_vcs.discard(temp_vc.id)

        if before.channel and before.channel.id in self.temp_vcs and len(before.channel.members) == 0:
            try: 
                await before.channel.delete()
                self.temp_vcs.discard(before.channel.id)
            except: pass

    @commands.command(aliases=["pengumuman"])
    async def announce(self, ctx, *, pesan: str = None):
        is_staff = any(r.name in [ROLE_STF, "Admin"] for r in getattr(ctx.author, "roles", []))
        if not (is_staff or ctx.author.id == self.bot.owner_id): return
            
        if not pesan and not ctx.message.attachments:
            return await ctx.send("Instruksi dibatalkan: Diperlukan masukan teks atau lampiran media.", delete_after=5)

        ann_ch = discord.utils.get(ctx.guild.text_channels, name="announcements")
        if not ann_ch:
            return await ctx.send("Instruksi dibatalkan: Saluran #announcements tidak ditemukan dalam struktur server.", delete_after=5)

        try: await ctx.message.delete()
        except: pass
        
        content = "@everyone\n\n"
        if pesan:
            content += f"{pesan}\n\n"
        content += f"— *Pusat Informasi: {ctx.author.name}*"

        files = [await att.to_file() for att in ctx.message.attachments]
        
        await ann_ch.send(content=content, files=files)
        
        if ctx.channel != ann_ch:
            await ctx.send(f"Pengumuman telah berhasil dipublikasikan ke saluran {ann_ch.mention}.", delete_after=3)

    @commands.command()
    async def help(self, ctx):
        is_staff = any(r.name in [ROLE_STF, "Admin"] for r in getattr(ctx.author, "roles", []))
        if not (is_staff or ctx.author.id == self.bot.owner_id): return
        if ctx.channel.name != CMD_CH: return
        
        fields = [
            ("!monitor", "Memindai Cloudphone untuk mengecek apakah aplikasi Roblox masih aktif.", False),
            ("!profil [User ID]", "Melakukan ekstraksi analitik akun Discord target.", False),
            ("!roblox https://support.google.com/google-ads/answer/9004360?hl=id", "Memindai arsitektur dan aset akun Roblox target.", False),
            ("!github [Username]", "Menganalisis repositori dan telemetri GitHub.", False),
            ("!announce [Teks/Media]", "Mendistribusikan pengumuman publik (Khusus Staff/Owner).", False),
            ("!ping", "Melakukan diagnostik latensi jaringan.", False),
            ("!stats", "Menampilkan telemetri perangkat keras dan perangkat lunak bot.", False),
            ("!setup", "Melakukan rekonstruksi struktur saluran server secara otomatis.", False),
            ("!update", "Protokol Over-The-Air untuk menimpa skrip pembaruan bot.", False),
            ("!warn, !mute, !kick, !ban", "Alat penindakan dan moderasi anggota server.", False)
        ]
        
        e = self._build_embed("Dokumentasi Sistem Operasional", None, discord.Color.dark_gray(), fields, "Daftar perintah yang tersedia di dalam infrastruktur:")
        await ctx.send(embed=e)

    @commands.command()
    @commands.is_owner()
    async def monitor(self, ctx):
        if ctx.channel.name != CMD_CH: return
        m = await ctx.send("Melakukan pemindaian tingkat sistem pada mesin host Cloudphone...")

        rbx_status = "Tidak Terdeteksi (Tertutup / Crash)"
        rbx_pid = "-"

        try:
            output = subprocess.check_output("su -c 'pidof com.roblox.client'", shell=True, stderr=subprocess.DEVNULL).decode('utf-8').strip()
            if output:
                rbx_status = "Aktif (Terbuka di Latar Belakang)"
                rbx_pid = output
                
                fg_check = subprocess.check_output("su -c 'dumpsys window windows | grep -E mCurrentFocus'", shell=True, stderr=subprocess.DEVNULL).decode('utf-8')
                if "com.roblox.client" in fg_check:
                    rbx_status = "Aktif (Di Layar Utama / Terbuka Saat Ini)"
        except Exception:
            try:
                ps_check = subprocess.check_output("ps -ef | grep com.roblox.client | grep -v grep", shell=True, stderr=subprocess.DEVNULL).decode('utf-8').strip()
                if ps_check:
                    rbx_status = "Aktif (Ditemukan dalam Cache Memori)"
            except:
                pass

        sys_uptime = "Tidak dapat dikalkulasi"
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.readline().split()[0])
                sys_uptime = str(timedelta(seconds=int(uptime_seconds))).split('.')[0]
        except: pass

        fields = [
            ("Laporan Eksekusi Aplikasi (Roblox)", f"**Kondisi Saat Ini:** {rbx_status}\n**Process ID (PID):** {rbx_pid}", False),
            ("Telemetri Mesin Host", f"**Waktu Operasional (Uptime):** {sys_uptime}\n**Sistem Inti:** {platform.system()} {platform.release()}", False)
        ]

        e = self._build_embed("Monitor Infrastruktur Cloudphone", None, discord.Color.green() if "Aktif" in rbx_status else discord.Color.red(), fields, "Menampilkan status langsung dari eksekusi aplikasi pada perangkat host (Cloudphone).")
        await m.edit(content=None, embed=e)

    @commands.command()
    @commands.is_owner()
    async def ping(self, ctx):
        if ctx.channel.name != CMD_CH: return
        start = time.time()
        msg = await ctx.send("Melakukan diagnostik jaringan...")
        end = time.time()
        
        api_ms = round((end - start) * 1000)
        ws_ms = round(self.bot.latency * 1000)
        
        e = discord.Embed(title="Statistik Latensi Jaringan", color=0x2b2d31)
        e.add_field(name="Gateway Websocket", value=f"`{ws_ms} ms`", inline=True)
        e.add_field(name="Respons API", value=f"`{api_ms} ms`", inline=True)
        await msg.edit(content=None, embed=e)

    @commands.command()
    @commands.is_owner()
    async def stats(self, ctx):
        if ctx.channel.name != CMD_CH: return
        e = discord.Embed(title="Telemetri Server & Hosting", color=0x2b2d31)
        e.add_field(name="Versi Infrastruktur", value=f"`{VERSION}`", inline=True)
        e.add_field(name="Sistem Operasi", value=f"{platform.system()} {platform.release()}", inline=True)
        e.add_field(name="Distribusi Python", value=platform.python_version(), inline=True)
        e.add_field(name="Dependensi Inti", value=f"Discord.py v{discord.__version__}", inline=True)
        e.add_field(name="Latensi Internal", value=f"`{round(self.bot.latency * 1000)} ms`", inline=True)
        await ctx.send(embed=e)

    @commands.command()
    @commands.is_owner()
    async def setup(self, ctx):
        m = await ctx.send("Memulai protokol rekonstruksi server...")
        old_chans = list(ctx.guild.channels)
        new_chans = set()
        
        me, ev = ctx.guild.me, ctx.guild.default_role
        
        r_mem = discord.utils.get(ctx.guild.roles, name=ROLE_MEM) or await ctx.guild.create_role(name=ROLE_MEM, reason="Inisialisasi Otomatis")
        r_stf = discord.utils.get(ctx.guild.roles, name=ROLE_STF) or await ctx.guild.create_role(name=ROLE_STF, reason="Inisialisasi Otomatis", permissions=discord.Permissions(manage_messages=True, kick_members=True, ban_members=True))

        ow_info = {ev: discord.PermissionOverwrite(read_messages=True, send_messages=False), me: discord.PermissionOverwrite(read_messages=True, send_messages=True)}
        ow_gen = {ev: discord.PermissionOverwrite(read_messages=False), r_mem: discord.PermissionOverwrite(read_messages=True, send_messages=True), me: discord.PermissionOverwrite(read_messages=True, send_messages=True)}
        ow_mod = {ev: discord.PermissionOverwrite(read_messages=False), r_stf: discord.PermissionOverwrite(read_messages=True, send_messages=True), me: discord.PermissionOverwrite(read_messages=True, send_messages=True)}
        ow_prf = {ev: discord.PermissionOverwrite(read_messages=False), ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True), me: discord.PermissionOverwrite(read_messages=True, send_messages=True)}
        ow_voi = {ev: discord.PermissionOverwrite(connect=False, view_channel=True), r_mem: discord.PermissionOverwrite(connect=True, view_channel=True), me: discord.PermissionOverwrite(connect=True, manage_channels=True)}

        async def _create_cat(name, overwrites):
            cat = await ctx.guild.create_category(name, overwrites=overwrites)
            new_chans.add(cat.id)
            return cat
            
        async def _create_txt(name, cat):
            ch = await ctx.guild.create_text_channel(name, category=cat)
            new_chans.add(ch.id)
            return ch
            
        async def _create_vc(name, cat):
            ch = await ctx.guild.create_voice_channel(name, category=cat)
            new_chans.add(ch.id)
            return ch

        c_info = await _create_cat("IMPORTANT", ow_info)
        await _create_txt("welcome", c_info)
        ch_rules = await _create_txt("rules", c_info)
        await _create_txt("announcements", c_info)

        c_gen = await _create_cat("COMMUNITY", ow_gen)
        await _create_txt("general-chat", c_gen)
        await _create_txt("media-sharing", c_gen)
        await _create_txt("bot-commands", c_gen)

        c_voice = await _create_cat("VOICE CHANNELS", ow_voi)
        await _create_vc("Join to Create", c_voice)

        c_mod = await _create_cat("STAFF ONLY", ow_mod)
        await _create_txt("staff-chat", c_mod)
        await _create_txt(LOG_CH, c_mod)

        c_prof = await _create_cat(CAT_NAME, ow_prf)
        for ch in [CMD_CH, RES_CH, MEDIA_CH]: await _create_txt(ch, c_prof)

        rules_text = (
            "**Dokumen Regulasi dan Tata Tertib Komunitas**\n\n"
            "Guna menjaga stabilitas dan keamanan lingkungan server, setiap entitas yang tergabung diwajibkan untuk mematuhi regulasi berikut. Pelanggaran terhadap poin-poin di bawah ini akan dikenakan sanksi administratif.\n\n"
            "**1. Integritas dan Sopan Santun**\n"
            "Seluruh anggota diwajibkan menjaga profesionalisme. Tindakan provokasi, perundungan, diskriminasi, dan ujaran kebencian dilarang secara tegas.\n\n"
            "**2. Distribusi Konten**\n"
            "Dilarang mendistribusikan konten yang mengandung unsur pornografi, kekerasan ekstrem, atau materi yang melanggar hukum. Praktik spamming dan penyebutan (mention) massal tanpa urgensi juga tidak diperkenankan.\n\n"
            "**3. Larangan Aktivitas Ilegal**\n"
            "Komunitas ini tidak memfasilitasi aktivitas peretasan, eksploitasi perangkat lunak, maupun transaksi barang ilegal.\n\n"
            "**4. Kewenangan Administratif**\n"
            "Keputusan administrator bersifat mutlak. Pihak manajemen memiliki otoritas penuh untuk menangguhkan akses pengguna yang terindikasi mengganggu ekosistem server.\n\n"
            "Silakan menekan tombol di bawah ini untuk memverifikasi identitas Anda dan menyetujui perjanjian operasional."
        )
        
        rules_embed = discord.Embed(title="Regulasi Server & Verifikasi Keamanan", description=rules_text, color=0x2b2d31)
        await ch_rules.send(embed=rules_embed, view=VerifyView())

        for c in old_chans:
            if c.id not in new_chans:
                try: 
                    await c.delete()
                    await asyncio.sleep(0.3)
                except: pass

        new_cmd = discord.utils.get(ctx.guild.text_channels, name=CMD_CH)
        if new_cmd:
            await new_cmd.send(f"{ctx.author.mention} Rekonstruksi struktur server telah diselesaikan secara otomatis.")

    @commands.command()
    async def warn(self, ctx, member: discord.Member, *, reason="Tidak ada keterangan spesifik"):
        is_staff = any(r.name in [ROLE_STF, "Admin"] for r in getattr(ctx.author, "roles", []))
        if not (is_staff or ctx.author.id == self.bot.owner_id): return
        
        await ctx.send(f"Peringatan resmi telah diberikan kepada {member.mention}.\n**Konteks:** {reason}")
        await self._log_mod(ctx.guild, "Laporan Penindakan: Peringatan", f"**Tersangka:** {member.mention}\n**Eksekutor:** {ctx.author.mention}\n**Alasan Investigasi:** {reason}", 0xFFA500)

    @commands.command()
    async def mute(self, ctx, member: discord.Member, *, reason="Tidak ada keterangan spesifik", minutes: int = 10):
        is_staff = any(r.name in [ROLE_STF, "Admin"] for r in getattr(ctx.author, "roles", []))
        if not (is_staff or ctx.author.id == self.bot.owner_id): return
        
        await member.timeout(datetime.now(timezone.utc) + timedelta(minutes=minutes), reason=reason)
        await ctx.send(f"Akses komunikasi {member.mention} telah dibekukan sementara selama {minutes} menit.\n**Konteks:** {reason}")
        await self._log_mod(ctx.guild, "Laporan Penindakan: Pembatasan Akses", f"**Tersangka:** {member.mention}\n**Durasi Pembekuan:** {minutes} Menit\n**Eksekutor:** {ctx.author.mention}\n**Alasan Investigasi:** {reason}", 0x808080)

    @commands.command()
    async def kick(self, ctx, member: discord.Member, *, reason="Tidak ada keterangan spesifik"):
        is_staff = any(r.name in [ROLE_STF, "Admin"] for r in getattr(ctx.author, "roles", []))
        if not (is_staff or ctx.author.id == self.bot.owner_id): return
        
        await member.kick(reason=reason)
        await ctx.send(f"{member.mention} telah dikeluarkan secara paksa dari server.\n**Konteks:** {reason}")
        await self._log_mod(ctx.guild, "Laporan Penindakan: Eliminasi", f"**Tersangka:** {member.name}\n**Eksekutor:** {ctx.author.mention}\n**Alasan Investigasi:** {reason}", 0xFF4500)

    @commands.command()
    async def ban(self, ctx, member: discord.Member, *, reason="Tidak ada keterangan spesifik"):
        is_staff = any(r.name in [ROLE_STF, "Admin"] for r in getattr(ctx.author, "roles", []))
        if not (is_staff or ctx.author.id == self.bot.owner_id): return
        
        await member.ban(reason=reason)
        await ctx.send(f"Entitas {member.mention} telah ditangguhkan secara permanen dari server.\n**Konteks:** {reason}")
        await self._log_mod(ctx.guild, "Laporan Penindakan: Penangguhan Akses", f"**Tersangka:** {member.name}\n**Eksekutor:** {ctx.author.mention}\n**Alasan Investigasi:** {reason}", 0x8B0000)

    @commands.command()
    @commands.is_owner()
    async def update(self, ctx):
        if not ctx.message.attachments or not ctx.message.attachments[0].filename.endswith('.py'):
            return await ctx.send("Protokol ditolak. Lampiran skrip instalasi (.py) tidak terdeteksi.", delete_after=5)
        m = await ctx.send("Mengunduh komponen pembaruan via Over-The-Air...")
        try:
            # Menggunakan absolute path agar Termux tidak kebingungan saat restart
            script_path = os.path.abspath(__file__)
            await ctx.message.attachments[0].save(script_path)
            await m.edit(content="Skrip sistem telah berhasil ditimpa. Menginisialisasi ulang siklus operasi...")
            
            # Menjalankan ulang menggunakan environment python absolut yang sama
            os.execv(sys.executable, [sys.executable, script_path])
        except Exception as e: 
            await m.edit(content=f"Anomali fatal saat memuat pembaruan: {e}")

    async def process_media(self, ctx, msg, embed, t_b=None, t_n=None, i_b=None, i_n=None):
        m_ch, r_ch = discord.utils.get(ctx.guild.text_channels, name=MEDIA_CH), discord.utils.get(ctx.guild.text_channels, name=RES_CH)
        if not m_ch or not r_ch: return await msg.edit(content="Error: Direktori penyimpanan infrastruktur tidak ditemukan.")
        files = [discord.File(b, filename=n) for b, n in [(t_b, t_n), (i_b, i_n)] if b and n]
        if files:
            m_msg = await m_ch.send(content=f"Registri Penyimpanan Media: {datetime.now().timestamp()}", files=files)
            for a in m_msg.attachments:
                if t_n and a.filename == t_n: embed.set_thumbnail(url=a.url)
                if i_n and a.filename == i_n: embed.set_image(url=a.url)
        await r_ch.send(embed=embed)
        await msg.edit(content=f"Siklus analisis selesai. Laporan diterbitkan di {r_ch.mention}. Relik media diarsipkan pada {m_ch.mention}.")

    @commands.command(aliases=['profile'])
    @commands.is_owner()
    async def profil(self, ctx, target: str = None):
        if ctx.channel.name != CMD_CH: return
        if not target or not target.isdigit(): return await ctx.send("Parameter ditolak. Eksekusi membutuhkan format angka User ID Discord.", delete_after=5)
        m = await ctx.send("Mengekstrak data dasar dari Discord API...")
        try: user = await ctx.guild.fetch_member(int(target))
        except:
            try: user = await self.bot.fetch_user(int(target))
            except: return await m.edit(content="Kegagalan API: Identitas target tidak terdaftar dalam database.")

        c_dt = user.created_at
        fields = [
            ("Kredensial Akun", f"**Username:** {user.name}\n**Identitas Global:** {user.global_name or 'Tidak diatur'}\n**Sistem ID:** {user.id}", True),
            ("Kategori Profil", f"**Tipe:** {'Infrastruktur Bot' if user.bot else 'Pengguna Eksternal'}\n**Palet Warna:** {f'#{user.accent_color.value:06x}'.upper() if user.accent_color else 'Kalkulasi Sistem (Default)'}", True),
            ("Jaringan Internal", f"Ditemukan di **{len(user.mutual_guilds)}** basis server" if hasattr(user, 'mutual_guilds') else "Tidak terdeteksi", True)
        ]

        if isinstance(user, discord.Member):
            act = user.activity.name if user.activity else "Tidak ada aktivitas"
            if user.activity and user.activity.type.name in ["playing", "listening", "watching", "streaming"]: 
                act = f"{user.activity.type.name.title()} {act}"
            
            status_dict = {"online": "Online", "idle": "Idle", "dnd": "Do Not Disturb"}
            m_status = status_dict.get(str(user.status), "Offline")

            fields.extend([
                ("Telemetri Kehadiran", f"**Kondisi Jaringan:** {m_status}\n**Status Aktivitas:** {act}", True),
                ("Spesifikasi Keanggotaan", f"**Alias Domain:** {user.nick or 'Tidak dikonfigurasi'}\n**Kewenangan Puncak:** {user.top_role.name if user.top_role else 'Level Dasar'}", True),
                ("Indeks Registrasi", f"**Tingkat Booster:** {discord.utils.format_dt(user.premium_since, 'R') if user.premium_since else 'Bukan Akses Premium'}\n**Terkoneksi Sejak:** {discord.utils.format_dt(user.joined_at, 'F') if user.joined_at else 'Data korup'}", False)
            ])

        bgs = [BADGES.get(f.name, f.name.replace('_', ' ').title()) for f in user.public_flags.all()]
        fields.extend([
            ("Inventaris Lencana", ", ".join(bgs) if bgs else "Tidak ditemukan lencana terverifikasi", False), 
            ("Tanggal Penciptaan", f"{discord.utils.format_dt(c_dt, 'F')} (Usia akumulatif {(datetime.now(timezone.utc) - c_dt).days:,} hari)", False)
        ])
        
        t_b = await self._fetch(user.avatar.with_size(1024).url, is_json=False) if user.avatar else None
        i_b = await self._fetch(user.banner.with_size(1024).url, is_json=False) if user.banner else None
        t_n = f"av_{user.id}.{'gif' if user.avatar and user.avatar.is_animated() else 'png'}" if t_b else None
        i_n = f"bn_{user.id}.{'gif' if user.banner and user.banner.is_animated() else 'png'}" if i_b else None

        await self.process_media(ctx, m, self._build_embed("Laporan Analitik Discord", None, user.accent_color or discord.Color.dark_gray(), fields), t_b, t_n, i_b, i_n)

    @commands.command()
    @commands.is_owner()
    async def github(self, ctx, target: str = None):
        if ctx.channel.name != CMD_CH: return
        if not target: return await ctx.send("Parameter ditolak. Nama pengguna GitHub dibutuhkan.", delete_after=5)
        m = await ctx.send("Membuka jembatan koneksi ke server GitHub...")
        
        reqs = {
            "u": f"https://api.github.com/users/{target}",
            "r": f"https://api.github.com/users/{target}/repos?per_page=100",
            "o": f"https://api.github.com/users/{target}/orgs"
        }
        res = dict(zip(reqs.keys(), await asyncio.gather(*(self._fetch(url) for url in reqs.values()))))
        if not res["u"]: return await m.edit(content="Kegagalan Proses: Target tidak valid di database GitHub.")

        u, r, o = res["u"], res["r"] or [], res["o"] or []
        orgs = ", ".join([x.get("login") for x in o]) or "Tidak berafiliasi secara publik"
        c_dt = parse_dt(u['created_at'], "%Y-%m-%dT%H:%M:%SZ")

        fields = [
            ("Parameter Pengguna", f"**Identitas:** {u.get('login')}\n**Kredensial Resmi:** {u.get('name') or 'Disembunyikan'}\n**Nomor Indeks:** {u.get('id')}", True),
            ("Infrastruktur Sosial", f"**Korporasi:** {u.get('company') or 'Tidak terikat'}\n**Area Fisik:** {u.get('location') or 'Tidak dipublikasi'}\n**Tautan Eksternal:** {u.get('twitter_username') or 'Tidak terhubung'}", True),
            ("Statistik Komputasi", f"**Repositori Terbuka:** {u.get('public_repos')}\n**Distribusi Gists:** {u.get('public_gists')}\n**Akumulasi Stars:** {sum(x.get('stargazers_count', 0) for x in r)}\n**Total Percabangan:** {sum(x.get('forks_count', 0) for x in r)}", True),
            ("Jaringan Kolektif", f"**Pengikut:** {u.get('followers')} Entitas | **Mengikuti:** {u.get('following')} Entitas", True), 
            ("Daftar Organisasi Internal", orgs, False)
        ]
        if u.get('bio'): fields.append(("Catatan Tambahan (Bio)", u.get('bio'), False))
        fields.append(("Rekam Jejak Pendaftaran", f"{discord.utils.format_dt(c_dt, 'F')} (Aktivitas terdeteksi sejak {(datetime.now(timezone.utc) - c_dt).days:,} hari lalu)", False))
        
        if r: 
            top_repos = "\n".join([f"Stars: {x.get('stargazers_count')} - [{x.get('name')}]({x.get('html_url')})" for x in sorted(r, key=lambda i: i.get('stargazers_count', 0), reverse=True)[:3]])
            fields.append(("Tiga Repositori Berpengaruh", top_repos or "Data Stars tidak mencukupi", False))

        t_b = await self._fetch(u['avatar_url'], is_json=False) if u.get('avatar_url') else None
        await self.process_media(ctx, m, self._build_embed("Laporan Telemetri GitHub", u.get('html_url'), discord.Color.dark_gray(), fields), t_b, f"gh_{u.get('login')}.png" if t_b else None, None, None)

    @commands.command()
    @commands.is_owner()
    async def roblox(self, ctx, target: str = None):
        if ctx.channel.name != CMD_CH: return
        if not target: return await ctx.send("Parameter ditolak. Tautan atau User ID Roblox diperlukan.", delete_after=5)
        tid = re.search(r'users/(\d+)', target).group(1) if "roblox.com" in target else target
        if not tid.isdigit(): return await ctx.send("Kondisi tidak terpenuhi. Ekstrak User ID tidak memuat angka valid.", delete_after=5)
        
        m = await ctx.send("Memulai pengambilan data agregat paralel dari server pusat Roblox...")
        u_data = await self._fetch(f"https://users.roblox.com/v1/users/{tid}")
        if not u_data: return await m.edit(content="Kegagalan Sinkronisasi: Akun terindikasi palsu atau telah dihapus oleh Roblox.")

        apis = {
            "p": ("POST", "https://presence.roblox.com/v1/presence/users", {"userIds": [int(tid)]}),
            "f": ("GET", f"https://friends.roblox.com/v1/users/{tid}/friends/count", None),
            "fol": ("GET", f"https://friends.roblox.com/v1/users/{tid}/followers/count", None),
            "fng": ("GET", f"https://friends.roblox.com/v1/users/{tid}/followings/count", None),
            "g": ("GET", f"https://groups.roblox.com/v1/users/{tid}/groups/roles", None),
            "pg": ("GET", f"https://groups.roblox.com/v1/users/{tid}/groups/primary/role", None),
            "h": ("GET", f"https://users.roblox.com/v1/users/{tid}/username-history?limit=10&sortOrder=Desc", None),
            "prem": ("GET", f"https://premiumfeatures.roblox.com/v1/users/{tid}/validate-membership", None),
            "bdg": ("GET", f"https://accountinformation.roblox.com/v1/users/{tid}/roblox-badges", None),
            "inv": ("GET", f"https://inventory.roblox.com/v1/users/{tid}/can-view-inventory", None),
            "av": ("GET", f"https://avatar.roblox.com/v1/users/{tid}/avatar", None),
            "gm": ("GET", f"https://games.roblox.com/v2/users/{tid}/games?limit=50", None),
            "soc": ("GET", f"https://users.roblox.com/v1/users/{tid}/social-links", None),
            "col": ("GET", f"https://inventory.roblox.com/v1/users/{tid}/assets/collectibles?limit=100", None),
            "fav": ("GET", f"https://games.roblox.com/v2/users/{tid}/favorite/games?limit=50", None),
            "out": ("GET", f"https://avatar.roblox.com/v1/users/{tid}/outfits?page=1&itemsPerPage=10", None),
            "gb": ("GET", f"https://badges.roblox.com/v1/users/{tid}/badges?limit=100&sortOrder=Desc", None),
            "th": ("GET", f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={tid}&size=420x420&format=Png", None),
            "tf": ("GET", f"https://thumbnails.roblox.com/v1/users/avatar?userIds={tid}&size=720x720&format=Png", None)
        }
        r = dict(zip(apis.keys(), await asyncio.gather(*(self._fetch(url, meth, j) for meth, url, j in apis.values()))))

        p_txt, l_loc, l_on = "Sesi Tertutup", "Parameter tidak terdeteksi", "Parameter tidak terdeteksi"
        if r["p"] and r["p"].get("userPresences"):
            pr = r["p"]["userPresences"][0]
            p_typ = pr.get("userPresenceType", 0)
            p_txt = {0:"Offline", 1:"Modul Online", 2:"Di Dalam Game", 3:"Modul Studio Aktif"}.get(p_typ, "Offline")
            l_loc = pr.get("lastLocation", "Lokasi dikunci")
            if pr.get("lastOnline"): l_on = discord.utils.format_dt(parse_dt(pr["lastOnline"][:19], "%Y-%m-%dT%H:%M:%S"), 'R')

        pg_str = f"{r['pg']['group'].get('name', 'Unknown')} (Kewenangan: {r['pg'].get('role', {}).get('name', 'Member')})" if r["pg"] and "group" in r["pg"] else "Tidak berafiliasi dengan grup pusat"
        soc_str = "\n".join([f"**{s['type']}:** {s.get('title', s.get('url'))}" for s in r["soc"]["data"]]) if r["soc"] and r["soc"].get("data") else "Privat atau tidak ada integrasi sosial"
        b_names = [b["name"] for b in r["bdg"]] if r["bdg"] else []
        col_data = r["col"].get("data", []) if r["col"] else []
        
        eq_str, t_rbx, av_typ, av_scl, em_cnt = "Tidak ada atribut terpasang", 0, "Standar", "H: 1 | W: 1 | Hd: 1", 0
        if r["av"]:
            em_cnt = len(r["av"].get("emotes", []))
            av_typ = r["av"].get("playerAvatarType", "Tidak Spesifik")
            sc = r["av"].get("scales", {})
            av_scl = f"Tinggi: {sc.get('height', 1)} | Dimensi Lebar: {sc.get('width', 1)} | Visual Kepala: {sc.get('head', 1)}"
            assets = r["av"].get("assets", [])
            if assets:
                ga = {}
                for a in assets: ga.setdefault(a.get("assetType", {}).get("name", "Unknown"), []).append(a.get("name", "Unknown"))
                eq_str = "\n".join([f"**{t}:** {', '.join(ns)}" for t, ns in ga.items()])[:1020]
                c_data = await self._fetch("https://catalog.roblox.com/v1/catalog/items/details", "POST", {"items": [{"itemType": "Asset", "id": a["id"]} for a in assets]})
                t_rbx = sum((i.get("price") or 0) for i in c_data.get("data", [])) if c_data else 0

        c_dt = parse_dt(u_data['created'])
        fields = [
            ("Registri Sentral", f"**Username:** {u_data.get('name')}\n**Display Akses:** {u_data.get('displayName')}\n**Indeks Pemain:** {tid}\n**Autentikasi Korporat:** {'Tervalidasi (Centang)' if u_data.get('hasVerifiedBadge') else 'Negatif'}", True),
            ("Indikator Pergerakan", f"**Status:** {p_txt}\n**Zona Lingkungan:** {l_loc[:20]}\n**Jejak Aktif:** {l_on}", True),
            ("Evaluasi Keamanan", f"**Langganan Premium:** {'Beroperasi' if r['prem'] else 'Pasif'}\n**Pemblokiran Sistem:** {'Ditangguhkan' if u_data.get('isBanned') else 'Status Aman'}\n**Arsip Barang:** {'Terbuka untuk Publik' if r['inv'] and r['inv'].get('canView') else 'Disembunyikan'}", True),
            ("Kalkulasi Ekonomi Digital", f"**Valuasi RAP:** {sum(i.get('recentAveragePrice', 0) for i in col_data):,} R$\n**Aset Langka (Limited):** {len(col_data)} Objek\n**Harga Konversi Atribut:** {t_rbx:,} R$\n**Blueprint Outfit:** {r['out'].get('total', 0) if r['out'] else 0} Format", True),
            ("Konstruksi Karakter", f"**Model Mesin:** {av_typ}\n**Kalkulasi Proporsi:** {av_scl}\n**Total Emote:** {em_cnt} Tautan", True),
            ("Statistik Komunitas", f"**Rasio Teman:** {r['f'].get('count', 0) if r['f'] else 0:,}\n**Tingkat Pengikut:** {r['fol'].get('count', 0) if r['fol'] else 0:,}\n**Jaringan Target:** {r['fng'].get('count', 0) if r['fng'] else 0:,}", True),
            ("Capaian Lencana (Badges)", f"**Penghargaan Resmi:** {len(b_names)} Koleksi\n**Medali Permainan:** {len(r['gb'].get('data', [])) if r['gb'] else 0}{'+' if r['gb'] and r['gb'].get('nextPageCursor') else ''} Poin", True),
            ("Tingkat Kreativitas Kreator", f"**Aliansi Terdaftar:** {len(r['g'].get('data', [])) if r['g'] else 0:,}\n**Proyek Terselesaikan:** {len(r['gm'].get('data', [])) if r['gm'] else 0:,}\n**Game Dianalisis:** {len(r['fav'].get('data', [])) if r['fav'] else 0:,}", True),
            ("Indikator Afiliasi Grup", pg_str, True), ("Sistem Autentikasi Pihak Ketiga", soc_str[:1024], False), ("Rincian Modul Visual Terpasang", eq_str, False),
            ("Histori Medali Korporat", ", ".join(b_names)[:1024] or "Tidak ada sejarah keterlibatan platform", False), ("Catatan Perubahan Identitas", ", ".join([n["name"] for n in r["h"].get("data", [])])[:1024] if r["h"] and r["h"].get("data") else "Identitas akun tidak pernah dimodifikasi", False)
        ]
        if u_data.get('description'): fields.append(("Catatan Operasional Khusus", u_data.get('description')[:1024], False))
        fields.append(("Rekam Jejak Siklus Hidup", f"{discord.utils.format_dt(c_dt, 'F')} (Rentang eksistensi {(datetime.now(timezone.utc) - c_dt).days:,} hari)", False))

        t_b, t_n, i_b, i_n = None, None, None, None
        if r["th"] and r["th"].get("data"):
            t_b, t_n = await self._fetch(r["th"]["data"][0]["imageUrl"], is_json=False), f"rh_{tid}.png"
        if r["tf"] and r["tf"].get("data"):
            i_b, i_n = await self._fetch(r["tf"]["data"][0]["imageUrl"], is_json=False), f"rf_{tid}.png"

        await self.process_media(ctx, m, self._build_embed("Laporan Analitik Roblox Tingkat Lanjut", f"https://www.roblox.com/users/{tid}/profile", discord.Color.dark_gray(), fields), t_b, t_n, i_b, i_n)

if __name__ == "__main__":
    bot = MasterBot()
    bot.run(TOKEN)
