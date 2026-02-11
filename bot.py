import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from dotenv import load_dotenv
import yt_dlp
import subprocess

# --- SYSTEM DIAGNOSTICS ---
print("\n" + "="*30)
print("   BOT VERSION: 3.0 (DEBUG)   ")
print("="*30)

# Check Node.js
try:
    node_version = subprocess.check_output(["node", "-v"]).decode().strip()
    print(f"✅ Node.js found: {node_version}")
except FileNotFoundError:
    print("❌ Node.js NOT found! (YouTube might block us)")

# Check cookies.txt
if os.path.exists("cookies.txt"):
    size = os.path.getsize("cookies.txt")
    print(f"✅ cookies.txt found! Size: {size} bytes")
else:
    print("❌ cookies.txt NOT found in root directory!")
    print(f"Files in current dir: {os.listdir('.')}")

print("="*30 + "\n")
# --------------------------

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Hi! Send me a YouTube link and I'll download it for you."
    )

async def video_url_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    # Store URL in user_data to access it in the callback
    context.user_data['url'] = url
    
    keyboard = [
        [
            InlineKeyboardButton("360p", callback_data='360'),
            InlineKeyboardButton("720p", callback_data='720'),
        ],
        [InlineKeyboardButton("Audio (MP3)", callback_data='mp3')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("Select download format:", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    format_choice = query.data
    url = context.user_data.get('url')
    
    if not url:
        await query.edit_message_text(text="Error: session expired. Please send the link again.")
        return

    chat_id = update.effective_chat.id
    status_msg = await query.edit_message_text(text=f"Downloading {format_choice}...")

    ydl_opts = {
        'outtmpl': '%(title)s.%(ext)s',
        'noplaylist': True,
        'verbose': True, # Enable verbose logging to see what's happening
    }
    
    # Check for cookies.txt
    if os.path.exists('cookies.txt'):
        print(f"FOUND cookies.txt! Size: {os.path.getsize('cookies.txt')} bytes")
        ydl_opts['cookiefile'] = 'cookies.txt'
    else:
        print("WARNING: cookies.txt NOT FOUND in current directory.")
        # List files to help debug
        print(f"Current directory files: {os.listdir('.')}")

    if format_choice == '360':
        ydl_opts['format'] = 'best[height<=360]'
    elif format_choice == '720':
        ydl_opts['format'] = 'best[height<=720]'
    elif format_choice == 'mp3':
        ydl_opts['format'] = 'bestaudio/best'
        # We will not force mp3 conversion to avoid dependency issues if ffmpeg is missing. 
        # Most of the time bestaudio is m4a/opus which behaves like audio on Telegram.

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
        await context.bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text="Uploading...")
        
        if format_choice == 'mp3':
             await context.bot.send_audio(
                chat_id=chat_id,
                audio=open(filename, 'rb'),
                title=info.get('title', 'Audio'),
                performer=info.get('uploader', 'Unknown')
            )
        else:
            await context.bot.send_video(
                chat_id=chat_id,
                video=open(filename, 'rb'),
                caption=info.get('title', 'Video')
            )
        
        # Cleanup
        os.remove(filename)
        await context.bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)

    except Exception as e:
        logging.error(f"Error downloading {url}: {e}")
        await context.bot.edit_message_text(
            chat_id=chat_id, 
            message_id=status_msg.message_id, 
            text=f"Error: {str(e)}"
        )

if __name__ == '__main__':
    token = os.getenv('TELEGRAM_TOKEN')
    if not token:
        print("Error: TELEGRAM_TOKEN not found in .env")
        exit(1)
        
    application = ApplicationBuilder().token(token).build()
    
    start_handler = CommandHandler('start', start)
    video_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), video_url_handler)
    callback_handler = CallbackQueryHandler(button_handler)
    
    application.add_handler(start_handler)
    application.add_handler(video_handler)
    application.add_handler(callback_handler)
    
    # Start a dummy web server to keep Render happy
    # Render requires a web service to bind to a port within 60 seconds.
    import threading
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class HealthCheckHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot is runnning!")

    def start_web_server():
        port = int(os.environ.get('PORT', 8080))
        server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        print(f"Starting dummy web server on port {port}")
        server.serve_forever()

    # Start a dummy web server to keep the hosting service happy
    # Many free tiers (Render, Koyeb) require a web service to bind to a port.
    import threading
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class HealthCheckHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot is runnning!")

    def start_web_server():
        port = int(os.environ.get('PORT', 8080))
        # Bind to 0.0.0.0 to be accessible externally
        server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        print(f"Starting dummy web server on port {port}")
        server.serve_forever()

    # Run web server in a background thread
    threading.Thread(target=start_web_server, daemon=True).start()

    # Configure HTTPXRequest to be more robust
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(http_version="1.1", connect_timeout=30, read_timeout=30)

    application = ApplicationBuilder().token(token).request(request).build()
    
    start_handler = CommandHandler('start', start)
    video_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), video_url_handler)
    callback_handler = CallbackQueryHandler(button_handler)
    
    application.add_handler(start_handler)
    application.add_handler(video_handler)
    application.add_handler(callback_handler)
    
    application.run_polling()
