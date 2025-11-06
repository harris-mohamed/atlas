"""
Discord Bot for forwarding messages to n8n webhook
"""

import os
import logging
import requests
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
N8N_WEBHOOK_URL = os.getenv('N8N_WEBHOOK_URL')
COMMAND_PREFIX = os.getenv('COMMAND_PREFIX', '!')

# Validate required environment variables
if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN environment variable is required")
if not N8N_WEBHOOK_URL:
    raise ValueError("N8N_WEBHOOK_URL environment variable is required")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configure intents
intents = discord.Intents.default()
intents.message_content = True  # Required to read message content

# Create bot instance (disable default help command to use custom one)
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents, help_command=None)


@bot.event
async def on_ready():
    """Called when the bot is ready"""
    logger.info(f'Bot logged in as {bot.user.name} (ID: {bot.user.id})')
    logger.info(f'Command prefix: {COMMAND_PREFIX}')
    logger.info(f'Connected to {len(bot.guilds)} guild(s)')
    logger.info('Bot is ready!')


@bot.event
async def on_message(message):
    """Handle incoming messages"""
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return

    # Process commands
    await bot.process_commands(message)


@bot.command(name='ping')
async def ping(ctx):
    """Test command to check if bot is responsive"""
    await ctx.send(f'Pong! Latency: {round(bot.latency * 1000)}ms')


@bot.command(name='schedule')
async def schedule(ctx, *, message: str):
    """Send a scheduling request to n8n for processing"""
    logger.info(f'Schedule command from {ctx.author.name}: {message}')

    # Prepare webhook payload
    payload = {
        'command': 'schedule',
        'message': message,
        'author': str(ctx.author.name),
        'author_id': str(ctx.author.id),
        'channel': str(ctx.channel.name) if hasattr(ctx.channel, 'name') else 'DM',
        'channel_id': str(ctx.channel.id),
        'timestamp': ctx.message.created_at.isoformat(),
        'guild': str(ctx.guild.name) if ctx.guild else None,
        'guild_id': str(ctx.guild.id) if ctx.guild else None
    }

    try:
        # Send webhook to n8n
        response = requests.post(
            N8N_WEBHOOK_URL,
            json=payload,
            timeout=10
        )
        response.raise_for_status()

        logger.info(f'Successfully sent schedule request to n8n (status: {response.status_code})')

        # React to show it was processed successfully
        await ctx.message.add_reaction('✅')
        await ctx.send('📅 Scheduling request sent to ATLAS for processing!')

    except requests.exceptions.RequestException as e:
        logger.error(f'Failed to send webhook to n8n: {e}')
        # React with error emoji
        await ctx.message.add_reaction('❌')
        await ctx.send('❌ Failed to send scheduling request. Please try again later.')

@bot.command(name='help')
async def help_command(ctx):
    """Display help information"""
    help_text = f"""
**ATLAS Discord Bot**

Your personal virtual assistant for scheduling and task management!

**Commands:**
- `{COMMAND_PREFIX}ping` - Check bot responsiveness
- `{COMMAND_PREFIX}schedule <message>` - Send a scheduling request to ATLAS
  - Example: `{COMMAND_PREFIX}schedule meeting with team tomorrow at 2pm`
  - Example: `{COMMAND_PREFIX}schedule remind me to review PRs on Friday`
- `{COMMAND_PREFIX}help` - Show this help message

Only schedule commands are sent to n8n for AI processing.
    """
    await ctx.send(help_text)


@bot.event
async def on_command_error(ctx, error):
    """Handle command errors"""
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(f'Unknown command. Use `{COMMAND_PREFIX}help` to see available commands.')
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f'Missing required argument. Use `{COMMAND_PREFIX}help` for usage examples.')
    else:
        logger.error(f'Command error: {error}')
        await ctx.send(f'An error occurred: {str(error)}')


if __name__ == '__main__':
    logger.info('Starting Discord bot...')
    bot.run(DISCORD_TOKEN)
