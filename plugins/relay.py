import asyncio
import time
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import API_ID, API_HASH
from plugins.database import db

# Configuration
LINK_REQUEST_COOLDOWN = 10  # Per-user cooldown in seconds
RELAY_TIMEOUT = 8  # Max time to wait for Bot B response
FLOODWAIT_DELAY = 2  # Delay between user account requests to avoid FloodWait

async def extract_link_from_response(message):
    """
    Extract the join link from Bot B's response.
    Could be:
    1. A button URL in inline keyboard
    2. A direct link in message text
    3. Or both
    """
    link = None
    
    # First, check for inline keyboard button
    if message.reply_markup and hasattr(message.reply_markup, 'inline_keyboard'):
        for row in message.reply_markup.inline_keyboard:
            for button in row:
                if button.url and ('join' in button.url.lower() or 'joinchat' in button.url.lower()):
                    link = button.url
                    break
            if link:
                break
    
    # If no button found, check message text for links
    if not link and message.text:
        # Look for telegram invite links in text
        import re
        url_pattern = r'https?://(?:www\.)?t\.me/(?:joinchat|[a-zA-Z0-9_-]+)'
        matches = re.findall(url_pattern, message.text)
        if matches:
            link = matches[0]
    
    return link


async def fetch_fresh_link(user_id, bot_b_start_link):
    """
    Use user account to fetch fresh link from Bot B.
    Bot B responds with link when /start <payload> is sent.
    """
    try:
        # Extract payload from the bot b link
        # Format: https://t.me/botusername?start=payload
        import re
        payload_match = re.search(r'start=([^\s&]+)', bot_b_start_link)
        payload = payload_match.group(1) if payload_match else ""
        
        # Extract bot username from link
        bot_match = re.search(r't\.me/([a-zA-Z0-9_]+)', bot_b_start_link)
        bot_username = bot_match.group(1) if bot_match else None
        
        if not bot_username:
            return None, "Invalid Bot B link format"
        
        # Create user account session client
        try:
            user_session = Client(
                f"relay_user_{user_id}",
                session_string=None,  # This would need actual user session
                api_id=API_ID,
                api_hash=API_HASH,
                in_memory=True  # Keep session in memory only
            )
            await user_session.connect()
        except Exception as e:
            return None, f"Failed to initialize user session: {str(e)}"
        
        try:
            # Send /start command to Bot B
            await asyncio.sleep(FLOODWAIT_DELAY)
            
            # Start the bot with payload
            await user_session.send_message(bot_username, f"/start {payload}")
            
            # Wait for Bot B's response
            async def wait_for_response():
                async with user_session.listen() as listener:
                    start_time = time.time()
                    while time.time() - start_time < RELAY_TIMEOUT:
                        response = await asyncio.wait_for(listener.get_response(), timeout=1)
                        
                        # Check if this is a response from Bot B (not another message)
                        if response.from_user and response.from_user.is_bot:
                            return response
                    return None
            
            response_msg = await wait_for_response()
            
            if not response_msg:
                return None, "Bot B did not respond in time"
            
            # Extract link from response
            link = await extract_link_from_response(response_msg)
            
            if not link:
                return None, "Could not extract link from Bot B's response"
            
            return link, None
            
        finally:
            await user_session.disconnect()
    
    except Exception as e:
        return None, f"Error fetching link: {str(e)}"


async def relay_link_to_user(client, user_id, link):
    """
    Send the extracted link to user in the same format as Bot B.
    """
    try:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("REQUEST TO JOIN", url=link)]
        ])
        
        await client.send_message(
            user_id,
            "HERE IS YOUR LINK! CLICK BELOW TO PROCEED",
            reply_markup=keyboard
        )
        return True
    except Exception as e:
        return False
      
