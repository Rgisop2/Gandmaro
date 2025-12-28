import asyncio
import uuid
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup
from pyrogram.handlers import MessageHandler
from config import API_ID, API_HASH, ADMIN_ID
from plugins.database import db

# Store active relay sessions with message collection
active_relays = {}
relay_clients = {}

async def relay_message_handler(client, message, relay_session_id):
    """Handler to capture messages from external bot"""
    session = active_relays.get(relay_session_id)
    if not session:
        print(f"[v0] Relay: Session {relay_session_id} not found")
        return

    # ❌ DO NOT FILTER BY USERNAME (FIX)
    print(f"[v0] Relay: Captured message, forwarding")

    try:
        await message.copy(chat_id=session['user_id'])
        print(f"[v0] Relay: ✓ Forwarded to user {session['user_id']}")
    except Exception as e:
        print(f"[v0] Relay: Error forwarding - {str(e)}")
        return

    session['last_message_time'] = asyncio.get_event_loop().time()

    # ❌ DO NOT STOP ON FINAL MESSAGE (FIX)
    # Let idle timeout handle stopping


@Client.on_message(filters.command('start') & filters.private)
async def start_message(c, m):
    user_id = m.from_user.id
    args = m.text.split()

    if len(args) > 1 and args[1].startswith('generate_'):
        unique_id = args[1].replace('generate_', '')
        external_bot_link = await db.get_link(unique_id)

        if not external_bot_link:
            return await m.reply("❌ Link has expired or is invalid.")

        admin_session = await db.get_session(ADMIN_ID)
        if not admin_session:
            return await m.reply("⚠️ Bot is not properly configured. Please try again later.")

        bot_username = None
        start_param = None

        if '?start=' in external_bot_link:
            parts = external_bot_link.split('?start=')
            bot_username = parts[0].replace('https://t.me/', '').strip('/')
            start_param = parts[1]
        else:
            bot_username = external_bot_link.replace('https://t.me/', '').strip('/')

        bot_username = bot_username.lstrip('@')

        try:
            await m.reply("⏳ Fetching information from external bot...")

            admin_client = Client(
                ":memory:",
                session_string=admin_session,
                api_id=API_ID,
                api_hash=API_HASH
            )
            await admin_client.connect()

            relay_session_id = str(uuid.uuid4())

            active_relays[relay_session_id] = {
                'user_id': m.from_user.id,
                'bot_username': bot_username,
                'stop_listening': False,
                'last_message_time': asyncio.get_event_loop().time(),
                'client': admin_client
            }

            relay_clients[relay_session_id] = admin_client

            async def wrapped_handler(client, message):
                await relay_message_handler(client, message, relay_session_id)

            handler = MessageHandler(wrapped_handler, filters.private)
            admin_client.add_handler(handler)
            print(f"[v0] Relay: Handler registered for @{bot_username}")

            print(f"[v0] Relay: Sending /start {start_param} to @{bot_username}")
            if start_param:
                await admin_client.send_message(bot_username, f"/start {start_param}")
            else:
                await admin_client.send_message(bot_username, "/start")

            timeout_seconds = 30
            idle_timeout = 3
            start_time = asyncio.get_event_loop().time()

            while (asyncio.get_event_loop().time() - start_time) < timeout_seconds:
                time_since_last_msg = asyncio.get_event_loop().time() - active_relays[relay_session_id]['last_message_time']
                if time_since_last_msg > idle_timeout and active_relays[relay_session_id]['last_message_time'] != start_time:
                    print(f"[v0] Relay: No activity for {idle_timeout}s, stopping")
                    break

                await asyncio.sleep(0.1)

            print(f"[v0] Relay: Disconnecting client")
            admin_client.remove_handler(handler)
            await admin_client.disconnect()

            if relay_session_id in active_relays:
                del active_relays[relay_session_id]
            if relay_session_id in relay_clients:
                del relay_clients[relay_session_id]

        except Exception as e:
            print(f"[v0] Relay error: {str(e)}")
            if relay_session_id in active_relays:
                del active_relays[relay_session_id]
            if relay_session_id in relay_clients:
                try:
                    await relay_clients[relay_session_id].disconnect()
                except:
                    pass
                del relay_clients[relay_session_id]
            await m.reply(f"❌ Error: {str(e)}")

    else:
        await m.reply(
            "<b>Welcome to Link Relay Bot! 👋</b>\n\n"
            "This bot relays messages from external bots using admin account.\n\n"
            "For admin commands: /login, /logout, /setlink"
        )


@Client.on_message(filters.command('login') & filters.private)
async def login_handler(bot, message):
    if message.from_user.id != ADMIN_ID:
        return await message.reply("❌ You are not authorized to use this command.")

    existing_session = await db.get_session(ADMIN_ID)
    if existing_session:
        return await message.reply("✅ Admin already logged in. Use /logout to switch accounts.")

    user_id = ADMIN_ID

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
        pass

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
    if message.from_user.id != ADMIN_ID:
        return await message.reply("❌ You are not authorized.")

    await db.set_session(ADMIN_ID, None)
    await message.reply("✅ Logged out successfully.")


@Client.on_message(filters.command('setlink') & filters.private)
async def setlink_handler(bot, message):
    if message.from_user.id != ADMIN_ID:
        return await message.reply("❌ You are not authorized.")

    admin_session = await db.get_session(ADMIN_ID)
    if not admin_session:
        return await message.reply("❌ You must /login first.")

    link_msg = await bot.ask(
        message.from_user.id,
        "<b>🔗 Enter external bot link</b>\n\n"
        "<b>Example:</b> <code>https://t.me/Urban_Links_bot?start=req_xxxxx</code>"
    )

    external_bot_link = link_msg.text

    if not external_bot_link.startswith('http'):
        return await link_msg.reply("❌ Invalid URL format.")

    unique_id = str(uuid.uuid4())[:8]
    await db.save_link(unique_id, external_bot_link)

    bot_me = await bot.get_me()
    shareable_link = f"https://t.me/{bot_me.username}?start=generate_{unique_id}"

    await link_msg.reply(
        "✅ <b>Link has been saved successfully!</b>\n\n"
        "Use this link to share with users:\n\n"
        f"<code>{shareable_link}</code>"
    )
