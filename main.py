import os
import discord
from discord.ext import commands
import wavelink
import asyncio
import sys
import aiohttp

print("=== MAIN.PY VERSION: v6 - Lavalink with Test Command ===")
print("🚀 Script starting...")
print(f"Python version: {sys.version}")

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    print("❌ DISCORD_TOKEN not found!")
    raise ValueError("DISCORD_TOKEN environment variable not set")

print("✅ DISCORD_TOKEN loaded")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

LAVALINK_URI = os.getenv("LAVALINK_URI", "http://discord-music-bot.railway.internal:2333")
LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD", "youshallnotpass")

print(f"🔗 LAVALINK_URI = {LAVALINK_URI}")
print(f"🔑 Password length = {len(LAVALINK_PASSWORD)}")

@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")
    try:
        await bot.tree.sync()
        print("✅ Commands synced")
    except Exception as e:
        print(f"❌ Sync failed: {e}")

    # Connect to Lavalink
    print("🔄 Connecting to Lavalink from on_ready...")
    retries = 0
    max_retries = 10
    while retries < max_retries:
        try:
            node = wavelink.Node(
                uri=LAVALINK_URI,
                password=LAVALINK_PASSWORD,
                secure=False,
                timeout=30
            )
            await wavelink.Pool.connect(client=bot, nodes=[node])
            print("🎉 Successfully connected to Lavalink!")
            break
        except Exception as e:
            retries += 1
            print(f"❌ Attempt {retries}/{max_retries} failed: {type(e).__name__} - {e}")
            await asyncio.sleep(5)
    else:
        print("❌ Failed to connect to Lavalink after all retries.")

@bot.command(name="testlavalink")
async def test_lavalink(ctx):
    """Test Lavalink connection"""
    await ctx.send(f"🔗 Trying to connect to: {LAVALINK_URI}")
    await ctx.send(f"🔑 Password: {'*' * len(LAVALINK_PASSWORD)}")
    
    # Check if wavelink is connected
    try:
        if len(wavelink.Pool.nodes) > 0:
            await ctx.send("✅ Wavelink Pool has nodes connected!")
        else:
            await ctx.send("❌ Wavelink Pool has NO nodes connected")
    except Exception as e:
        await ctx.send(f"❌ Wavelink check failed: {e}")
    
    # Try to ping Lavalink with authentication
    try:
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": LAVALINK_PASSWORD}
            url = f"{LAVALINK_URI}/version"
            await ctx.send(f"🌐 Testing HTTP connection to: {url}")
            try:
                async with session.get(url, headers=headers, timeout=5) as resp:
                    if resp.status == 200:
                        version = await resp.text()
                        await ctx.send(f"✅ Lavalink is reachable! Version: {version[:50]}")
                    else:
                        await ctx.send(f"❌ Lavalink returned status: {resp.status}")
            except aiohttp.ClientConnectorError:
                await ctx.send(f"❌ Cannot connect to {url} - Host unreachable")
            except aiohttp.ClientResponseError as e:
                await ctx.send(f"❌ HTTP Error: {e}")
            except Exception as e:
                await ctx.send(f"❌ Connection error: {type(e).__name__} - {e}")
    except Exception as e:
        await ctx.send(f"❌ Session error: {e}")

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
        track = tracks[0]
        await vc.play(track)
        await interaction.followup.send(f"▶️ Now playing: **{track.title}**")
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

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

bot.run(TOKEN)