import asyncio
import uuid
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup
from pyrogram.handlers import MessageHandler
from config import API_ID, API_HASH, ADMIN_ID
from plugins.database import db

active_relays = {}
relay_clients = {}

# =========================
# RELAY HANDLER (FIXED)
# =========================
async def relay_message_handler(bot_client, admin_message, relay_session_id):
    session = active_relays.get(relay_session_id)
    if not session:
        return

    try:
        # ✅ SEND USING BOT CLIENT (NOT USER ACCOUNT)
        if admin_message.text:
            await bot_client.send_message(
                session["user_id"],
                admin_message.text,
                reply_markup=admin_message.reply_markup
            )

        elif admin_message.caption:
            if admin_message.photo:
                await bot_client.send_photo(
                    session["user_id"],
                    admin_message.photo.file_id,
                    caption=admin_message.caption,
                    reply_markup=admin_message.reply_markup
                )
            elif admin_message.document:
                await bot_client.send_document(
                    session["user_id"],
                    admin_message.document.file_id,
                    caption=admin_message.caption,
                    reply_markup=admin_message.reply_markup
                )

        print(f"[v0] Relay: Delivered message to user {session['user_id']}")

    except Exception as e:
        print(f"[v0] Relay send error: {e}")
        return

    session["last_message_time"] = asyncio.get_event_loop().time()


# =========================
# START HANDLER
# =========================
@Client.on_message(filters.command("start") & filters.private)
async def start_handler(bot, message):
    args = message.text.split()

    if len(args) > 1 and args[1].startswith("generate_"):
        uid = args[1].replace("generate_", "")
        external_link = await db.get_link(uid)

        if not external_link:
            return await message.reply("❌ Link expired or invalid.")

        admin_session = await db.get_session(ADMIN_ID)
        if not admin_session:
            return await message.reply("❌ Admin not logged in.")

        bot_username = external_link.split("?")[0].replace("https://t.me/", "").strip("/")
        start_param = external_link.split("?start=")[1] if "?start=" in external_link else None

        await message.reply("⏳ Fetching information from external bot...")

        admin_client = Client(
            ":memory:",
            session_string=admin_session,
            api_id=API_ID,
            api_hash=API_HASH
        )
        await admin_client.connect()

        relay_id = str(uuid.uuid4())
        active_relays[relay_id] = {
            "user_id": message.from_user.id,
            "last_message_time": asyncio.get_event_loop().time()
        }
        relay_clients[relay_id] = admin_client

        async def wrapped(admin_client, admin_msg):
            await relay_message_handler(bot, admin_msg, relay_id)

        handler = MessageHandler(wrapped, filters.private)
        admin_client.add_handler(handler)

        # SEND START TO EXTERNAL BOT
        if start_param:
            await admin_client.send_message(bot_username, f"/start {start_param}")
        else:
            await admin_client.send_message(bot_username, "/start")

        # WAIT & RELAY EVERYTHING
        timeout = 30
        idle = 4
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            if asyncio.get_event_loop().time() - active_relays[relay_id]["last_message_time"] > idle:
                break
            await asyncio.sleep(0.2)

        admin_client.remove_handler(handler)
        await admin_client.disconnect()
        active_relays.pop(relay_id, None)
        relay_clients.pop(relay_id, None)

    else:
        await message.reply(
            "<b>Welcome to Link Relay Bot 👋</b>\n\n"
            "Use shared links to get join request buttons.\n\n"
            "Admin commands:\n"
            "/login\n/setlink\n/logout"
        )


# =========================
# LOGIN / LOGOUT / SETLINK
# =========================
@Client.on_message(filters.command("login") & filters.private)
async def login_handler(bot, message):
    if message.from_user.id != ADMIN_ID:
        return await message.reply("❌ Unauthorized.")

    if await db.get_session(ADMIN_ID):
        return await message.reply("Already logged in. Use /logout first.")

    phone = await bot.ask(message.chat.id, "Send phone number with country code")
    client = Client(":memory:", API_ID, API_HASH)
    await client.connect()
    sent = await client.send_code(phone.text)

    code = await bot.ask(message.chat.id, "Send OTP (space separated)")
    await client.sign_in(phone.text, sent.phone_code_hash, code.text.replace(" ", ""))

    try:
        pwd = await bot.ask(message.chat.id, "Enter 2FA password")
        await client.check_password(pwd.text)
    except:
        pass

    session = await client.export_session_string()
    await db.set_session(ADMIN_ID, session)
    await client.disconnect()
    await message.reply("✅ Admin logged in successfully.")


@Client.on_message(filters.command("logout") & filters.private)
async def logout_handler(bot, message):
    if message.from_user.id != ADMIN_ID:
        return
    await db.set_session(ADMIN_ID, None)
    await message.reply("✅ Logged out.")


@Client.on_message(filters.command("setlink") & filters.private)
async def setlink_handler(bot, message):
    if message.from_user.id != ADMIN_ID:
        return

    if not await db.get_session(ADMIN_ID):
        return await message.reply("❌ Login first.")

    link_msg = await bot.ask(
        message.chat.id,
        "Send external bot link\nExample:\nhttps://t.me/Urban_Links_bot?start=req_xxxx"
    )

    uid = str(uuid.uuid4())[:8]
    await db.save_link(uid, link_msg.text)

    me = await bot.get_me()
    await link_msg.reply(
        f"✅ Link saved\n\n"
        f"https://t.me/{me.username}?start=generate_{uid}"
    )
