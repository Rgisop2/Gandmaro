from pyrogram import Client, filters
from config import ADMINS, LOG_CHANNEL
from plugins.database import db
from urllib.parse import urlparse, parse_qs



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
    
    # Check if admin is logged in
    admin_session = await db.get_session(message.from_user.id)
    if not admin_session:
        await message.reply(
            "Error: You must be logged in to use this command.\n\n"
            "Use /login first to log in your user account.\n\n"
            "The relay system uses your logged-in account to fetch links from Bot B."
        )
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
        admin_session = await db.get_session(message.from_user.id)
        
        relay_status = "✓ Ready" if admin_session else "✗ Not Logged In (use /login)"
        
        if link:
            parsed_url = urlparse(link)
            query_params = parse_qs(parsed_url.query)
            payload = query_params.get('start', [None])[0]
            
            our_bot_username = client.me.username
            our_bot_link = f"https://t.me/{our_bot_username}?start={payload}" if payload else "N/A"
            
            await message.reply(
                f"<b>Bot B Link (Source):</b>\n<code>{link}</code>\n\n"
                f"<b>Our Bot Link (To Share):</b>\n<code>{our_bot_link}</code>\n\n"
                f"<b>Relay Status:</b>\n{relay_status}"
            )
        else:
            await message.reply(
                f"No Bot B link has been set yet. Use /setlink to set one.\n\n"
                f"<b>Relay Status:</b>\n{relay_status}"
            )
    except Exception as e:
        await message.reply(f"Error retrieving link: {str(e)}")
