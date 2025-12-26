import asyncio 
from pyrogram import Client, filters, enums
from config import LOG_CHANNEL, API_ID, API_HASH
from plugins.database import db
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

LOG_TEXT = """<b>#NewUser
    
ID - <code>{}</code>

Nᴀᴍᴇ - {}</b>
"""

@Client.on_message(filters.command('start'))
async def start_message(c, m):
    if not await db.is_user_exist(m.from_user.id):
        await db.add_user(m.from_user.id, m.from_user.first_name)
        await c.send_message(LOG_CHANNEL, LOG_TEXT.format(m.from_user.id, m.from_user.mention))
    
    # Check if user started with a deep link (deep_linking parameter)
    args = m.command
    if len(args) > 1 and args[1] == 'generate':
        # User clicked on a shared link, generate fresh link for them
        await generate_fresh_link(c, m)
    else:
        # Regular start message
        await m.reply_photo(f"https://te.legra.ph/file/119729ea3cdce4fefb6a1.jpg",
            caption=f"<b>Hello {m.from_user.mention} 👋\n\nI Am Link Generator Bot. I help you generate fresh join request links.\n\nShare my link with your users and they will get fresh links every time!</b>",
            reply_markup=InlineKeyboardMarkup(
                [[
                    InlineKeyboardButton('💝 sᴜʙsᴄʀɪʙᴇ ʏᴏᴜᴛᴜʙᴇ ᴄʜᴀɴɴᴇʟ', url='https://youtube.com/@Tech_VJ')
                ],[
                    InlineKeyboardButton("❣️ ᴅᴇᴠᴇʟᴏᴘᴇʀ", url='https://t.me/Kingvj01'),
                    InlineKeyboardButton("🤖 ᴜᴘᴅᴀᴛᴇ", url='https://t.me/VJ_Botz')
                ]]
            )
        )

@Client.on_message(filters.command('setlink') & filters.private)
async def set_link(client, message):
    try:
        # Extract link from command
        args = message.text.split(None, 1)
        if len(args) < 2:
            return await message.reply("**Usage:** `/setlink https://t.me/Urban_Links_bot?start=req_xxxxx`")
        
        urban_link = args[1].strip()
        
        # Validate it's a Telegram URL
        if not urban_link.startswith('https://t.me/'):
            return await message.reply("**Invalid link format. Please provide a valid Telegram bot link.**")
        
        # Store the link
        await db.set_urban_link(urban_link)
        
        # Generate bot's own shareable link
        bot_me = await client.get_me()
        bot_link = f"https://t.me/{bot_me.username}?start=generate"
        
        await message.reply(
            f"**✅ Link has been saved successfully!**\n\n"
            f"**Use this link to share with users:**\n\n"
            f"`{bot_link}`",
            disable_web_page_preview=True
        )
    except Exception as e:
        await message.reply(f"**Error:** {str(e)}")

async def generate_fresh_link(client, message):
    show = await message.reply("**Please wait, generating fresh link for you...**")
    
    # Get stored Urban Links URL
    urban_link = await db.get_urban_link()
    if not urban_link:
        return await show.edit("**Admin has not configured the link yet. Please try again later.**")
    
    # Get user's session
    user_session = await db.get_session(message.from_user.id)
    if user_session is None:
        return await show.edit(
            "**You need to login first to generate links.**\n\n"
            "Use `/login` to login with your account."
        )
    
    try:
        # Create client with user session
        acc = Client("user_client", session_string=user_session, api_hash=API_HASH, api_id=API_ID)
        await acc.connect()
    except:
        return await show.edit("**Your login session expired. Use `/logout` then `/login` again.**")
    
    try:
        # Start the Urban Links bot with the configured link
        await acc.send_message("Urban_Links_bot", "/start req_LTEwMDE4MjU1MjgwMDI")
        
        await show.edit("**Processing... This may take a moment...**")
        
        # Wait for response from Urban_Links_bot
        # The bot will send a message with the REQUEST TO JOIN button
        # We'll listen for messages from Urban_Links_bot
        conversation_messages = []
        async for msg in acc.get_chat_history("Urban_Links_bot", limit=10):
            if msg.from_user and msg.from_user.username == "Urban_Links_bot":
                conversation_messages.append(msg)
                break
        
        if conversation_messages:
            response_msg = conversation_messages[0]
            # Forward the message to the user
            await response_msg.forward(message.from_user.id)
            await show.delete()
            await message.reply(
                "**✅ Fresh link generated!**\n\n"
                "Click the button below to proceed with your request."
            )
        else:
            await show.edit("**Could not retrieve link. Please try again.**")
    
    except Exception as e:
        await show.edit(f"**Error generating link:** {str(e)}")
    
    finally:
        try:
            await acc.disconnect()
        except:
            pass
