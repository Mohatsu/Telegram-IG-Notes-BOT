"""
Instagram Session Login Script

This script performs a one-time login to Instagram and saves the session locally.
Use this to authenticate each Instagram account before running the main bot.

The saved session allows the main bot to reuse authentication without requiring
login credentials every time it starts.

Process:
1. Attempts initial login
2. If 2FA is triggered, prompts for verification code
3. Saves session to a local JSON file for reuse

Setup:
1. Update USERNAME, PASSWORD, and SESSION_NAME below
2. Run this script: python login_once.py
3. Enter 2FA code if prompted
4. Session file is created and ready for main.py
"""

from instagrapi import Client
from pathlib import Path

# === CHANGE THESE FOR THE ACCOUNT YOU WANT TO LOGIN ===
USERNAME = "PUT_YOUR_USERNAME_HERE"          # your Instagram username
PASSWORD = "PUT_YOUR_PASSWORD_HERE"      # your real password with special characters
SESSION_NAME = "ADD_THE_ALIAS_FROM_ENV"      # must match the name in your .env (e.g. clememovil)

cl = Client()
cl.delay_range = [1, 5]

# Better device to avoid detection
cl.set_device({
    'phone_manufacturer': 'Google',
    'phone_model': 'Pixel 8',
    'android_version': 34,
    'android_release': '14'
})

session_file = Path(f"session_{SESSION_NAME}.json")

print("Attempting login...")

try:
    cl.login(USERNAME, PASSWORD)
    print("Login successful! No 2FA needed.")
except Exception as e:
    print("Challenge or 2FA triggered:", str(e))
    code = input("Enter the CURRENT 6-digit code from your 2FA app NOW: ").strip()
    if not code.isdigit() or len(code) != 6:
        print("Invalid code format. Must be 6 digits.")
        exit(1)
    try:
        cl.login(USERNAME, PASSWORD, verification_code=code)
        print("2FA login successful!")
    except Exception as e2:
        print("2FA failed (wrong/expired code or block):", str(e2))
        print("Try again with a fresh code, or wait 30 minutes and retry.")
        exit(1)

# Save session
cl.dump_settings(session_file)
print(f"\nSUCCESS! Session saved as: {session_file}")
print("You can now run your main bot (main.py) — it will use this session automatically.")