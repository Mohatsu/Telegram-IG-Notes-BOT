"""
Instagram Notes Manager Bot

A Telegram bot that manages Instagram Notes across multiple accounts.
Allows posting, viewing, and deleting Instagram Notes directly from Telegram.

Features:
- Multi-account support
- Post notes to "Mutual Followers" or "Close Friends"
- View current notes
- Delete active notes
- Check recent replies
- 2FA support
- Session persistence

Setup:
1. Use login_once.py to create session files for each account
2. Fill .env correctly
3. Run: python bot.py
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
    print(f"   ALLOWED_USER_ID: {ALLOWED_USER_ID_STR.strip() if ALLOWED_USER_ID_STR else '❌ empty'}")
    print(f"   INSTA_ACCOUNTS raw: {repr(INSTA_ACCOUNTS_STR)}")
    print("\nFormat: INSTA_ACCOUNTS=personal=username:pass|secreta=user2:pass2")
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
    exit(1)

print(f"✅ Successfully loaded {len(accounts)} Instagram account(s)!\n")

# ==================== State & Client ====================
pending_action = {}
waiting_for_2fa = None

def get_client(name):
    data = accounts[name]
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
    if update.effective_user.id != ALLOWED_USER_ID:
        return
    
    await update.message.reply_text(
        "📝 Instagram Notes Bot Ready!\n\n"
        "Available Commands:\n\n"
        "/note <message> → Post to mutual followers\n"
        "/note_cf <message> → Post to Close Friends\n"
        "/current_note → Show current note(s)\n"
        "/delete_note → Delete current note\n"
        "/note_replies → Check recent replies\n\n"
        "Example: /note Hello from Telegram! 🚀"
    )

async def handle_note_command(update: Update, context: ContextTypes.DEFAULT_TYPE, audience=0):
    user_id = update.effective_user.id
    if user_id != ALLOWED_USER_ID:
        return
    if not context.args:
        await update.message.reply_text("Please add your note text after the command.")
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
        lines.append("\nReply with the number (1, 2, 3...)")
        await update.message.reply_text("\n".join(lines))

async def note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_note_command(update, context, audience=0)

async def note_cf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_note_command(update, context, audience=1)

async def current_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ALLOWED_USER_ID:
        return
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
            lines.append(f"{i}. {name}: Error - {e}")
    await update.message.reply_text("\n".join(lines))

async def delete_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ALLOWED_USER_ID:
        return

    if len(account_list) == 1:
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
                await update.message.reply_text("Note deleted successfully.")
            else:
                await update.message.reply_text("No active note to delete.")
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")
    else:
        pending_action[user_id] = {'type': 'delete_note'}
        lines = ["Delete note from which account?"]
        for i, name in enumerate(account_list, 1):
            lines.append(f"{i}. {name} (@{accounts[name]['username']})")
        lines.append("\nReply with the number")
        await update.message.reply_text("\n".join(lines))

async def note_replies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ALLOWED_USER_ID:
        return
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
                    if msg.user_id != cl.user_id:  # Message from someone else
                        # Robust sender username extraction
                        sender_username = "unknown"
                        if hasattr(msg, 'sender') and msg.sender:
                            sender_username = msg.sender.username
                        elif hasattr(msg, 'user_id'):
                            try:
                                user = cl.user_info(msg.user_id)
                                sender_username = user.username
                            except:
                                sender_username = f"user_{msg.user_id}"
                        
                        text = msg.text or "[media/emoji/reel]"
                        time = msg.timestamp.strftime('%H:%M')
                        recent.append(f"@{sender_username}: {text} ({time})")
            status = "\n".join(recent[-8:]) if recent else "No recent replies"
            replies_list.append(f"{i}. {name} (@{accounts[name]['username']}):\n{status}")
        except Exception as e:
            replies_list.append(f"{i}. {name}: Error - {str(e)}")
    await update.message.reply_text("📨 Recent replies/reactions (last 24h):\n\n" + "\n\n".join(replies_list))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # 2FA handling
    global waiting_for_2fa
    if waiting_for_2fa and user_id == ALLOWED_USER_ID:
        if text.isdigit() and len(text) == 6:
            name = waiting_for_2fa
            data = accounts[name]
            await update.message.reply_text("Verifying 2FA code...")
            try:
                cl = Client()
                cl.delay_range = [1, 5]
                cl.login(data['username'], data['password'], verification_code=int(text))
                cl.dump_settings(data['session_file'])
                accounts[name]['client'] = cl
                waiting_for_2fa = None
                await update.message.reply_text(f"2FA successful for {name}! Session saved.")
            except Exception as e:
                waiting_for_2fa = None
                await update.message.reply_text(f"2FA failed: {str(e)}")
            return

    # Account selection for pending actions
    if user_id in pending_action and text.isdigit():
        choice = int(text)
        if 1 <= choice <= len(account_list):
            name = account_list[choice - 1]
            cl = get_client(name)
            if not cl:
                await update.message.reply_text("Login failed. Send 2FA code if prompted.")
                return
            action = pending_action.pop(user_id)
            if action['type'] == 'note':
                try:
                    note = cl.create_note(action['text'], audience=action['audience'])
                    aud = "Close Friends" if action['audience'] == 1 else "Mutual Followers"
                    await update.message.reply_text(f"Posted to {aud} (@{accounts[name]['username']}):\n'{note.text}'")
                except Exception as e:
                    await update.message.reply_text(f"Failed: {str(e)}")
            elif action['type'] == 'delete_note':
                try:
                    notes = cl.get_notes()
                    active = next((n for n in notes if n.user.pk == cl.user_id), None)
                    if active:
                        cl.delete_note(active.id)
                        await update.message.reply_text("Note deleted successfully.")
                    else:
                        await update.message.reply_text("No active note to delete.")
                except Exception as e:
                    await update.message.reply_text(f"Error: {e}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Exception occurred:", exc_info=context.error)

# ==================== Main ====================
def main():
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