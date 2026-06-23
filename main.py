import os
import sys
import asyncio
import discord
from discord.ext import commands
import wavelink

print("=== MAIN.PY VERSION: v7 - Lavalink SetupHook ===")
print("🚀 Script starting...")
print(f"Python version: {sys.version}")

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("❌ DISCORD_TOKEN environment variable not set")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

LAVALINK_URI = os.getenv("LAVALINK_URI", "http://discord-music-bot-production-363a.up.railway.app:2333")
LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD", "youshallnotpass")

class MusicBot(commands.Bot):
    async def setup_hook(self):
        print(f"🔗 Connecting to Lavalink: {LAVALINK_URI}")
        node = wavelink.Node(
            uri=LAVALINK_URI,
            password=LAVALINK_PASSWORD,
            secure=False
        )
        try:
            await wavelink.Pool.connect(client=self, nodes=[node])
            print("🎉 Lavalink connected successfully!")
        except Exception as e:
            print(f"❌ Lavalink connection failed: {e}")

bot = MusicBot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")
    try:
        await bot.tree.sync()
        print("✅ Slash commands synced")
    except Exception as e:
        print(f"❌ Sync failed: {e}")

@bot.tree.command(name="status", description="Check bot and Lavalink status")
async def slash_status(interaction: discord.Interaction):
    status = "✅ Bot is running\n"
    try:
        if len(wavelink.Pool.nodes) > 0:
            status += "🔊 Lavalink Connected"
        else:
            status += "❌ Lavalink Not Connected"
    except:
        status += "❌ Lavalink Check Failed"
    await interaction.response.send_message(status, ephemeral=True)

@bot.tree.command(name="join", description="Join your voice channel")
async def slash_join(interaction: discord.Interaction):
    if not interaction.user.voice:
        await interaction.response.send_message("❌ You need to be in a voice channel!", ephemeral=True)
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
        vc = await interaction.user.voice.channel.connect(cls=wavelink.Player)
    try:
        tracks = await wavelink.Playable.search(query, source="youtube")
        if not tracks:
            await interaction.followup.send("❌ No tracks found!")
            return
        track = tracks[0]
        await vc.play(track)
        await interaction.followup.send(f"▶️ Now playing: **{track.title}**")
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

bot.run(TOKEN)
