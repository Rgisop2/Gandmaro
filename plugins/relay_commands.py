from pyrogram import Client, filters
from config import ADMINS, LOG_CHANNEL
from plugins.database import db
from urllib.parse import urlparse, parse_qs


@Client.on_message(filters.command('setrelay') & filters.private)
async def set_relay_session(client, message):
    """
    Admin command to set relay user account session.
    The relay user account is used as a bridge to fetch links from Bot B.
    
    Usage: /setrelay <SESSION_STRING>
    Session string is obtained from Pyrogram when logging in with a user account.
    """
    # Check if user is admin
    if message.from_user.id != ADMINS:
        await message.reply("You are not authorized to use this command.")
        return
    
    # Parse session string from command
    args = message.text.split(None, 1)
    if len(args) < 2:
        await message.reply(
            "Usage: /setrelay <SESSION_STRING>\n\n"
            "To get session string:\n"
            "1. Run Pyrogram user login script\n"
            "2. Copy the generated session string\n"
            "3. Use this command with the session string"
        )
        return
    
    session_string = args[1].strip()
    
    if not session_string or len(session_string) < 20:
        await message.reply("Invalid session string. Session string must be at least 20 characters.")
        return
    
    try:
        # Validate session by trying to connect
        test_client = Client(
            "test_relay",
            session_string=session_string,
            api_id=__import__('config').API_ID,
            api_hash=__import__('config').API_HASH,
            in_memory=True
        )
        
        await test_client.connect()
        user_info = await test_client.get_me()
        await test_client.disconnect()
        
        print(f"[v0] Relay session validated for user: {user_info.first_name}")
        
        # Save to database
        await db.set_relay_user_session(session_string, message.from_user.id)
        
        # Log the action
        log_text = f"<b>#AdminAction\n\nAdmin set relay user session\nUser: {user_info.first_name} ({user_info.id})</b>"
        await client.send_message(LOG_CHANNEL, log_text)
        
        await message.reply(
            f"Relay user session has been set successfully!\n\n"
            f"Relay User: {user_info.first_name}\n"
            f"The relay bridge is now active and ready to fetch links from Bot B."
        )
        
    except Exception as e:
        print(f"[v0] Error validating relay session: {str(e)}")
        await message.reply(f"Error validating session: {str(e)}\n\nMake sure the session string is valid.")


@Client.on_message(filters.command('setlink') & filters.private)
async def set_bot_b_link(client, message):
    """
    Admin command to set Bot B's start link.
    Usage: /setlink <BOT_B_START_LINK>
    Example: /setlink https://t.me/Urban_Links_bot?start=req_LTEwMDE4MjU1MjgwMDI
    
    Extracts the payload and returns OUR bot's link, not Bot B's link.
    """
    # Check if user is admin
    if message.from_user.id != ADMINS:
        await message.reply("You are not authorized to use this command.")
        return
    
    # Parse the link from command
    args = message.text.split(None, 1)
    if len(args) < 2:
        await message.reply(
            "Usage: /setlink <BOT_B_START_LINK>\n\n"
            "Example:\n/setlink https://t.me/Urban_Links_bot?start=req_LTEwMDE4MjU1MjgwMDI"
        )
        return
    
    bot_b_link = args[1].strip()
    
    # Validate link format
    if not bot_b_link.startswith('https://t.me/'):
        await message.reply("Invalid link format. Must be a valid Telegram link (https://t.me/...)")
        return
    
    try:
        parsed_url = urlparse(bot_b_link)
        query_params = parse_qs(parsed_url.query)
        payload = query_params.get('start', [None])[0]
        
        if not payload:
            await message.reply("Invalid link format. Must contain ?start=<payload>")
            return
        
        # Save to database
        await db.set_bot_b_link(message.from_user.id, bot_b_link)
        
        our_bot_username = client.me.username
        our_bot_link = f"https://t.me/{our_bot_username}?start={payload}"
        
        # Log the action
        log_text = f"<b>#AdminAction\n\nAdmin set Bot B link:\n<code>{bot_b_link}</code>\n\nGenerated link:\n<code>{our_bot_link}</code></b>"
        await client.send_message(LOG_CHANNEL, log_text)
        
        await message.reply(
            f"Bot B link has been saved successfully!\n\n"
            f"Use this link to share with users:\n"
            f"<code>{our_bot_link}</code>"
        )
    except Exception as e:
        await message.reply(f"Error saving link: {str(e)}")


@Client.on_message(filters.command('getlink') & filters.private)
async def get_bot_b_link(client, message):
    """
    Admin command to view current Bot B link and relay status.
    """
    # Check if user is admin
    if message.from_user.id != ADMINS:
        await message.reply("You are not authorized to use this command.")
        return
    
    try:
        link = await db.get_bot_b_link()
        relay_session = await db.get_relay_user_session()
        
        relay_status = "✓ Configured" if relay_session else "✗ Not Configured (use /setrelay)"
        
        if link:
            parsed_url = urlparse(link)
            query_params = parse_qs(parsed_url.query)
            payload = query_params.get('start', [None])[0]
            
            our_bot_username = client.me.username
            our_bot_link = f"https://t.me/{our_bot_username}?start={payload}" if payload else "N/A"
            
            await message.reply(
                f"<b>Bot B Link (Source):</b>\n<code>{link}</code>\n\n"
                f"<b>Our Bot Link (To Share):</b>\n<code>{our_bot_link}</code>\n\n"
                f"<b>Relay User Session:</b>\n{relay_status}"
            )
        else:
            await message.reply(
                f"No Bot B link has been set yet. Use /setlink to set one.\n\n"
                f"<b>Relay User Session:</b>\n{relay_status}"
            )
    except Exception as e:
        await message.reply(f"Error retrieving link: {str(e)}")
