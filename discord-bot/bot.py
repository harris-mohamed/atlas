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

# Create bot instance
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)


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

    # Only process messages that start with the command prefix
    if not message.content.startswith(COMMAND_PREFIX):
        return

    # Extract the command and content
    # Remove the prefix to get the actual message content
    content = message.content[len(COMMAND_PREFIX):].strip()

    # If there's no content after the prefix, ignore
    if not content:
        return

    logger.info(f'Processing message from {message.author.name}: {content}')

    # Prepare webhook payload
    payload = {
        'message': content,
        'author': str(message.author.name),
        'author_id': str(message.author.id),
        'channel': str(message.channel.name) if hasattr(message.channel, 'name') else 'DM',
        'channel_id': str(message.channel.id),
        'timestamp': message.created_at.isoformat(),
        'guild': str(message.guild.name) if message.guild else None,
        'guild_id': str(message.guild.id) if message.guild else None
    }

    try:
        # Send webhook to n8n
        response = requests.post(
            N8N_WEBHOOK_URL,
            json=payload,
            timeout=10
        )
        response.raise_for_status()

        logger.info(f'Successfully sent webhook to n8n (status: {response.status_code})')

        # Optional: React to the message to show it was processed
        await message.add_reaction('✅')

    except requests.exceptions.RequestException as e:
        logger.error(f'Failed to send webhook to n8n: {e}')
        # React with error emoji
        await message.add_reaction('❌')

    # Process commands (if any are defined)
    await bot.process_commands(message)


@bot.command(name='ping')
async def ping(ctx):
    """Test command to check if bot is responsive"""
    await ctx.send(f'Pong! Latency: {round(bot.latency * 1000)}ms')


@bot.command(name='help')
async def help_command(ctx):
    """Display help information"""
    help_text = f"""
**ATLAS Discord Bot**

I forward your messages to n8n for processing!

**Usage:**
- Start your message with `{COMMAND_PREFIX}` followed by your text
- Example: `{COMMAND_PREFIX}remind me to check email tomorrow`

**Commands:**
- `{COMMAND_PREFIX}ping` - Check bot responsiveness
- `{COMMAND_PREFIX}help` - Show this help message

Your messages will be processed and sent to the n8n workflow.
    """
    await ctx.send(help_text)


@bot.event
async def on_command_error(ctx, error):
    """Handle command errors"""
    if isinstance(error, commands.CommandNotFound):
        # For unknown commands, still forward to n8n (already handled in on_message)
        pass
    else:
        logger.error(f'Command error: {error}')
        await ctx.send(f'An error occurred: {str(error)}')


if __name__ == '__main__':
    logger.info('Starting Discord bot...')
    bot.run(DISCORD_TOKEN)
