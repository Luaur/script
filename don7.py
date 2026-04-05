import discord
from discord.ext import commands, tasks
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
import random

TOKEN = ""
OWNER_ID = 1463723091489194150
VERSION = "v2.4.5 (Bugfix & Stability Edition)"
BOT_START_TIME = time.time()
THEME_COLOR = 0x2b2d31

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPDATE_FILE = os.path.join(BASE_DIR, "update_trigger.txt")
VERSION_FILE = os.path.join(BASE_DIR, "version_record.txt")

AUTO_FARM_URL = "https://www.roblox.com/share?code=4aa66c9d90ca654b940a598c9ce3e969&type=Server"

LATEST_CHANGES = (
    "Sistem telah distabilkan ke versi 2.4.5. Berikut perbaikan bug kritis yang dilakukan:\n\n"
    "1. Perbaikan Bug (!setup): Mengatasi masalah duplikasi pembuatan saluran #system-changelog dan #active-proxies.\n"
    "2. Perbaikan Bug (!update): Menyempurnakan metode os.execv agar proses muat ulang (restart) kode berjalan mulus tanpa crash di environment Termux.\n"
    "3. Pemulihan API Proxy: Menambahkan lapisan koneksi ganda pada Proxy Scraper untuk mencegah blokir jaringan (rate limit), memastikan proxy aktif tidak terlewatkan.\n"
    "4. Kompatibilitas OS Android: Memperluas pemindaian background (ps) agar bot dapat melacak Roblox di semua versi Android tanpa kegagalan membaca proses."
)

CAT_NAME, CMD_CH, RES_CH, MEDIA_CH, PROXY_CH = "PROFILER SYSTEM", "cmd-profiler", "result-profiler", "media-profiler", "active-proxies"
LOG_CH = "server-logs"
CHANGELOG_CH = "system-changelog"
ROLE_MEM, ROLE_STF = "Member", "Staff"

ROBLOX_URL_PATTERN = re.compile(r'users/(\d+)')
BATT_LEVEL_PATTERN = re.compile(r'level: (\d+)')
BATT_TEMP_PATTERN = re.compile(r'temperature: (\d+)')
BATT_STATUS_PATTERN = re.compile(r'status: (\d+)')

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

    @discord.ui.button(label="Verifikasi Akses", style=discord.ButtonStyle.secondary, custom_id="verify_gatekeeper")
    async def verify_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = discord.utils.get(interaction.guild.roles, name=ROLE_MEM)
        if not role:
            return await interaction.response.send_message("Kesalahan: Peran akses dasar tidak ditemukan.", ephemeral=True)
        if role in interaction.user.roles:
            await interaction.response.send_message("Anda sudah terverifikasi di dalam sistem.", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("Verifikasi berhasil. Hak akses telah dibuka.", ephemeral=True)

class MasterBot(commands.Bot):
    def __init__(self):
        ints = discord.Intents.default()
        ints.message_content = True
        ints.members = True
        ints.presences = True
        ints.voice_states = True
        super().__init__(command_prefix="!", intents=ints, help_command=None, owner_id=OWNER_ID)
        self.booted = False

    async def setup_hook(self):
        self.add_view(VerifyView())
        await self.add_cog(SystemCog(self))

    async def on_ready(self):
        if self.booted: return
        self.booted = True
        
        try: owner = await self.fetch_user(self.owner_id)
        except: return
        
        for g in self.guilds:
            ow = {
                g.default_role: discord.PermissionOverwrite(read_messages=False),
                owner: discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True),
                g.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True, attach_files=True)
            }
            cat = discord.utils.get(g.categories, name=CAT_NAME) or await g.create_category(CAT_NAME, overwrites=ow)
            for ch in [CMD_CH, RES_CH, MEDIA_CH, PROXY_CH]:
                if not discord.utils.get(g.text_channels, name=ch, category=cat): await g.create_text_channel(ch, category=cat)

        should_send_changelog = False
        catatan = LATEST_CHANGES

        if os.path.exists(UPDATE_FILE):
            try:
                with open(UPDATE_FILE, "r") as f:
                    isi = f.read().strip()
                os.remove(UPDATE_FILE)
                if isi != "AUTO": catatan = isi
                should_send_changelog = True
            except: pass
        else:
            saved_version = ""
            if os.path.exists(VERSION_FILE):
                try:
                    with open(VERSION_FILE, "r") as f: saved_version = f.read().strip()
                except: pass
            if saved_version != VERSION:
                should_send_changelog = True

        if should_send_changelog:
            try:
                with open(VERSION_FILE, "w") as f: f.write(VERSION)
            except: pass
            
            await asyncio.sleep(2) 

            for g in self.guilds:
                ch = discord.utils.get(g.text_channels, name=CHANGELOG_CH)
                if not ch: ch = discord.utils.get(g.text_channels, name=CMD_CH)
                
                if ch:
                    e = discord.Embed(title="Pembaruan Bot Berhasil", color=THEME_COLOR, timestamp=datetime.now(timezone.utc))
                    e.add_field(name="Versi Saat Ini", value=f"`{VERSION}`", inline=False)
                    e.add_field(name="Catatan Rilis", value=catatan, inline=False)
                    try:
                        await ch.send(content=f"<@{self.owner_id}>", embed=e)
                        break
                    except: pass

class SystemCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = None
        self.temp_vcs = set()
        
        self.roblox_instances = {}
        self.instances_state = {}

    async def cog_load(self): 
        self.session = aiohttp.ClientSession()
        await self.auto_scan_packages()
        self.roblox_monitor_loop.start()
        self.proxy_scraper_loop.start()

    async def cog_unload(self): 
        if self.session: await self.session.close()
        self.roblox_monitor_loop.cancel()
        self.proxy_scraper_loop.cancel()
        
    async def auto_scan_packages(self):
        try:
            # Menggunakan kombinasi ps -A dan ps -ef untuk menghindari bug OS Termux
            output = subprocess.run("su -c 'ps -A | grep -i roblox'", shell=True, capture_output=True, text=True).stdout
            if not output.strip():
                output = subprocess.run("su -c 'ps -ef | grep -i roblox'", shell=True, capture_output=True, text=True).stdout
                
            packages = [line.split()[-1].strip() for line in output.split('\n') if line.strip() and "com.roblox" in line]
            packages = list(set(packages)) # Hapus duplikat
            
            self.roblox_instances.clear()
            self.instances_state.clear()
            
            idx = 1
            for pkg in packages:
                name = "Ori" if pkg == "com.roblox.client" else f"Clone{idx}"
                self.roblox_instances[name] = {"user": "0", "package": pkg, "url": AUTO_FARM_URL}
                self.instances_state[name] = None
                if name != "Ori": idx += 1
                
        except Exception as e:
            print(f"Gagal memindai paket otomatis: {e}")
    
    async def cog_command_error(self, ctx, error):
        if isinstance(error, (commands.NotOwner, commands.CheckFailure, commands.CommandNotFound)): 
            return

        await ctx.send("Perintah gagal dijalankan. Laporan kesalahan telah dikirimkan ke pesan pribadi Anda.", delete_after=5)
        owner = await self.bot.fetch_user(self.bot.owner_id)
        if owner:
            tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
            e = discord.Embed(title="Laporan Kesalahan Bot", color=0xFF0000, timestamp=datetime.now(timezone.utc))
            e.add_field(name="Perintah Masukan", value=ctx.command.name if ctx.command else "Tidak teridentifikasi", inline=True)
            e.add_field(name="Lokasi Eksekusi", value=ctx.channel.name, inline=True)
            if len(tb) > 2000:
                await owner.send(embed=e, file=discord.File(io.BytesIO(tb.encode('utf-8')), filename="crash_log.txt"))
            else:
                e.description = f"```python\n{tb}\n```"
                await owner.send(embed=e)

    # ------------------ SISTEM PROXY MULTI-SOURCE ------------------
    @tasks.loop(hours=4)
    async def proxy_scraper_loop(self):
        await self.bot.wait_until_ready()
        
        proxy_channel = None
        for guild in self.bot.guilds:
            proxy_channel = discord.utils.get(guild.text_channels, name=PROXY_CH)
            if proxy_channel: break
            
        if not proxy_channel: return

        sources = [
            "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all",
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
            "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
            "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt"
        ]

        raw_proxies = set() 

        async def fetch_source(url):
            try:
                async with self.session.get(url, timeout=15) as r:
                    if r.status == 200:
                        text = await r.text()
                        for line in text.splitlines():
                            p = line.strip()
                            if p and ":" in p:
                                raw_proxies.add(p)
            except: pass

        await proxy_channel.send("📥 **Mengumpulkan proxy dari berbagai sumber...**")
        await asyncio.gather(*(fetch_source(url) for url in sources))

        if not raw_proxies: 
            return await proxy_channel.send("❌ Gagal mengumpulkan data proxy dari sumber.")

        proxy_list = list(raw_proxies)
        random.shuffle(proxy_list) 
        proxy_list = proxy_list[:250] 

        await proxy_channel.send(f"🔍 **Mulai memindai {len(proxy_list)} proxy terpilih...** (Sistem akan langsung mengirim proxy yang aktif).")

        working_count = 0
        sem = asyncio.Semaphore(10) 

        async def check_and_send(proxy):
            nonlocal working_count
            async with sem:
                start_time = time.time()
                try:
                    # Mengecek koneksi murni terlebih dahulu untuk menghindari rate limit API lokasi
                    async with self.session.get("http://httpbin.org/ip", proxy=f"http://{proxy}", timeout=5) as resp:
                        if resp.status == 200:
                            latency = round((time.time() - start_time) * 1000)
                            
                            # Mengambil detail lokasi jika proxy valid
                            country, isp = "Tidak Diketahui", "Tidak Diketahui"
                            try:
                                async with self.session.get("http://ip-api.com/json/", proxy=f"http://{proxy}", timeout=3) as geo:
                                    if geo.status == 200:
                                        data = await geo.json()
                                        if data.get("status") == "success":
                                            country = data.get("country", country)
                                            isp = data.get("isp", isp)[:30]
                            except: pass
                            
                            working_count += 1
                            
                            e = discord.Embed(title="🟢 Proxy Valid Terdeteksi", color=0x00FF00)
                            e.add_field(name="Kredensial IP", value=f"`{proxy}`", inline=False)
                            e.add_field(name="Negara", value=country, inline=True)
                            e.add_field(name="ISP (Penyedia)", value=isp, inline=True)
                            e.add_field(name="Latensi (Ping)", value=f"`{latency} ms`", inline=True)
                            
                            await proxy_channel.send(embed=e)
                except:
                    pass

        await asyncio.gather(*(check_and_send(p) for p in proxy_list))
        await proxy_channel.send(f"✅ **Siklus Pemindaian Selesai:** Total proxy yang lolos verifikasi: **{working_count} Proxy**.")

    @proxy_scraper_loop.before_loop
    async def before_proxy_scraper(self):
        await self.bot.wait_until_ready()
    # --------------------------------------------------

    @tasks.loop(seconds=30)
    async def roblox_monitor_loop(self):
        if not self.roblox_instances: return 
        
        try:
            dump_output = subprocess.run("su -c 'ps -ef | grep roblox'", shell=True, capture_output=True, text=True).stdout
        except Exception:
            dump_output = ""

        for name, config in self.roblox_instances.items():
            pkg = config["package"]
            user_id = config["user"]
            
            is_running = pkg in dump_output
            was_running = self.instances_state.get(name)

            if was_running is True and not is_running:
                for guild in self.bot.guilds:
                    ch = discord.utils.get(guild.text_channels, name=CMD_CH)
                    if ch:
                        e = discord.Embed(
                            title=f"Aplikasi Terhenti: {name}", 
                            description=f"Sistem mendeteksi Roblox sesi **{name}** (`{pkg}`) telah tertutup.\n\nMemulai proses pemulihan otomatis ke tautan awal...", 
                            color=0xFF0000, 
                            timestamp=datetime.now(timezone.utc)
                        )
                        e.set_footer(text="Pengawas Aplikasi Otomatis")
                        await ch.send(content=f"<@{OWNER_ID}>", embed=e)
                        break
                
                try:
                    url = config["url"]
                    cmd = f'su -c "am start --user {user_id} -p {pkg} -a android.intent.action.VIEW -d \'{url}\'"'
                    subprocess.run(cmd, shell=True)
                except Exception as e:
                    print(f"Gagal memulihkan sesi {name}: {e}")

            self.instances_state[name] = is_running

    @roblox_monitor_loop.before_loop
    async def before_roblox_monitor(self):
        await self.bot.wait_until_ready()

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
        await self._log_mod(message.guild, "Catatan Pesan Dihapus", f"**Penulis:** {message.author.mention}\n**Lokasi:** {message.channel.mention}\n**Konten:** {message.content[:3000]}", 0xFF0000)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot or before.content == after.content: return
        e = discord.Embed(title="Catatan Pesan Diubah", description=f"**Penulis:** {before.author.mention}\n**Lokasi:** {before.channel.mention}", color=0xFFFF00, timestamp=datetime.now(timezone.utc))
        e.add_field(name="Sebelum", value=before.content[:1024] or "Kosong", inline=False)
        e.add_field(name="Sesudah", value=after.content[:1024] or "Kosong", inline=False)
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
            temp_vc = await after.channel.guild.create_voice_channel(f"Sesi {member.display_name}", category=cat, overwrites=ow)
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
            return await ctx.send("Format masukan tidak lengkap. Harap lampirkan teks atau gambar.", delete_after=5)

        ann_ch = discord.utils.get(ctx.guild.text_channels, name="announcements")
        if not ann_ch:
            return await ctx.send("Saluran pengumuman tidak ditemukan di server ini.", delete_after=5)

        try: await ctx.message.delete()
        except: pass
        
        content = "@everyone\n\n"
        if pesan: content += f"{pesan}\n\n"
        content += f"— Pesan dari: {ctx.author.name}"

        files = [await att.to_file() for att in ctx.message.attachments]
        await ann_ch.send(content=content, files=files)
        
        if ctx.channel != ann_ch:
            await ctx.send("Pengumuman telah berhasil dikirimkan.", delete_after=3)

    @commands.command()
    async def help(self, ctx):
        is_staff = any(r.name in [ROLE_STF, "Admin"] for r in getattr(ctx.author, "roles", []))
        if not (is_staff or ctx.author.id == self.bot.owner_id): return
        if ctx.channel.name != CMD_CH: return
        
        fields = [
            ("!monitor", "Memeriksa status proses aplikasi dan kondisi perangkat utama.", False),
            ("!screenshot / !ss", "Meminta tangkapan layar secara langsung dari memori perangkat.", False),
            ("!scan", "Memindai proses sistem untuk melihat apa saja aplikasi Roblox yang terdeteksi otomatis.", False),
            ("!game [start/stop/restart] [Nama]", "Memaksa perangkat utama untuk menjalankan atau menutup aplikasi. Contoh: `!game restart Clone1`.", False),
            ("!join [Nama Sesi] [Tautan/Link]", "Membuka tautan server Roblox secara spesifik. Contoh: `!join Ori https...`", False),
            ("!profil [User ID]", "Menampilkan data lengkap dari profil akun Discord.", False),
            ("!roblox https://www.merriam-webster.com/dictionary/id", "Mencari data riwayat dan inventaris akun target di platform Roblox.", False),
            ("!github [Username]", "Membaca riwayat repositori dan data profil akun GitHub.", False),
            ("!announce [Teks]", "Mengirimkan pesan massal ke saluran pengumuman server.", False),
            ("!ping", "Menguji kecepatan respons koneksi jaringan.", False),
            ("!stats", "Menampilkan data penggunaan sumber daya sistem yang dipakai bot.", False),
            ("!setup", "Menyusun ulang kategori dan saluran dasar di dalam server tanpa menghapus log penting.", False),
            ("!update [Opsional: Catatan]", "Menerapkan pembaruan modul secara instan beserta catatan versinya.", False),
            ("!warn, !mute, !kick, !ban", "Alat moderasi dasar untuk mengelola anggota server.", False)
        ]
        
        e = self._build_embed("Daftar Perintah Sistem", None, THEME_COLOR, fields, "Berikut adalah perintah yang dapat digunakan pada bot ini:")
        await ctx.send(embed=e)

    @commands.command()
    @commands.is_owner()
    async def scan(self, ctx):
        if ctx.channel.name != CMD_CH: return
        
        if not self.roblox_instances:
            await self.auto_scan_packages()
            
        if not self.roblox_instances:
            return await ctx.send("Radar tidak mendeteksi adanya aplikasi kloning atau asli yang berhubungan dengan Roblox di perangkat ini.")
            
        m_teks = "**Radar Auto-Scan Mendeteksi Aplikasi Berikut:**\n"
        for name, config in self.roblox_instances.items():
            m_teks += f"• **Nama Sesi:** `{name}` | **Package:** `{config['package']}` | **User ID:** `{config['user']}`\n"
            
        await ctx.send(f"{m_teks}\n*Bot secara otomatis melindungi aplikasi di atas. Gunakan nama sesi pada perintah `!game` atau `!join`.*")

    @commands.command()
    @commands.is_owner()
    async def game(self, ctx, action: str = None, name: str = None):
        if ctx.channel.name != CMD_CH: return
        valid_actions = ["start", "stop", "restart"]
        
        if action not in valid_actions or not name or name not in self.roblox_instances:
            return await ctx.send(f"Format tidak valid. Contoh: `!game start Ori`. Pilihan: {', '.join(self.roblox_instances.keys())}.", delete_after=10)

        pkg = self.roblox_instances[name]["package"]
        user_id = self.roblox_instances[name]["user"]
        m = await ctx.send(f"Meneruskan perintah `{action}` untuk sesi **{name}**...")
        
        try:
            if action in ["stop", "restart"]:
                subprocess.run(f"su -c 'am force-stop --user {user_id} {pkg}'", shell=True)
            
            if action in ["start", "restart"]:
                if action == "restart": await asyncio.sleep(2)
                subprocess.run(f"su -c 'monkey -p {pkg} -c android.intent.category.LAUNCHER 1'", shell=True, capture_output=True)
            
            await m.edit(content=f"Perintah `{action}` untuk sesi **{name}** telah berhasil dieksekusi.")
        except Exception as e:
            await m.edit(content=f"Terjadi kesalahan saat memproses kontrol perangkat: {e}")

    @commands.command()
    @commands.is_owner()
    async def join(self, ctx, name: str = None, url: str = None):
        if ctx.channel.name != CMD_CH: return
        if not name or name not in self.roblox_instances or not url or "roblox.com" not in url:
            return await ctx.send(f"Format tidak valid. Contoh penggunaan: `!join Ori https...`. Pilihan sesi: {', '.join(self.roblox_instances.keys())}.", delete_after=10)

        pkg = self.roblox_instances[name]["package"]
        user_id = self.roblox_instances[name]["user"]
        m = await ctx.send(f"Meneruskan tautan ke sesi **{name}**...")
        try:
            cmd = f'su -c "am start --user {user_id} -p {pkg} -a android.intent.action.VIEW -d \'{url}\'"'
            subprocess.run(cmd, shell=True)
            await m.edit(content=f"Tautan berhasil diteruskan. Sesi **{name}** akan segera membuka server permainan tersebut.")
        except Exception as e:
            await m.edit(content=f"Terjadi kesalahan saat memproses tautan: {e}")

    @commands.command()
    @commands.is_owner()
    async def monitor(self, ctx):
        if ctx.channel.name != CMD_CH: return
        m = await ctx.send("Menarik data diagnostik dari perangkat utama...")

        try:
            dump_output = subprocess.run("su -c 'ps -A | grep roblox'", shell=True, capture_output=True, text=True).stdout
            if not dump_output.strip():
                dump_output = subprocess.run("su -c 'ps -ef | grep roblox'", shell=True, capture_output=True, text=True).stdout
        except Exception:
            dump_output = ""

        fields = []
        if not self.roblox_instances:
            fields.append(("Status Sesi", "Tidak ada aplikasi Roblox yang terdeteksi.", False))
        else:
            for name, config in self.roblox_instances.items():
                pkg = config["package"]
                status = "🟢 Sedang Berjalan" if pkg in dump_output else "🔴 Tidak Beroperasi"
                fields.append((f"Status Sesi: {name}", f"Modul: `{pkg}`\nKondisi: {status}", True))

        sys_uptime = "Data tidak tersedia"
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.readline().split()[0])
                sys_uptime = str(timedelta(seconds=int(uptime_seconds))).split('.')[0]
        except: pass

        batt_str = "Data tidak tersedia"
        temp_str = "-"
        try:
            batt_info = subprocess.run("su -c 'dumpsys battery'", shell=True, capture_output=True, text=True).stdout
            level = BATT_LEVEL_PATTERN.search(batt_info)
            temp = BATT_TEMP_PATTERN.search(batt_info)
            status = BATT_STATUS_PATTERN.search(batt_info)
            
            if level:
                lvl = level.group(1)
                st = "Sedang Mengisi Daya" if status and status.group(1) == '2' else ("Baterai Penuh" if status and status.group(1) == '5' else "Menggunakan Baterai")
                batt_str = f"{lvl}% ({st})"
            if temp:
                temp_c = int(temp.group(1)) / 10
                temp_str = f"{temp_c} Celcius"
        except: pass

        fields.append(("Sistem Perangkat Utama", f"**Waktu Aktif:** {sys_uptime}\n**Sistem:** {platform.system()} {platform.release()}", False))
        fields.append(("Kesehatan Perangkat", f"**Status Baterai:** {batt_str}\n**Suhu Perangkat:** {temp_str}", False))

        e = self._build_embed("Pemantauan Perangkat Utama", None, THEME_COLOR, fields, "Data status ini memisahkan pemantauan setiap aplikasi Roblox yang beroperasi.")
        await m.edit(content=None, embed=e)

    @commands.command(aliases=['ss'])
    @commands.is_owner()
    async def screenshot(self, ctx):
        if ctx.channel.name != CMD_CH: return
        m = await ctx.send("Mengambil tangkapan layar perangkat...")
        
        try:
            process = await asyncio.create_subprocess_shell(
                "su -c 'screencap -p'",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0 and stdout:
                file = discord.File(io.BytesIO(stdout), filename="display.png")
                e = discord.Embed(title="Tampilan Layar Perangkat", color=THEME_COLOR, timestamp=datetime.now(timezone.utc))
                e.set_image(url="attachment://display.png")
                e.set_footer(text="Diproses langsung melalui memori (RAM) agar lebih cepat")
                
                await ctx.send(embed=e, file=file)
                await m.delete()
            else:
                await m.edit(content="Sistem gagal membaca gambar layar dari perangkat tujuan.")
        except Exception as e:
            await m.edit(content=f"Terjadi kesalahan saat mengambil layar: {e}")

    @commands.command()
    @commands.is_owner()
    async def ping(self, ctx):
        if ctx.channel.name != CMD_CH: return
        start = time.time()
        msg = await ctx.send("Memeriksa respons jaringan...")
        end = time.time()
        
        api_ms = round((end - start) * 1000)
        ws_ms = round(self.bot.latency * 1000)
        
        e = discord.Embed(title="Kestabilan Jaringan", color=THEME_COLOR)
        e.add_field(name="Respons Internal", value=f"`{ws_ms} ms`", inline=True)
        e.add_field(name="Respons Antarmuka", value=f"`{api_ms} ms`", inline=True)
        await msg.edit(content=None, embed=e)

    @commands.command()
    @commands.is_owner()
    async def stats(self, ctx):
        if ctx.channel.name != CMD_CH: return
        
        bot_uptime = str(timedelta(seconds=int(time.time() - BOT_START_TIME)))
        
        ram_str = "Data tidak tersedia"
        try:
            with open('/proc/meminfo', 'r') as f:
                lines = f.readlines()
                total = int(lines[0].split()[1]) / 1024
                avail = int(lines[2].split()[1]) / 1024
                used = total - avail
                ram_str = f"`{used:.0f} MB / {total:.0f} MB`"
        except: pass

        cpu_count = os.cpu_count() or "Tidak diketahui"
        load_avg = "Data tidak tersedia"
        try:
            with open('/proc/loadavg', 'r') as f:
                load_avg = f.read().split()[:3]
                load_avg = ", ".join(load_avg)
        except: pass

        server_count = len(self.bot.guilds)
        user_count = sum(g.member_count for g in self.bot.guilds)
        ws_ping = round(self.bot.latency * 1000)

        e = discord.Embed(title="Statistik dan Penggunaan Sistem", color=THEME_COLOR)
        
        e.add_field(name="Versi Bot", value=f"`{VERSION}`", inline=True)
        e.add_field(name="Durasi Aktif", value=f"`{bot_uptime}`", inline=True)
        e.add_field(name="Latensi Jaringan", value=f"`{ws_ping} ms`", inline=True)
        
        e.add_field(name="Penggunaan RAM", value=f"`{ram_str}`", inline=True)
        e.add_field(name="Beban CPU", value=f"`{load_avg}`", inline=True)
        e.add_field(name="Jumlah Core CPU", value=f"`{cpu_count} Core`", inline=True)
        
        e.add_field(name="Jumlah Server", value=f"`{server_count} Server`", inline=True)
        e.add_field(name="Jumlah Pengguna", value=f"`{user_count} Anggota`", inline=True)
        e.add_field(name="Pustaka Python", value=f"`v{platform.python_version()}`", inline=True)

        await ctx.send(embed=e)

    @commands.command()
    @commands.is_owner()
    async def setup(self, ctx):
        m = await ctx.send("Memulai penghapusan dan penataan ulang struktur server...")
        old_chans = list(ctx.guild.channels)
        new_chans = set()
        
        me, ev = ctx.guild.me, ctx.guild.default_role
        
        r_mem = discord.utils.get(ctx.guild.roles, name=ROLE_MEM) or await ctx.guild.create_role(name=ROLE_MEM, reason="Pembuatan Peran Otomatis")
        r_stf = discord.utils.get(ctx.guild.roles, name=ROLE_STF) or await ctx.guild.create_role(name=ROLE_STF, reason="Pembuatan Peran Otomatis", permissions=discord.Permissions(manage_messages=True, kick_members=True, ban_members=True))

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

        # Setup Kategori 1
        c_info = await _create_cat("Pusat Informasi", ow_info)
        await _create_txt("welcome", c_info)
        ch_rules = await _create_txt("rules", c_info)
        await _create_txt("announcements", c_info)
        
        # Penyelamatan Saluran Penting
        existing_changelog = discord.utils.get(old_chans, name=CHANGELOG_CH)
        if existing_changelog:
            await existing_changelog.edit(category=c_info, sync_permissions=True)
            new_chans.add(existing_changelog.id)
        else:
            await _create_txt(CHANGELOG_CH, c_info)

        # Setup Kategori 2
        c_gen = await _create_cat("Komunitas", ow_gen)
        await _create_txt("general-chat", c_gen)
        await _create_txt("media-sharing", c_gen)
        await _create_txt("bot-commands", c_gen)

        # Setup Kategori 3
        c_voice = await _create_cat("Saluran Suara", ow_voi)
        await _create_vc("Join to Create", c_voice)

        # Setup Kategori 4
        c_mod = await _create_cat("Area Moderator", ow_mod)
        await _create_txt("staff-chat", c_mod)
        await _create_txt(LOG_CH, c_mod)

        # Setup Kategori 5
        c_prof = await _create_cat(CAT_NAME, ow_prf)
        for ch in [CMD_CH, RES_CH, MEDIA_CH]: 
            await _create_txt(ch, c_prof)
            
        existing_proxy = discord.utils.get(old_chans, name=PROXY_CH)
        if existing_proxy:
            await existing_proxy.edit(category=c_prof, sync_permissions=True)
            new_chans.add(existing_proxy.id)
        else:
            await _create_txt(PROXY_CH, c_prof)

        rules_text = (
            "**Kebijakan dan Peraturan Komunitas**\n\n"
            "Demi kenyamanan bersama, seluruh pengguna diwajibkan untuk mematuhi aturan berikut. Pelanggaran dapat menyebabkan pembatasan akses secara permanen.\n\n"
            "**1. Etika Dasar**\n"
            "Utamakan komunikasi yang baik. Sikap diskriminasi, provokasi, maupun ancaman personal dilarang secara tegas.\n\n"
            "**2. Batasan Konten**\n"
            "Tidak diperkenankan membagikan materi yang memuat unsur pornografi, kekerasan, atau pelanggaran hukum. Hindari pengiriman pesan berulang (spam).\n\n"
            "**3. Fokus Pembahasan**\n"
            "Server ini tidak digunakan untuk mendukung modifikasi program ilegal, penyebaran eksploitasi, maupun transaksi barang tidak resmi.\n\n"
            "**4. Keputusan Moderator**\n"
            "Penilaian akhir berada di tangan admin atau staf. Semua keputusan bersifat mutlak.\n\n"
            "Silakan setujui pedoman ini melalui tombol di bawah untuk mendapatkan akses penuh ke seluruh saluran."
        )
        
        rules_embed = discord.Embed(title="Peraturan Server", description=rules_text, color=THEME_COLOR)
        await ch_rules.send(embed=rules_embed, view=VerifyView())

        for c in old_chans:
            if c.id not in new_chans:
                try: 
                    await c.delete()
                    await asyncio.sleep(0.3)
                except: pass

        new_cmd = discord.utils.get(ctx.guild.text_channels, name=CMD_CH)
        if new_cmd:
            await new_cmd.send(f"{ctx.author.mention} Saluran dasar server telah berhasil diatur ulang dengan aman (Penyelamatan log aktif).")

    @commands.command()
    async def warn(self, ctx, member: discord.Member, *, reason="Alasan tidak dicantumkan"):
        is_staff = any(r.name in [ROLE_STF, "Admin"] for r in getattr(ctx.author, "roles", []))
        if not (is_staff or ctx.author.id == self.bot.owner_id): return
        
        await ctx.send(f"Peringatan telah diberikan kepada {member.mention}.\n**Keterangan:** {reason}")
        await self._log_mod(ctx.guild, "Tindakan Moderasi: Peringatan", f"**Pengguna:** {member.mention}\n**Oleh:** {ctx.author.mention}\n**Alasan:** {reason}", THEME_COLOR)

    @commands.command()
    async def mute(self, ctx, member: discord.Member, *, reason="Alasan tidak dicantumkan", minutes: int = 10):
        is_staff = any(r.name in [ROLE_STF, "Admin"] for r in getattr(ctx.author, "roles", []))
        if not (is_staff or ctx.author.id == self.bot.owner_id): return
        
        await member.timeout(datetime.now(timezone.utc) + timedelta(minutes=minutes), reason=reason)
        await ctx.send(f"Hak pesan {member.mention} telah dikunci selama {minutes} menit.\n**Keterangan:** {reason}")
        await self._log_mod(ctx.guild, "Tindakan Moderasi: Pembatasan Pesan", f"**Pengguna:** {member.mention}\n**Durasi:** {minutes} Menit\n**Oleh:** {ctx.author.mention}\n**Alasan:** {reason}", THEME_COLOR)

    @commands.command()
    async def kick(self, ctx, member: discord.Member, *, reason="Alasan tidak dicantumkan"):
        is_staff = any(r.name in [ROLE_STF, "Admin"] for r in getattr(ctx.author, "roles", []))
        if not (is_staff or ctx.author.id == self.bot.owner_id): return
        
        await member.kick(reason=reason)
        await ctx.send(f"Akses {member.mention} telah diputus dari server.\n**Keterangan:** {reason}")
        await self._log_mod(ctx.guild, "Tindakan Moderasi: Mengeluarkan Pengguna", f"**Pengguna:** {member.name}\n**Oleh:** {ctx.author.mention}\n**Alasan:** {reason}", THEME_COLOR)

    @commands.command()
    async def ban(self, ctx, member: discord.Member, *, reason="Alasan tidak dicantumkan"):
        is_staff = any(r.name in [ROLE_STF, "Admin"] for r in getattr(ctx.author, "roles", []))
        if not (is_staff or ctx.author.id == self.bot.owner_id): return
        
        await member.ban(reason=reason)
        await ctx.send(f"Akun {member.mention} telah diblokir secara permanen dari server.\n**Keterangan:** {reason}")
        await self._log_mod(ctx.guild, "Tindakan Moderasi: Blokir Permanen", f"**Pengguna:** {member.name}\n**Oleh:** {ctx.author.mention}\n**Alasan:** {reason}", THEME_COLOR)

    @commands.command()
    @commands.is_owner()
    async def update(self, ctx, *, catatan: str = None):
        if not ctx.message.attachments or not ctx.message.attachments[0].filename.endswith('.py'):
            return await ctx.send("Perintah ditolak. Sertakan file .py yang berisi pembaruan kode.", delete_after=5)
        m = await ctx.send("Menerima berkas pembaruan...")
        try:
            # Menggunakan __file__ untuk stabilitas di Termux
            script_path = os.path.abspath(__file__)
            await ctx.message.attachments[0].save(script_path)
            
            with open(UPDATE_FILE, "w") as f:
                f.write(catatan if catatan else "AUTO")
                
            await m.edit(content="Kode berhasil diperbarui. Memulai ulang bot secara paksa...")
            
            # Memulai ulang proses Python
            executable = sys.executable or 'python'
            os.execv(executable, ['python', script_path])
        except Exception as e: 
            await m.edit(content=f"Terjadi kesalahan saat memproses pembaruan: {e}")

    async def process_media(self, ctx, msg, embed, t_b=None, t_n=None, i_b=None, i_n=None):
        m_ch, r_ch = discord.utils.get(ctx.guild.text_channels, name=MEDIA_CH), discord.utils.get(ctx.guild.text_channels, name=RES_CH)
        if not m_ch or not r_ch: return await msg.edit(content="Kesalahan: Saluran hasil pencarian tidak ditemukan.")
        files = [discord.File(b, filename=n) for b, n in [(t_b, t_n), (i_b, i_n)] if b and n]
        if files:
            m_msg = await m_ch.send(content=f"Riwayat Gambar Pencarian: {datetime.now().timestamp()}", files=files)
            for a in m_msg.attachments:
                if t_n and a.filename == t_n: embed.set_thumbnail(url=a.url)
                if i_n and a.filename == i_n: embed.set_image(url=a.url)
        await r_ch.send(embed=embed)
        await msg.edit(content=f"Pencarian selesai. Hasil data dapat dilihat di saluran {r_ch.mention}.")

    @commands.command(aliases=['profile'])
    @commands.is_owner()
    async def profil(self, ctx, target: str = None):
        if ctx.channel.name != CMD_CH: return
        if not target or not target.isdigit(): return await ctx.send("Perintah gagal. Pastikan target menggunakan angka ID pengguna.", delete_after=5)
        m = await ctx.send("Mengambil data informasi profil Discord...")
        try: user = await ctx.guild.fetch_member(int(target))
        except:
            try: user = await self.bot.fetch_user(int(target))
            except: return await m.edit(content="Data tidak ditemukan: Pengguna tersebut tidak ada di Discord.")

        c_dt = user.created_at
        fields = [
            ("Informasi Utama", f"**Nama Akun:** {user.name}\n**Nama Tampilan:** {user.global_name or 'Kosong'}\n**ID Angka:** {user.id}", True),
            ("Variabel Akun", f"**Tipe:** {'Bot / Aplikasi' if user.bot else 'Pengguna Manusia'}\n**Warna Tema:** {f'#{user.accent_color.value:06x}'.upper() if user.accent_color else 'Warna Bawaan'}", True),
            ("Jejak Pengguna", f"Memiliki **{len(user.mutual_guilds)}** kesamaan server Discord" if hasattr(user, 'mutual_guilds') else "Informasi server disembunyikan", True)
        ]

        if isinstance(user, discord.Member):
            act = "Kosong"
            if user.activity:
                act = user.activity.name
                if user.activity.type.name in ["playing", "listening", "watching", "streaming"]: 
                    act = f"{user.activity.type.name.title()} {act}"
            
            status_dict = {"online": "Online", "idle": "Tidak di Layar", "dnd": "Mode Senyap"}
            m_status = status_dict.get(str(user.status), "Offline")

            fields.extend([
                ("Aktivitas Berjalan", f"**Status:** {m_status}\n**Sedang Melakukan:** {act}", True),
                ("Data Server Saat Ini", f"**Nama Panggilan:** {user.nick or 'Tidak Diubah'}\n**Peran Tertinggi:** {user.top_role.name if user.top_role else 'Tanpa Peran Khusus'}", True),
                ("Riwayat Gabung", f"**Tingkat Booster:** {discord.utils.format_dt(user.premium_since, 'R') if user.premium_since else 'Tidak Berlangganan'}\n**Waktu Masuk Server:** {discord.utils.format_dt(user.joined_at, 'F') if user.joined_at else 'Data tidak valid'}", False)
            ])

        bgs = [BADGES.get(f.name, f.name.replace('_', ' ').title()) for f in user.public_flags.all()]
        fields.extend([
            ("Label Penghargaan", ", ".join(bgs) if bgs else "Tidak memiliki lencana khusus", False), 
            ("Waktu Pembuatan Akun", f"{discord.utils.format_dt(c_dt, 'F')} (Akun aktif sejak {(datetime.now(timezone.utc) - c_dt).days:,} hari yang lalu)", False)
        ])
        
        t_b = await self._fetch(user.avatar.with_size(1024).url, is_json=False) if user.avatar else None
        i_b = await self._fetch(user.banner.with_size(1024).url, is_json=False) if user.banner else None
        t_n = f"av_{user.id}.{'gif' if user.avatar and user.avatar.is_animated() else 'png'}" if t_b else None
        i_n = f"bn_{user.id}.{'gif' if user.banner and user.banner.is_animated() else 'png'}" if i_b else None

        await self.process_media(ctx, m, self._build_embed("Informasi Akun Discord", None, THEME_COLOR, fields), t_b, t_n, i_b, i_n)

    @commands.command()
    @commands.is_owner()
    async def github(self, ctx, target: str = None):
        if ctx.channel.name != CMD_CH: return
        if not target: return await ctx.send("Pencarian dibatalkan. Nama pengguna GitHub wajib dilampirkan.", delete_after=5)
        m = await ctx.send("Memulai proses penarikan data dari GitHub...")
        
        reqs = {
            "u": f"https://api.github.com/users/{target}",
            "r": f"https://api.github.com/users/{target}/repos?per_page=100",
            "o": f"https://api.github.com/users/{target}/orgs"
        }
        res = dict(zip(reqs.keys(), await asyncio.gather(*(self._fetch(url) for url in reqs.values()))))
        if not res["u"]: return await m.edit(content="Respon jaringan: Nama pengguna tersebut tidak ditemukan.")

        u, r, o = res["u"], res["r"] or [], res["o"] or []
        orgs = ", ".join([x.get("login") for x in o]) or "Tidak memiliki ikatan grup secara publik"
        c_dt = parse_dt(u['created_at'], "%Y-%m-%dT%H:%M:%SZ")

        fields = [
            ("Informasi Dasar", f"**Nama Akun:** {u.get('login')}\n**Nama Asli:** {u.get('name') or 'Tidak terdaftar'}\n**ID Angka:** {u.get('id')}", True),
            ("Area Sosialisasi", f"**Perusahaan Terkait:** {u.get('company') or 'Pekerja Independen'}\n**Lokasi:** {u.get('location') or 'Data disembunyikan'}\n**Tautan Sosial X:** {u.get('twitter_username') or 'Kosong'}", True),
            ("Riwayat Pekerjaan (Repo)", f"**Proyek Publik:** {u.get('public_repos')} Pustaka\n**Gists:** {u.get('public_gists')}\n**Bintang Diperoleh:** {sum(x.get('stargazers_count', 0) for x in r)}\n**Salinan (Forks):** {sum(x.get('forks_count', 0) for x in r)}", True),
            ("Jaringan Pertemanan", f"**Pengikut:** {u.get('followers')} Orang | **Mengikuti:** {u.get('following')} Orang", True), 
            ("Daftar Organisasi", orgs, False)
        ]
        if u.get('bio'): fields.append(("Catatan Biodata", u.get('bio'), False))
        fields.append(("Waktu Pendaftaran Akun", f"{discord.utils.format_dt(c_dt, 'F')} (Telah aktif sejak {(datetime.now(timezone.utc) - c_dt).days:,} hari terakhir)", False))
        
        if r: 
            top_repos = "\n".join([f"Nilai: {x.get('stargazers_count')} - [{x.get('name')}]({x.get('html_url')})" for x in sorted(r, key=lambda i: i.get('stargazers_count', 0), reverse=True)[:3]])
            fields.append(("Tiga Pustaka Paling Banyak Mendapat Bintang", top_repos or "Belum ada repositori yang menerima bintang", False))

        t_b = await self._fetch(u['avatar_url'], is_json=False) if u.get('avatar_url') else None
        await self.process_media(ctx, m, self._build_embed("Data Profil Akun GitHub", u.get('html_url'), THEME_COLOR, fields), t_b, f"gh_{u.get('login')}.png" if t_b else None, None, None)

    @commands.command()
    @commands.is_owner()
    async def roblox(self, ctx, target: str = None):
        if ctx.channel.name != CMD_CH: return
        if not target: return await ctx.send("Kesalahan argumen. Target Tautan atau ID Angka Roblox harus disertakan.", delete_after=5)
        
        match = ROBLOX_URL_PATTERN.search(target)
        tid = match.group(1) if match else target
        if not tid.isdigit(): return await ctx.send("Kesalahan pencarian. Pastikan Anda memasukkan nomor ID pengguna yang valid.", delete_after=5)
        
        m = await ctx.send("Memulai proses pengumpulan data di platform Roblox...")
        u_data = await self._fetch(f"https://users.roblox.com/v1/users/{tid}")
        if not u_data: return await m.edit(content="Respon kesalahan: Data akun Roblox target telah dihapus atau dikunci.")

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

        p_txt, l_loc, l_on = "Offline", "Posisi disamarkan", "Catatan aktivitas tidak tersedia"
        if r["p"] and r["p"].get("userPresences"):
            pr = r["p"]["userPresences"][0]
            p_typ = pr.get("userPresenceType", 0)
            p_txt = {0:"Offline", 1:"Sedang Online", 2:"Membuka Aplikasi Permainan", 3:"Membuka Roblox Studio"}.get(p_typ, "Offline")
            l_loc = pr.get("lastLocation", "Lokasi disembunyikan")
            if pr.get("lastOnline"): l_on = discord.utils.format_dt(parse_dt(pr["lastOnline"][:19], "%Y-%m-%dT%H:%M:%S"), 'R')

        pg_str = f"{r['pg']['group'].get('name', 'Tanpa Nama')} (Sebagai: {r['pg'].get('role', {}).get('name', 'N/A')})" if r["pg"] and "group" in r["pg"] else "Aktivitas grup utama dibatalkan"
        soc_str = "\n".join([f"**{s['type']}:** {s.get('title', s.get('url'))}" for s in r["soc"]["data"]]) if r["soc"] and r["soc"].get("data") else "Tautan profil publik kosong"
        b_names = [b["name"] for b in r["bdg"]] if r["bdg"] else []
        col_data = r["col"].get("data", []) if r["col"] else []
        
        eq_str, t_rbx, av_typ, av_scl, em_cnt = "Menggunakan pakaian dasar", 0, "Bentukan Statis R6/R15", "Tinggi: 1 | Lebar: 1 | Kepala: 1", 0
        if r["av"]:
            em_cnt = len(r["av"].get("emotes", []))
            av_typ = r["av"].get("playerAvatarType", "Kerangka Dasar")
            sc = r["av"].get("scales", {})
            av_scl = f"Proporsi Tinggi: {sc.get('height', 1)} | Proporsi Lebar: {sc.get('width', 1)} | Ukuran Kepala: {sc.get('head', 1)}"
            assets = r["av"].get("assets", [])
            if assets:
                ga = {}
                for a in assets: ga.setdefault(a.get("assetType", {}).get("name", "Unknown"), []).append(a.get("name", "Unknown"))
                eq_str = "\n".join([f"**{t}:** {', '.join(ns)}" for t, ns in ga.items()])[:1020]
                c_data = await self._fetch("https://catalog.roblox.com/v1/catalog/items/details", "POST", {"items": [{"itemType": "Asset", "id": a["id"]} for a in assets]})
                t_rbx = sum((i.get("price") or 0) for i in c_data.get("data", [])) if c_data else 0

        c_dt = parse_dt(u_data['created'])
        fields = [
            ("Laporan Identitas Akun", f"**Nama Terdaftar:** {u_data.get('name')}\n**Nama Tampilan:** {u_data.get('displayName')}\n**ID Angka:** {tid}\n**Status Lencana (Centang):** {'Sah' if u_data.get('hasVerifiedBadge') else 'Tidak Memiliki Lencana'}", True),
            ("Indikator Aktivitas Terkini", f"**Status Akun:** {p_txt}\n**Terakhir Dilihat Di:** {l_loc[:20]}\n**Jejak Waktu:** {l_on}", True),
            ("Keamanan dan Batasan", f"**Langganan Premium:** {'Menyala' if r['prem'] else 'Mati'}\n**Keadaan Akun:** {'Terblokir (Banned)' if u_data.get('isBanned') else 'Catatan Bersih'}\n**Daftar Penyimpanan Barang:** {'Dapat Dilihat Umum' if r['inv'] and r['inv'].get('canView') else 'Terkunci'}", True),
            ("Informasi Aset dan Kekayaan", f"**Total Estimasi Barang:** {sum(i.get('recentAveragePrice', 0) for i in col_data):,} R$\n**Barang Edisi Langka:** {len(col_data)} Tersimpan\n**Harga Kostum Saat Ini:** {t_rbx:,} R$\n**Kostum Tersimpan:** {r['out'].get('total', 0) if r['out'] else 0} Setelan", True),
            ("Proporsi Visual Karakter", f"**Kerangka Dasar:** {av_typ}\n**Dimensi Tubuh:** {av_scl}\n**Total Gaya Emosi:** {em_cnt} Dipasang", True),
            ("Relasi Lingkaran Pertemanan", f"**Jumlah Teman:** {r['f'].get('count', 0) if r['f'] else 0:,} Orang\n**Jumlah Pengikut:** {r['fol'].get('count', 0) if r['fol'] else 0:,} Orang\n**Akun yang Diikuti:** {r['fng'].get('count', 0) if r['fng'] else 0:,} Akun", True),
            ("Pencapaian Permainan", f"**Penghargaan Resmi Platform:** {len(b_names)} Berkas\n**Penghargaan Dalam Game:** {len(r['gb'].get('data', [])) if r['gb'] else 0}{'+' if r['gb'] and r['gb'].get('nextPageCursor') else ''} Terselesaikan", True),
            ("Skala Interaksi Permainan", f"**Jumlah Grup Diikuti:** {len(r['g'].get('data', [])) if r['g'] else 0:,} Faksi\n**Pembuatan Permainan Sendiri:** {len(r['gm'].get('data', [])) if r['gm'] else 0:,} Game\n**Permainan yang Disukai:** {len(r['fav'].get('data', [])) if r['fav'] else 0:,} Judul", True),
            ("Grup Prioritas Akun", pg_str, True), ("Tautan Platform Luar", soc_str[:1024], False), ("Daftar Item Pakaian yang Dipakai", eq_str, False),
            ("Catatan Perolehan Lencana Resmi", ", ".join(b_names)[:1024] or "Belum ada lencana dari pihak pusat", False), ("Catatan Perubahan Nama Masa Lalu", ", ".join([n["name"] for n in r["h"].get("data", [])])[:1024] if r["h"] and r["h"].get("data") else "Tidak ada perubahan nama sejak pendaftaran", False)
        ]
        if u_data.get('description'): fields.append(("Catatan Profil Singkat", u_data.get('description')[:1024], False))
        fields.append(("Jejak Pendaftaran Awal", f"{discord.utils.format_dt(c_dt, 'F')} (Rentang waktu akun ini beroperasi adalah {(datetime.now(timezone.utc) - c_dt).days:,} hari)", False))

        t_b, t_n, i_b, i_n = None, None, None, None
        if r["th"] and r["th"].get("data"):
            t_b, t_n = await self._fetch(r["th"]["data"][0]["imageUrl"], is_json=False), f"rh_{tid}.png"
        if r["tf"] and r["tf"].get("data"):
            i_b, i_n = await self._fetch(r["tf"]["data"][0]["imageUrl"], is_json=False), f"rf_{tid}.png"

        await self.process_media(ctx, m, self._build_embed("Laporan Data Akun Roblox", f"https://www.roblox.com/users/{tid}/profile", THEME_COLOR, fields), t_b, t_n, i_b, i_n)

if __name__ == "__main__":
    bot = MasterBot()
    bot.run(TOKEN)
