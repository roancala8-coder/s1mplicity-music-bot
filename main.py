import os
import discord
from discord.ext import commands
import wavelink
import asyncio

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("DISCORD_TOKEN environment variable not set")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# Lavalink connection info
LAVALINK_URI = os.getenv("LAVALINK_URI", "http://localhost:2333")
LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD", "youshallnotpass")

@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")
    try:
        await bot.tree.sync()
        print("✅ Commands synced")
    except Exception as e:
        print(f"❌ Sync failed: {e}")

@bot.event
async def setup_hook():
    print("🔄 Setting up Lavalink connection...")
    print(f"🔗 LAVALINK_URI: {LAVALINK_URI}")
    print(f"🔑 LAVALINK_PASSWORD: {'*' * len(LAVALINK_PASSWORD)}")
    
    try:
        node = wavelink.Node(
            uri=LAVALINK_URI,
            password=LAVALINK_PASSWORD,
            timeout=30
        )
        await wavelink.Pool.connect(client=bot, nodes=[node])
        print("🔊 Connected to Lavalink")
    except Exception as e:
        print(f"❌ Failed to connect to Lavalink: {e}")

@bot.tree.command(name="join", description="Join your voice channel")
async def slash_join(interaction: discord.Interaction):
    if not interaction.user.voice:
        await interaction.response.send_message("❌ You need to be in a voice channel!", ephemeral=True)
        return
    
    if interaction.guild.voice_client:
        await interaction.response.send_message("❌ Already in a voice channel!", ephemeral=True)
        return
    
    try:
        await interaction.user.voice.channel.connect(cls=wavelink.Player)
        await interaction.response.send_message(f"✅ Joined **{interaction.user.voice.channel.name}**")
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to join: {str(e)}", ephemeral=True)

@bot.tree.command(name="play", description="Play a song from YouTube")
async def slash_play(interaction: discord.Interaction, query: str):
    await interaction.response.defer(thinking=True)
    
    if not interaction.user.voice:
        await interaction.followup.send("❌ You need to be in a voice channel!")
        return
    
    vc = interaction.guild.voice_client
    if not vc:
        try:
            vc = await interaction.user.voice.channel.connect(cls=wavelink.Player)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to connect: {str(e)}")
            return
    
    try:
        tracks = await wavelink.Playable.search(query, source="youtube")
        if not tracks:
            await interaction.followup.send("❌ No tracks found!")
            return
        
        track = tracks[0] if not isinstance(tracks, list) else tracks[0]
        await vc.play(track)
        await interaction.followup.send(f"▶️ Now playing: **{track.title}**")
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

@bot.tree.command(name="skip", description="Skip current song")
async def slash_skip(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.current:
        await vc.stop()
        await interaction.response.send_message("⏭️ Skipped!")
    else:
        await interaction.response.send_message("❌ Nothing to skip", ephemeral=True)

@bot.tree.command(name="pause", description="Pause current song")
async def slash_pause(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.current and not vc.paused:
        await vc.pause()
        await interaction.response.send_message("⏸️ Paused")
    else:
        await interaction.response.send_message("❌ Nothing to pause", ephemeral=True)

@bot.tree.command(name="resume", description="Resume current song")
async def slash_resume(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.current and vc.paused:
        await vc.resume()
        await interaction.response.send_message("▶️ Resumed")
    else:
        await interaction.response.send_message("❌ Nothing to resume", ephemeral=True)

@bot.tree.command(name="stop", description="Stop playback and clear queue")
async def slash_stop(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc:
        await vc.stop()
        await vc.disconnect()
        await interaction.response.send_message("⏹️ Stopped and disconnected")
    else:
        await interaction.response.send_message("❌ Not in voice", ephemeral=True)

@bot.tree.command(name="leave", description="Leave voice channel")
async def slash_leave(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc:
        await vc.disconnect()
        await interaction.response.send_message("👋 Left voice channel")
    else:
        await interaction.response.send_message("❌ Not in voice", ephemeral=True)

@bot.tree.command(name="volume", description="Set volume (0-100)")
async def slash_volume(interaction: discord.Interaction, level: int):
    if level < 0 or level > 100:
        await interaction.response.send_message("❌ Volume must be between 0 and 100", ephemeral=True)
        return
    
    vc = interaction.guild.voice_client
    if vc and vc.current:
        await vc.set_volume(level)
        await interaction.response.send_message(f"🔊 Volume set to {level}%")
    else:
        await interaction.response.send_message("❌ Nothing playing", ephemeral=True)

@bot.tree.command(name="nowplaying", description="Show current song")
async def slash_nowplaying(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.current:
        track = vc.current
        embed = discord.Embed(
            title="🎵 Now Playing",
            description=f"**{track.title}**",
            color=discord.Color.blue()
        )
        embed.add_field(name="Duration", value=f"{int(track.length / 60)}:{int(track.length % 60):02d}")
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("❌ Nothing playing", ephemeral=True)

bot.run(TOKEN)