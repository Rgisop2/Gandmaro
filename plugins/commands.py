import asyncio
import uuid
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import API_ID, API_HASH, ADMIN_ID
from plugins.database import db

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
        
        try:
            # Create admin client with saved session
            admin_client = Client(
                ":memory:",
                session_string=admin_session,
                api_hash=API_HASH,
                api_id=API_ID
            )
            await admin_client.connect()
            
            # Extract start parameter from external bot link
            start_param = None
            if '?start=' in external_bot_link:
                start_param = external_bot_link.split('?start=')[1]
            
            # Send /start to external bot with parameter
            if start_param:
                await admin_client.send_message("me", f"/start {start_param}")
            else:
                await admin_client.send_message("me", "/start")
            
            # Listen for messages from external bot
            await m.reply("⏳ Fetching information from external bot...")
            
            # Relay messages from external bot to user
            collected_messages = []
            timeout_seconds = 15  # Wait max 15 seconds for bot response
            start_time = asyncio.get_event_loop().time()
            
            # Keep listening for messages
            while (asyncio.get_event_loop().time() - start_time) < timeout_seconds:
                try:
                    # Get the last message from the external bot
                    messages = await admin_client.get_chat_history("me", limit=1)
                    for msg in messages:
                        if msg.id not in collected_messages:
                            collected_messages.append(msg.id)
                            # Forward the message to user
                            await msg.copy(chat_id=user_id)
                except:
                    pass
                
                await asyncio.sleep(0.5)
            
            await admin_client.disconnect()
            
        except Exception as e:
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
