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
        # Get stored Urban Links URL by ID
        urban_link = await db.get_urban_link_by_id(link_id)
        if not urban_link:
            return await message.reply("**The link configuration has expired or been removed. Please contact admin.**")
        
        # Extract bot username from the Urban Links URL
        bot_username_match = re.search(r'https://t\.me/(\w+)', urban_link)
        if not bot_username_match:
            return await message.reply("**Invalid link configuration. Please contact admin.**")
        
        urban_bot_username = bot_username_match.group(1)
        
        # Extract the start parameter from the Urban Links URL
        start_param_match = re.search(r'\?start=(.+)', urban_link)
        if not start_param_match:
            return await message.reply("**Invalid link configuration. Please contact admin.**")
        
        start_param = start_param_match.group(1)
        
        # Get user's session
        user_session = await db.get_session(message.from_user.id)
        if user_session is None:
            return await message.reply(
                "**You need to login first to generate links.**\n\n"
                "Use `/login` to login with your account."
            )
        
        try:
            # Create client with user session
            acc = Client("user_client", session_string=user_session, api_hash=API_HASH, api_id=API_ID)
            await acc.connect()
        except:
            return await message.reply("**Your login session expired. Use `/logout` then `/login` again.**")
        
        try:
            try:
                await acc.get_chat(urban_bot_username)
            except Exception as peer_err:
                print(f"[v0] Could not fetch peer {urban_bot_username}: {str(peer_err)}")
                # Continue anyway - the bot might still work
            
            await acc.send_message(urban_bot_username, f"/start {start_param}")
            
            # Wait a bit for the Urban_Links_bot to respond
            await asyncio.sleep(2)
            
            conversation_messages = []
            try:
                async for msg in acc.get_chat_history(urban_bot_username, limit=5):
                    if msg.from_user and msg.from_user.username == urban_bot_username:
                        conversation_messages.append(msg)
                
                if conversation_messages:
                    # Get the most recent message from the bot
                    response_msg = conversation_messages[0]
                    
                    # Send the response message text and button to the user
                    if response_msg.text:
                        reply_markup = response_msg.reply_markup if response_msg.reply_markup else None
                        await message.reply(
                            response_msg.text,
                            reply_markup=reply_markup
                        )
                    elif response_msg.caption:
                        # Handle media with caption
                        reply_markup = response_msg.reply_markup if response_msg.reply_markup else None
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
                        else:
                            await message.reply(response_msg.caption, reply_markup=reply_markup)
                    else:
                        await message.reply(
                            "**✅ Fresh link generated!**\n\n"
                            "Click the button above to proceed with your request.\n\n"
                            "⏰ *Note: The link expires in 1 minute. If it expires, request a new one.*"
                        )
                else:
                    await message.reply("**Could not retrieve link. Please try again.**")
            
            except Exception as hist_err:
                print(f"[v0] Error retrieving messages: {str(hist_err)}")
                await message.reply("**Could not retrieve link. Please try again.**")
        
        except Exception as e:
            print(f"[v0] Error generating link: {str(e)}")
            await message.reply(f"**Error generating link:** {str(e)}")
        
        finally:
            try:
                await acc.disconnect()
            except:
                pass
