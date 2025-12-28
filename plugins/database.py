import motor.motor_asyncio
from config import DB_NAME, DB_URI

class Database:
    
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.users_col = self.db.users
        self.links_col = self.db.links

    def new_user(self, id, name):
        return dict(
            id = id,
            name = name,
            session = None,
        )
    
    async def add_user(self, id, name):
        user = self.new_user(id, name)
        await self.users_col.insert_one(user)
    
    async def is_user_exist(self, id):
        user = await self.users_col.find_one({'id': int(id)})
        return bool(user)
    
    async def delete_user(self, user_id):
        await self.users_col.delete_many({'id': int(user_id)})

    async def set_session(self, admin_id, session):
        await self.users_col.update_one({'id': int(admin_id)}, {'$set': {'session': session}}, upsert=True)

    async def get_session(self, admin_id):
        user = await self.users_col.find_one({'id': int(admin_id)})
        if user:
            return user.get('session')
        return None

    async def save_link(self, unique_id, external_bot_link):
        """Save external bot link with unique ID"""
        await self.links_col.update_one(
            {'unique_id': unique_id},
            {'$set': {'external_bot_link': external_bot_link}},
            upsert=True
        )

    async def get_link(self, unique_id):
        """Retrieve external bot link by unique ID"""
        link_data = await self.links_col.find_one({'unique_id': unique_id})
        if link_data:
            return link_data.get('external_bot_link')
        return None

db = Database(DB_URI, DB_NAME)
