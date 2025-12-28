from os import environ

API_ID = int(environ.get("API_ID", "38627319"))
API_HASH = environ.get("API_HASH", "18b0827896e979267ae2251b63830827")
BOT_TOKEN = environ.get("BOT_TOKEN", "8298659033:AAGnS9bKVidzKOISev_Ek9GCQqFM0NykCkQ")

ADMIN_ID = int(environ.get("ADMIN_ID", "1327021082"))

ADMINS = int(environ.get("ADMINS", "1327021082"))

# Warning - Give Db uri in deploy server environment variable, don't give in repo.
DB_URI = environ.get("DB_URI", "mongodb+srv://poulomig644_db_user:d9MMUd5PsTP5MDFf@cluster0.q5evcku.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
DB_NAME = environ.get("DB_NAME", "vjjoinrequetbot")

# If this is True Then Bot Accept New Join Request 
NEW_REQ_MODE = bool(environ.get('NEW_REQ_MODE', False))
