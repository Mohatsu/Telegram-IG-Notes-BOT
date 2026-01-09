"""
Instagram Notes Manager Bot

A Telegram bot that manages Instagram Notes across multiple accounts.
Allows posting, viewing, and deleting Instagram Notes directly from Telegram.

Features:
- Multi-account support (login to multiple Instagram accounts)
- Post notes to "Mutual Followers" or "Close Friends" audiences
- View current notes on each account
- Delete active notes
- Check recent replies/DMs
- 2FA support with manual code entry
- Session persistence (no need to login every time)

Environment Variables Required (in .env):
- TELEGRAM_BOT_TOKEN: Your Telegram bot token
- ALLOWED_TELEGRAM_USER_ID: Your Telegram user ID (only you can use the bot)
- INSTA_ACCOUNTS: Multiple accounts in format: name=username:password|name2=username2:password2

Setup:
1. Run login_once.py for each Instagram account to create sessions
2. Set environment variables in .env
3. Run this bot: python main.py
"""

import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from instagrapi import Client
from instagrapi.exceptions import LoginRequired, TwoFactorRequired
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== .env Loading & Debugger ====================
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ALLOWED_USER_ID_STR = os.getenv('ALLOWED_TELEGRAM_USER_ID')
INSTA_ACCOUNTS_STR = os.getenv('INSTA_ACCOUNTS', '')

missing = []
if not TELEGRAM_BOT_TOKEN or not TELEGRAM_BOT_TOKEN.strip():
    missing.append("TELEGRAM_BOT_TOKEN")
if not ALLOWED_USER_ID_STR or not ALLOWED_USER_ID_STR.strip():
    missing.append("ALLOWED_TELEGRAM_USER_ID")
else:
    try:
        ALLOWED_USER_ID = int(ALLOWED_USER_ID_STR.strip())
    except ValueError:
        raise ValueError("ALLOWED_TELEGRAM_USER_ID must be a number (your Telegram ID)")
if not INSTA_ACCOUNTS_STR or not INSTA_ACCOUNTS_STR.strip():
    missing.append("INSTA_ACCOUNTS")

if missing:
    print("\n" + "="*70)
    print("⚠️  .ENV CONFIGURATION ERROR")
    print("="*70)
    for item in missing:
        print(f"   ❌ {item} is missing or empty")
    print("\nCurrent raw values:")
    print(f"   TELEGRAM_BOT_TOKEN: {'✅ set' if TELEGRAM_BOT_TOKEN else '❌ empty'}")
    print(f"   ALLOWED_TELEGRAM_USER_ID: {ALLOWED_USER_ID_STR.strip() if ALLOWED_USER_ID_STR else '❌ empty'}")
    print(f"   INSTA_ACCOUNTS raw: {repr(INSTA_ACCOUNTS_STR)}")
    print("\nCorrect format:")
    print("INSTA_ACCOUNTS=personal=username1:pass!|secreta=username2:pass~!|clememovil=username3:pass!")
    print("="*70 + "\n")
    exit(1)

print("✅ All required .env variables loaded successfully!")

# ==================== Account Parsing ====================
accounts = {}
account_list = []

for part in INSTA_ACCOUNTS_STR.split('|'):
    part = part.strip()
    if not part:
        continue
    if '=' not in part:
        logger.warning(f"Skipping part (no '='): {part}")
        continue
    name_part, user_pass = part.split('=', 1)
    name = name_part.strip()
    if ':' not in user_pass:
        logger.warning(f"Skipping part (no ':' in user:pass): {part}")
        continue
    username, password = user_pass.split(':', 1)
    username = username.strip()
    accounts[name] = {
        'username': username,
        'password': password,
        'session_file': Path(f"session_{name}.json"),
        'client': None
    }
    account_list.append(name)
    print(f"   Loaded account: {name} (@{username})")

if not accounts:
    print("❌ No valid accounts parsed from INSTA_ACCOUNTS.")
    print("   Use format: name=username:password|name2=username2:password2")
    exit(1)

print(f"✅ Successfully loaded {len(accounts)} Instagram account(s)!\n")

# ==================== State & Client ====================
pending_action = {}
waiting_for_2fa = None

def get_client(name):
    """
    Get or create an Instagram client for the specified account.
    
    Attempts to load an existing session from disk. If the session is valid,
    reuses it. If expired, logs in again with stored credentials.
    
    Args:
        name (str): Account name (key in accounts dict)
    
    Returns:
        Client or None: Authenticated instagrapi Client if login succeeds,
                       None if 2FA is required or login fails
    """
    if data['client']:
        return data['client']
    
    cl = Client()
    cl.delay_range = [1, 5]
    session_file = data['session_file']

    if session_file.exists():
        cl.load_settings(session_file)
        try:
            cl.get_timeline_feed()
            data['client'] = cl
            logger.info(f"Session valid for {name}")
            return cl
        except LoginRequired:
            logger.warning(f"Session expired for {name}")

    try:
        cl.login(data['username'], data['password'])
        cl.dump_settings(session_file)
        data['client'] = cl
        logger.info(f"Logged in successfully: {name}")
        return cl
    except TwoFactorRequired:
        global waiting_for_2fa
        waiting_for_2fa = name
        logger.info(f"2FA required for {name}")
        return None
    except Exception as e:
        logger.error(f"Login failed for {name}: {e}")
        return None

# ==================== Handlers ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /start command. Shows help menu with available commands.
    Only responds to authorized user.
    """
        return
    await update.message.reply_text(
        "📝 Instagram Notes Bot\n\n"
        "Commands:\n"
        "/note <text> → Post note\n"
        "/note_cf <text> → Post to Close Friends\n"
        "/current_note → View current note(s)\n"
        "/delete_note → Delete current note\n"
        "/note_replies → Check recent replies"
    )

async def handle_note_command(update: Update, context: ContextTypes.DEFAULT_TYPE, audience=0):
    """
    Handle note posting commands (/note and /note_cf).
    
    Args:
        audience (int): 0 for Mutual Followers, 1 for Close Friends
    
    If multiple accounts exist, prompts user to select one.
    If single account, posts directly.
    """
    if user_id != ALLOWED_USER_ID: return
    if not context.args:
        await update.message.reply_text("Please add text after the command.")
        return
    text = ' '.join(context.args)
    if len(text) > 60:
        await update.message.reply_text("Too long! Max 60 characters.")
        return

    if len(account_list) == 1:
        name = account_list[0]
        cl = get_client(name)
        if not cl:
            await update.message.reply_text("Login failed. Send 2FA code if prompted.")
            return
        try:
            note = cl.create_note(text, audience=audience)
            aud = "Close Friends" if audience == 1 else "Mutual Followers"
            await update.message.reply_text(f"Posted to {aud} (@{accounts[name]['username']}):\n'{note.text}'")
        except Exception as e:
            await update.message.reply_text(f"Failed: {str(e)}")
    else:
        pending_action[user_id] = {'type': 'note', 'text': text, 'audience': audience}
        lines = ["Which account?"]
        for i, name in enumerate(account_list, 1):
            lines.append(f"{i}. {name} (@{accounts[name]['username']})")
        lines.append("\nReply with the number")
        await update.message.reply_text("\n".join(lines))

async def note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /note command - post note to Mutual Followers."""
    await handle_note_command(update, context, audience=0)

async def note_cf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /note_cf command - post note to Close Friends."""
    await handle_note_command(update, context, audience=1)

async def current_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /current_note command - display active notes on all accounts."""
    user_id = update.effective_user.id
    if user_id != ALLOWED_USER_ID: return
    lines = ["Current notes:"]
    for i, name in enumerate(account_list, 1):
        cl = get_client(name)
        if not cl:
            lines.append(f"{i}. {name}: Login failed")
            continue
        try:
            notes = cl.get_notes()
            active = next((n for n in notes if n.user.pk == cl.user_id), None)
            status = f"'{active.text}'" if active else "(none)"
            lines.append(f"{i}. {name} (@{accounts[name]['username']}): {status}")
        except Exception as e:
            lines.append(f"{i}. {name}: Error")
    await update.message.reply_text("\n".join(lines))

async def delete_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /delete_note command - remove active note from selected account."""
        name = account_list[0]
        cl = get_client(name)
        if not cl:
            await update.message.reply_text("Login failed.")
            return
        try:
            notes = cl.get_notes()
            active = next((n for n in notes if n.user.pk == cl.user_id), None)
            if active:
                cl.delete_note(active.id)
                await update.message.reply_text("Note deleted.")
            else:
                await update.message.reply_text("No active note.")
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")
    else:
        pending_action[user_id] = {'type': 'delete_note'}
        lines = ["Delete note from which account?"]
        for i, name in enumerate(account_list, 1):
            lines.append(f"{i}. {name} (@{accounts[name]['username']})")
        lines.append("\nReply with number")
        await update.message.reply_text("\n".join(lines))

async def note_replies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /note_replies command - show recent DM replies from last 24 hours."""
    user_id = update.effective_user.id
    if user_id != ALLOWED_USER_ID: return
    replies_list = []
    for i, name in enumerate(account_list, 1):
        cl = get_client(name)
        if not cl:
            replies_list.append(f"{i}. {name}: Login failed")
            continue
        try:
            threads = cl.direct_threads(amount=20)
            recent = []
            for thread in threads:
                msgs = cl.direct_messages(thread.id, amount=10)
                for msg in reversed(msgs):
                    if msg.timestamp < datetime.now() - timedelta(hours=24):
                        continue
                    if msg.user_id != cl.user_id:
                        text = msg.text or "[media/emoji]"
                        time = msg.timestamp.strftime('%H:%M')
                        recent.append(f"@{msg.sender.username}: {text} ({time})")
            status = "\n".join(recent[-8:]) if recent else "No recent replies"
            replies_list.append(f"{i}. {name} (@{accounts[name]['username']}):\n{status}")
        except Exception as e:
            replies_list.append(f"{i}. {name}: Error")
    await update.message.reply_text("📨 Recent replies (last 24h):\n\n" + "\n\n".join(replies_list))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle all text messages from authorized user.
    
    Routes to:
    - 2FA code verification if waiting for 2FA
    - Account selection if user has pending action
    """

    # 2FA
    global waiting_for_2fa
    if waiting_for_2fa and user_id == ALLOWED_USER_ID:
        if text.isdigit() and len(text) == 6:
            name = waiting_for_2fa
            data = accounts[name]
            await update.message.reply_text("Verifying 2FA...")
            try:
                cl = Client()
                cl.delay_range = [1, 5]
                cl.login(data['username'], data['password'], verification_code=int(text))
                cl.dump_settings(data['session_file'])
                accounts[name]['client'] = cl
                waiting_for_2fa = None
                await update.message.reply_text(f"2FA success for {name}! Ready.")
            except Exception as e:
                waiting_for_2fa = None
                await update.message.reply_text(f"2FA failed: {str(e)}")
            return

    # Account selection
    if user_id in pending_action and text.isdigit():
        choice = int(text)
        if 1 <= choice <= len(account_list):
            name = account_list[choice - 1]
            cl = get_client(name)
            if not cl:
                await update.message.reply_text("Login failed. Send 2FA if prompted.")
                return
            action = pending_action.pop(user_id)
            if action['type'] == 'note':
                try:
                    note = cl.create_note(action['text'], audience=action['audience'])
                    aud = "Close Friends" if action['audience'] == 1 else "Mutual Followers"
                    await update.message.reply_text(f"Posted to {aud} (@{accounts[name]['username']}):\n'{note.text}'")
                except Exception as e:
                    await update.message.reply_text(f"Failed: {e}")
            elif action['type'] == 'delete_note':
                try:
                    notes = cl.get_notes()
                    active = next((n for n in notes if n.user.pk == cl.user_id), None)
                    if active:
                        cl.delete_note(active.id)
                        await update.message.reply_text("Note deleted.")
                    else:
                        await update.message.reply_text("No note to delete.")
                except Exception as e:
                    await update.message.reply_text(f"Error: {e}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Log all errors from the bot."""
    logger.error("Error:", exc_info=context.error)

# ==================== Main ====================
def main():
    """
    Initialize and start the Telegram bot.
    
    Sets up command handlers and message handlers, then starts polling
    for updates from Telegram servers.
    """
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("note", note))
    app.add_handler(CommandHandler("note_cf", note_cf))
    app.add_handler(CommandHandler("current_note", current_note))
    app.add_handler(CommandHandler("delete_note", delete_note))
    app.add_handler(CommandHandler("note_replies", note_replies))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    print("Instagram Notes Bot is running! 🚀")
    app.run_polling()

if __name__ == '__main__':
    main()