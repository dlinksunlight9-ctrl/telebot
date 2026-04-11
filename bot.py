import asyncio
import os
import sys
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, filters, MessageHandler
from telegram.error import TelegramError

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get bot token
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("BOT_TOKEN environment variable is not set!")
    sys.exit(1)

logger.info(f"Bot token loaded: {BOT_TOKEN[:10]}...{BOT_TOKEN[-10:]}")

DELETE_AFTER = 120  # 2 minutes
BATCH_DELAY = 0.5  # Seconds between files

# TEMPORARY: Empty list - you'll fill this with new file IDs
FILES = []  # We'll populate this after capturing all 31 files

# Storage for captured file IDs
captured_files = []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command - currently disabled until files are captured"""
    await update.message.reply_text(
        "⚠️ **Bot is in setup mode**\n\n"
        "Please forward all 31 files to this bot first.\n"
        "The bot will capture and save the file IDs.\n\n"
        "Commands:\n"
        "/capture - Start capture mode\n"
        "/show - Show captured file IDs\n"
        "/clear - Clear captured IDs\n"
        "/done - Generate final code with captured IDs",
        parse_mode="Markdown"
    )

async def capture_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enable capture mode"""
    context.user_data['capture_mode'] = True
    context.user_data['captured_files'] = []
    
    await update.message.reply_text(
        "📸 **Capture Mode Enabled**\n\n"
        "Now forward all 31 files to this bot one by one.\n"
        "The bot will save each file ID automatically.\n\n"
        "Commands:\n"
        "/show - Show captured IDs so far\n"
        "/done - Finish and generate final code",
        parse_mode="Markdown"
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle forwarded documents and capture file IDs"""
    
    # If not in capture mode, just show the file ID
    if not context.user_data.get('capture_mode', False):
        if update.message.document:
            file_id = update.message.document.file_id
            file_name = update.message.document.file_name or "Unknown"
            
            await update.message.reply_text(
                f"📎 **File ID:**\n`{file_id}`\n\n"
                f"📄 Name: {file_name}\n\n"
                f"💡 Enable capture mode with /capture to save multiple IDs",
                parse_mode="Markdown"
            )
        return
    
    # In capture mode - save the file ID
    if update.message.document:
        file_id = update.message.document.file_id
        file_name = update.message.document.file_name or "Unknown"
        
        # Initialize list if not exists
        if 'captured_files' not in context.user_data:
            context.user_data['captured_files'] = []
        
        # Add to list
        context.user_data['captured_files'].append({
            'id': file_id,
            'name': file_name,
            'number': len(context.user_data['captured_files']) + 1
        })
        
        count = len(context.user_data['captured_files'])
        
        await update.message.reply_text(
            f"✅ **Captured File #{count}**\n"
            f"📄 Name: {file_name}\n"
            f"🆔 ID: `{file_id}`\n\n"
            f"📊 Total captured: {count}/31",
            parse_mode="Markdown"
        )
        
        # Auto-generate code when all 31 files are captured
        if count == 31:
            await generate_code(update, context)

async def show_captured(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all captured file IDs"""
    captured = context.user_data.get('captured_files', [])
    
    if not captured:
        await update.message.reply_text("❌ No files captured yet. Use /capture to start.")
        return
    
    message = f"📋 **Captured Files ({len(captured)}/31)**\n\n"
    
    for file in captured:
        message += f"{file['number']}. {file['name']}\n`{file['id']}`\n\n"
    
    # Split if too long
    if len(message) > 4000:
        # Send as file
        with open("captured_ids.txt", "w") as f:
            for file in captured:
                f.write(f"Part {file['number']:02d} → {file['id']}\n")
        
        with open("captured_ids.txt", "rb") as f:
            await update.message.reply_document(
                document=f,
                caption=f"📋 {len(captured)} file IDs captured"
            )
        os.remove("captured_ids.txt")
    else:
        await update.message.reply_text(message, parse_mode="Markdown")

async def clear_captured(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear all captured file IDs"""
    context.user_data['captured_files'] = []
    context.user_data['capture_mode'] = False
    await update.message.reply_text("🗑️ All captured file IDs cleared.")

async def generate_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate the final FILES list code"""
    captured = context.user_data.get('captured_files', [])
    
    if not captured:
        await update.message.reply_text("❌ No files captured yet. Use /capture to start.")
        return
    
    # Generate the FILES list code
    code = "# Complete list of captured file IDs\n"
    code += "FILES = [\n"
    
    for file in captured:
        code += f'    "{file["id"]}",  # Part {file["number"]}\n'
    
    code += "]\n"
    
    # Save to file
    filename = "updated_bot_code.txt"
    with open(filename, "w") as f:
        f.write("=" * 60 + "\n")
        f.write("COPY AND PASTE THIS INTO YOUR bot.py FILE\n")
        f.write("=" * 60 + "\n\n")
        f.write(code)
        f.write("\n" + "=" * 60 + "\n")
        f.write(f"Total: {len(captured)} files captured\n")
        f.write("=" * 60 + "\n")
    
    # Send the generated code
    with open(filename, "rb") as f:
        await update.message.reply_document(
            document=f,
            caption=f"✅ **Generated Code with {len(captured)} Files**\n\n"
                   f"Replace the FILES list in your bot.py with this code!",
            parse_mode="Markdown"
        )
    
    os.remove(filename)
    
    # Also send as text if not too long
    if len(captured) <= 10:
        await update.message.reply_text(
            f"```python\n{code}```",
            parse_mode="Markdown"
        )
    
    # Disable capture mode
    context.user_data['capture_mode'] = False

async def send_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send all captured files (after they're captured)"""
    captured = context.user_data.get('captured_files', [])
    
    if not captured:
        await update.message.reply_text(
            "❌ No files captured yet!\n"
            "Use /capture first, then forward all 31 files to me."
        )
        return
    
    if len(captured) < 31:
        await update.message.reply_text(
            f"⚠️ Only {len(captured)}/31 files captured.\n"
            f"Please capture all 31 files first."
        )
        return
    
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    logger.info(f"User {user.id} sending {len(captured)} files")
    
    status_msg = await update.message.reply_text(
        f"📤 Sending {len(captured)} files...\n"
        f"⏱️ Files will be deleted in 2 minutes."
    )
    
    sent_messages = [status_msg.message_id]
    failed = 0
    
    for file in captured:
        try:
            msg = await update.message.reply_document(
                document=file['id'],
                caption=f"📄 {file['name']} ({file['number']}/{len(captured)})"
            )
            sent_messages.append(msg.message_id)
            await asyncio.sleep(BATCH_DELAY)
        except Exception as e:
            logger.error(f"Failed to send {file['name']}: {e}")
            failed += 1
    
    await status_msg.edit_text(
        f"✅ Sent {len(captured) - failed}/{len(captured)} files.\n"
        f"⏱️ Deleting in 2 minutes..."
    )
    
    await asyncio.sleep(DELETE_AFTER)
    
    # Delete messages
    for msg_id in sent_messages:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            await asyncio.sleep(0.05)
        except:
            pass

async def health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Health check"""
    captured = len(context.user_data.get('captured_files', []))
    await update.message.reply_text(
        f"✅ Bot is running!\n"
        f"📊 Captured files: {captured}/31\n"
        f"🎯 Mode: {'Capture' if context.user_data.get('capture_mode') else 'Standby'}"
    )

if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("Starting Telegram Bot in SETUP MODE...")
    logger.info("=" * 50)
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("capture", capture_mode))
    app.add_handler(CommandHandler("show", show_captured))
    app.add_handler(CommandHandler("clear", clear_captured))
    app.add_handler(CommandHandler("done", generate_code))
    app.add_handler(CommandHandler("send", send_files))
    app.add_handler(CommandHandler("health", health))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    logger.info("Bot ready! Follow these steps:")
    logger.info("1. Send /capture to the bot")
    logger.info("2. Forward all 31 files to the bot")
    logger.info("3. Send /done to generate the new code")
    logger.info("4. Update your bot.py with the new FILES list")
    logger.info("5. Redeploy on Railway")
    
    app.run_polling(drop_pending_updates=True)
