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

TOKEN = "MTQ3MTU2NTczNDkzNjA1MTg2Ng.GguDDb.k4CSMDcRrvwS82jn0z64HnW9xLvRRTdHj0eU4s"
OWNER_ID = 1463723091489194150
VERSION = "v1.5.0"

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
            return await interaction.response.send_message("Sistem error: Role Member tidak ditemukan.", ephemeral=True)
        if role in interaction.user.roles:
            await interaction.response.send_message("Kamu sudah memiliki akses. Tidak perlu verifikasi ulang.", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("Verifikasi berhasil! Akses ke semua channel sudah dibuka.", ephemeral=True)

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

        await ctx.send("Ada sedikit error di sistem. Laporan lengkap udah dikirim ke DM Owner.", delete_after=5)
        
        owner = await self.bot.fetch_user(self.bot.owner_id)
        if owner:
            tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
            e = discord.Embed(title="Log Error Sistem", color=0xFF0000, timestamp=datetime.now(timezone.utc))
            e.add_field(name="Command", value=ctx.command.name if ctx.command else "Unknown", inline=True)
            e.add_field(name="Channel", value=ctx.channel.name, inline=True)
            
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
        await self._log_mod(message.guild, "Pesan Dihapus", f"**Oleh:** {message.author.mention}\n**Di Channel:** {message.channel.mention}\n**Isi Pesan:** {message.content[:3000]}", 0xFF0000)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot or before.content == after.content: return
        e = discord.Embed(title="Pesan Diedit", description=f"**Oleh:** {before.author.mention}\n**Di Channel:** {before.channel.mention}", color=0xFFFF00, timestamp=datetime.now(timezone.utc))
        e.add_field(name="Sebelumnya", value=before.content[:1024] or "Kosong", inline=False)
        e.add_field(name="Menjadi", value=after.content[:1024] or "Kosong", inline=False)
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
            return await ctx.send("Jangan lupa masukin teks atau gambar buat pengumumannya.", delete_after=5)

        ann_ch = discord.utils.get(ctx.guild.text_channels, name="announcements")
        if not ann_ch:
            return await ctx.send("Channel announcements nggak ketemu. Coba bikin atau jalankan !setup lagi.", delete_after=5)

        try: await ctx.message.delete()
        except: pass
        
        content = "@everyone\n\n"
        if pesan:
            content += f"{pesan}\n\n"
        content += f"— *Pengumuman dari: {ctx.author.name}*"

        files = [await att.to_file() for att in ctx.message.attachments]
        
        await ann_ch.send(content=content, files=files)
        
        if ctx.channel != ann_ch:
            await ctx.send(f"Sip, pengumuman udah berhasil dikirim ke {ann_ch.mention}.", delete_after=3)

    @commands.command()
    async def help(self, ctx):
        is_staff = any(r.name in [ROLE_STF, "Admin"] for r in getattr(ctx.author, "roles", []))
        if not (is_staff or ctx.author.id == self.bot.owner_id): return
        if ctx.channel.name != CMD_CH: return
        
        fields = [
            ("!profil [User ID]", "Cek detail akun Discord seseorang.", False),
            ("!roblox https://support.google.com/google-ads/answer/9004360?hl=id", "Tarik semua data dari akun Roblox target.", False),
            ("!github [Username]", "Intip repositori dan profil GitHub seseorang.", False),
            ("!announce [Teks/Gambar]", "Kirim pengumuman resmi ke channel announcements (Khusus Staff/Owner).", False),
            ("!ping", "Cek kecepatan respon bot.", False),
            ("!stats", "Lihat spesifikasi server yang nge-host bot ini.", False),
            ("!setup", "Bangun ulang struktur kategori & channel server (Wipe & Rebuild).", False),
            ("!update", "Timpa script bot secara langsung via upload file.", False),
            ("!warn, !mute, !kick, !ban", "Command untuk moderasi member.", False)
        ]
        
        e = self._build_embed("Daftar Command Bot", None, discord.Color.dark_gray(), fields, "Berikut adalah fitur-fitur yang bisa dipakai:")
        await ctx.send(embed=e)

    @commands.command()
    @commands.is_owner()
    async def ping(self, ctx):
        if ctx.channel.name != CMD_CH: return
        start = time.time()
        msg = await ctx.send("Mengecek koneksi...")
        end = time.time()
        
        api_ms = round((end - start) * 1000)
        ws_ms = round(self.bot.latency * 1000)
        
        e = discord.Embed(title="Koneksi Sistem", color=0x2b2d31)
        e.add_field(name="Websocket", value=f"`{ws_ms}ms`", inline=True)
        e.add_field(name="API Latency", value=f"`{api_ms}ms`", inline=True)
        await msg.edit(content=None, embed=e)

    @commands.command()
    @commands.is_owner()
    async def stats(self, ctx):
        if ctx.channel.name != CMD_CH: return
        e = discord.Embed(title="Informasi Mesin & Hosting", color=0x2b2d31)
        e.add_field(name="Versi Bot", value=f"`{VERSION}`", inline=True)
        e.add_field(name="Sistem Operasi", value=f"{platform.system()} {platform.release()}", inline=True)
        e.add_field(name="Versi Python", value=platform.python_version(), inline=True)
        e.add_field(name="Library", value=f"Discord.py v{discord.__version__}", inline=True)
        e.add_field(name="Server Ping", value=f"`{round(self.bot.latency * 1000)}ms`", inline=True)
        await ctx.send(embed=e)

    @commands.command()
    @commands.is_owner()
    async def setup(self, ctx):
        m = await ctx.send("Memulai proses pembuatan ulang server...")
        old_chans = list(ctx.guild.channels)
        new_chans = set()
        
        me, ev = ctx.guild.me, ctx.guild.default_role
        
        r_mem = discord.utils.get(ctx.guild.roles, name=ROLE_MEM) or await ctx.guild.create_role(name=ROLE_MEM, reason="Auto Setup")
        r_stf = discord.utils.get(ctx.guild.roles, name=ROLE_STF) or await ctx.guild.create_role(name=ROLE_STF, reason="Auto Setup", permissions=discord.Permissions(manage_messages=True, kick_members=True, ban_members=True))

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
            "**Peraturan Komunitas & Verifikasi Server**\n\n"
            "Untuk menjaga kenyamanan bersama, seluruh anggota wajib mengikuti aturan di bawah ini:\n\n"
            "**1. Sikap & Sopan Santun**\n"
            "Hargai sesama anggota. Segala bentuk toxic berlebihan, pelecehan, diskriminasi, dan ujaran kebencian tidak akan diberi toleransi.\n\n"
            "**2. Ketentuan Chat & Konten**\n"
            "Dilarang melakukan spamming atau tag (mention) massal tanpa alasan yang jelas. Konten yang mengandung unsur pornografi, gore, atau NSFW sangat dilarang keras.\n\n"
            "**3. Larangan Aktivitas Ilegal**\n"
            "Tidak diperbolehkan membahas, membagikan, atau mempromosikan hal-hal yang berkaitan dengan peretasan (hacking), exploit game, atau jual-beli ilegal.\n\n"
            "**4. Keputusan Staff Bersifat Mutlak**\n"
            "Admin dan Staff berhak menindak atau mengeluarkan anggota yang dianggap merusak ekosistem server.\n\n"
            "Klik tombol di bawah ini untuk menyetujui semua peraturan dan mendapatkan akses penuh ke dalam server."
        )
        
        rules_embed = discord.Embed(title="Peraturan Server", description=rules_text, color=0x2b2d31)
        await ch_rules.send(embed=rules_embed, view=VerifyView())

        for c in old_chans:
            if c.id not in new_chans:
                try: 
                    await c.delete()
                    await asyncio.sleep(0.3)
                except: pass

        new_cmd = discord.utils.get(ctx.guild.text_channels, name=CMD_CH)
        if new_cmd:
            await new_cmd.send(f"{ctx.author.mention} Setup otomatis selesai. Channel lama udah dihapus.")

    @commands.command()
    async def warn(self, ctx, member: discord.Member, *, reason="Tidak ada alasan yang diberikan"):
        is_staff = any(r.name in [ROLE_STF, "Admin"] for r in getattr(ctx.author, "roles", []))
        if not (is_staff or ctx.author.id == self.bot.owner_id): return
        
        await ctx.send(f"{member.mention} telah diberikan peringatan.\n**Alasan:** {reason}")
        await self._log_mod(ctx.guild, "Peringatan Diberikan", f"**Target:** {member.mention}\n**Oleh:** {ctx.author.mention}\n**Alasan:** {reason}", 0xFFA500)

    @commands.command()
    async def mute(self, ctx, member: discord.Member, minutes: int, *, reason="Tidak ada alasan yang diberikan"):
        is_staff = any(r.name in [ROLE_STF, "Admin"] for r in getattr(ctx.author, "roles", []))
        if not (is_staff or ctx.author.id == self.bot.owner_id): return
        
        await member.timeout(datetime.now(timezone.utc) + timedelta(minutes=minutes), reason=reason)
        await ctx.send(f"{member.mention} telah di-mute selama {minutes} menit.\n**Alasan:** {reason}")
        await self._log_mod(ctx.guild, "Member Di-mute", f"**Target:** {member.mention}\n**Durasi:** {minutes} Menit\n**Oleh:** {ctx.author.mention}\n**Alasan:** {reason}", 0x808080)

    @commands.command()
    async def kick(self, ctx, member: discord.Member, *, reason="Tidak ada alasan yang diberikan"):
        is_staff = any(r.name in [ROLE_STF, "Admin"] for r in getattr(ctx.author, "roles", []))
        if not (is_staff or ctx.author.id == self.bot.owner_id): return
        
        await member.kick(reason=reason)
        await ctx.send(f"{member.mention} telah dikeluarkan dari server.\n**Alasan:** {reason}")
        await self._log_mod(ctx.guild, "Member Di-kick", f"**Target:** {member.name}\n**Oleh:** {ctx.author.mention}\n**Alasan:** {reason}", 0xFF4500)

    @commands.command()
    async def ban(self, ctx, member: discord.Member, *, reason="Tidak ada alasan yang diberikan"):
        is_staff = any(r.name in [ROLE_STF, "Admin"] for r in getattr(ctx.author, "roles", []))
        if not (is_staff or ctx.author.id == self.bot.owner_id): return
        
        await member.ban(reason=reason)
        await ctx.send(f"{member.mention} telah di-ban permanen.\n**Alasan:** {reason}")
        await self._log_mod(ctx.guild, "Member Di-ban", f"**Target:** {member.name}\n**Oleh:** {ctx.author.mention}\n**Alasan:** {reason}", 0x8B0000)

    @commands.command()
    @commands.is_owner()
    async def update(self, ctx):
        if not ctx.message.attachments or not ctx.message.attachments[0].filename.endswith('.py'):
            return await ctx.send("Format salah. Jangan lupa lampirkan file .py barunya.", delete_after=5)
        m = await ctx.send("Lagi download update script...")
        try:
            await ctx.message.attachments[0].save(os.path.abspath(__file__))
            await m.edit(content="Sip, script berhasil ditimpa. Bot akan restart sekarang...")
            os.execv(sys.executable, ['python'] + sys.argv)
        except Exception as e: await m.edit(content=f"Gagal melakukan update: {e}")

    async def process_media(self, ctx, msg, embed, t_b=None, t_n=None, i_b=None, i_n=None):
        m_ch, r_ch = discord.utils.get(ctx.guild.text_channels, name=MEDIA_CH), discord.utils.get(ctx.guild.text_channels, name=RES_CH)
        if not m_ch or not r_ch: return await msg.edit(content="Error: Channel output tidak ditemukan, coba jalankan !setup lagi.")
        files = [discord.File(b, filename=n) for b, n in [(t_b, t_n), (i_b, i_n)] if b and n]
        if files:
            m_msg = await m_ch.send(content=f"Log Backup Media: {datetime.now().timestamp()}", files=files)
            for a in m_msg.attachments:
                if t_n and a.filename == t_n: embed.set_thumbnail(url=a.url)
                if i_n and a.filename == i_n: embed.set_image(url=a.url)
        await r_ch.send(embed=embed)
        await msg.edit(content=f"Proses selesai. Hasilnya ada di {r_ch.mention}, gambar disimpan di {m_ch.mention}.")

    @commands.command(aliases=['profile'])
    @commands.is_owner()
    async def profil(self, ctx, target: str = None):
        if ctx.channel.name != CMD_CH: return
        if not target or not target.isdigit(): return await ctx.send("Pake User ID Discord yang bentuknya angka ya.", delete_after=5)
        m = await ctx.send("Lagi narik data dari Discord...")
        try: user = await ctx.guild.fetch_member(int(target))
        except:
            try: user = await self.bot.fetch_user(int(target))
            except: return await m.edit(content="Gagal: User ID nggak terdaftar.")

        c_dt = user.created_at
        fields = [
            ("Informasi Akun", f"**Username:** {user.name}\n**Nama Global:** {user.global_name or 'Tidak ada'}\n**User ID:** {user.id}", True),
            ("Detail Profil", f"**Tipe:** {'Akun Bot' if user.bot else 'Pengguna Biasa'}\n**Warna Tema:** {f'#{user.accent_color.value:06x}'.upper() if user.accent_color else 'Bawaan'}", True),
            ("Jaringan", f"Berbagi **{len(user.mutual_guilds)}** Server sama bot ini" if hasattr(user, 'mutual_guilds') else "Tidak kedeteksi", True)
        ]

        if isinstance(user, discord.Member):
            act = user.activity.name if user.activity else "Lagi nggak ngapa-ngapain"
            if user.activity and user.activity.type.name in ["playing", "listening", "watching", "streaming"]: 
                act = f"{user.activity.type.name.title()} {act}"
            
            fields.extend([
                ("Status Kehadiran", f"**Kondisi:** {{'online':'Online', 'idle':'Idle', 'dnd':'DND'}}.get(str(user.status), 'Offline')\n**Aktivitas:** {act}", True),
                ("Keanggotaan Server", f"**Nama Server:** {user.nick or 'Tidak diset'}\n**Role Tertinggi:** {user.top_role.name if user.top_role else 'Tidak ada'}", True),
                ("Dukungan Server", f"**Server Booster:** {discord.utils.format_dt(user.premium_since, 'R') if user.premium_since else 'Bukan Booster'}\n**Masuk Server:** {discord.utils.format_dt(user.joined_at, 'F') if user.joined_at else 'Tidak diketahui'}", False)
            ])

        bgs = [BADGES.get(f.name, f.name.replace('_', ' ').title()) for f in user.public_flags.all()]
        fields.extend([
            ("Lencana (Badges)", ", ".join(bgs) if bgs else "Nggak ada lencana khusus", False), 
            ("Akun Dibuat", f"{discord.utils.format_dt(c_dt, 'F')} (Umur akun {(datetime.now(timezone.utc) - c_dt).days:,} hari)", False)
        ])
        
        t_b = await self._fetch(user.avatar.with_size(1024).url, is_json=False) if user.avatar else None
        i_b = await self._fetch(user.banner.with_size(1024).url, is_json=False) if user.banner else None
        t_n = f"av_{user.id}.{'gif' if user.avatar and user.avatar.is_animated() else 'png'}" if t_b else None
        i_n = f"bn_{user.id}.{'gif' if user.banner and user.banner.is_animated() else 'png'}" if i_b else None

        await self.process_media(ctx, m, self._build_embed("Data Profil Discord", None, user.accent_color or discord.Color.dark_gray(), fields), t_b, t_n, i_b, i_n)

    @commands.command()
    @commands.is_owner()
    async def github(self, ctx, target: str = None):
        if ctx.channel.name != CMD_CH: return
        if not target: return await ctx.send("Jangan lupa masukin username GitHub-nya.", delete_after=5)
        m = await ctx.send("Nyari data di GitHub...")
        
        reqs = {
            "u": f"https://api.github.com/users/{target}",
            "r": f"https://api.github.com/users/{target}/repos?per_page=100",
            "o": f"https://api.github.com/users/{target}/orgs"
        }
        res = dict(zip(reqs.keys(), await asyncio.gather(*(self._fetch(url) for url in reqs.values()))))
        if not res["u"]: return await m.edit(content="Gagal: Username tersebut nggak ada di GitHub.")

        u, r, o = res["u"], res["r"] or [], res["o"] or []
        orgs = ", ".join([x.get("login") for x in o]) or "Tidak join organisasi apapun"
        c_dt = parse_dt(u['created_at'], "%Y-%m-%dT%H:%M:%SZ")

        fields = [
            ("Informasi Dasar", f"**Username:** {u.get('login')}\n**Nama Asli:** {u.get('name') or 'Rahasia'}\n**User ID:** {u.get('id')}", True),
            ("Pekerjaan & Lokasi", f"**Company:** {u.get('company') or '-'}\n**Lokasi:** {u.get('location') or '-'}\n**Twitter/X:** {u.get('twitter_username') or '-'}", True),
            ("Statistik Kode", f"**Repo Publik:** {u.get('public_repos')}\n**Gists:** {u.get('public_gists')}\n**Total Stars:** {sum(x.get('stargazers_count', 0) for x in r)}\n**Total Forks:** {sum(x.get('forks_count', 0) for x in r)}", True),
            ("Koneksi & Jaringan", f"**Followers:** {u.get('followers')} | **Following:** {u.get('following')}", True), 
            ("Daftar Organisasi", orgs, False)
        ]
        if u.get('bio'): fields.append(("Bio", u.get('bio'), False))
        fields.append(("Bergabung di GitHub", f"{discord.utils.format_dt(c_dt, 'F')} (Sejak {(datetime.now(timezone.utc) - c_dt).days:,} hari lalu)", False))
        
        if r: 
            top_repos = "\n".join([f"Stars: {x.get('stargazers_count')} - [{x.get('name')}]({x.get('html_url')})" for x in sorted(r, key=lambda i: i.get('stargazers_count', 0), reverse=True)[:3]])
            fields.append(("Top 3 Repositori", top_repos or "Belum ada repo yang dapet star", False))

        t_b = await self._fetch(u['avatar_url'], is_json=False) if u.get('avatar_url') else None
        await self.process_media(ctx, m, self._build_embed("Data Profil GitHub", u.get('html_url'), discord.Color.dark_gray(), fields), t_b, f"gh_{u.get('login')}.png" if t_b else None, None, None)

    @commands.command()
    @commands.is_owner()
    async def roblox(self, ctx, target: str = None):
        if ctx.channel.name != CMD_CH: return
        if not target: return await ctx.send("Masukin URL atau ID Roblox-nya ya.", delete_after=5)
        tid = re.search(r'users/(\d+)', target).group(1) if "roblox.com" in target else target
        if not tid.isdigit(): return await ctx.send("Kayaknya formatnya salah tuh.", delete_after=5)
        
        m = await ctx.send("Lagi narik banyak data dari Roblox nih...")
        u_data = await self._fetch(f"https://users.roblox.com/v1/users/{tid}")
        if not u_data: return await m.edit(content="Gagal: Akun Roblox itu nggak ada di sistem.")

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

        p_txt, l_loc, l_on = "Offline", "Tidak diketahui", "Tidak diketahui"
        if r["p"] and r["p"].get("userPresences"):
            pr = r["p"]["userPresences"][0]
            p_typ = pr.get("userPresenceType", 0)
            p_txt = {0:"Offline", 1:"Online", 2:"Lagi Main Game", 3:"Buka Roblox Studio"}.get(p_typ, "Offline")
            l_loc = pr.get("lastLocation", "Tidak diketahui")
            if pr.get("lastOnline"): l_on = discord.utils.format_dt(parse_dt(pr["lastOnline"][:19], "%Y-%m-%dT%H:%M:%S"), 'R')

        pg_str = f"{r['pg']['group'].get('name', 'Unknown')} (sebagai {r['pg'].get('role', {}).get('name', 'Member')})" if r["pg"] and "group" in r["pg"] else "Nggak punya grup utama"
        soc_str = "\n".join([f"**{s['type']}:** {s.get('title', s.get('url'))}" for s in r["soc"]["data"]]) if r["soc"] and r["soc"].get("data") else "Tidak menautkan akun apapun"
        b_names = [b["name"] for b in r["bdg"]] if r["bdg"] else []
        col_data = r["col"].get("data", []) if r["col"] else []
        
        eq_str, t_rbx, av_typ, av_scl, em_cnt = "Nggak pakai aksesoris", 0, "Unknown", "H: 1 | W: 1 | Hd: 1", 0
        if r["av"]:
            em_cnt = len(r["av"].get("emotes", []))
            av_typ = r["av"].get("playerAvatarType", "Tidak Spesifik")
            sc = r["av"].get("scales", {})
            av_scl = f"Tinggi: {sc.get('height', 1)} | Lebar: {sc.get('width', 1)} | Kepala: {sc.get('head', 1)}"
            assets = r["av"].get("assets", [])
            if assets:
                ga = {}
                for a in assets: ga.setdefault(a.get("assetType", {}).get("name", "Unknown"), []).append(a.get("name", "Unknown"))
                eq_str = "\n".join([f"**{t}:** {', '.join(ns)}" for t, ns in ga.items()])[:1020]
                c_data = await self._fetch("https://catalog.roblox.com/v1/catalog/items/details", "POST", {"items": [{"itemType": "Asset", "id": a["id"]} for a in assets]})
                t_rbx = sum((i.get("price") or 0) for i in c_data.get("data", [])) if c_data else 0

        c_dt = parse_dt(u_data['created'])
        fields = [
            ("Profil Utama", f"**Username:** {u_data.get('name')}\n**Display:** {u_data.get('displayName')}\n**ID:** {tid}\n**Centang Biru:** {'Ya' if u_data.get('hasVerifiedBadge') else 'Bukan'}", True),
            ("Status & Lokasi", f"**Status:** {p_txt}\n**Lokasi:** {l_loc[:20]}\n**Terakhir Aktif:** {l_on}", True),
            ("Keamanan Akun", f"**Premium:** {'Aktif' if r['prem'] else 'Nggak'}\n**Banned:** {'Kena Ban' if u_data.get('isBanned') else 'Aman'}\n**Inventory:** {'Bisa dilihat publik' if r['inv'] and r['inv'].get('canView') else 'Disembunyikan'}", True),
            ("Kekayaan & Item", f"**RAP (Nilai Barang):** {sum(i.get('recentAveragePrice', 0) for i in col_data):,} R$\n**Koleksi Limited:** {len(col_data)} Item\n**Harga Outfit Dipakai:** {t_rbx:,} R$\n**Outfit Tersimpan:** {r['out'].get('total', 0) if r['out'] else 0} Preset", True),
            ("Detail Avatar", f"**Tipe Model:** {av_typ}\n**Proporsi:** {av_scl}\n**Emote Terpasang:** {em_cnt}", True),
            ("Teman & Sosial", f"**Teman:** {r['f'].get('count', 0) if r['f'] else 0:,}\n**Followers:** {r['fol'].get('count', 0) if r['fol'] else 0:,}\n**Following:** {r['fng'].get('count', 0) if r['fng'] else 0:,}", True),
            ("Pencapaian Akun", f"**Badge Resmi:** {len(b_names)}\n**Badge Dari Game:** {len(r['gb'].get('data', [])) if r['gb'] else 0}{'+' if r['gb'] and r['gb'].get('nextPageCursor') else ''}", True),
            ("Grup & Karya", f"**Grup Diikuti:** {len(r['g'].get('data', [])) if r['g'] else 0:,}\n**Game Buatan Sendiri:** {len(r['gm'].get('data', [])) if r['gm'] else 0:,}\n**Game Favorit:** {len(r['fav'].get('data', [])) if r['fav'] else 0:,}", True),
            ("Grup Utama Terpilih", pg_str, True), ("Tautan Eksternal", soc_str[:1024], False), ("Rincian Item yang Dipakai", eq_str, False),
            ("Koleksi Badge Resmi", ", ".join(b_names)[:1024] or "Nggak punya badge resmi", False), ("Riwayat Username Lama", ", ".join([n["name"] for n in r["h"].get("data", [])])[:1024] if r["h"] and r["h"].get("data") else "Nggak pernah ganti nama", False)
        ]
        if u_data.get('description'): fields.append(("Deskripsi (About)", u_data.get('description')[:1024], False))
        fields.append(("Akun Dibuat", f"{discord.utils.format_dt(c_dt, 'F')} (Umur akun {(datetime.now(timezone.utc) - c_dt).days:,} hari)", False))

        t_b, t_n, i_b, i_n = None, None, None, None
        if r["th"] and r["th"].get("data"):
            t_b, t_n = await self._fetch(r["th"]["data"][0]["imageUrl"], is_json=False), f"rh_{tid}.png"
        if r["tf"] and r["tf"].get("data"):
            i_b, i_n = await self._fetch(r["tf"]["data"][0]["imageUrl"], is_json=False), f"rf_{tid}.png"

        await self.process_media(ctx, m, self._build_embed("Data Analitik Roblox", f"https://www.roblox.com/users/{tid}/profile", discord.Color.dark_gray(), fields), t_b, t_n, i_b, i_n)

if __name__ == "__main__":
    bot = MasterBot()
    bot.run(TOKEN)
