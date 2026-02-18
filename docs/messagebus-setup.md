# Message Bus Setup Guide

## Telegram Setup

1. Create a Telegram bot:
   - Open Telegram and search for @BotFather
   - Send `/newbot` and follow instructions
   - Copy the bot token

2. Add to config:
   ```yaml
   # ~/.pickle-bot/config.user.yaml
   messagebus:
     enabled: true
     default_platform: "telegram"
     telegram:
       bot_token: "YOUR_BOT_TOKEN"
       allowed_chat_ids: ["123456789"]  # Optional: whitelist for incoming messages
       default_chat_id: "123456789"     # Optional: target for agent-initiated messages
   ```

3. Start server:
   ```bash
   uv run picklebot server
   ```

4. Test:
   - Open Telegram
   - Find your bot
   - Send a message
   - Verify response

## Discord Setup

1. Create a Discord bot:
   - Go to https://discord.com/developers/applications
   - Click "New Application"
   - Go to "Bot" section
   - Click "Add Bot"
   - Copy the token
   - Enable "Message Content Intent" under "Privileged Gateway Intents"

2. Invite bot to server:
   - Go to "OAuth2" > "URL Generator"
   - Select "bot" scope
   - Select permissions: "Send Messages", "Read Message History"
   - Copy and open the URL

3. Add to config:
   ```yaml
   # ~/.pickle-bot/config.user.yaml
   messagebus:
     enabled: true
     default_platform: "discord"
     discord:
       bot_token: "YOUR_BOT_TOKEN"
       channel_id: "CHANNEL_ID"        # Optional: restrict to specific channel
       allowed_chat_ids: ["123456789"] # Optional: whitelist for incoming messages
       default_chat_id: "123456789"    # Optional: target for agent-initiated messages
   ```

4. Start server and test

## Running Both Platforms

```yaml
messagebus:
  enabled: true
  default_platform: "telegram"  # Cron responses go here
  telegram:
    bot_token: "TELEGRAM_TOKEN"
    allowed_chat_ids: ["123456789"]
    default_chat_id: "123456789"
  discord:
    bot_token: "DISCORD_TOKEN"
    allowed_chat_ids: []
    default_chat_id: ""
```

Both platforms will send messages to the same shared session.
