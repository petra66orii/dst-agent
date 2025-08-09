import requests
from config.config import DISCORD_WEBHOOK_URL

def send_to_discord(report):
    try:
        if not DISCORD_WEBHOOK_URL:
            print("DISCORD_WEBHOOK_URL not set; skipping Discord delivery.")
            return
        lines = [f"📊 **DST Report — {report['date']}**"]

        lines.append(f"\n🟢 **Buy ({len(report['buy'])})**: {', '.join(report['buy']) or 'None'}")
        lines.append(f"🔴 **Sell ({len(report['sell'])})**: {', '.join(report['sell']) or 'None'}")
        lines.append(f"🟡 **Hold ({len(report['hold'])})**: {', '.join(report['hold']) or 'None'}")

        # Add AI Insights Summary
        ai_insights = []
        for s in report["signals"]:
            if s.get("signal") in ["Buy", "Sell"] and s.get("confidence") == "High":
                news_analysis = s.get("news_analysis", {})
                if news_analysis and news_analysis.get("summary"):
                    ai_insights.append(f"**{s['ticker']}**: {news_analysis['summary'][:100]}...")
        
        if ai_insights:
            lines.append("\n🤖 **Key AI Insights:**")
            for insight in ai_insights[:3]:  # Limit to top 3
                lines.append(f"• {insight}")

        lines.append("\n---\n**Detailed Analysis:**")

        for s in report["signals"]:
            fundamentals = s.get("fundamentals", {})
            fundamentals_str = ", ".join(
                f"{k}: {v}" for k, v in fundamentals.items() if v
            )

            lines.append(f"\n🔹 **{s['ticker']}** — {s['signal']} ({s['confidence']})")
            lines.append(f"• Score: {s['score']} | Δ Price: {s['price_change_pct']}%")
            
            if fundamentals_str:
                lines.append(f"• Fundamentals: {fundamentals_str}")
                
            # Add ChatGPT News Analysis
            news_analysis = s.get("news_analysis", {})
            if news_analysis and news_analysis.get("summary"):
                lines.append(f"• 🤖 **News AI**: {news_analysis['summary']} (Score: {news_analysis.get('sentiment_score', 0)})")
            
            # Add ChatGPT Insider Analysis  
            insider_analysis = s.get("insider_analysis", {})
            if insider_analysis and insider_analysis.get("summary") and "No significant" not in insider_analysis.get("summary", ""):
                lines.append(f"• 🕵️ **Insider AI**: {insider_analysis['summary']} (Score: {insider_analysis.get('sentiment_score', 0)})")

        if report.get("insider_activity"):
            lines.append("\n---\n**Notable Insider/Senator Trades:**")
            for line in report["insider_activity"]:
                lines.append(f"🔍 {line}")

        # Join content and split into multiple messages if needed
        full_content = "\n".join(lines)
        
        def split_message(content, max_length=1950):
            """Split content into chunks that fit Discord's limit"""
            if len(content) <= max_length:
                return [content]
            
            chunks = []
            current_chunk = ""
            
            for line in content.split('\n'):
                # If adding this line would exceed the limit
                if len(current_chunk) + len(line) + 1 > max_length:
                    if current_chunk:
                        chunks.append(current_chunk)
                        current_chunk = line
                    else:
                        # Single line is too long, force split
                        chunks.append(line[:max_length])
                        current_chunk = line[max_length:]
                else:
                    if current_chunk:
                        current_chunk += "\n" + line
                    else:
                        current_chunk = line
            
            if current_chunk:
                chunks.append(current_chunk)
            
            return chunks
        
        message_chunks = split_message(full_content)
        
        # Send each chunk as a separate message
        for i, chunk in enumerate(message_chunks):
            if len(message_chunks) > 1:
                # Add part indicator for multi-part messages
                header = f"**[Part {i+1}/{len(message_chunks)}]**\n\n" if i > 0 else ""
                content_to_send = header + chunk
            else:
                content_to_send = chunk
            
            response = requests.post(
                DISCORD_WEBHOOK_URL,
                json={"content": content_to_send},
                timeout=10
            )
            
            if response.status_code in [200, 204]:
                if len(message_chunks) > 1:
                    print(f"Report part {i+1}/{len(message_chunks)} sent to Discord successfully")
                else:
                    print("Report sent to Discord successfully")
            else:
                print(f"Failed to send report part {i+1}: {response.status_code}")
                print(f"Response: {response.text}")
                break  # Stop sending if one fails

    except Exception as e:
        print(f"Error sending report to Discord: {e}")
