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
    """Generate fresh link using admin's session"""
    try:
        wait_msg = await message.reply("⏳ **Please wait...**")
        
        admin_session = await db.get_admin_session()
        if admin_session is None:
            return await wait_msg.edit_text(
                "**Admin has not logged in yet.**\n\n"
                "Please contact admin and ask them to use `/login` first."
            )
        
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
        
        acc = Client(
            name="admin_session",
            session_string=admin_session,
            api_id=API_ID,
            api_hash=API_HASH
        )
        
        received_messages = []
        
        try:
            await acc.connect()
            
            try:
                await acc.get_chat(urban_bot_username)
            except Exception as e:
                print(f"[v0] Could not fetch peer {urban_bot_username}: {str(e)}")
            
            @acc.on_message(filters.user(urban_bot_username) & filters.private)
            async def capture_response(aclient, msg):
                received_messages.append(msg)
            
            # Send the /start command
            await acc.send_message(urban_bot_username, f"/start {start_param}")
            
            max_wait_time = 15.0
            silence_threshold = 3.0
            start_time = asyncio.get_event_loop().time()
            last_message_count = 0
            last_check_time = start_time
            
            while True:
                current_time = asyncio.get_event_loop().time()
                elapsed = current_time - start_time
                current_message_count = len(received_messages)
                time_since_last_check = current_time - last_check_time
                
                if current_message_count > last_message_count:
                    last_message_count = current_message_count
                    last_check_time = current_time
                    silence_time = 0
                else:
                    silence_time = current_time - last_check_time
                
                if (current_message_count > 0 and silence_time >= silence_threshold) or elapsed >= max_wait_time:
                    break
                
                await asyncio.sleep(0.2)
            
            if not received_messages:
                await wait_msg.edit_text("**No response received from link service. Please try again.**")
            else:
                for idx, response_msg in enumerate(received_messages):
                    try:
                        if response_msg.text:
                            if idx == 0:
                                await wait_msg.edit_text(
                                    response_msg.text,
                                    reply_markup=response_msg.reply_markup
                                )
                            else:
                                await message.reply(
                                    response_msg.text,
                                    reply_markup=response_msg.reply_markup
                                )
                        elif response_msg.caption:
                            if idx == 0:
                                await wait_msg.delete()
                            
                            if response_msg.photo:
                                await message.reply_photo(
                                    response_msg.photo.file_id,
                                    caption=response_msg.caption,
                                    reply_markup=response_msg.reply_markup
                                )
                            elif response_msg.document:
                                await message.reply_document(
                                    response_msg.document.file_id,
                                    caption=response_msg.caption,
                                    reply_markup=response_msg.reply_markup
                                )
                    except Exception as e:
                        print(f"[v0] Error forwarding message {idx}: {str(e)}")
        
        except Exception as e:
            print(f"[v0] Error generating link: {str(e)}")
            await wait_msg.edit_text(f"**Error:** {str(e)}")
        
        finally:
            try:
                await acc.disconnect()
            except:
                pass
    
    except Exception as e:
        print(f"[v0] Error in generate_fresh_link: {str(e)}")
        await message.reply("**An error occurred. Please try again.**")
