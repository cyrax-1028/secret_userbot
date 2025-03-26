import logging
import asyncpg
import asyncio
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_IDS = [int(i) for i in os.getenv("ADMIN_IDS", "").split(',') if i.strip().isdigit()]
SECRET_GROUP_ID = int(os.getenv("SECRET_GROUP_ID"))

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
db = None


async def init_db():
    global db
    db = await asyncpg.create_pool(DATABASE_URL)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            invited_count INT DEFAULT 0,
            referral_link TEXT,
            is_subscriber BOOLEAN DEFAULT FALSE,
            referrer_id BIGINT
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL
        )
    """)

    await db.execute("""
        ALTER TABLE users ADD COLUMN IF NOT EXISTS referrer_given BOOLEAN DEFAULT FALSE
    """)


async def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def is_subscribed(user_id: int) -> bool:
    channels = await db.fetch("SELECT username FROM channels")
    for channel in channels:
        try:
            member = await bot.get_chat_member(chat_id=f"@{channel['username']}", user_id=user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except Exception:
            return False
    return True


async def generate_invite_link():
    invite_link = await bot.create_chat_invite_link(SECRET_GROUP_ID, expire_date=None, member_limit=1)
    return invite_link.invite_link


async def get_or_create_user(user_id: int, referrer_id=None):
    ref_link = f"https://t.me/juristmind_bot?start={user_id}"
    user = await db.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)

    if not user:  # Foydalanuvchi bazada yo'q bo'lsa, yangisini qo'shamiz
        await db.execute(
            "INSERT INTO users (user_id, referral_link, referrer_id) VALUES ($1, $2, $3)",
            user_id, ref_link, referrer_id
        )
        return ref_link, True  # Yangi foydalanuvchi qo'shildi

    return ref_link, False  # Foydalanuvchi allaqachon bor


async def update_referrer(referrer_id: int):
    await db.execute("UPDATE users SET invited_count = invited_count + 1 WHERE user_id = $1", referrer_id)
    invited_count = await db.fetchval("SELECT invited_count FROM users WHERE user_id=$1", referrer_id)

    if invited_count >= 5:
        invite_link = await generate_invite_link()
        await bot.send_message(referrer_id,
                               f"🎉 Siz 5 ta odamni kanalga qo‘shdingiz!\n🔗 Guruhga kirish havolasi: {invite_link}")


@dp.message(Command("check"))
async def check_referrals(message: types.Message):
    user_id = message.from_user.id
    count = await db.fetchval("SELECT invited_count FROM users WHERE user_id=$1", user_id) or 0

    if count >= 5:
        invite_link = await generate_invite_link()
        await message.answer(f"🎉 Siz {count} ta odamni kanalga qo‘shdingiz! \n🔗 Guruhga kirish havolasi: {invite_link}")
    else:
        await message.answer(f"📊 Siz {count}/5 ta odamni taklif qildingiz.\n👥 Yana {5 - count} ta odam taklif qiling!")


@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id
    referrer_id = None

    if len(message.text.split()) > 1:
        referrer_id = message.text.split(" ")[1]
        if referrer_id.isdigit():
            referrer_id = int(referrer_id)

    ref_link, is_new_user = await get_or_create_user(user_id, referrer_id)

    if await is_admin(user_id):
        await message.answer(
            "👑 Siz adminsiz, obuna shart emas.\n\nAdmin buyruqlari => /admin")
        return

    if not await is_subscribed(user_id):
        await db.execute("UPDATE users SET is_subscriber = FALSE WHERE user_id = $1", user_id)
        channels = await db.fetch("SELECT username FROM channels")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ {channel['username']} ga a’zo bo‘lish",
                                  url=f"https://t.me/{channel['username']}")]
            for channel in channels
        ])
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔄 Tekshirish", callback_data="check_sub")])

        await message.answer("⚠️ Botdan foydalanish uchun quyidagi kanallarga a’zo bo‘ling:", reply_markup=keyboard)
        return

    await db.execute("UPDATE users SET is_subscriber = TRUE WHERE user_id = $1", user_id)

    user_data = await db.fetchrow("SELECT referrer_given FROM users WHERE user_id = $1", user_id)
    referrer_given = user_data["referrer_given"] if user_data else False

    print(f"User ID: {user_id}, Referrer ID: {referrer_id}, Referrer Given: {referrer_given}")

    if is_new_user and referrer_id and referrer_id != user_id and not referrer_given:
        print(f"Updating referrer {referrer_id} for user {user_id}")
        await update_referrer(referrer_id)  # Refererga bonus qo‘shish
        await db.execute("UPDATE users SET referrer_given = TRUE WHERE user_id = $1", user_id)

        # Yozilganini tekshiramiz
        check_data = await db.fetchrow("SELECT referrer_given FROM users WHERE user_id = $1", user_id)
        print(f"After update, Referrer Given: {check_data['referrer_given']}")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Do‘stlarga yuborish", url=f"https://t.me/share/url?url={ref_link}")]
    ])

    await message.answer(
        f"👋 Salom!\nSizning shaxsiy referal havolangiz:\n\n<code>{ref_link}</code>\n\nTekshirish uchun /check",
        reply_markup=keyboard
    )


@dp.callback_query(lambda c: c.data == "check_sub")
async def check_subscription(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id

    if await is_subscribed(user_id):
        await db.execute("UPDATE users SET is_subscriber = TRUE WHERE user_id = $1", user_id)

        user = await db.fetchrow("SELECT referrer_id, referrer_given FROM users WHERE user_id = $1", user_id)
        referrer_id = user["referrer_id"] if user else None
        referrer_given = user["referrer_given"] if user else False

        if referrer_id and referrer_id != user_id and not referrer_given:
            print(f"Checking referrer for user {user_id}. Referrer ID: {referrer_id}, Referrer Given: {referrer_given}")
            await update_referrer(referrer_id)
            await db.execute("UPDATE users SET referrer_given = TRUE WHERE user_id = $1", user_id)

        await callback_query.message.answer(
            "✅ Siz obuna bo‘lgansiz!\n /start buyrug'i orqali botni qaytadan ishga tushiring")
    else:
        await callback_query.answer("❌ Hali obuna bo‘lmagansiz!", show_alert=True)


@dp.message(Command("add_channel"))
async def add_channel(message: types.Message):
    if not await is_admin(message.from_user.id):
        await message.answer("❌ Bu buyruq faqat adminlar uchun!")
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Kanal username kiriting: <code>/add_channel KanalUsername</code>", parse_mode="HTML")
        return

    channel_username = args[1].replace("@", "")

    existing_channel = await db.fetchrow("SELECT username FROM channels WHERE username = $1", channel_username)
    if existing_channel:
        await message.answer(f"⚠️ @{channel_username} kanal allaqachon bazada mavjud.")
        return

    await db.execute("INSERT INTO channels (username) VALUES ($1)", channel_username)
    await message.answer(f"✅ @{channel_username} kanal qo‘shildi!")


@dp.message(Command("remove_channel"))
async def remove_channel(message: types.Message):
    if not await is_admin(message.from_user.id):
        await message.answer("❌ Bu buyruq faqat adminlar uchun!")
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Kanal username kiriting: <code>/add_channel KanalUsername</code>", parse_mode="HTML")
        return

    channel_username = args[1].replace("@", "")

    result = await db.execute("DELETE FROM channels WHERE username = $1 RETURNING username", channel_username)

    if result:
        await message.answer(f"🚫 @{channel_username} kanal o‘chirildi!")
    else:
        await message.answer(f"⚠️ @{channel_username} kanal bazada topilmadi.")


@dp.message(Command("channels"))
async def list_channels(message: types.Message):
    if not await is_admin(message.from_user.id):
        await message.answer("❌ Bu buyruq faqat adminlar uchun!")
        return

    channels = await db.fetch("SELECT username FROM channels")

    if not channels:
        await message.answer("⚠️ Hech qanday kanal qo‘shilmagan.")
        return

    channel_list = "\n".join([f"@{ch['username']}" for ch in channels])
    await message.answer(f"📌 Hozirgi kanallar:\n{channel_list}")


@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if not await is_admin(message.from_user.id):
        return

    admin_commands = """
🔧 <b>Admin Buyruqlari:</b>

/add_channel — Kanal qo‘shish
/remove_channel — Kanalni o‘chirish
/channels — Barcha kanallar ro‘yxati
    """

    await message.answer(admin_commands, parse_mode="HTML")


async def main():
    logging.basicConfig(level=logging.INFO)
    await init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
