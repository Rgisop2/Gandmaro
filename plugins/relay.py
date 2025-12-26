import asyncio
import time
import re
from pyrogram import Client
from config import API_ID, API_HASH, RELAY_TIMEOUT

# Configuration
FLOODWAIT_DELAY = 2  # Delay between user account requests to avoid FloodWait

async def extract_link_from_response(message):
    """
    Extract the join link from Bot B's response.
    Could be:
    1. A button URL in inline keyboard
    2. A direct link in message text
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
        url_pattern = r'https?://(?:www\.)?t\.me/(?:joinchat|[a-zA-Z0-9_-]+)'
        matches = re.findall(url_pattern, message.text)
        if matches:
            link = matches[0]
    
    return link


async def fetch_fresh_link(user_id, bot_b_start_link, admin_session):
    """
    Use the logged-in user account session to fetch fresh link from Bot B.
    
    Args:
        user_id: The user requesting the link (for logging)
        bot_b_start_link: Bot B's start link containing the payload
        admin_session: The session string from admin's login (already authenticated user)
    """
    try:
        if not admin_session:
            return None, "Admin user account not logged in. Admin must use /login first."
        
        # Extract payload from Bot B link
        payload_match = re.search(r'start=([^\s&]+)', bot_b_start_link)
        payload = payload_match.group(1) if payload_match else ""
        
        # Extract bot username from link
        bot_match = re.search(r't\.me/([a-zA-Z0-9_]+)', bot_b_start_link)
        bot_username = bot_match.group(1) if bot_match else None
        
        if not bot_username:
            return None, "Invalid Bot B link format"
        
        if not payload:
            return None, "No payload found in Bot B link"
        
        print(f"[v0] Starting relay: bot_username={bot_username}, payload={payload}, for_user={user_id}")
        
        try:
            user_session = Client(
                f"relay_user_{user_id}",
                session_string=admin_session,
                api_id=API_ID,
                api_hash=API_HASH,
                in_memory=True
            )
            await user_session.connect()
            print(f"[v0] Admin session connected for relaying (user_id={user_id})")
        except Exception as e:
            print(f"[v0] Failed to connect admin session: {str(e)}")
            return None, f"Failed to initialize relay: {str(e)}"
        
        try:
            # Send /start command to Bot B
            await asyncio.sleep(FLOODWAIT_DELAY)
            
            print(f"[v0] Sending /start {payload} to @{bot_username}")
            await user_session.send_message(bot_username, f"/start {payload}")
            
            # Wait for Bot B's response with timeout
            response_msg = None
            start_time = time.time()
            
            async def get_bot_response():
                """Listen for response from Bot B"""
                try:
                    # Get last message from Bot B
                    async for msg in user_session.get_chat_history(bot_username, limit=1):
                        if msg.from_user and msg.from_user.is_bot and msg.from_user.username == bot_username:
                            return msg
                except:
                    pass
                return None
            
            # Poll for response with timeout
            while time.time() - start_time < RELAY_TIMEOUT:
                response_msg = await get_bot_response()
                if response_msg:
                    print(f"[v0] Received response from Bot B")
                    break
                await asyncio.sleep(0.5)
            
            if not response_msg:
                print("[v0] Timeout waiting for Bot B response")
                return None, "Bot B did not respond in time"
            
            # Extract link from response
            link = await extract_link_from_response(response_msg)
            
            if not link:
                print("[v0] Could not extract link from response")
                return None, "Could not extract link from Bot B's response"
            
            print(f"[v0] Successfully extracted link: {link}")
            return link, None
            
        finally:
            await user_session.disconnect()
            print(f"[v0] Admin session disconnected (user_id={user_id})")
    
    except Exception as e:
        print(f"[v0] Error in fetch_fresh_link: {str(e)}")
        return None, f"Error fetching link: {str(e)}"


async def relay_link_to_user(client, user_id, link):
    """
    Send the extracted link to user in the same format as Bot B.
    """
    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    try:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("REQUEST TO JOIN", url=link)]
        ])
        
        await client.send_message(
            user_id,
            "HERE IS YOUR LINK! CLICK BELOW TO PROCEED",
            reply_markup=keyboard
        )
        print(f"[v0] Link relayed to user {user_id}")
        return True
    except Exception as e:
        print(f"[v0] Error relaying link to user: {str(e)}")
        return False
