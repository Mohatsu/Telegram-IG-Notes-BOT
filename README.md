# Instagram Notes Manager Bot

A Telegram bot that manages Instagram Notes across multiple accounts with ease.

## Features

- 📝 **Post Notes** - Share notes to "Mutual Followers" or "Close Friends" audiences
- 👥 **Multi-Account Support** - Manage multiple Instagram accounts from one bot
- 👀 **View Notes** - Check current active notes on all your accounts
- 🗑️ **Delete Notes** - Remove active notes with a single command
- 💬 **Check Replies** - See recent DM replies from the last 24 hours
- 🔐 **2FA Support** - Handles two-factor authentication with manual code entry
- 💾 **Session Persistence** - Saves sessions locally to avoid repeated logins

## Prerequisites

- Python 3.8+
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- Your Telegram User ID
- Instagram accounts with credentials

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Create Environment File

Create a `.env` file in the project root with your credentials:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
ALLOWED_TELEGRAM_USER_ID=your_telegram_user_id_here
INSTA_ACCOUNTS=personal=username1:password1|work=username2:password2|backup=username3:password3
```

**Format for INSTA_ACCOUNTS:**
- Separate multiple accounts with `|`
- Each account: `name=username:password`
- Name must match the session file name (without `session_` prefix and `.json` extension)

### 3. Login to Instagram Accounts

For each account, run the login script to create a session:

```bash
python login_once.py
```

Then update the script with:
1. The Instagram username
2. The Instagram password
3. A session name (must match your .env account names)

If 2FA is enabled, enter the 6-digit code when prompted.

This creates a `session_<name>.json` file that the bot reuses.

### 4. Run the Bot

```bash
python main.py
```

The bot will connect to Telegram and wait for commands.

## Usage

### Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/start` | Show help menu | `/start` |
| `/note <text>` | Post note to Mutual Followers (max 60 chars) | `/note Hello everyone!` |
| `/note_cf <text>` | Post note to Close Friends (max 60 chars) | `/note_cf Secret message` |
| `/current_note` | View active notes on all accounts | `/current_note` |
| `/delete_note` | Delete active note from selected account | `/delete_note` |
| `/note_replies` | Check recent replies from last 24 hours | `/note_replies` |

### Multi-Account Selection

If you have multiple accounts configured, the bot will prompt you to select which account to use:

```
Which account?
1. personal (@username1)
2. work (@username2)
3. backup (@username3)

Reply with the number
```

Simply reply with `1`, `2`, or `3` to proceed.

## File Structure

```
.
├── main.py              # Main bot logic
├── login_once.py        # One-time Instagram login script
├── requirements.txt     # Python dependencies
├── .env                 # Environment variables (create this)
├── session_*.json       # Instagram session files (auto-generated)
└── README.md           # This file
```

## Security Notes

⚠️ **Important:**
- Never commit `.env` or `session_*.json` files to git (add to `.gitignore`)
- Keep your `.env` file secure - it contains your Instagram credentials
- Only the Telegram user ID specified in `.env` can use the bot
- Session files should be kept private

## Troubleshooting

### 2FA Required
If Instagram triggers 2FA during login, you'll see a prompt in Telegram asking for the 6-digit verification code. Enter it within the valid time window (usually 30 seconds).

### Session Expired
If a session expires, the bot will automatically attempt to re-login using stored credentials.

### Login Failed
- Verify credentials in `.env` are correct
- Ensure the account isn't rate-limited or temporarily blocked
- Check Instagram's app settings haven't changed

### Permission Errors
- Confirm your Telegram User ID is correct in `.env`
- Only the authorized user can interact with the bot

## Dependencies

- `python-telegram-bot` - Telegram bot API
- `instagrapi` - Instagram API client
- `python-dotenv` - Environment variable management

See `requirements.txt` for versions.


## License

This project is provided as-is for personal use.

## Disclaimer

This bot uses unofficial Instagram API (instagrapi). Instagram may block accounts using unauthorized API access. Use at your own risk and respect Instagram's terms of service.
