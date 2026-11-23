"""Discord bot: chat with the DST research agent, plus quick $TICKER signal cards.

Talk to it by DM, by @mentioning it, or in any channel listed in AGENT_CHANNEL_IDS.
Only users in ALLOWED_USER_IDS get agent replies (it costs API credit and can log ideas).
"""
import asyncio
import os
import re
from datetime import datetime

import discord
from discord.ext import commands

from src import agent
from src.dst_agent import analyze_tickers
from src.send_report import split_message
from src.settings import DISCORD_BOT_TOKEN


def _ids(name):
    return {int(x) for x in os.getenv(name, "").replace(" ", "").split(",") if x.isdigit()}


ALLOWED_USER_IDS = _ids("ALLOWED_USER_IDS")
AGENT_CHANNEL_IDS = _ids("AGENT_CHANNEL_IDS")
TICKER_RE = re.compile(r'^\$([A-Za-z]{1,5})\b')

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='$', intents=intents)

COLOURS = {"Buy": 0x00ff00, "Sell": 0xff0000, "Hold": 0xffff00}


class TradingAnalysisBot:
    def __init__(self):
        self.active_channels = set()

    async def analyze_ticker(self, ticker):
        """Run the full signal engine for one ticker (off the event loop)."""
        try:
            print(f"Analyzing {ticker}...")
            result = await asyncio.to_thread(analyze_tickers, [ticker.upper()])
            signal = next((s for s in result.get('signals', []) if s['ticker'] == ticker.upper()), None)
            if not signal:
                return None
            return dict(signal, timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        except Exception as e:
            print(f"Error analyzing {ticker}: {e}")
            return None

    def format_analysis_embed(self, s):
        """Format a signal into a Discord embed"""
        c, p, ins = s['components'], s.get('price') or {}, s.get('insiders') or {}
        embed = discord.Embed(
            title=f"📈 {s['ticker']} Analysis",
            description=f"**{s['signal'].upper()}** ({s['confidence']}) · score {s['score']:+.2f}",
            color=COLOURS.get(s['signal'], 0xffff00),
            timestamp=datetime.now(),
        )
        if p:
            embed.add_field(
                name="💰 Price & trend",
                value=(f"**Close:** ${p['close']}\n**1d:** {p['ret_1d_pct']:+.2f}%\n"
                       f"**20d:** {p['ret_20d_pct']:+.2f}% ({p['rel_20d_pct']:+.2f}% vs bench)\n"
                       f"**Above 50/200d MA:** {p['above_ma50']} / {p['above_ma200']}"),
                inline=True,
            )
        embed.add_field(
            name="🧮 Components",
            value=f"Trend {c['momentum']:+.2f}\nInsider {c['insider']:+.2f}\nNews {c['news']:+.2f}",
            inline=True,
        )
        if not ins.get('error'):
            embed.add_field(
                name="🔍 Insiders (90d, open market)",
                value=(f"Buyers: {ins.get('buyers', 0)} (${ins.get('buy_value', 0):,.0f})\n"
                       f"Discretionary sellers: {ins.get('sellers', 0)} (${ins.get('sell_value', 0):,.0f})"),
                inline=False,
            )
            if ins.get('notable'):
                embed.add_field(name="📋 Notable trades",
                                value="\n".join(f"• {t[:100]}" for t in ins['notable'][:3]), inline=False)
        if s['news'].get('summary'):
            embed.add_field(name="📰 News", value=s['news']['summary'][:1000], inline=False)
        embed.set_footer(text=f"Generated {s['timestamp']} · not financial advice")
        return embed

trading_bot = TradingAnalysisBot()

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print('Bot is ready to analyze tickers!')

@bot.event
async def on_command_error(ctx, error):
    """Handle command errors silently"""
    # Ignore CommandNotFound errors (these happen when users type $TICKER)
    if isinstance(error, commands.CommandNotFound):
        return
    
    # Log other errors
    print(f"Command error: {error}")

# Conversation memory per channel/thread/DM (in memory; resets when the bot restarts)
conversations: dict[int, list] = {}
locks: dict[int, asyncio.Lock] = {}


def wants_agent(message) -> bool:
    if isinstance(message.channel, discord.DMChannel):
        return True
    if bot.user and bot.user.mentioned_in(message) and not message.mention_everyone:
        return True
    channel_id = message.channel.id
    parent_id = getattr(message.channel, "parent_id", None)  # threads inside an agent channel
    return channel_id in AGENT_CHANNEL_IDS or parent_id in AGENT_CHANNEL_IDS


async def reply_with_agent(message):
    if ALLOWED_USER_IDS and message.author.id not in ALLOWED_USER_IDS:
        return  # silently ignore strangers
    if not ALLOWED_USER_IDS:
        await message.channel.send("⚠️ ALLOWED_USER_IDS isn't set, so I'm not answering anyone yet.")
        return
    text = re.sub(rf"<@!?{bot.user.id}>", "", message.content).strip()
    if not text:
        return
    key = message.channel.id
    lock = locks.setdefault(key, asyncio.Lock())
    async with lock:
        history = agent.trim_history(conversations.get(key, []))
        history.append({"role": "user", "content": f"{message.author.display_name}: {text}"})
        used = []
        async with message.channel.typing():
            reply, history = await agent.arun(history, on_tool=lambda name, _: used.append(name))
        conversations[key] = history
        if used:
            reply += "\n-# 🔧 " + ", ".join(dict.fromkeys(used))
        for i, chunk in enumerate(split_message(reply, 1900)):
            if i == 0:
                await message.reply(chunk, mention_author=False, suppress_embeds=True)
            else:
                await message.channel.send(chunk, suppress_embeds=True)


@bot.event
async def on_message(message):
    if message.author.bot:
        return
    content = message.content.strip()

    if content.startswith("$"):
        match = TICKER_RE.match(content)
        command_names = {c.name for c in bot.commands}
        if match and match.group(1).lower() not in command_names:
            # $NVDA -> quick signal card
            ticker = match.group(1).upper()
            async with message.channel.typing():
                analysis = await trading_bot.analyze_ticker(ticker)
            if analysis:
                await message.channel.send(embed=trading_bot.format_analysis_embed(analysis))
            else:
                await message.channel.send(f"❌ Could not analyze {ticker}. Please check the ticker symbol.")
            return
        await bot.process_commands(message)
        return

    if wants_agent(message):
        try:
            await reply_with_agent(message)
        except Exception as e:
            print(f"[agent] {e}")
            await message.channel.send(f"❌ Agent error: {e}")


@bot.command(name='reset')
async def reset_command(ctx):
    """Forget the conversation in this channel"""
    conversations.pop(ctx.channel.id, None)
    await ctx.send("🧹 Conversation cleared.")


@bot.command(name='analyze')
async def analyze_command(ctx, ticker: str):
    """Manually analyze a ticker with $analyze TICKER"""
    try:
        async with ctx.typing():
            analysis = await trading_bot.analyze_ticker(ticker.upper())
            
            if analysis:
                embed = trading_bot.format_analysis_embed(analysis)
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"❌ Could not analyze {ticker.upper()}. Please check the ticker symbol.")
                
    except Exception as e:
        await ctx.send(f"❌ Error analyzing {ticker}: {str(e)}")

@bot.command(name='guide')
async def guide_command(ctx):
    """Show bot help"""
    embed = discord.Embed(
        title="📈 Trading Analysis Bot Help",
        description="Get real-time stock analysis and recommendations!",
        color=0x00ff00
    )
    
    embed.add_field(
        name="💬 Chat with the agent",
        value="DM me, @mention me, or talk in the agent channel:\n"
              "• `why is NVDA a buy today?`\n"
              "• `any 8-Ks or insider buying in AMD this month?`\n"
              "• `give me a trade idea for MSFT and log it`",
        inline=False
    )
    embed.add_field(
        name="⚡ Quick signal card",
        value="Type a ticker with $: `$AAPL`, `$NVDA`",
        inline=False
    )
    
    embed.add_field(
        name="🔧 Commands",
        value="• `$analyze TICKER` - Force analysis of a ticker\n"
              "• `$reset` - Forget this channel's conversation\n"
              "• `$guide` - Show this help message\n"
              "• `$status` - Check bot status",
        inline=False
    )
    
    embed.add_field(
        name="📊 Analysis Includes",
        value="• Price & technical indicators\n"
              "• Insider trading activity\n"
              "• News sentiment\n"
              "• BUY/HOLD/SELL recommendation",
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command(name='status')
async def status_command(ctx):
    """Show bot status"""
    embed = discord.Embed(
        title="🤖 Bot Status",
        color=0x00ff00
    )
    
    embed.add_field(name="Status", value="✅ Online", inline=True)
    embed.add_field(name="Servers", value=len(bot.guilds), inline=True)
    embed.add_field(name="Latency", value=f"{round(bot.latency * 1000)}ms", inline=True)
    
    await ctx.send(embed=embed)

def run_discord_bot():
    """Run the Discord bot"""
    if not DISCORD_BOT_TOKEN:
        print("❌ DISCORD_BOT_TOKEN not set. Add it to your environment or .env file.")
        return
    try:
        bot.run(DISCORD_BOT_TOKEN)
    except Exception as e:
        print(f"❌ Error running Discord bot: {e}")


if __name__ == "__main__":
    run_discord_bot()
