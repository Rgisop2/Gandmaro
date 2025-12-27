import asyncio
import re
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import API_ID, API_HASH, LOG_CHANNEL
from plugins.database import db

LOG_TEXT = """<b>#NewUser
ID - <code>{}</code>
Name - {}</b>
"""


# =========================
# /start
# =========================
@Client.on_message(filters.command("start"))
async def start_handler(client, message):
    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id, message.from_user.first_name)
        await client.send_message(
            LOG_CHANNEL,
            LOG_TEXT.format(message.from_user.id, message.from_user.mention)
        )

    args = message.command

    if len(args) > 1 and args[1].startswith("generate_"):
        link_id = args[1].replace("generate_", "")
        await generate_fresh_link(client, message, link_id)
        return

    await message.reply_photo(
        "https://te.legra.ph/file/119729ea3cdce4fefb6a1.jpg",
        caption=f"<b>Hello {message.from_user.mention} 👋\n\n"
                "I am a Link Generator Bot.\n"
                "Use shared links to get fresh join request links.</b>",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🤖 Updates", url="https://t.me/VJ_Botz")]]
        )
    )


# =========================
# /setlink (ADMIN)
# =========================
@Client.on_message(filters.command("setlink") & filters.private)
async def setlink_handler(client, message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.reply(
            "**Usage:** `/setlink https://t.me/Urban_Links_bot?start=req_xxx`"
        )

    urban_link = args[1].strip()
    if not urban_link.startswith("https://t.me/"):
        return await message.reply("**Invalid Telegram link.**")

    link_id = await db.add_urban_link(urban_link)
    me = await client.get_me()
    bot_link = f"https://t.me/{me.username}?start=generate_{link_id}"

    await message.reply(
        f"**✅ Link saved successfully!**\n\n"
        f"**Use this link:**\n\n`{bot_link}`",
        disable_web_page_preview=True
    )


# =========================
# CORE FIXED FUNCTION
# =========================
async def generate_fresh_link(client, message, link_id):
    wait = await message.reply("⏳ **Please wait...**")

    urban_link = await db.get_urban_link_by_id(link_id)
    if not urban_link:
        return await wait.edit_text("**Link expired. Contact admin.**")

    bot_username = re.search(r"https://t\.me/(\w+)", urban_link).group(1)
    start_param = re.search(r"\?start=(.+)", urban_link).group(1)

    # 🔐 ADMIN SESSION ONLY
    admin_session = await db.get_admin_session()
    if not admin_session:
        return await wait.edit_text("**Admin not logged in.**")

    acc = Client(
        "admin_user",
        session_string=admin_session,
        api_id=API_ID,
        api_hash=API_HASH
    )

    await acc.connect()

    try:
        # 🔑 MARK LAST MESSAGE ID (CRITICAL FIX)
        last_msg = await acc.get_chat_history(bot_username, limit=1)
        last_id = last_msg[0].id if last_msg else 0

        # SEND FRESH START
        await acc.send_message(bot_username, f"/start {start_param}")

        end_time = asyncio.get_event_loop().time() + 15
        forwarded = False

        while asyncio.get_event_loop().time() < end_time:
            await asyncio.sleep(1)

            async for msg in acc.get_chat_history(bot_username, limit=5):
                # ❌ IGNORE OLD MESSAGES
                if msg.id <= last_id:
                    continue

                last_id = msg.id  # update marker

                # first real response → remove wait
                if not forwarded:
                    try:
                        await wait.delete()
                    except:
                        pass
                    forwarded = True

                # FORWARD SAME MESSAGE
                if msg.text:
                    await message.reply(msg.text, reply_markup=msg.reply_markup)
                elif msg.photo:
                    await message.reply_photo(
                        msg.photo.file_id,
                        caption=msg.caption,
                        reply_markup=msg.reply_markup
                    )
                elif msg.document:
                    await message.reply_document(
                        msg.document.file_id,
                        caption=msg.caption,
                        reply_markup=msg.reply_markup
                    )

                # STOP AFTER BUTTON MESSAGE
                if msg.reply_markup:
                    return

        if not forwarded:
            await wait.edit_text("**No response received. Try again.**")

    finally:
        await acc.disconnect()
