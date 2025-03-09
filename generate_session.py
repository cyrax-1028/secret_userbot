# import os
# from telethon.sync import TelegramClient
# from telethon.sessions import StringSession
# from dotenv import load_dotenv
#
# load_dotenv()
#
# API_ID = os.getenv("API_ID")
# API_HASH =os.getenv("API_HASH")
#
# with TelegramClient(StringSession(), API_ID, API_HASH) as client:
#     print("\n✅ Yangi STRING_SESSION yaratildi:")
#     print(client.session.save())