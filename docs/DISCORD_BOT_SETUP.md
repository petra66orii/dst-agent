# 🤖 Discord Trading Bot Setup Guide

## Step 1: Create a Discord Application & Bot

1. **Go to Discord Developer Portal**

   - Visit: https://discord.com/developers/applications
   - Click "New Application"
   - Name it "Trading Analysis Bot" (or whatever you prefer)

2. **Create the Bot**

   - Go to the "Bot" section in the left sidebar
   - Click "Add Bot"
   - Under "Token" section, click "Copy" to get your bot token
   - **Important:** Keep this token secret!

3. **Configure Bot Settings**

   - **Public Bot:** Turn ON (required for OAuth2 URL generation)
   - **Require OAuth2 Code Grant:** Leave OFF
   - **Message Content Intent:** Turn ON (required for reading messages)

   **Note:** Setting it to "Public" doesn't mean others can automatically add your bot - they still need the specific invite link that only you will have.

## Step 2: Add Bot Token to `.env`

1. **Copy:** `cp .env.example .env` (in the repo root)
2. **Set:** `DISCORD_BOT_TOKEN=` to your bot token
3. **Save the file** (`.env` is git-ignored)

## Step 3: Invite Bot to Your Server

1. **Go to OAuth2 > URL Generator**
2. **Select Scopes:**

   - ✅ `bot`

3. **Select Bot Permissions:**

   - ✅ Send Messages
   - ✅ Use Slash Commands
   - ✅ Embed Links
   - ✅ Read Message History
   - ✅ Add Reactions

4. **Copy the generated URL** and open it in your browser
5. **Select your Discord server** and authorize the bot

## Step 4: Install Discord.py

```bash
pip install discord.py
```

## Step 5: Run the Bot

```bash
python -m src.discord_bot
```

## 🎯 How to Use the Bot

### Automatic Analysis

Just type any ticker with a $ symbol in your Discord server:

- `$AAPL` - Analyzes Apple stock
- `$TSLA` - Analyzes Tesla stock
- `$NVDA` - Analyzes NVIDIA stock

### Manual Commands

- `$analyze TICKER` - Force analysis of a specific ticker
- `$guide` - Show help message
- `$status` - Check bot status

### Example Usage

```
User: Hey guys, what do you think about $AAPL and $TSLA?

Bot: [Responds with two embeds showing detailed analysis for both AAPL and TSLA]
```

## 📊 What the Bot Shows

For each ticker, you'll get:

- **🟢 BUY / 🟡 HOLD / 🔴 SELL** recommendation
- **Current price & change**
- **Technical indicators** (RSI, Moving Averages)
- **Insider trading activity** (recent buys/sells)
- **Notable insider trades**
- **News sentiment score**
- **Overall score out of 10**

## 🛠️ Advanced Features

### Multiple Tickers

The bot can analyze up to 3 tickers per message:

```
User: Comparing $AAPL vs $MSFT vs $GOOGL
Bot: [Shows 3 analysis embeds]
```

### Real-time Analysis

Each analysis is performed in real-time using:

- ✅ Your existing price analysis
- ✅ SEC insider trading data
- ✅ News sentiment analysis
- ✅ GPT-powered insights

## 🔧 Troubleshooting

### Bot doesn't respond

1. Check if bot is online (should show green status)
2. Verify bot has proper permissions in your server
3. Make sure Message Content Intent is enabled

### "Could not analyze ticker"

1. Check if ticker symbol is valid
2. Verify API keys are working
3. Check bot logs for specific errors

### Permission errors

1. Re-invite bot with updated permissions
2. Check channel-specific permissions
3. Ensure bot role is above restricted roles

## 🚀 Running 24/7

To keep the bot running continuously:

### Option 1: Local

```bash
./scripts/start_discord_bot.sh   # or: python -m src.discord_bot
```

### Option 2: Cloud Hosting

Consider hosting on:

- Heroku
- Railway
- DigitalOcean
- AWS EC2

## 🔐 Security Notes

- **Never share your bot token**
- **Don't commit tokens to git**
- **Use environment variables in production**
- **Regularly rotate API keys**

## 📈 Bot Capabilities Summary

✅ **Real-time stock analysis**
✅ **Automatic ticker detection**
✅ **Beautiful embed formatting**
✅ **Multiple ticker support**
✅ **Insider trading data**
✅ **News sentiment analysis**
✅ **BUY/HOLD/SELL recommendations**
✅ **Technical indicators**
✅ **Error handling**
✅ **Rate limiting protection**

Your Discord server will now have a powerful trading analysis bot that responds instantly to ticker mentions!
