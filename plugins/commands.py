import asyncio 
import time
from pyrogram import Client, filters, enums
from config import LOG_CHANNEL, API_ID, API_HASH, NEW_REQ_MODE, RELAY_MODE, BOT_B_LINK, LINK_COOLDOWN, ADMINS
from plugins.database import db
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from plugins.relay import fetch_fresh_link, relay_link_to_user

LOG_TEXT = """<b>#NewUser
    
ID - <code>{}</code>

Nᴀᴍᴇ - {}</b>
"""

@Client.on_message(filters.command('start'))
async def start_message(c, m):
    if not await db.is_user_exist(m.from_user.id):
        await db.add_user(m.from_user.id, m.from_user.first_name)
        await c.send_message(LOG_CHANNEL, LOG_TEXT.format(m.from_user.id, m.from_user.mention))
    
    args = m.text.split(None, 1)
    payload = args[1] if len(args) > 1 else ""
    
    if RELAY_MODE and payload and payload.startswith("req_"):
        # Flow 2: Payload Start - Trigger link relay logic
        
        # Check cooldown
        current_time = time.time()
        last_request = await db.get_user_link_cooldown(m.from_user.id)
        
        if current_time - last_request < LINK_COOLDOWN:
            remaining = int(LINK_COOLDOWN - (current_time - last_request))
            await m.reply(f"Please wait {remaining} more seconds before requesting another link.")
            return
        
        # Show loading message
        loading_msg = await m.reply("Generating your link, please wait...")
        
        stored_payload = await db.get_bot_b_link()
        
        if not stored_payload:
            await loading_msg.edit("Error: Bot B link has not been configured. Admin must use /setlink first.")
            return
        
        try:
            admin_id = ADMINS[0] if ADMINS else None
            
            if not admin_id:
                await loading_msg.edit("Error: No admin configured. Check ADMINS in config.")
                return
            
            admin_session = await db.get_session(admin_id)
            
            if not admin_session:
                await loading_msg.edit("Error: Admin user account not logged in. Admin must use /login first.")
                return
            
        except Exception as e:
            print(f"[v0] Error getting admin session: {str(e)}")
            await loading_msg.edit(f"Error: {str(e)}")
            return
        
        try:
            link, error = await fetch_fresh_link(m.from_user.id, stored_payload, admin_session)
            
            if error:
                await loading_msg.edit(f"Error generating link: {error}")
                return
            
            if not link:
                await loading_msg.edit("Could not fetch link from Bot B. Please try again.")
                return
            
            # Update cooldown in database
            await db.set_user_link_cooldown(m.from_user.id, current_time)
            
            # Delete loading message and send the link
            await loading_msg.delete()
            await relay_link_to_user(c, m.from_user.id, link)
            return  # Return immediately after relay logic
            
        except Exception as e:
            await loading_msg.edit(f"Error: {str(e)}")
            return  # Return immediately on error
    
    await m.reply_photo(f"https://te.legra.ph/file/119729ea3cdce4fefb6a1.jpg",
        caption=f"<b>Hello {m.from_user.mention} 👋\n\nI Am Join Request Acceptor Bot. I Can Accept All Old Pending Join Request.\n\nFor All Pending Join Request Use - /accept</b>",
        reply_markup=InlineKeyboardMarkup(
            [[
                InlineKeyboardButton('💝 sᴜʙsᴄʀɪʙᴇ ʏᴏᴜᴛᴜʙᴇ ᴄʜᴀɴɴᴇʟ', url='https://youtube.com/@Tech_VJ')
            ],[
                InlineKeyboardButton("❣️ ᴅᴇᴠᴇʟᴏᴘᴇʀ", url='https://t.me/Kingvj01'),
                InlineKeyboardButton("🤖 ᴜᴘᴅᴀᴛᴇ", url='https://t.me/VJ_Botz')
            ]]
        )
    )

@Client.on_message(filters.command('accept') & filters.private)
async def accept(client, message):
    show = await message.reply("**Please Wait.....**")
    user_data = await db.get_session(message.from_user.id)
    if user_data is None:
        await show.edit("**For Accepte Pending Request You Have To /login First.**")
        return
    try:
        acc = Client("joinrequest", session_string=user_data, api_hash=API_HASH, api_id=API_ID)
        await acc.connect()
    except:
        return await show.edit("**Your Login Session Expired. So /logout First Then Login Again By - /login**")
    show = await show.edit("**Now Forward A Message From Your Channel Or Group With Forward Tag\n\nMake Sure Your Logged In Account Is Admin In That Channel Or Group With Full Rights.**")
    vj = await client.listen(message.chat.id)
    if vj.forward_from_chat and not vj.forward_from_chat.type in [enums.ChatType.PRIVATE, enums.ChatType.BOT]:
        chat_id = vj.forward_from_chat.id
        try:
            info = await acc.get_chat(chat_id)
        except:
            await show.edit("**Error - Make Sure Your Logged In Account Is Admin In This Channel Or Group With Rights.**")
    else:
        return await message.reply("**Message Not Forwarded From Channel Or Group.**")
    await vj.delete()
    msg = await show.edit("**Accepting all join requests... Please wait until it's completed.**")
    try:
        while True:
            await acc.approve_all_chat_join_requests(chat_id)
            await asyncio.sleep(1)
            join_requests = [request async for request in acc.get_chat_join_requests(chat_id)]
            if not join_requests:
                break
        await msg.edit("**Successfully accepted all join requests.**")
    except Exception as e:
        await msg.edit(f"**An error occurred:** {str(e)}")
        
@Client.on_chat_join_request(filters.group | filters.channel)
async def approve_new(client, m):
    if NEW_REQ_MODE == False:
        return 
    try:
        if not await db.is_user_exist(m.from_user.id):
            await db.add_user(m.from_user.id, m.from_user.first_name)
            await client.send_message(LOG_CHANNEL, LOG_TEXT.format(m.from_user.id, m.from_user.mention))
        await client.approve_chat_join_request(m.chat.id, m.from_user.id)
        try:
            await client.send_message(m.from_user.id, "**Hello {}!\nWelcome To {}\n\n__Powered By : @VJ_Botz __**".format(m.from_user.mention, m.chat.title))
        except:
            pass
    except Exception as e:
        print(str(e))
        pass
