import os
import asyncio
import requests
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.sessions import StringSession
import random

load_dotenv()

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
STRING_SESSION = os.getenv("STRING_SESSION")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)

channels = {
    # -1001337701474: -1001956847541,  # Inline
    # -1002460046152: -1001694845676,  # Futbolishee
    # -1001295901534: -1001707418611,  # cristiano
    -1002339069316: -1002212791539,  # cyrax
    # -1002331884910: -1002273035080,  # Efuzpage
    # -1001449117896: -1002409602563,  # Stock
    # -1001062126548: -1001421061345,  # Sky
    # -1001100384194: -1001134200110,  # rma
    # -1001238413678: -1002125074069,  # just football
}

comments = [
    "ajoyib",
    "..."
]


def send_to_bot(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print(f"⚠️ Xatolik botga xabar yuborishda: {e}")


async def main():
    await client.start()
    print("✅ Userbot Railway'da ishga tushdi!")
    send_to_bot("✅ Userbot Railway'da ishga tushdi!")


@client.on(events.NewMessage(chats=list(channels.keys())))
async def handler(event):
    try:
        if event.is_channel:
            channel_id = event.chat_id
            linked_chat_id = channels.get(channel_id)

            entity = await client.get_entity(channel_id)
            channel_name = entity.title

            message = f"✅ Yangi post topildi! Kanal: {channel_name} (ID: {channel_id}), Post ID: {event.id}"
            print(message)
            send_to_bot(message)

            start_time = asyncio.get_event_loop().time()
            found = False

            while asyncio.get_event_loop().time() - start_time < 5:
                async for msg in client.iter_messages(linked_chat_id, limit=10):
                    if msg.forward and msg.forward.original_fwd:
                        if msg.forward.original_fwd.channel_post == event.id:
                            message = f"🔗 Ulangan post topildi! Guruhdagi ID: {msg.id}"
                            print(message)
                            send_to_bot(message)

                            comment = random.choice(comments)

                            await client.send_message(linked_chat_id, comment, reply_to=msg.id)

                            message = f"💬 Fikr bildirish bo‘limiga sharh yuborildi!: {comment}"
                            print(message)
                            send_to_bot(message)

                            found = True
                            break

                if found:
                    break

                await asyncio.sleep(0.3)

            if not found:
                message = "⛔ Guruhda mos post topilmadi!"
                print(message)
                send_to_bot(message)

    except Exception as e:
        message = f"⚠️ Xatolik: {e}"
        print(message)
        send_to_bot(message)


with client:
    client.loop.run_until_complete(main())
    client.run_until_disconnected()