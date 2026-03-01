"""
OpenBudget Telegram Bot - Python/aiogram 3 versiyasi
Barcha funksiyalar saqlangan + xatolar tuzatilgan
"""

import asyncio
import logging
import random
import re
import json
import os
import time
import glob
import hashlib
import uuid

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove,
    KeyboardButtonRequestContact
)
import aiohttp
import aiofiles

# ==================== SOZLAMALAR ====================

BOT_TOKEN = ""  # <-- Bu yerga bot tokeningizni kiriting

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_DIR = os.path.join(BASE_DIR, "users")
VOTES_DIR = os.path.join(BASE_DIR, "votes")
REQUESTS_DIR = os.path.join(BASE_DIR, "requests")
NOTIFICATIONS_DIR = os.path.join(BASE_DIR, "notifications")
REFERALS_DIR = os.path.join(BASE_DIR, "referals")
DATA_DIR = os.path.join(BASE_DIR, "data")
TMP_DIR = os.path.join(BASE_DIR, "tmp")

# Papkalarni yaratish
for d in [USERS_DIR, VOTES_DIR, REQUESTS_DIR, NOTIFICATIONS_DIR, REFERALS_DIR, DATA_DIR, TMP_DIR]:
    os.makedirs(d, exist_ok=True)

OPENBUDGET_API = "https://admin.openbudget.uz/api/v1/"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ==================== FSM HOLATLARI ====================

class UserStates(StatesGroup):
    validate_otp = State()
    exchange = State()

class AdminStates(StatesGroup):
    send_notification = State()
    clear_notification_confirm = State()
    set_project_id = State()
    set_description = State()
    set_vote_payment = State()
    set_ref_payment = State()
    add_owner = State()

# ==================== YORDAMCHI FUNKSIYALAR ====================

def get_random_ip():
    prefixes = ['46.227.123.', '37.110.212.', '46.255.69.', '62.209.128.',
                '37.110.214.', '31.135.209.', '37.110.213.']
    return random.choice(prefixes) + str(random.randint(1, 255))

def clear_phone(number: str) -> str:
    return re.sub(r'\D', '', number)

def validate_phone(number: str) -> bool:
    return bool(re.match(r'^998(90|91|93|94|95|97|98|99|33|88)\d{7}$', number))

def format_phone(number: str) -> str:
    m = re.match(r'^(998)(90|91|93|94|95|97|98|99|33|88)(\d{3})(\d{2})(\d{2})$', number)
    if m:
        return f"+{m.group(1)} ({m.group(2)}) {m.group(3)}-{m.group(4)}-{m.group(5)}"
    return number

def generate_uuid() -> str:
    return uuid.uuid4().hex[:12]

# ==================== DATA O'QISH/YOZISH ====================

def get_owners() -> list:
    f = os.path.join(DATA_DIR, "owners.dat")
    if not os.path.exists(f):
        return []
    content = open(f).read().strip()
    return [x.strip() for x in content.split("|") if x.strip()]

def save_owners(owners: list):
    with open(os.path.join(DATA_DIR, "owners.dat"), "w") as f:
        f.write("|".join(str(o) for o in owners))

def get_project_id() -> str:
    f = os.path.join(DATA_DIR, "porjectid.dat")
    return open(f).read().strip() if os.path.exists(f) else "0"

def save_project_id(val: str):
    with open(os.path.join(DATA_DIR, "porjectid.dat"), "w") as f:
        f.write(val)

def get_description() -> str:
    f = os.path.join(DATA_DIR, "description.dat")
    if os.path.exists(f):
        return open(f).read().strip()
    return "Xush kelibsiz!!!\n\nUshbu botga telefon raqam kiritib telefonga kelgan sms kodni 3 daqiqa ichida kiriting va har bir ovoz uchun pul ishlang!"

def save_description(val: str):
    with open(os.path.join(DATA_DIR, "description.dat"), "w") as f:
        f.write(val)

def get_vote_payment() -> int:
    f = os.path.join(DATA_DIR, "vote_payment.dat")
    return int(open(f).read().strip()) if os.path.exists(f) else 0

def save_vote_payment(val: int):
    with open(os.path.join(DATA_DIR, "vote_payment.dat"), "w") as f:
        f.write(str(val))

def get_ref_payment() -> int:
    f = os.path.join(DATA_DIR, "ref_payment.dat")
    return int(open(f).read().strip()) if os.path.exists(f) else 0

def save_ref_payment(val: int):
    with open(os.path.join(DATA_DIR, "ref_payment.dat"), "w") as f:
        f.write(str(val))

def get_message_status() -> str:
    f = os.path.join(DATA_DIR, "status.dat")
    return open(f).read().strip() if os.path.exists(f) else "on"

def set_message_status(val: str):
    with open(os.path.join(DATA_DIR, "status.dat"), "w") as f:
        f.write(val)

def get_notifications_count() -> int:
    return len(glob.glob(os.path.join(NOTIFICATIONS_DIR, "*.json")))

# Foydalanuvchi konfiguratsiyasi
def get_user_config(chat_id, key=None):
    f = os.path.join(USERS_DIR, f"{chat_id}.json")
    if not os.path.exists(f):
        return {} if key is None else None
    try:
        data = json.loads(open(f).read())
        if key is None:
            return data
        return data.get(key)
    except:
        return {} if key is None else None

def set_user_config(chat_id, key, value):
    f = os.path.join(USERS_DIR, f"{chat_id}.json")
    data = get_user_config(chat_id) or {}
    data[key] = value
    with open(f, "w") as fp:
        json.dump(data, fp, ensure_ascii=False)

def get_user_balance(chat_id) -> int:
    return int(get_user_config(chat_id, "balance") or 0)

def set_user_balance(chat_id, val: int):
    set_user_config(chat_id, "balance", str(val))

def get_user_votes_count(chat_id) -> int:
    return int(get_user_config(chat_id, "votes") or 0)

def get_user_referals(chat_id) -> int:
    return int(get_user_config(chat_id, "referals") or 0)

# Ovozlar
def check_phone_voted(phone: str) -> bool:
    for f in glob.glob(os.path.join(VOTES_DIR, "*.json")):
        try:
            data = json.loads(open(f).read())
            if data.get("phone") == phone:
                return True
        except:
            pass
    return False

def add_vote(data: dict) -> bool:
    fname = os.path.join(VOTES_DIR, hashlib.md5((generate_uuid() + str(time.time())).encode()).hexdigest() + ".json")
    if not os.path.exists(fname):
        with open(fname, "w") as f:
            json.dump(data, f, ensure_ascii=False)
        return True
    return False

def get_votes() -> list:
    votes = []
    for f in glob.glob(os.path.join(VOTES_DIR, "*.json")):
        try:
            data = json.loads(open(f).read())
            data["filename"] = f
            votes.append(data)
        except:
            pass
    votes.sort(key=lambda x: x.get("time", 0), reverse=True)
    return votes

def clear_votes():
    for f in glob.glob(os.path.join(VOTES_DIR, "*.json")):
        try:
            os.unlink(f)
        except:
            pass

# Foydalanuvchilar
def get_users(include_owners=False) -> list:
    owners = get_owners()
    users = []
    for f in glob.glob(os.path.join(USERS_DIR, "*.json")):
        try:
            chat_id = os.path.splitext(os.path.basename(f))[0]
            if not include_owners and chat_id in owners:
                continue
            data = json.loads(open(f).read())
            data["id"] = chat_id
            users.append(data)
        except:
            pass
    users.sort(key=lambda x: int(x.get("lastaction", 0) or 0), reverse=True)
    return users

# Murojaatlar
def get_applications() -> list:
    apps = []
    for f in glob.glob(os.path.join(REQUESTS_DIR, "*.json")):
        try:
            data = json.loads(open(f).read())
            data["filename"] = f
            apps.append(data)
        except:
            pass
    apps.sort(key=lambda x: x.get("time", 0), reverse=True)
    return apps

def add_request(data: dict) -> bool:
    fname = os.path.join(REQUESTS_DIR, f"{data['chat_id']}.json")
    if not os.path.exists(fname):
        with open(fname, "w") as f:
            json.dump(data, f, ensure_ascii=False)
        return True
    return False

# Bildirishnomalar
def add_notifications(message: dict):
    users = get_users(include_owners=True)
    for user in users:
        msg = dict(message)
        msg["chat_id"] = user["id"]
        fname = os.path.join(NOTIFICATIONS_DIR, hashlib.md5((generate_uuid() + str(time.time())).encode()).hexdigest() + ".json")
        with open(fname, "w") as f:
            json.dump(msg, f, ensure_ascii=False)
        time.sleep(0.001)

def clear_notifications():
    for f in glob.glob(os.path.join(NOTIFICATIONS_DIR, "*")):
        try:
            os.unlink(f)
        except:
            pass

# ==================== API ====================

async def openbudget_api(method: str, data: dict) -> dict:
    ip = get_random_ip()
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Host": "admin.openbudget.uz",
        "REMOTE_ADDR": ip,
        "HTTP_X_FORWARDED_FOR": ip,
        "HTTP_X_REAL_IP": ip,
        "X-Forwarded-For": ip,
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36"
    }
    url = OPENBUDGET_API + method
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data, headers=headers, ssl=False, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                status = resp.status
                try:
                    body = await resp.json(content_type=None)
                except:
                    body = {}
                return {"code": status, "data": body}
    except Exception as e:
        logger.error(f"API xatolik: {e}")
        return {"code": 0, "data": {"detail": str(e)}}

# ==================== KLAVIATURALAR ====================

def admin_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🗣 Ovozlar"), KeyboardButton(text="🏦 Murojaatlar")],
        [KeyboardButton(text="📝 Matn"), KeyboardButton(text="🗄 Loyiha")],
        [KeyboardButton(text="💴 Ovoz berish"), KeyboardButton(text="💶 Referal")],
        [KeyboardButton(text="✍️ Bildirishnoma"), KeyboardButton(text="🟢 Holat")],
        [KeyboardButton(text="📁 Excel"), KeyboardButton(text="🗑 Tozalash")],
        [KeyboardButton(text="👨‍👩‍👧 Foydalanuvchilar"), KeyboardButton(text="👨‍💻 Adminlar")],
    ], resize_keyboard=True)

def user_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📲 Telefon raqamni yuborish", request_contact=True)],
        [KeyboardButton(text="💳 Hisobim"), KeyboardButton(text="🔄 Pul yechib olish")],
        [KeyboardButton(text="🔗 Referal")],
    ], resize_keyboard=True)

def back_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🔙 Orqaga")]
    ], resize_keyboard=True)

def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="❌ Bekor qilish")]
    ], resize_keyboard=True)

def pagination_keyboard(current: int, total: int, type_name: str, query_val, extra_buttons=None) -> InlineKeyboardMarkup:
    nav = []
    if current > 0:
        from urllib.parse import urlencode
        nav.append(InlineKeyboardButton(
            text="◀️ Avvalgi",
            callback_data=f"{type_name}={query_val}&prev={current - 1}"
        ))
    if current < total - 1:
        nav.append(InlineKeyboardButton(
            text="Keyingi ▶️",
            callback_data=f"{type_name}={query_val}&next={current + 1}"
        ))
    rows = []
    if extra_buttons:
        rows.append(extra_buttons)
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ==================== XABAR FORMATLASH ====================

def format_user_message(user: dict, total: int) -> str:
    uid = user.get("id", "")
    lines = [f'🆔 <a href="tg://user?id={uid}">{uid}</a>', "—" * 30]
    if user.get("first_name"):
        lines.append(f"▫️ {user['first_name']}")
    if user.get("last_name"):
        lines.append(f"▫️ {user['last_name']}")
    if user.get("username"):
        lines.append(f"▫️ @{user['username']}")
    lines.append("—" * 30)
    if user.get("lastmessage"):
        lines.append(f"💬 {user['lastmessage']}")
    if user.get("lastaction"):
        t = time.strftime("%Y-%m-%d | %H:%M:%S", time.localtime(int(user["lastaction"])))
        lines.append(f"🕐 {t}")
    lines.append(f"💰 {get_user_balance(uid)} so'm")
    lines.append(f"🗣 {get_user_votes_count(uid)} ta ovoz")
    lines.append(f"🔗 {get_user_referals(uid)} referal")
    lines.append("—" * 30)
    lines.append(f"👥 Jami: {total}")
    return "\n".join(lines)

def format_owner_message(user: dict, total: int) -> str:
    uid = user.get("id", "")
    lines = [f'🆔 <a href="tg://user?id={uid}">{uid}</a>', "—" * 30]
    if user.get("first_name"):
        lines.append(f"▫️ {user['first_name']}")
    if user.get("last_name"):
        lines.append(f"▫️ {user['last_name']}")
    if user.get("username"):
        lines.append(f"▫️ @{user['username']}")
    lines.append("—" * 30)
    lines.append(f"👥 Jami: {total}")
    return "\n".join(lines)

def format_vote_message(vote: dict, total: int) -> str:
    uid = str(vote.get("chat_id", ""))
    users = get_users(include_owners=True)
    user = next((u for u in users if str(u.get("id")) == uid), {})
    lines = []
    if user.get("id"):
        lines += [f'🆔 <a href="tg://user?id={user["id"]}">{user["id"]}</a>', "—" * 30]
    if user.get("first_name"):
        lines.append(f"▫️ {user['first_name']}")
    if user.get("last_name"):
        lines.append(f"▫️ {user['last_name']}")
    if user.get("username"):
        lines.append(f"▫️ @{user['username']}")
    lines.append("—" * 30)
    t = time.strftime("%Y-%m-%d | %H:%M:%S", time.localtime(int(vote.get("time", 0))))
    lines.append(f"🕐 {t}")
    lines.append("—" * 30)
    lines.append(f"📞 {format_phone(vote.get('phone', ''))}")
    lines.append(f"💰 {get_user_balance(uid)} so'm")
    lines.append(f"🗣 {get_user_votes_count(uid)} ta ovoz")
    lines.append("—" * 30)
    lines.append(f"📝 Jami: {total}")
    return "\n".join(lines)

def format_application_message(app: dict, total: int) -> str:
    uid = str(app.get("chat_id", ""))
    users = get_users(include_owners=True)
    user = next((u for u in users if str(u.get("id")) == uid), {})
    lines = []
    if user.get("id"):
        lines += [f'🆔 <a href="tg://user?id={user["id"]}">{user["id"]}</a>', "—" * 30]
    if user.get("first_name"):
        lines.append(f"▫️ {user['first_name']}")
    if user.get("last_name"):
        lines.append(f"▫️ {user['last_name']}")
    if user.get("username"):
        lines.append(f"▫️ @{user['username']}")
    lines.append("—" * 30)
    t = time.strftime("%Y-%m-%d | %H:%M:%S", time.localtime(int(app.get("time", 0))))
    lines.append(f"🕐 {t}")
    lines.append("—" * 30)
    lines.append(f"🆔 Karta/Tel: {app.get('text', '')}")
    lines.append(f"💰 {get_user_balance(uid)} so'm")
    lines.append("—" * 30)
    lines.append(f"📝 Jami: {total}")
    return "\n".join(lines)

# ==================== EXCEL EXPORT ====================

def export_to_excel() -> str:
    """Foydalanuvchilarni CSV ga export qilish"""
    import csv
    fname = os.path.join(TMP_DIR, "users_export.csv")
    users = get_users(include_owners=True)
    with open(fname, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "Ism", "Familiya", "Username", "Balans", "Ovozlar", "Referallar", "Oxirgi harakat"])
        for user in users:
            uid = user.get("id", "")
            last = ""
            if user.get("lastaction"):
                last = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(user["lastaction"])))
            writer.writerow([
                uid,
                user.get("first_name", ""),
                user.get("last_name", ""),
                user.get("username", ""),
                get_user_balance(uid),
                get_user_votes_count(uid),
                get_user_referals(uid),
                last
            ])
    return fname

# ==================== PHONE VALIDATION ====================

async def process_phone_validation(bot: Bot, chat_id: int, phone: str, state: FSMContext):
    """Telefon raqamni OpenBudget API orqali tekshirish"""
    application = get_project_id()

    # Avval local vote bazasida tekshirish
    if check_phone_voted(phone):
        await bot.send_message(chat_id, "⚠️ Bu raqam avval ovoz berish uchun ishlatilgan")
        return

    data = await openbudget_api("user/validate_phone/", {
        "phone": phone,
        "application": application,
    })

    if data["code"] == 200 and data["data"].get("token"):
        token = data["data"]["token"]
        # State ga saqlash
        await state.set_state(UserStates.validate_otp)
        await state.update_data(phone=phone, token=token, token_time=time.time())
        await bot.send_message(
            chat_id,
            "⏳ Iltimos sms orqali yuborilgan kodni kiriting",
            reply_markup=cancel_keyboard()
        )
    elif data["code"] == 400 and data["data"].get("detail") == "This number was used to vote":
        await bot.send_message(chat_id, "⚠️ Bu raqam avval ovoz berish uchun ishlatilgan")
    else:
        approximate_time = ""
        detail = data["data"].get("detail", "") if isinstance(data["data"], dict) else ""
        m = re.search(r'Expected available in (\d+) seconds\.', str(detail))
        if m:
            t = time.strftime("%Y-%m-%d | %H:%M:%S", time.localtime(time.time() + int(m.group(1))))
            approximate_time = f". Taxminiy vaqt: {t}"
        await bot.send_message(
            chat_id,
            f"⚠️ Openbudget saytida yuklama oshganligi sababli ulanishlarda xatolik yuz berdi. "
            f"Iltimos keyinroq ovoz berishga qaytadan urinib ko'ring{approximate_time}"
        )

# ==================== ROUTER ====================

router = Router()

# ==================== /start ====================

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    chat_id = str(message.from_user.id)
    owners = get_owners()

    # Foydalanuvchi ma'lumotlarini saqlash
    set_user_config(chat_id, "first_name", message.from_user.first_name or "")
    set_user_config(chat_id, "last_name", message.from_user.last_name or "")
    set_user_config(chat_id, "username", message.from_user.username or "")
    set_user_config(chat_id, "lastaction", str(int(time.time())))

    # Referal tekshirish: /start 123456789
    args = message.text.split()
    if len(args) > 1 and args[1].isdigit():
        ref_id = args[1]
        referal_file = os.path.join(REFERALS_DIR, f"{chat_id}")
        if ref_id != chat_id and not os.path.exists(referal_file):
            ref_payment = get_ref_payment()
            old_balance = get_user_balance(ref_id)
            set_user_balance(ref_id, old_balance + ref_payment)
            old_refs = get_user_referals(ref_id)
            set_user_config(ref_id, "referals", str(old_refs + 1))
            with open(referal_file, "w") as f:
                f.write(ref_id)
            try:
                await message.bot.send_message(int(ref_id), "ℹ️ Sizda yangi referal mavjud")
            except:
                pass

    description = get_description()
    text = f"{description}\n\n<b>Ovoz berish uchun telefon raqamingizni yuboring.</b>\n\nNamuna: <em>919992543</em>"

    if chat_id in owners:
        await message.answer(text, reply_markup=admin_keyboard(), parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=user_keyboard(), parse_mode="HTML")

async def send_start_message(bot: Bot, chat_id: int | str, custom_text: str = ""):
    owners = get_owners()
    description = get_description()
    text = custom_text if custom_text else f"{description}\n\n<b>Ovoz berish uchun telefon raqamingizni yuboring.</b>\n\nNamuna: <em>919992543</em>"
    kbd = admin_keyboard() if str(chat_id) in owners else user_keyboard()
    await bot.send_message(int(chat_id), text, reply_markup=kbd, parse_mode="HTML")

# ==================== FOYDALANUVCHI HANDLERLARI ====================

@router.message(F.text == "💳 Hisobim")
async def user_balance(message: Message):
    balance = get_user_balance(str(message.from_user.id))
    await message.answer(f"💰 Hisobda <b>{balance} so'm</b> mavjud", parse_mode="HTML")

@router.message(F.text == "🔗 Referal")
async def user_referal(message: Message):
    chat_id = str(message.from_user.id)
    ref_payment = get_ref_payment()
    refs = get_user_referals(chat_id)
    bot_info = await message.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={chat_id}"
    await message.answer(
        f"ℹ️ Referal manzil orqali do'stlaringizni botga taklif qiling va \"pul\" ishlab toping. "
        f"Har bir referal uchun {ref_payment} so'mdan taqdim etiladi.\n\n"
        f"👨‍👩‍👦 Referal orqali qo'shilganlar: {refs} dona\n\n"
        f"Sizning referal manzilingiz 👇\n\n{link}"
    )

@router.message(F.text == "🔄 Pul yechib olish")
async def user_exchange_start(message: Message, state: FSMContext):
    await state.set_state(UserStates.exchange)
    await message.answer(
        "👉 <b>Pul</b> yechib olish uchun iltimos <b>Telefon yoki Karta</b> raqamni kiriting.\n\n"
        "<em>ℹ️ Minimal pul yechish miqdori: 10 000 so'm</em>",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )

@router.message(UserStates.exchange)
async def user_exchange_process(message: Message, state: FSMContext):
    if message.text in ["❌ Bekor qilish", "/bekor"]:
        await state.clear()
        await send_start_message(message.bot, message.from_user.id, "ℹ️ Jarayon bekor qilindi")
        return

    chat_id = str(message.from_user.id)
    balance = get_user_balance(chat_id)
    if balance < 10000:
        await state.clear()
        await send_start_message(
            message.bot, message.from_user.id,
            "⚠️ Kechirasiz, ayriboshlash uchun hisob yetarli emas.\n\n<em>ℹ️ Minimal pul yechish miqdori: 10 000 so'm</em>"
        )
        return

    success = add_request({
        "chat_id": chat_id,
        "time": int(time.time()),
        "text": clear_phone(message.text)
    })
    await state.clear()
    if success:
        await send_start_message(message.bot, message.from_user.id, "✅ Pul yechib olish uchun so'rov muvaffaqiyatli yuborildi")
    else:
        await send_start_message(
            message.bot, message.from_user.id,
            "⏳ Kechirasiz sizda avvalroq yuborilgan so'rov mavjud. Iltimos, jarayon yakunlanishini kuting."
        )

@router.message(UserStates.validate_otp)
async def user_otp_process(message: Message, state: FSMContext):
    if message.text in ["❌ Bekor qilish", "/bekor"]:
        await state.clear()
        await send_start_message(message.bot, message.from_user.id, "ℹ️ Jarayon bekor qilindi")
        return

    chat_id = str(message.from_user.id)
    data = await state.get_data()
    phone = data.get("phone")
    token = data.get("token")
    token_time = data.get("token_time", 0)
    application = get_project_id()

    # OTP 3 daqiqa ichida bo'lishi kerak (TUZATILDI: PHP dagi mantiq xatosi)
    if time.time() - token_time > 180:
        await state.clear()
        await send_start_message(
            message.bot, message.from_user.id,
            "🚫 Tasdiqlash kodini kiritish vaqti tugagan. Iltimos qaytadan so'rov yuboring"
        )
        return

    result = await openbudget_api("user/temp/vote/", {
        "phone": phone,
        "token": token,
        "otp": message.text,
        "application": application,
    })

    if result["code"] == 200:
        vote_payment = get_vote_payment()
        old_balance = get_user_balance(chat_id)
        new_balance = old_balance + vote_payment
        set_user_balance(chat_id, new_balance)
        old_votes = get_user_votes_count(chat_id)
        set_user_config(chat_id, "votes", str(old_votes + 1))
        add_vote({
            "time": int(time.time()),
            "chat_id": chat_id,
            "phone": phone
        })
        await state.clear()
        await send_start_message(
            message.bot, message.from_user.id,
            f"✅ Ovoz qabul qilindi.\nHisobdagi mablag': <b>{new_balance} so'm</b>\n\n"
            "👉 Ovoz berib pul ishlashda davom etish uchun telefon raqam kiring..."
        )
    elif result["code"] == 400 and result["data"].get("detail") == "Invalid code":
        await message.answer("❌ Tasdiqlash kodi xato kiritildi")
    else:
        detail = result["data"].get("detail", "") if isinstance(result["data"], dict) else ""
        approximate_time = ""
        m = re.search(r'Expected available in (\d+) seconds\.', str(detail))
        if m:
            t = time.strftime("%Y-%m-%d | %H:%M:%S", time.localtime(time.time() + int(m.group(1))))
            approximate_time = f". Taxminiy vaqt: {t}"
        await state.clear()
        await send_start_message(
            message.bot, message.from_user.id,
            f"❌ Openbudget saytida yuklama oshganligi sababli xatolik yuz berdi. "
            f"Iltimos keyinroq qaytadan urinib ko'ring{approximate_time}"
        )

# ==================== KONTAKT QABUL QILISH ====================

@router.message(F.contact)
async def contact_received(message: Message, state: FSMContext):
    phone = clear_phone(message.contact.phone_number)
    if validate_phone(phone):
        await process_phone_validation(message.bot, message.from_user.id, phone, state)
    else:
        await message.answer("⚠️ Kechirasiz telefon raqam formati mos emas yoki raqam O'zbekiston hududidan tashqarida")

# ==================== MATN ORQALI RAQAM ====================

@router.message(F.text.regexp(r'^[+]?998') | F.text.regexp(r'^\d{9}$'))
async def phone_text_received(message: Message, state: FSMContext):
    # OTP holati bo'lsa, OTP handler ishlaydi
    current_state = await state.get_state()
    if current_state == UserStates.validate_otp:
        return

    text = message.text.strip()
    if len(text) == 9:
        text = "998" + text
    phone = clear_phone(text)
    if validate_phone(phone):
        await process_phone_validation(message.bot, message.from_user.id, phone, state)
    else:
        await message.answer("⚠️ Kechirasiz telefon raqam formati mos emas yoki raqam O'zbekiston hududidan tashqarida")

# ==================== ADMIN HANDLERLARI ====================

def is_admin(chat_id) -> bool:
    return str(chat_id) in get_owners()

@router.message(F.text == "🔙 Orqaga")
async def back_handler(message: Message, state: FSMContext):
    await state.clear()
    await send_start_message(message.bot, message.from_user.id, "👉 Asosiy menyu")

@router.message(F.text == "❌ Bekor qilish")
async def cancel_handler(message: Message, state: FSMContext):
    await state.clear()
    await send_start_message(message.bot, message.from_user.id, "ℹ️ Jarayon bekor qilindi")

# ---- OVOZLAR ----
@router.message(F.text == "🗣 Ovozlar")
async def admin_votes(message: Message):
    if not is_admin(message.from_user.id):
        return
    votes = get_votes()
    total = len(votes)
    if total == 0:
        await message.answer("⚠️ Ovozlar mavjud emas")
        return
    vote = votes[0]
    text = format_vote_message(vote, total)
    kbd = pagination_keyboard(0, total, "votes", vote.get("time", ""))
    await message.answer(text, reply_markup=kbd, parse_mode="HTML")

# ---- FOYDALANUVCHILAR ----
@router.message(F.text == "👨‍👩‍👧 Foydalanuvchilar")
async def admin_users(message: Message):
    if not is_admin(message.from_user.id):
        return
    users = get_users()
    total = len(users)
    if total == 0:
        await message.answer("⚠️ Foydalanuvchilar mavjud emas")
        return
    user = users[0]
    text = format_user_message(user, total)
    kbd = pagination_keyboard(0, total, "users", user.get("id", ""))
    await message.answer(text, reply_markup=kbd, parse_mode="HTML")

# ---- MUROJAATLAR ----
@router.message(F.text == "🏦 Murojaatlar")
async def admin_applications(message: Message):
    if not is_admin(message.from_user.id):
        return
    apps = get_applications()
    total = len(apps)
    if total == 0:
        await message.answer("❌ Murojaatlar mavjud emas")
        return
    app = apps[0]
    text = format_application_message(app, total)
    kbd = pagination_keyboard(0, total, "app", app.get("time", ""), extra_buttons=[
        InlineKeyboardButton(text="✅ Bajarildi", callback_data=f"app_s={app['chat_id']}")
    ])
    await message.answer(text, reply_markup=kbd, parse_mode="HTML")

# ---- BILDIRISHNOMA ----
@router.message(F.text == "✍️ Bildirishnoma")
async def admin_notification_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminStates.send_notification)
    await message.answer(
        "📢 Foydalanuvchilarga bildirishnoma yuborish uchun quyida xabarni kiriting...",
        reply_markup=back_keyboard()
    )

@router.message(AdminStates.send_notification, F.text)
async def admin_notification_text(message: Message, state: FSMContext):
    if message.text == "🔙 Orqaga":
        await state.clear()
        await send_start_message(message.bot, message.from_user.id, "👉 Asosiy menyu")
        return
    if len(message.text) < 10:
        await message.answer("<em>🛑 Kechirasiz, bildirishnoma matni 10 dona belgidan kam bo'lmasligi lozim.</em>", parse_mode="HTML")
        return
    add_notifications({"text": message.text})
    await state.clear()
    await send_start_message(message.bot, message.from_user.id, "✅ Foydalanuvchilarga bildirishnoma yuborish jarayoni boshlandi")

@router.message(AdminStates.send_notification, F.photo)
async def admin_notification_photo(message: Message, state: FSMContext):
    photo = message.photo[-1].file_id
    caption = message.caption or ""
    add_notifications({"photo": photo, "caption": caption})
    await state.clear()
    await send_start_message(message.bot, message.from_user.id, "✅ Foydalanuvchilarga bildirishnoma yuborish jarayoni boshlandi")

@router.message(AdminStates.send_notification, F.video)
async def admin_notification_video(message: Message, state: FSMContext):
    video = message.video.file_id
    caption = message.caption or ""
    add_notifications({"video": video, "caption": caption})
    await state.clear()
    await send_start_message(message.bot, message.from_user.id, "✅ Foydalanuvchilarga bildirishnoma yuborish jarayoni boshlandi")

# ---- HOLAT ----
@router.message(F.text == "🟢 Holat")
async def admin_status(message: Message):
    if not is_admin(message.from_user.id):
        return
    status = get_message_status()
    count = get_notifications_count()
    icon = "🟢" if status == "on" else "🔴"
    kbd = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🟢", callback_data="status=on"),
            InlineKeyboardButton(text="🔄", callback_data="status=check"),
            InlineKeyboardButton(text="🔴", callback_data="status=off"),
        ],
        [InlineKeyboardButton(text="🗑 Tozalash", callback_data="clear=true")]
    ])
    await message.answer(
        f"Bildirishnoma yuborish holati: {icon}\n\n⏳ Jarayondagi xabarlar: {count}",
        reply_markup=kbd
    )

# ---- LOYIHA ID ----
@router.message(F.text == "🗄 Loyiha")
async def admin_project_id(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminStates.set_project_id)
    await message.answer(
        f"🆔 Iltimos loyiha identifikatori kiriting\n\n👉 Joriy identifikator: {get_project_id()}",
        reply_markup=back_keyboard()
    )

@router.message(AdminStates.set_project_id)
async def admin_project_id_set(message: Message, state: FSMContext):
    if message.text == "🔙 Orqaga":
        await state.clear()
        await send_start_message(message.bot, message.from_user.id, "👉 Asosiy menyu")
        return
    save_project_id(message.text)
    await state.clear()
    await send_start_message(message.bot, message.from_user.id, "ℹ️ Ma'lumot muvaffaqiyatli yangilandi")

# ---- TAVSIF ----
@router.message(F.text == "📝 Matn")
async def admin_description(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminStates.set_description)
    await message.answer(
        f"💬 Iltimos loyiha tavsifini kiriting\n\n👉 Joriy matn: {get_description()}",
        reply_markup=back_keyboard()
    )

@router.message(AdminStates.set_description)
async def admin_description_set(message: Message, state: FSMContext):
    if message.text == "🔙 Orqaga":
        await state.clear()
        await send_start_message(message.bot, message.from_user.id, "👉 Asosiy menyu")
        return
    save_description(message.text)
    await state.clear()
    await send_start_message(message.bot, message.from_user.id, "ℹ️ Ma'lumot muvaffaqiyatli yangilandi")

# ---- OVOZ TO'LOVI ----
@router.message(F.text == "💴 Ovoz berish")
async def admin_vote_payment(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminStates.set_vote_payment)
    await message.answer(
        f"💴 Iltimos har bir ovoz summasini kiriting\n\n👉 Joriy summa: {get_vote_payment()}",
        reply_markup=back_keyboard()
    )

@router.message(AdminStates.set_vote_payment)
async def admin_vote_payment_set(message: Message, state: FSMContext):
    if message.text == "🔙 Orqaga":
        await state.clear()
        await send_start_message(message.bot, message.from_user.id, "👉 Asosiy menyu")
        return
    if message.text.isdigit():
        save_vote_payment(int(message.text))
        await state.clear()
        await send_start_message(message.bot, message.from_user.id, "ℹ️ Ma'lumot muvaffaqiyatli yangilandi")
    else:
        await message.answer("⚠️ Iltimos faqat raqam kiriting")

# ---- REFERAL TO'LOVI ----
@router.message(F.text == "💶 Referal")
async def admin_ref_payment(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminStates.set_ref_payment)
    await message.answer(
        f"💴 Iltimos har bir referal summasini kiriting\n\n👉 Joriy summa: {get_ref_payment()}",
        reply_markup=back_keyboard()
    )

@router.message(AdminStates.set_ref_payment)
async def admin_ref_payment_set(message: Message, state: FSMContext):
    if message.text == "🔙 Orqaga":
        await state.clear()
        await send_start_message(message.bot, message.from_user.id, "👉 Asosiy menyu")
        return
    if message.text.isdigit():
        save_ref_payment(int(message.text))
        await state.clear()
        await send_start_message(message.bot, message.from_user.id, "ℹ️ Ma'lumot muvaffaqiyatli yangilandi")
    else:
        await message.answer("⚠️ Iltimos faqat raqam kiriting")

# ---- EXCEL ----
@router.message(F.text == "📁 Excel")
async def admin_excel(message: Message):
    if not is_admin(message.from_user.id):
        return
    fname = export_to_excel()
    await message.answer_document(
        document=open(fname, "rb"),
        caption="📊 Foydalanuvchilar ma'lumotlari"
    )

# ---- TOZALASH ----
@router.message(F.text == "🗑 Tozalash")
async def admin_clear(message: Message):
    if not is_admin(message.from_user.id):
        return
    kbd = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tozalash", callback_data="clearvote=yes")]
    ])
    await message.answer("Siz chindan ham ovozlarni tozalamoqchimisiz?", reply_markup=kbd)

# ---- ADMINLAR ----
@router.message(F.text == "👨‍💻 Adminlar")
async def admin_owners_list(message: Message):
    if not is_admin(message.from_user.id):
        return
    owners = get_owners()
    total = len(owners)
    if total == 0:
        await message.answer("⚠️ Adminlar mavjud emas")
        return
    owner_id = owners[0]
    user_data = get_user_config(owner_id) or {}
    user_data["id"] = owner_id
    text = format_owner_message(user_data, total)
    kbd = pagination_keyboard(0, total, "owner", owner_id, extra_buttons=[
        InlineKeyboardButton(text="➕ Qo'shish", callback_data="addowner=yes"),
        InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"removeowner={owner_id}"),
    ])
    await message.answer(text, reply_markup=kbd, parse_mode="HTML")

@router.message(AdminStates.add_owner)
async def admin_add_owner_set(message: Message, state: FSMContext):
    if message.text == "🔙 Orqaga":
        await state.clear()
        await send_start_message(message.bot, message.from_user.id, "👉 Asosiy menyu")
        return
    owner_id = clear_phone(message.text)
    owners = get_owners()
    if owner_id not in owners:
        owners.append(owner_id)
        save_owners(owners)
    await state.clear()
    await send_start_message(message.bot, message.from_user.id, "ℹ️ Admin muvaffaqiyatli qo'shildi")

# ==================== CALLBACK HANDLERLARI ====================

def parse_callback(data: str) -> dict:
    """callback_data ni parse qilish"""
    result = {}
    for part in data.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            result[k] = v
    return result

@router.callback_query()
async def callback_handler(callback: CallbackQuery, state: FSMContext):
    data = parse_callback(callback.data)
    chat_id = str(callback.message.chat.id)
    msg = callback.message

    # STATUS
    if "status" in data:
        s = data["status"]
        if s in ["on", "off"]:
            set_message_status(s)
        status = get_message_status()
        count = get_notifications_count()
        icon = "🟢" if status == "on" else "🔴"
        try:
            await callback.message.edit_text(
                f"Bildirishnoma yuborish holati: {icon}\n\n⏳ Jarayondagi xabarlar: {count}",
                reply_markup=callback.message.reply_markup,
                parse_mode="HTML"
            )
        except:
            pass
        text = "Holat o'zgartirildi" if s in ["on", "off"] else "Natija yangilandi"
        await callback.answer(text)

    # CLEAR NOTIFICATION
    elif "clear" in data and data["clear"] == "true":
        await state.set_state(AdminStates.clear_notification_confirm)
        kbd = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="👍 Ha"), KeyboardButton(text="🙅‍♂️ Yo'q")],
            [KeyboardButton(text="🔙 Orqaga")]
        ], resize_keyboard=True)
        await callback.message.answer("⚠️ Siz chindan ham jarayondagi bildirishnomalarni o'chirmoqchimisiz?", reply_markup=kbd)
        await callback.answer("Variantlardan birini tanlang")

    # ADD OWNER
    elif "addowner" in data:
        await state.set_state(AdminStates.add_owner)
        try:
            await callback.bot.delete_message(msg.chat.id, msg.message_id)
        except:
            pass
        await callback.message.answer("🆔 Admin qo'shish uchun identifikator kiriting", reply_markup=back_keyboard())
        await callback.answer("Ma'lumotni kiriting")

    # REMOVE OWNER
    elif "removeowner" in data:
        rm_id = data["removeowner"]
        owners = get_owners()
        owners = [o for o in owners if o != rm_id]
        save_owners(owners)
        try:
            await callback.bot.delete_message(msg.chat.id, msg.message_id)
        except:
            pass
        await callback.answer("Admin o'chirildi")
        await send_start_message(callback.bot, chat_id, "✅ Admin o'chirildi")

    # CLEAR VOTES
    elif "clearvote" in data and data["clearvote"] == "yes":
        clear_votes()
        try:
            await callback.bot.delete_message(msg.chat.id, msg.message_id)
        except:
            pass
        await callback.message.answer("Ma'lumotlar o'chirildi")
        await callback.answer("Ma'lumotlar tozalandi")

    # PAGINATION - OWNERS
    elif "owner" in data:
        owners = get_owners()
        total = len(owners)
        page = int(data.get("prev", data.get("next", 0)))
        if page < total:
            owner_id = owners[page]
            user_data = get_user_config(owner_id) or {}
            user_data["id"] = owner_id
            text = format_owner_message(user_data, total)
            kbd = pagination_keyboard(page, total, "owner", owner_id, extra_buttons=[
                InlineKeyboardButton(text="➕ Qo'shish", callback_data="addowner=yes"),
                InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"removeowner={owner_id}"),
            ])
            try:
                await msg.edit_text(text, reply_markup=kbd, parse_mode="HTML")
            except:
                pass
            await callback.answer("Natija yangilandi")
        else:
            await callback.answer("Natijalar topilmadi")

    # PAGINATION - USERS
    elif "users" in data:
        users = get_users()
        total = len(users)
        page = int(data.get("prev", data.get("next", 0)))
        if page < total:
            user = users[page]
            text = format_user_message(user, total)
            kbd = pagination_keyboard(page, total, "users", user.get("id", ""))
            try:
                await msg.edit_text(text, reply_markup=kbd, parse_mode="HTML")
            except:
                pass
            await callback.answer("Natija yangilandi")
        else:
            await callback.answer("Natijalar topilmadi")

    # PAGINATION - VOTES
    elif "votes" in data:
        votes = get_votes()
        total = len(votes)
        page = int(data.get("prev", data.get("next", 0)))
        if page < total:
            vote = votes[page]
            text = format_vote_message(vote, total)
            kbd = pagination_keyboard(page, total, "votes", vote.get("time", ""))
            try:
                await msg.edit_text(text, reply_markup=kbd, parse_mode="HTML")
            except:
                pass
            await callback.answer("Natija yangilandi")
        else:
            await callback.answer("Natijalar topilmadi")

    # PAGINATION - APPLICATIONS
    elif "app" in data and "app_s" not in data:
        apps = get_applications()
        total = len(apps)
        page = int(data.get("prev", data.get("next", 0)))
        if page < total:
            app = apps[page]
            text = format_application_message(app, total)
            kbd = pagination_keyboard(page, total, "app", app.get("time", ""), extra_buttons=[
                InlineKeyboardButton(text="✅ Bajarildi", callback_data=f"app_s={app['chat_id']}")
            ])
            try:
                await msg.edit_text(text, reply_markup=kbd, parse_mode="HTML")
            except:
                pass
            await callback.answer("Natija yangilandi")
        else:
            await callback.answer("Natijalar topilmadi")

    # APPLICATION DONE
    elif "app_s" in data:
        target_id = data["app_s"]
        set_user_balance(target_id, 0)
        req_file = os.path.join(REQUESTS_DIR, f"{target_id}.json")
        if os.path.exists(req_file):
            os.unlink(req_file)
        try:
            await callback.bot.send_message(int(target_id), "✅ Pul ayriboshlash muvaffaqiyatli amalga oshirildi")
        except:
            pass
        await callback.answer("✅ Harakat muvaffaqiyatli bajarildi", show_alert=True)
        try:
            await callback.bot.delete_message(msg.chat.id, msg.message_id)
        except:
            pass
        # Keyingi murojaatni ko'rsatish
        apps = get_applications()
        if apps:
            app = apps[0]
            text = format_application_message(app, len(apps))
            kbd = pagination_keyboard(0, len(apps), "app", app.get("time", ""), extra_buttons=[
                InlineKeyboardButton(text="✅ Bajarildi", callback_data=f"app_s={app['chat_id']}")
            ])
            await callback.message.answer(text, reply_markup=kbd, parse_mode="HTML")
        else:
            await callback.message.answer("❌ Murojaatlar mavjud emas")

# ---- NOTIFICATION CONFIRM ----
@router.message(AdminStates.clear_notification_confirm)
async def admin_clear_confirm(message: Message, state: FSMContext):
    if message.text == "👍 Ha":
        clear_notifications()
        await state.clear()
        await send_start_message(message.bot, message.from_user.id, "✅ Jarayondagi bildirishnomalar muvaffaqiyatli tozalandi.")
    else:
        await state.clear()
        await send_start_message(message.bot, message.from_user.id, "Asosiy menyu 👇")

# ---- NOMA'LUM XABAR ----
@router.message()
async def unknown_message(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state:
        return
    await message.answer("Kechirasiz men sizni tushuna olmadim 🤷‍♂️")

# ==================== BILDIRISHNOMA YUBORUVCHI ====================

async def notification_sender(bot: Bot):
    """Bildirishnomalarni fon jarayonida yuborish"""
    logger.info("Bildirishnoma yuboruvchi ishga tushdi")
    while True:
        try:
            if get_message_status() == "on":
                files = sorted(glob.glob(os.path.join(NOTIFICATIONS_DIR, "*.json")), key=os.path.getmtime)
                count = 0
                for fpath in files:
                    if get_message_status() == "off":
                        break
                    try:
                        item = json.loads(open(fpath).read())
                        chat_id = item.get("chat_id")
                        if not chat_id:
                            os.unlink(fpath)
                            continue

                        if item.get("text"):
                            await bot.send_message(int(chat_id), item["text"], parse_mode="HTML")
                        elif item.get("photo"):
                            await bot.send_photo(int(chat_id), item["photo"], caption=item.get("caption", ""))
                        elif item.get("video"):
                            await bot.send_video(int(chat_id), item["video"], caption=item.get("caption", ""))
                        elif item.get("from_chat_id"):
                            await bot.forward_message(int(chat_id), item["from_chat_id"], item["message_id"])

                        os.unlink(fpath)
                        count += 1
                        if count % 5 == 0:
                            await asyncio.sleep(1)
                        else:
                            await asyncio.sleep(0.05)
                    except Exception as e:
                        err = str(e)
                        if "429" in err:
                            logger.warning(f"Rate limit! 30s kutilmoqda...")
                            await asyncio.sleep(30)
                        elif "Forbidden" in err:
                            logger.info(f"Bot blocked by {chat_id}")
                            try:
                                os.unlink(fpath)
                            except:
                                pass
                        else:
                            logger.error(f"Notification xatolik: {e}")
                            try:
                                os.unlink(fpath)
                            except:
                                pass
        except Exception as e:
            logger.error(f"Notification loop xatolik: {e}")
        await asyncio.sleep(1)

# ==================== MAIN ====================

async def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN bo'sh! bot.py faylidagi BOT_TOKEN o'zgaruvchisiga tokeningizni kiriting.")
        return

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    logger.info("Bot ishga tushmoqda...")

    # Fon jarayonini ishga tushirish
    asyncio.create_task(notification_sender(bot))

    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    asyncio.run(main())
