import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import discord
from discord.ext import commands
from datetime import datetime
import re

# Import your existing analysis modules
from dst_agent import analyze_tickers
from insider_scraper import get_insider_activity
from news_scraper import get_stock_news
from config.config import DISCORD_BOT_TOKEN

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='$', intents=intents)

class TradingAnalysisBot:
    def __init__(self):
        self.active_channels = set()
    
    async def analyze_ticker(self, ticker):
        """Perform comprehensive analysis on a single ticker"""
        try:
            print(f"Analyzing {ticker}...")
            
            # Run analysis for a single ticker and extract its signal entry
            analysis_result = analyze_tickers([ticker])
            if not analysis_result:
                return None
            signals = analysis_result.get('signals', [])
            ticker_data = next((s for s in signals if s.get('ticker') == ticker.upper()), {})
            
            # Get additional data
            insider_data = get_insider_activity(ticker)
            news_data = get_stock_news(ticker)
            
            return {
                'ticker': ticker.upper(),
                'price_data': ticker_data,
                'insider_data': insider_data,
                'news_data': news_data,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            print(f"Error analyzing {ticker}: {e}")
            return None
    
    def format_analysis_embed(self, analysis):
        """Format analysis data into a Discord embed"""
        ticker = analysis['ticker']
        price_data = analysis['price_data']
        insider_data = analysis['insider_data']

        # Determine recommendation using the computed score
        score = price_data.get('score', 0.0)
        if score >= 0.5:
            recommendation = "🟢 **BUY**"
            color = 0x00ff00
        elif score <= -0.5:
            recommendation = "🔴 **SELL**"
            color = 0xff0000
        else:
            recommendation = "🟡 **HOLD**"
            color = 0xffff00

        embed = discord.Embed(
            title=f"📈 {ticker} Analysis",
            description=f"**Recommendation: {recommendation}**",
            color=color,
            timestamp=datetime.now()
        )

        # Price & Score
        current_price = 'N/A'  # Not fetched in current pipeline
        price_change = price_data.get('price_change_pct', 0) or 0
        price_emoji = "📈" if price_change > 0 else "📉" if price_change < 0 else "➡️"
        embed.add_field(
            name="💰 Price Info",
            value=(
                f"**Current:** ${current_price}\n"
                f"**Change:** {price_emoji} {price_change:.2f}%\n"
                f"**Score:** {score:.2f}"
            ),
            inline=True
        )

        # Fundamentals summary if available
        fundamentals = price_data.get('fundamentals', {})
        if fundamentals:
            fundamentals_str = ", ".join(
                f"{k}: {v}" for k, v in fundamentals.items() if v
            )[:200]
            embed.add_field(
                name="🏢 Fundamentals",
                value=fundamentals_str or "N/A",
                inline=True
            )

        # Insider Activity
        insider_buys = insider_data.get('recent_buys', 0)
        insider_sells = insider_data.get('recent_sells', 0)
        insider_emoji = "🟢" if insider_buys > insider_sells else "🔴" if insider_sells > insider_buys else "⚪"
        embed.add_field(
            name="🔍 Insider Activity",
            value=(
                f"{insider_emoji} Buys: {insider_buys} | Sells: {insider_sells}\n"
                f"**Last Activity:** {insider_data.get('last_activity', 'N/A')}"
            ),
            inline=False
        )

        # Notable insider trades (limit to 3 for Discord)
        notable_trades = insider_data.get('notable', [])[:3]
        if notable_trades and notable_trades[0] != "No notable trades":
            trades_text = "\n".join(
                [f"• {trade[:100]}..." if len(trade) > 100 else f"• {trade}" for trade in notable_trades]
            )
            embed.add_field(
                name="📋 Recent Notable Trades",
                value=trades_text,
                inline=False
            )

        # News Sentiment
        news_analysis = price_data.get('news_analysis', {})
        news_sentiment = news_analysis.get('sentiment_score')
        if isinstance(news_sentiment, (int, float)):
            sentiment_emoji = "🟢" if news_sentiment > 0.1 else "🔴" if news_sentiment < -0.1 else "🟡"
            embed.add_field(
                name="📰 News Sentiment",
                value=f"{sentiment_emoji} Score: {news_sentiment:.2f}",
                inline=True
            )

        embed.set_footer(text=f"Analysis generated at {analysis['timestamp']}")
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

@bot.event
async def on_message(message):
    # Don't respond to bot messages
    if message.author == bot.user:
        return
    
    # Check for ticker pattern (e.g., $AAPL, $TSLA, $NVDA)
    ticker_pattern = r'\$([A-Z]{1,5})\b'
    tickers = re.findall(ticker_pattern, message.content.upper())
    
    if tickers:
        # Limit to 3 tickers per message to avoid spam
        for ticker in tickers[:3]:
            try:
                # Send "typing" indicator
                async with message.channel.typing():
                    # Perform analysis
                    analysis = await trading_bot.analyze_ticker(ticker)
                    
                    if analysis:
                        embed = trading_bot.format_analysis_embed(analysis)
                        await message.channel.send(embed=embed)
                    else:
                        await message.channel.send(f"❌ Could not analyze {ticker}. Please check the ticker symbol.")
                        
            except Exception as e:
                print(f"Error processing ticker {ticker}: {e}")
                await message.channel.send(f"❌ Error analyzing {ticker}: {str(e)}")
    
    # Process other commands
    await bot.process_commands(message)

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
        name="💡 How to Use",
        value="Simply type any ticker with a $ symbol:\n"
              "• `$AAPL` - Analyze Apple\n"
              "• `$TSLA` - Analyze Tesla\n"
              "• `$NVDA` - Analyze NVIDIA",
        inline=False
    )
    
    embed.add_field(
        name="🔧 Commands",
        value="• `$analyze TICKER` - Force analysis of a ticker\n"
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
    try:
        bot.run(DISCORD_BOT_TOKEN)
    except Exception as e:  
        print(f"❌ Error running Discord bot: {e}")

    if not DISCORD_BOT_TOKEN:
        print("❌ DISCORD_BOT_TOKEN not found in config!")
    print("Please set DISCORD_BOT_TOKEN in your environment or .env file.")
    return


if __name__ == "__main__":
    run_discord_bot()
