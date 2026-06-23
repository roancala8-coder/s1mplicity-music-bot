import os
import sys
import asyncio
import discord
from discord.ext import commands
import wavelink

print("=== MAIN.PY VERSION: v9 - Lavalink Fixed ===")
print("🚀 Script starting...")
print(f"Python version: {sys.version}")

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("❌ DISCORD_TOKEN environment variable not set")

intents = discord.Intents.all()

class MusicBot(commands.Bot):
    async def setup_hook(self):
        # Use Railway env vars, fallback to correct port 8080
        LAVALINK_URI = os.getenv("LAVALINK_URI", "http://discord-music-bot-production-363a.up.railway.app:8080")
        LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD", "youshallnotpass")

        print(f"🔗 Connecting to Lavalink: {LAVALINK_URI}")
        try:
            node = wavelink.Node(
                uri=LAVALINK_URI,
                password=LAVALINK_PASSWORD,
                secure=False  # critical: Lavalink only speaks HTTP
            )
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

# Run the bot
bot.run(TOKEN)
