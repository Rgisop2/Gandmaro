import asyncio
import re
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
    
    args = m.command
    if len(args) > 1 and args[1].startswith('generate_'):
        # User clicked on a shared link with specific link ID
        link_id = args[1].replace('generate_', '')
        await generate_fresh_link(c, m, link_id)
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
        
        link_id = await db.add_urban_link(urban_link)
        
        # Generate bot's own shareable link with unique ID
        bot_me = await client.get_me()
        bot_link = f"https://t.me/{bot_me.username}?start=generate_{link_id}"
        
        await message.reply(
            f"**✅ Link has been saved successfully!**\n\n"
            f"**Use this link to share with users:**\n\n"
            f"`{bot_link}`",
            disable_web_page_preview=True
        )
    except Exception as e:
        await message.reply(f"**Error:** {str(e)}")

async def generate_fresh_link(client, message, link_id):
    try:
        wait_msg = await message.reply("⏳ **Please wait...**")
        
        # Get stored Urban Links URL by ID
        urban_link = await db.get_urban_link_by_id(link_id)
        if not urban_link:
            return await wait_msg.edit_text("**The link configuration has expired or been removed. Please contact admin.**")
        
        # Extract bot username from the Urban Links URL
        bot_username_match = re.search(r'https://t\.me/(\w+)', urban_link)
        if not bot_username_match:
            return await wait_msg.edit_text("**Invalid link configuration. Please contact admin.**")
        
        urban_bot_username = bot_username_match.group(1)
        
        # Extract the start parameter from the Urban Links URL
        start_param_match = re.search(r'\?start=(.+)', urban_link)
        if not start_param_match:
            return await wait_msg.edit_text("**Invalid link configuration. Please contact admin.**")
        
        start_param = start_param_match.group(1)
        
        # Get user's session
        user_session = await db.get_session(message.from_user.id)
        if user_session is None:
            return await wait_msg.edit_text(
                "**You need to login first to generate links.**\n\n"
                "Use `/login` to login with your account."
            )
        
        try:
            try:
                await acc.get_chat(urban_bot_username)
            except Exception as peer_err:
                print(f"[v0] Could not fetch peer {urban_bot_username}: {str(peer_err)}")
            
            # This ensures we only process messages that arrive AFTER our command
            last_msg_id = 0
            async for last_msg in acc.get_chat_history(urban_bot_username, limit=1):
                last_msg_id = last_msg.id
            
            await acc.send_message(urban_bot_username, f"/start {start_param}")
            
            # We need to listen for messages until we get one with inline buttons (reply_markup)
            messages_received = []
            timeout = 10  # seconds to wait for messages
            start_time = asyncio.get_event_loop().time()
            last_message_time = start_time
            
            async for msg in acc.get_chat_history(urban_bot_username, limit=10):
                # Only process messages from the bot that are NEWER than the last message ID
                if msg.id > last_msg_id and msg.from_user and msg.from_user.username == urban_bot_username:
                    messages_received.append(msg)
                    last_message_time = asyncio.get_event_loop().time()
                    
                    # Check if this message has inline buttons (reply_markup)
                    if msg.reply_markup:
                        print(f"[v0] Found fresh message with reply_markup: {msg.text}")
                        break
                    
                    # Timeout if no new messages for 3 seconds
                    if asyncio.get_event_loop().time() - last_message_time > 3:
                        break
            
            if not messages_received:
                await asyncio.sleep(2)
                async for msg in acc.get_chat_history(urban_bot_username, limit=10):
                    if msg.id > last_msg_id and msg.from_user and msg.from_user.username == urban_bot_username:
                        messages_received.append(msg)
            
            if messages_received:
                # Reverse to get chronological order (oldest first)
                messages_received.reverse()
                
                message_with_button = None
                for idx, response_msg in enumerate(messages_received):
                    # Check if this message has inline buttons
                    has_button = response_msg.reply_markup is not None
                    
                    if response_msg.text:
                        reply_markup = response_msg.reply_markup if has_button else None
                        if idx == 0:
                            # First message, edit the wait message
                            await wait_msg.edit_text(
                                response_msg.text,
                                reply_markup=reply_markup
                            )
                        else:
                            # Subsequent messages, send as new message
                            await message.reply(
                                response_msg.text,
                                reply_markup=reply_markup
                            )
                    elif response_msg.caption:
                        reply_markup = response_msg.reply_markup if has_button else None
                        if idx == 0:
                            # First message, delete wait and send media
                            await wait_msg.delete()
                        
                        if response_msg.photo:
                            await message.reply_photo(
                                response_msg.photo.file_id,
                                caption=response_msg.caption,
                                reply_markup=reply_markup
                            )
                        elif response_msg.document:
                            await message.reply_document(
                                response_msg.document.file_id,
                                caption=response_msg.caption,
                                reply_markup=reply_markup
                            )
                    
                    # Stop after forwarding message with inline buttons
                    if has_button:
                        message_with_button = response_msg
                        break
                
                # If no message with buttons was found, show final wait message
                if not message_with_button:
                    await wait_msg.edit_text(
                        "**✅ Fresh link generated!**\n\n"
                        "Click the button above to proceed with your request.\n\n"
                        "⏰ *Note: The link expires in 1 minute. If it expires, request a new one.*"
                    )
            else:
                await wait_msg.edit_text("**Could not retrieve link. Please try again.**")
        
        except Exception as e:
            print(f"[v0] Error generating link: {str(e)}")
            await wait_msg.edit_text(f"**Error generating link:** {str(e)}")
        
        finally:
            try:
                await acc.disconnect()
            except:
                pass
    
    except Exception as e:
        print(f"[v0] Error in generate_fresh_link: {str(e)}")
        await message.reply("**An error occurred. Please try again.**")
