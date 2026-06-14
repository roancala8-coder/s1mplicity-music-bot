import os
import sys
import discord
from discord.ext import commands, tasks
from discord import app_commands
import yt_dlp
import asyncio
import time
import shutil
import tempfile
import subprocess
import threading

# ============================================================
# START PO TOKEN PROVIDER (runs in background)
# ============================================================

def start_token_provider():
    try:
        # Kill any existing provider process
        subprocess.Popen("pkill -f bgutil-ytdlp-pot-provider", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)
        # Start new provider
        subprocess.Popen(["bgutil-ytdlp-pot-provider"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(3)
        print("[PO-TOKEN] ✅ Provider started successfully")
    except Exception as e:
        print(f"[PO-TOKEN] ❌ Failed to start provider: {e}")

threading.Thread(target=start_token_provider, daemon=True).start()

# ============================================================
# CONFIGURATION - FFMPEG AUTO-DETECTION
# ============================================================

def find_ffmpeg():
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    
    common_paths = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        os.path.expanduser(r"~\ffmpeg\bin\ffmpeg.exe")
    ]
    
    for path in common_paths:
        if os.path.exists(path):
            return path
    
    return "ffmpeg"

FFMPEG_PATH = os.getenv("FFMPEG_PATH", find_ffmpeg())
print(f"[CONFIG] FFmpeg path: {FFMPEG_PATH}")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

CYBERPUNK_COLOR = discord.Color.from_rgb(90, 20, 160)

# ============================================================
# COOKIE CONFIGURATION - RAILWAY FRIENDLY
# ============================================================

BOT_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = None

cookies_content = os.getenv("COOKIES_CONTENT")
if cookies_content and len(cookies_content) > 500:
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write(cookies_content)
        COOKIE_FILE = f.name
    print(f"[CONFIG] ✅ Using cookies from COOKIES_CONTENT env var ({len(cookies_content)} bytes)")
elif os.path.exists(os.path.join(BOT_DIR, "cookies.txt")):
    COOKIE_FILE = os.path.join(BOT_DIR, "cookies.txt")
    print(f"[CONFIG] ✅ Using cookies from local file: {COOKIE_FILE}")
    print(f"[CONFIG] Cookie size: {os.path.getsize(COOKIE_FILE)} bytes")
else:
    print(f"[CONFIG] ⚠️ No cookies found! Age-restricted videos will fail.")

# ============================================================
# IGNORE PREFIX COMMANDS
# ============================================================

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    raise error

@bot.event
async def on_message(message):
    if message.content.startswith("!"):
        return
    await bot.process_commands(message)

# ============================================================
# MUSIC STATE
# ============================================================
class MusicPlayer:
    def __init__(self, guild_id: int):
        self.guild_id = guild_id
        self.queue = []
        self.current = None
        self.audio_url = None
        self.loop = False
        self.is_paused = False
        self.start_time = None
        self.duration = None
        self.message = None
        self.volume = 1.0

    def toggle_loop(self):
        self.loop = not self.loop
        return self.loop

music_players: dict[int, MusicPlayer] = {}

def get_player(guild: discord.Guild) -> MusicPlayer:
    if guild.id not in music_players:
        music_players[guild.id] = MusicPlayer(guild.id)
    return music_players[guild.id]

# ============================================================
# PROGRESS BAR
# ============================================================
def make_progress_bar(current: float, total: float, length: int = 20):
    if total <= 0:
        return "▱" * length
    ratio = min(1.0, current / total)
    filled = int(round(ratio * length))
    if total - current < 0.5 and filled < length:
        filled = length
    empty = length - filled
    return "▰" * filled + "▱" * empty

# ============================================================
# MUSIC CONTROL VIEW
# ============================================================
class MusicControlView(discord.ui.View):
    def __init__(self, player: MusicPlayer, timeout: float | None = 300):
        super().__init__(timeout=timeout)
        self.player = player

    async def _get_vc(self, interaction: discord.Interaction):
        return interaction.guild.voice_client if interaction.guild else None

    @discord.ui.button(emoji="⏯️", style=discord.ButtonStyle.blurple)
    async def play_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = await self._get_vc(interaction)
        if not vc:
            return await interaction.response.send_message("I'm not in a voice channel.", ephemeral=True)
        if vc.is_playing():
            vc.pause()
            self.player.is_paused = True
            await interaction.response.send_message("⏸ Paused.", ephemeral=True)
        else:
            vc.resume()
            self.player.is_paused = False
            await interaction.response.send_message("▶️ Resumed.", ephemeral=True)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.primary)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = await self._get_vc(interaction)
        if not vc or not vc.is_playing():
            return await interaction.response.send_message("Nothing to skip.", ephemeral=True)
        vc.stop()
        await interaction.response.send_message("⏭ Skipped.", ephemeral=True)

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.blurple)
    async def loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = self.player.toggle_loop()
        await interaction.response.send_message(f"🔁 Loop {'ON' if state else 'OFF'}", ephemeral=True)

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.red)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = await self._get_vc(interaction)
        if vc:
            if vc.is_playing():
                vc.stop()
            self.player.queue.clear()
            self.player.current = None
            self.player.audio_url = None
            await interaction.response.send_message("⏹ Stopped and queue cleared.", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing to stop.", ephemeral=True)

    @discord.ui.button(emoji="🔊", style=discord.ButtonStyle.green)
    async def volume_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        new_vol = min(1.0, self.player.volume + 0.1)
        self.player.volume = new_vol
        await interaction.response.send_message(f"🔊 Volume: {int(new_vol * 100)}%", ephemeral=True)

    @discord.ui.button(emoji="🔉", style=discord.ButtonStyle.green)
    async def volume_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        new_vol = max(0.0, self.player.volume - 0.1)
        self.player.volume = new_vol
        await interaction.response.send_message(f"🔉 Volume: {int(new_vol * 100)}%", ephemeral=True)

# ============================================================
# NOW PLAYING EMBED
# ============================================================
def make_now_playing_embed(player: MusicPlayer):
    info = player.current
    if not info:
        return discord.Embed(
            title="S1mplicity — Cyberpunk Player",
            description="Nothing is playing.",
            color=CYBERPUNK_COLOR
        )

    title = info.get("title", "Unknown Title")
    uploader = info.get("uploader", "Unknown Artist")
    thumb = info.get("thumbnail")
    duration = player.duration or 0

    if player.start_time and not player.is_paused:
        elapsed = time.time() - player.start_time
        elapsed = max(0, min(elapsed, duration))
    elif player.start_time:
        elapsed = player.start_time
    else:
        elapsed = 0

    bar = make_progress_bar(elapsed, duration)
    e_m, e_s = divmod(int(elapsed), 60)
    d_m, d_s = divmod(int(duration), 60)

    embed = discord.Embed(
        title="S1mplicity — Cyberpunk Hybrid Player",
        description=f"**{title}**\n*{uploader}*",
        color=CYBERPUNK_COLOR
    )
    embed.add_field(name="Progress", value=f"{bar}\n`{e_m}:{e_s:02d} / {d_m}:{d_s:02d}`", inline=False)
    embed.add_field(name="Loop", value="ON" if player.loop else "OFF", inline=True)
    embed.add_field(name="Queue", value=f"{len(player.queue)} tracks", inline=True)
    embed.add_field(name="Volume", value=f"{int(player.volume * 100)}%", inline=True)
    if thumb:
        embed.set_thumbnail(url=thumb)
    embed.set_footer(text="S1mplicity • Dark Spotify Cyberpunk UI")
    return embed

# ============================================================
# EMBED UPDATER
# ============================================================
@tasks.loop(seconds=3)
async def update_embeds():
    for guild in bot.guilds:
        player = music_players.get(guild.id)
        if not player or not player.message or not player.current:
            continue
        vc = guild.voice_client
        if not vc or (not vc.is_playing() and not player.is_paused):
            continue
        try:
            embed = make_now_playing_embed(player)
            await player.message.edit(embed=embed, view=MusicControlView(player))
        except (discord.NotFound, discord.Forbidden):
            pass
        except Exception as e:
            print(f"Embed update error: {e}")

# ============================================================
# YT-DLP OPTIONS - FIXED PO TOKEN + COOKIES
# ============================================================

def get_ytdl_options():
    opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "extract_flat": False,
        "js_runtimes": {"node": {}},
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        "extractor_args": {
            "youtube": {
                "skip": ["dash"],
                "player_client": ["ios", "android", "web"],
            }
        },
    }
    
    if COOKIE_FILE and os.path.exists(COOKIE_FILE):
        opts["cookiefile"] = COOKIE_FILE
        print(f"[YT-DLP] ✅ Cookies loaded from: {COOKIE_FILE}")
    else:
        print(f"[YT-DLP] ⚠️ No cookies file found")
    
    return opts

def create_source(url: str):
    try:
        ytdl_opts = get_ytdl_options()
        
        with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info is None:
                raise ValueError("Could not extract video info")
            
            if "entries" in info:
                if not info["entries"]:
                    raise ValueError("No results found for that query")
                info = info["entries"][0]
            
            if "url" not in info and "formats" in info:
                for f in info.get("formats", []):
                    if f.get("acodec") != "none" and f.get("vcodec") == "none":
                        info["url"] = f["url"]
                        break
            
            if "url" not in info:
                raise ValueError("Could not extract audio URL")
            
            return info, info["url"]
            
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        if "Sign in to confirm" in error_msg:
            raise RuntimeError("Age-restricted video. Cookies expired. Refresh COOKIES_CONTENT.")
        elif "Video unavailable" in error_msg:
            raise RuntimeError("Video is unavailable")
        elif "Requested format" in error_msg:
            raise RuntimeError("YouTube format error. Try another song.")
        else:
            raise RuntimeError(f"YouTube error: {error_msg[:100]}")
    except Exception as e:
        raise RuntimeError(f"Failed: {str(e)[:100]}")

# ============================================================
# PLAYBACK ENGINE
# ============================================================
async def play_next(guild: discord.Guild):
    vc = guild.voice_client
    if not vc:
        return

    player = get_player(guild)

    if player.loop and player.current and player.audio_url:
        info = player.current
        audio_url = player.audio_url
    else:
        if not player.queue:
            player.current = None
            player.audio_url = None
            player.start_time = None
            player.duration = None
            return

        next_track = player.queue.pop(0)
        info = next_track["info"]
        audio_url = next_track["url"]

    player.current = info
    player.audio_url = audio_url
    player.duration = info.get("duration", 0)
    player.start_time = time.time()
    player.is_paused = False

    ffmpeg_opts = {
        "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        "options": f"-vn -filter:a volume={player.volume}"
    }
    
    try:
        source = discord.FFmpegPCMAudio(audio_url, executable=FFMPEG_PATH, **ffmpeg_opts)
    except Exception as e:
        print(f"FFmpeg error: {e}")
        return

    def after_play(error):
        if error:
            print(f"Playback error: {error}")
        asyncio.run_coroutine_threadsafe(play_next(guild), bot.loop)

    vc.play(source, after=after_play)

    if player.message:
        try:
            await player.message.edit(embed=make_now_playing_embed(player), view=MusicControlView(player))
        except:
            pass

async def start_playback(interaction: discord.Interaction, url: str):
    guild = interaction.guild
    vc = guild.voice_client
    player = get_player(guild)

    try:
        info, audio_url = create_source(url)
    except RuntimeError as e:
        await interaction.followup.send(f"❌ {e}", ephemeral=True)
        return

    if not vc.is_playing() and not player.current:
        player.current = info
        player.audio_url = audio_url
        player.duration = info.get("duration", 0)
        player.start_time = time.time()

        ffmpeg_opts = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": f"-vn -filter:a volume={player.volume}"
        }
        
        try:
            source = discord.FFmpegPCMAudio(audio_url, executable=FFMPEG_PATH, **ffmpeg_opts)
        except Exception as e:
            await interaction.followup.send(f"FFmpeg error: {e}", ephemeral=True)
            return

        def after_play(error):
            if error:
                print(f"Playback error: {error}")
            asyncio.run_coroutine_threadsafe(play_next(guild), bot.loop)

        vc.play(source, after=after_play)

        embed = make_now_playing_embed(player)
        view = MusicControlView(player)
        player.message = await interaction.followup.send(embed=embed, view=view)
    else:
        player.queue.append({"info": info, "url": audio_url})
        queue_pos = len(player.queue)
        await interaction.followup.send(f"✅ Added **{info.get('title', 'Unknown')}** to queue (position {queue_pos})")

# ============================================================
# SLASH COMMANDS
# ============================================================

@bot.tree.command(name="join", description="Join your current voice channel")
async def slash_join(interaction: discord.Interaction):
    if not interaction.user.voice:
        return await interaction.response.send_message("❌ Join a voice channel first.", ephemeral=True)
    channel = interaction.user.voice.channel
    await channel.connect(self_deaf=True)
    await interaction.response.send_message(f"✅ Joined **{channel.name}**.")

@bot.tree.command(name="play", description="Play a song from YouTube")
async def slash_play(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    
    if not interaction.guild.voice_client:
        if not interaction.user.voice:
            await interaction.followup.send("❌ Join a voice channel first.", ephemeral=True)
            return
        await interaction.user.voice.channel.connect(self_deaf=True)
    
    if not query.startswith(("http://", "https://")):
        query = f"ytsearch:{query}"
    
    await start_playback(interaction, query)

@bot.tree.command(name="skip", description="Skip the current song")
async def slash_skip(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if not vc or not vc.is_playing():
        return await interaction.response.send_message("❌ Nothing to skip.", ephemeral=True)
    vc.stop()
    await interaction.response.send_message("⏭ Skipped.")

@bot.tree.command(name="pause", description="Pause the current song")
async def slash_pause(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_playing():
        vc.pause()
        player = get_player(interaction.guild)
        player.is_paused = True
        await interaction.response.send_message("⏸ Paused.")
    else:
        await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)

@bot.tree.command(name="resume", description="Resume the paused song")
async def slash_resume(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_paused():
        vc.resume()
        player = get_player(interaction.guild)
        player.is_paused = False
        await interaction.response.send_message("▶️ Resumed.")
    else:
        await interaction.response.send_message("❌ Music is not paused.", ephemeral=True)

@bot.tree.command(name="loop", description="Toggle loop for current song")
async def slash_loop(interaction: discord.Interaction):
    player = get_player(interaction.guild)
    state = player.toggle_loop()
    await interaction.response.send_message(f"🔁 Loop {'ON' if state else 'OFF'}")

@bot.tree.command(name="stop", description="Stop playback and clear queue")
async def slash_stop(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    player = get_player(interaction.guild)
    if vc:
        vc.stop()
        player.queue.clear()
        player.current = None
        player.audio_url = None
        await interaction.response.send_message("⏹ Stopped and cleared queue.")
    else:
        await interaction.response.send_message("❌ Nothing to stop.", ephemeral=True)

@bot.tree.command(name="queue", description="Show the current music queue")
async def slash_queue(interaction: discord.Interaction):
    player = get_player(interaction.guild)
    if not player.queue and not player.current:
        return await interaction.response.send_message("📭 Queue is empty.", ephemeral=True)
    
    embed = discord.Embed(title="📋 Current Queue", color=CYBERPUNK_COLOR)
    
    if player.current:
        current_title = player.current.get("title", "Unknown")
        embed.add_field(name="🎵 Now Playing", value=current_title, inline=False)
    
    if player.queue:
        tracks_to_show = player.queue[:10]
        queue_text = ""
        for i, track in enumerate(tracks_to_show, start=1):
            info = track["info"]
            title = info.get("title", "Unknown Title")
            if len(title) > 50:
                title = title[:47] + "..."
            queue_text += f"**{i}.** {title}\n"
        embed.add_field(name="📜 Up Next", value=queue_text, inline=False)
        
        if len(player.queue) > 10:
            embed.set_footer(text=f"➕ And {len(player.queue) - 10} more tracks...")
    else:
        embed.add_field(name="📜 Queue", value="Empty", inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="leave", description="Disconnect from voice channel")
async def slash_leave(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if not vc:
        return await interaction.response.send_message("❌ I'm not in a voice channel.", ephemeral=True)
    
    if interaction.guild.id in music_players:
        del music_players[interaction.guild.id]
    
    await vc.disconnect(force=True)
    await interaction.response.send_message("👋 Left the voice channel.")

@bot.tree.command(name="volume", description="Set volume (0-100)")
async def slash_volume(interaction: discord.Interaction, level: int):
    if level < 0 or level > 100:
        return await interaction.response.send_message("❌ Volume must be between 0 and 100.", ephemeral=True)
    
    player = get_player(interaction.guild)
    player.volume = level / 100.0
    await interaction.response.send_message(f"🔊 Volume set to {level}%.")

@bot.tree.command(name="nowplaying", description="Show currently playing song")
async def slash_nowplaying(interaction: discord.Interaction):
    player = get_player(interaction.guild)
    if not player.current:
        return await interaction.response.send_message("❌ Nothing is currently playing.", ephemeral=True)
    
    embed = make_now_playing_embed(player)
    await interaction.response.send_message(embed=embed)

# ============================================================
# ON READY
# ============================================================
@bot.event
async def on_ready():
    for guild in bot.guilds:
        try:
            await bot.tree.sync(guild=guild)
            print(f"✅ Synced commands to: {guild.name}")
        except Exception as e:
            print(f"Failed to sync to {guild.name}: {e}")
    
    update_embeds.start()
    print(f"✅ Bot is online. Logged in as {bot.user}")
    print(f"🎵 FFmpeg path: {FFMPEG_PATH}")
    print(f"✅ Slash commands ready")
    
    if COOKIE_FILE and os.path.exists(COOKIE_FILE):
        print(f"🍪 Cookies loaded")

# ============================================================
# RUN BOT
# ============================================================
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("DISCORD_TOKEN environment variable not set")
bot.run(TOKEN)