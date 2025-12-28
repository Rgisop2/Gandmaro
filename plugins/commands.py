import asyncio
import re
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import API_ID, API_HASH, BOT_TOKEN
from plugins.database import db

app = Client(
    "LinkRelayBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ======================
# /start
# ======================
@app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    args = message.command

    # START FROM GENERATED LINK
    if len(args) > 1 and args[1].startswith("generate_"):
        link_id = args[1].replace("generate_", "")
        await generate_fresh_link(client, message, link_id)
        return

    # NORMAL START
    await message.reply(
        "👋 **Welcome!**\n\n"
        "This bot generates fresh join links from external bots.\n\n"
        "Use shared links to continue."
    )

# ======================
# /setlink (ADMIN)
# ======================
@app.on_message(filters.command("setlink") & filters.private)
async def setlink_handler(client, message):
    args = message.text.split(None, 1)

    if len(args) < 2:
        return await message.reply("Usage:\n/setlink https://t.me/Urban_Links_bot?start=req_xxx")

    external_link = args[1].strip()

    if not external_link.startswith("https://t.me/"):
        return await message.reply("❌ Invalid Telegram link")

    link_id = await db.save_link(external_link)

    me = await client.get_me()
    share_link = f"https://t.me/{me.username}?start=generate_{link_id}"

    await message.reply(
        "✅ **Link saved successfully!**\n\n"
        f"Use this link:\n`{share_link}`",
        disable_web_page_preview=True
    )

# ======================
# CORE LOGIC
# ======================
async def generate_fresh_link(bot, message, link_id):
    wait = await message.reply("⏳ **Please wait...**")

    # Get external bot link
    external_link = await db.get_link(link_id)
    if not external_link:
        return await wait.edit("❌ Link expired")

    # Extract bot username
    bot_match = re.search(r"t\.me/(\w+)", external_link)
    start_match = re.search(r"\?start=(.+)", external_link)

    if not bot_match or not start_match:
        return await wait.edit("❌ Invalid external link")

    ext_bot = bot_match.group(1)
    start_param = start_match.group(1)

    # Get USER session
    user_session = await db.get_user_session(message.from_user.id)
    if not user_session:
        return await wait.edit(
            "⚠️ You must login first to generate links."
        )

    # Create USER client
    user = Client(
        "user_session",
        session_string=user_session,
        api_id=API_ID,
        api_hash=API_HASH
    )

    await user.connect()

    try:
        # Start external bot
        await user.send_message(ext_bot, f"/start {start_param}")

        await asyncio.sleep(2)

        # Read responses
        async for msg in user.get_chat_history(ext_bot, limit=5):
            if msg.text:
                await message.reply(
                    msg.text,
                    reply_markup=msg.reply_markup
                )

            elif msg.caption:
                if msg.photo:
                    await message.reply_photo(
                        msg.photo.file_id,
                        caption=msg.caption,
                        reply_markup=msg.reply_markup
                    )

            # Stop once button found
            if msg.reply_markup:
                break

        await wait.delete()

    except Exception as e:
        await wait.edit(f"❌ Error: {e}")

    finally:
        await user.disconnect()

# ======================
# RUN
# ======================
app.run()
