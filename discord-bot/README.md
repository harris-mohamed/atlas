# ATLAS Discord Bot

A Python-based Discord bot that forwards messages from your private Discord server to an n8n webhook for processing.

## Features

- Listens for messages with a configurable command prefix (default: `!`)
- Forwards message content to n8n webhook
- Provides visual feedback with reaction emojis (✅ for success, ❌ for errors)
- Built-in commands: `!ping` and `!help`
- Runs in a lightweight Docker container
- Secure non-root execution

## Prerequisites

- Docker installed on your system
- A Discord account and server
- An n8n instance with a webhook set up

## Setup Instructions

### 1. Create a Discord Bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name (e.g., "ATLAS Bot")
3. Navigate to the "Bot" section in the left sidebar
4. Click "Add Bot" and confirm
5. Under "Privileged Gateway Intents", enable:
   - Message Content Intent (required to read message content)
6. Click "Reset Token" and copy your bot token (save it securely!)

### 2. Invite the Bot to Your Server

1. In the Discord Developer Portal, go to "OAuth2" > "URL Generator"
2. Under "Scopes", select:
   - `bot`
3. Under "Bot Permissions", select:
   - Read Messages/View Channels
   - Send Messages
   - Add Reactions
4. Copy the generated URL and open it in your browser
5. Select your server and authorize the bot

### 3. Set Up n8n Webhook

1. In your n8n instance, create a new workflow
2. Add a "Webhook" node as the trigger
3. Set the HTTP Method to "POST"
4. Copy the webhook URL (e.g., `https://your-n8n-instance.com/webhook/abc123`)
5. Configure your workflow to process the incoming data:
   - The webhook will receive JSON with fields: `message`, `author`, `author_id`, `channel`, `channel_id`, `timestamp`, `guild`, `guild_id`

### 4. Configure the Bot

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and fill in your credentials:
   ```env
   DISCORD_TOKEN=your_actual_bot_token_here
   N8N_WEBHOOK_URL=https://your-n8n-instance.com/webhook/your-webhook-id
   COMMAND_PREFIX=!
   ```

3. Save the file

### 5. Build and Run with Docker

#### Build the Docker image:
```bash
docker build -t atlas-discord-bot .
```

#### Run the container:
```bash
docker run -d \
  --name atlas-discord-bot \
  --restart unless-stopped \
  --env-file .env \
  atlas-discord-bot
```

#### View logs:
```bash
docker logs -f atlas-discord-bot
```

#### Stop the bot:
```bash
docker stop atlas-discord-bot
```

#### Remove the container:
```bash
docker rm atlas-discord-bot
```

## Usage

Once the bot is running and online in your Discord server:

1. Send a message starting with the command prefix (default: `!`)
2. Example: `!remind me to check email tomorrow`
3. The bot will:
   - Process your message
   - Send it to your n8n webhook
   - React with ✅ if successful, or ❌ if there's an error

### Built-in Commands

- `!ping` - Check if the bot is responsive and see latency
- `!help` - Display help information about the bot

## Webhook Payload Structure

The bot sends the following JSON structure to your n8n webhook:

```json
{
  "message": "the actual message content (without prefix)",
  "author": "Discord username",
  "author_id": "Discord user ID",
  "channel": "Channel name",
  "channel_id": "Channel ID",
  "timestamp": "ISO 8601 timestamp",
  "guild": "Server name",
  "guild_id": "Server ID"
}
```

## Troubleshooting

### Bot doesn't respond to messages

1. Check that Message Content Intent is enabled in the Discord Developer Portal
2. Verify the bot has permission to read messages in your channel
3. Make sure you're using the correct command prefix
4. Check the bot logs: `docker logs atlas-discord-bot`

### Webhook errors (❌ reaction)

1. Verify your N8N_WEBHOOK_URL is correct
2. Check that your n8n instance is accessible
3. Check the bot logs for specific error messages

### Bot keeps restarting

1. Check logs: `docker logs atlas-discord-bot`
2. Verify your DISCORD_TOKEN is valid
3. Ensure all required environment variables are set

## Development

### Run locally without Docker:

```bash
# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the bot
python bot.py
```

## Security Notes

- Never commit your `.env` file to version control (it's in `.gitignore`)
- Keep your Discord bot token secret
- The Docker container runs as a non-root user for security
- Consider using Docker secrets or a secrets manager for production deployments

## Future Enhancements

- Integration with Anthropic API via n8n for AI-powered responses
- Support for slash commands
- Message history and context tracking
- Multi-server support
- Custom command handlers

## License

This bot is part of the ATLAS virtual assistant project.
