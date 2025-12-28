import asyncio
import uuid
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import API_ID, API_HASH, ADMIN_ID
from plugins.database import db

# Store active relay sessions
active_relays = {}

@Client.on_message(filters.command('start') & filters.private)
async def start_message(c, m):
    user_id = m.from_user.id
    args = m.text.split()
    
    # Check if user has start parameter (from generated link)
    if len(args) > 1 and args[1].startswith('generate_'):
        unique_id = args[1].replace('generate_', '')
        external_bot_link = await db.get_link(unique_id)
        
        if not external_bot_link:
            return await m.reply("❌ Link has expired or is invalid.")
        
        # Get admin session
        admin_session = await db.get_session(ADMIN_ID)
        if not admin_session:
            return await m.reply("⚠️ Bot is not properly configured. Please try again later.")
        
        # Extract start parameter and bot username from external bot link
        bot_username = None
        start_param = None
        
        if '?start=' in external_bot_link:
            parts = external_bot_link.split('?start=')
            bot_username = parts[0].replace('https://t.me/', '').strip('/')
            start_param = parts[1]
        else:
            bot_username = external_bot_link.replace('https://t.me/', '').strip('/')
        
        try:
            # Create admin client with saved session
            admin_client = Client(
                ":memory:",
                session_string=admin_session,
                api_id=API_ID,
                api_hash=API_HASH
            )
            await admin_client.connect()
            
            # Create relay session tracking
            relay_session_id = str(uuid.uuid4())
            active_relays[relay_session_id] = {
                'user_id': user_id,
                'bot_username': bot_username,
                'messages': [],
                'created_at': asyncio.get_event_loop().time()
            }
            
            await m.reply("⏳ Fetching information from external bot...")
            
            @admin_client.on_message(filters.private & filters.user(bot_username))
            async def relay_handler(client, message):
                if relay_session_id in active_relays:
                    # Store message ID to avoid duplicates
                    active_relays[relay_session_id]['messages'].append(message.id)
                    
                    try:
                        await message.copy(chat_id=user_id)
                    except Exception as e:
                        print(f"[v0] Error forwarding message: {e}")
            
            # Send /start to external bot with parameter
            if start_param:
                await admin_client.send_message(bot_username, f"/start {start_param}")
            else:
                await admin_client.send_message(bot_username, "/start")
            
            # Wait for messages with timeout
            timeout_seconds = 30  # Max 30 seconds to collect all messages
            start_time = asyncio.get_event_loop().time()
            last_message_time = start_time
            
            # Keep waiting until timeout or no new messages for 3 seconds
            while (asyncio.get_event_loop().time() - start_time) < timeout_seconds:
                current_message_count = len(active_relays[relay_session_id]['messages'])
                
                # If we have messages and haven't received new ones for 2 seconds, finish
                if current_message_count > 0:
                    current_time = asyncio.get_event_loop().time()
                    if (current_time - last_message_time) > 2:
                        break
                    last_message_time = current_time
                
                await asyncio.sleep(0.5)
            
            # Cleanup
            del active_relays[relay_session_id]
            await admin_client.disconnect()
            
        except Exception as e:
            print(f"[v0] Relay error: {e}")
            if relay_session_id in active_relays:
                del active_relays[relay_session_id]
            await m.reply(f"❌ Error: {str(e)}")
    else:
        # Default /start message (no relay parameters)
        await m.reply(
            "<b>Welcome to Link Relay Bot! 👋</b>\n\n"
            "This bot relays messages from external bots using admin account.\n\n"
            "For admin commands: /login, /logout, /setlink"
        )

@Client.on_message(filters.command('login') & filters.private)
async def login_handler(bot, message):
    """Admin login with OTP and 2FA"""
    if message.from_user.id != ADMIN_ID:
        return await message.reply("❌ You are not authorized to use this command.")
    
    # Check if already logged in
    existing_session = await db.get_session(ADMIN_ID)
    if existing_session:
        return await message.reply("✅ Admin already logged in. Use /logout to switch accounts.")
    
    user_id = ADMIN_ID
    
    # Get phone number
    phone_number_msg = await bot.ask(
        chat_id=user_id,
        text="<b>📱 Enter your phone number with country code</b>\n"
             "<b>Example:</b> <code>+13124562345</code>\n\n"
             "Send /cancel to abort."
    )
    
    if phone_number_msg.text == '/cancel':
        return await phone_number_msg.reply('❌ Login cancelled.')
    
    phone_number = phone_number_msg.text
    client = Client(":memory:", API_ID, API_HASH)
    
    try:
        await client.connect()
        await phone_number_msg.reply("⏳ Sending OTP...")
        
        code = await client.send_code(phone_number)
        
        # Get OTP
        phone_code_msg = await bot.ask(
            user_id,
            "<b>📝 Enter OTP</b>\n\n"
            "If OTP is <code>12345</code>, send it as: <code>1 2 3 4 5</code>\n\n"
            "Send /cancel to abort.",
            filters=filters.text,
            timeout=600
        )
        
        if phone_code_msg.text == '/cancel':
            await client.disconnect()
            return await phone_code_msg.reply('❌ Login cancelled.')
        
        phone_code = phone_code_msg.text.replace(" ", "")
        await client.sign_in(phone_number, code.phone_code_hash, phone_code)
        
    except Exception as e:
        await client.disconnect()
        return await message.reply(f"❌ OTP Error: {str(e)}")
    
    # Check for 2FA
    try:
        two_step_msg = await bot.ask(
            user_id,
            "<b>🔐 Two-step verification detected</b>\n\n"
            "Enter your password:\n\n"
            "Send /cancel to abort.",
            filters=filters.text,
            timeout=300
        )
        
        if two_step_msg.text == '/cancel':
            await client.disconnect()
            return await two_step_msg.reply('❌ Login cancelled.')
        
        await client.check_password(password=two_step_msg.text)
        
    except:
        pass  # No 2FA enabled
    
    # Save session
    try:
        session_string = await client.export_session_string()
        await db.set_session(ADMIN_ID, session_string)
        await client.disconnect()
        
        await message.reply(
            "✅ <b>Admin login successful!</b>\n\n"
            "Your session has been saved permanently.\n"
            "Now use /setlink to set an external bot link."
        )
    except Exception as e:
        await client.disconnect()
        await message.reply(f"❌ Session save error: {str(e)}")

@Client.on_message(filters.command('logout') & filters.private)
async def logout_handler(bot, message):
    """Admin logout"""
    if message.from_user.id != ADMIN_ID:
        return await message.reply("❌ You are not authorized.")
    
    await db.set_session(ADMIN_ID, None)
    await message.reply("✅ Logged out successfully.")

@Client.on_message(filters.command('setlink') & filters.private)
async def setlink_handler(bot, message):
    """Admin sets external bot link"""
    if message.from_user.id != ADMIN_ID:
        return await message.reply("❌ You are not authorized.")
    
    # Check admin session
    admin_session = await db.get_session(ADMIN_ID)
    if not admin_session:
        return await message.reply("❌ You must /login first.")
    
    # Get external bot link
    link_msg = await bot.ask(
        message.from_user.id,
        "<b>🔗 Enter external bot link</b>\n\n"
        "<b>Example:</b> <code>https://t.me/Urban_Links_bot?start=req_xxxxx</code>"
    )
    
    external_bot_link = link_msg.text
    
    if not external_bot_link.startswith('http'):
        return await link_msg.reply("❌ Invalid URL format.")
    
    # Generate unique ID
    unique_id = str(uuid.uuid4())[:8]
    
    # Save link
    await db.save_link(unique_id, external_bot_link)
    
    # Get bot username
    bot_me = await bot.get_me()
    shareable_link = f"https://t.me/{bot_me.username}?start=generate_{unique_id}"
    
    await link_msg.reply(
        "✅ <b>Link has been saved successfully!</b>\n\n"
        "Use this link to share with users:\n\n"
        f"<code>{shareable_link}</code>"
    )
