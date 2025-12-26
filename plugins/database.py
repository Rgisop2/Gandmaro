import motor.motor_asyncio
from config import DB_NAME, DB_URI
import time

class Database:
    
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db.users
        self.relay_col = self.db.relay_config  # Added relay configuration collection

    def new_user(self, id, name):
        return dict(
            id = id,
            name = name,
            session = None,
            last_link_request = 0,  # Track last link request time for cooldown
        )
    
    async def add_user(self, id, name):
        user = self.new_user(id, name)
        await self.col.insert_one(user)
    
    async def is_user_exist(self, id):
        user = await self.col.find_one({'id':int(id)})
        return bool(user)
    
    async def total_users_count(self):
        count = await self.col.count_documents({})
        return count

    async def get_all_users(self):
        return self.col.find({})

    async def delete_user(self, user_id):
        await self.col.delete_many({'id': int(user_id)})

    async def set_session(self, id, session):
        await self.col.update_one({'id': int(id)}, {'$set': {'session': session}})

    async def get_session(self, id):
        user = await self.col.find_one({'id': int(id)})
        return user['session']

    async def set_bot_b_link(self, admin_id, link):
        """Store Bot B's start link in relay config"""
        await self.relay_col.update_one(
            {'_id': 'bot_b_link'},
            {'$set': {'link': link, 'set_by': admin_id, 'timestamp': time.time()}},
            upsert=True
        )
    
    async def get_bot_b_link(self):
        """Retrieve Bot B's start link"""
        config = await self.relay_col.find_one({'_id': 'bot_b_link'})
        return config['link'] if config else None
    
    async def set_user_link_cooldown(self, user_id, timestamp):
        """Update user's last link request timestamp for cooldown tracking"""
        await self.col.update_one(
            {'id': int(user_id)},
            {'$set': {'last_link_request': timestamp}}
        )
    
    async def get_user_link_cooldown(self, user_id):
        """Get user's last link request timestamp"""
        user = await self.col.find_one({'id': int(user_id)})
        return user.get('last_link_request', 0) if user else 0
    
    async def set_relay_user_session(self, session_string, admin_id):
        """Store relay user account session string"""
        await self.relay_col.update_one(
            {'_id': 'relay_session'},
            {'$set': {'session': session_string, 'set_by': admin_id, 'timestamp': time.time()}},
            upsert=True
        )
    
    async def get_relay_user_session(self):
        """Retrieve relay user account session string"""
        config = await self.relay_col.find_one({'_id': 'relay_session'})
        return config.get('session') if config else None

db = Database(DB_URI, DB_NAME)
