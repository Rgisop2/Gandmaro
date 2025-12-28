import asyncio
import uuid
from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler
from config import API_ID, API_HASH, ADMIN_ID
from plugins.database import db

active_relays = {}

# =========================
# ADMIN -> BOT FORWARD HANDLER
# =========================
@Client.on_message(filters.forwarded & filters.private)
async def admin_forward_handler(bot, message):
    """
    Admin forwards messages from external bot to this bot.
    Bot will resend them to waiting user.
    """
    if message.from_user.id != ADMIN_ID:
        return

    relay = active_relays.get(ADMIN_ID)
    if not relay:
        return

    user_id = relay["user_id"]

    try:
        # Forward from admin -> user (bot sending)
        await message.copy(chat_id=user_id)
        relay["last_message_time"] = asyncio.get_event_loop().time()
        print(f"[v0] Bot forwarded admin message to user {user_id}")
    except Exception as e:
        print(f"[v0] Forward error: {e}")


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

        await message.reply("⏳ Please wait...")

        # Save waiting user
        active_relays[ADMIN_ID] = {
            "user_id": message.from_user.id,
            "last_message_time": asyncio.get_event_loop().time()
        }

        # Admin user client
        admin_client = Client(
            ":memory:",
            session_string=admin_session,
            api_id=API_ID,
            api_hash=API_HASH
        )
        await admin_client.connect()

        # Send /start to external bot
        if start_param:
            await admin_client.send_message(bot_username, f"/start {start_param}")
        else:
            await admin_client.send_message(bot_username, "/start")

        # Wait while admin forwards messages
        timeout = 60
        idle = 5
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            if asyncio.get_event_loop().time() - active_relays[ADMIN_ID]["last_message_time"] > idle:
                break
            await asyncio.sleep(0.3)

        await admin_client.disconnect()
        active_relays.pop(ADMIN_ID, None)

    else:
        await message.reply(
            "<b>Welcome to Link Relay Bot 👋</b>\n\n"
            "Use the shared link to get your join request button."
        )


# =========================
# LOGIN
# =========================
@Client.on_message(filters.command("login") & filters.private)
async def login_handler(bot, message):
    if message.from_user.id != ADMIN_ID:
        return await message.reply("❌ Unauthorized.")

    if await db.get_session(ADMIN_ID):
        return await message.reply("Already logged in.")

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


# =========================
# LOGOUT
# =========================
@Client.on_message(filters.command("logout") & filters.private)
async def logout_handler(bot, message):
    if message.from_user.id != ADMIN_ID:
        return
    await db.set_session(ADMIN_ID, None)
    await message.reply("✅ Logged out.")


# =========================
# SETLINK
# =========================
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
