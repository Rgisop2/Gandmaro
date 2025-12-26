from pyrogram import Client, filters
from config import ADMINS, LOG_CHANNEL
from plugins.database import db


@Client.on_message(filters.command('setlink') & filters.private)
async def set_bot_b_link(client, message):
    """
    Admin command to set Bot B's start link.
    Usage: /setlink <BOT_B_START_LINK>
    Example: /setlink https://t.me/Urban_Links_bot?start=req_LTEwMDE4MjU1MjgwMDI
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
        # Save to database
        await db.set_bot_b_link(message.from_user.id, bot_b_link)
        
        # Log the action
        log_text = f"<b>#AdminAction\n\nAdmin set Bot B link:\n<code>{bot_b_link}</code></b>"
        await client.send_message(LOG_CHANNEL, log_text)
        
        await message.reply(
            f"Bot B link has been saved successfully!\n\n"
            f"Link: <code>{bot_b_link}</code>"
        )
    except Exception as e:
        await message.reply(f"Error saving link: {str(e)}")


@Client.on_message(filters.command('getlink') & filters.private)
async def get_bot_b_link(client, message):
    """
    Admin command to view current Bot B link.
    """
    if message.from_user.id != ADMINS:
        await message.reply("You are not authorized to use this command.")
        return
    
    try:
        link = await db.get_bot_b_link()
        if link:
            await message.reply(f"Current Bot B link:\n<code>{link}</code>")
        else:
            await message.reply("No Bot B link has been set yet. Use /setlink to set one.")
    except Exception as e:
        await message.reply(f"Error retrieving link: {str(e)}")
  
