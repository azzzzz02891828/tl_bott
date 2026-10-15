import asyncio
import random
import time
import os
from aiohttp import web
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
CONTROL_TOKEN = "8936206172:AAEV0LFdeUcwlfXkpIn5JyoTLsImNBnRtWI"
USER_TOKEN = "8838773401:AAH8gaPm2-VjOhhE6WHO-yqhw1Su1AOlb_g"
ADMINS = [5885382011, 8602800425]
control_bot = Client("control_bot", api_id=2040, api_hash="b18441a1ff607e10a98a0528b788a122", bot_token=CONTROL_TOKEN)
user_bot = Client("user_bot", api_id=2040, api_hash="b18441a1ff607e10a98a0528b788a122", bot_token=USER_TOKEN)
db = {
"is_active": True,
"speed": "medium",
"start_cmd": "بدء",
"stop_cmd": "ايقاف",
"global_name": None,
"lines_male": ["هاي", "السلام", "عليكم"],
"lines_female": ["مرحبا", "اهلين", "كيفكم"],
"individual_msg": "رسالة فردية افتراضية",
"users": {},
"rejected": {},
"active_loops": {}
}
SPEED_MAP = {
"slow": 10,
"medium": 5,
"fast": 3,
"external": 1,
"max": 0.5
}
async def handle_ping(request):
return web.Response(text="Bot is alive")
async def start_web_server():
app = web.Application()
app.router.add_get('/', handle_ping)
runner = web.AppRunner(app)
await runner.setup()
port = int(os.environ.get("PORT", 8080))
site = web.TCPSite(runner, '0.0.0.0', port)
await site.start()
def get_admin_keyboard():
status_text = "تشغيل البوت ✅" if not db["is_active"] else "ايقاف البوت 🔴"
speed_text = f"السرعة ⚡️ ({db['speed']})"
name_text = f"الاسم ✏️ ({db['global_name']})" if db["global_name"] else "الاسم ✏️"
keyboard = [
[InlineKeyboardButton(status_text, callback_data="toggle_status")],
[InlineKeyboardButton(speed_text, callback_data="manage_speed")],
[InlineKeyboardButton("كلمة التشغيل ▶️", callback_data="set_start_cmd"), InlineKeyboardButton("كلمة الإيقاف ⏹️", callback_data="set_stop_cmd")],
[InlineKeyboardButton(name_text, callback_data="set_name")],
]
if db["global_name"]:
keyboard.append([InlineKeyboardButton("ازالة اسم الشخص ❌", callback_data="remove_name")])
keyboard.extend([
[InlineKeyboardButton("السطور 📖", callback_data="manage_lines"), InlineKeyboardButton("الفرديات 📖", callback_data="manage_indv")],
[InlineKeyboardButton("المشتركين 👥", callback_data="view_users"), InlineKeyboardButton("كلمة عامة 📢", callback_data="global_msg")]
])
return InlineKeyboardMarkup(keyboard)
async def main():
await start_web_server()
await control_bot.start()
await user_bot.start()
await asyncio.Event().wait()
@user_bot.on_message(filters.command("start") & filters.private)
async def user_start(client, message):
user_id = message.from_user.id
if user_id in db["rejected"] and time.time() < db["rejected"][user_id]:
remaining = int(db["rejected"][user_id] - time.time())
await message.reply_text(f"تم رفض طلبك سابقاً. يرجى الانتظار {remaining} ثانية قبل إعادة الطلب.")
return
if user_id in db["users"] and db["users"][user_id]["status"] == "active":
if db["users"][user_id]["expires_at"] and time.time() > db["users"][user_id]["expires_at"]:
db["users"].pop(user_id)
else:
gender_btn = "ذكر 🧍‍♂️ ✅" if db["users"][user_id]["gender"] == "male" else "أنثى 🧍‍♀️ ✅"
kb = InlineKeyboardMarkup([[InlineKeyboardButton(gender_btn, callback_data="toggle_gender")]])
await message.reply_text("البوت مفعّل عندك وشغال! اختر جنسك للسطور:", reply_markup=kb)
return
kb = InlineKeyboardMarkup([[InlineKeyboardButton("تفعيل ✅", callback_data="request_activate")]])
await message.reply_text("أهلاً بك في البوت. اضغط على تفعيل لإرسال طلب للمالك.", reply_markup=kb)
@user_bot.on_callback_query()
async def user_callbacks(client, callback_query):
user_id = callback_query.from_user.id
data = callback_query.data
if data == "request_activate":
if user_id in db["rejected"] and time.time() < db["rejected"][user_id]:
await callback_query.answer("أنت محظور حالياً من إرسال الطلبات.", show_alert=True)
return
db["users"][user_id] = {
"status": "pending", "expires_at": None, "gender": "male",
"phone": callback_query.from_user.phone_number or "لا يوجد",
"username": callback_query.from_user.username or "لا يوجد", "last_seen": time.time()
}
await callback_query.edit_message_text("تم ارسال طلب للمالك يرجى الانتظار لين يقبل...")
kb = InlineKeyboardMarkup([[InlineKeyboardButton("قبول ✅", callback_data=f"accept_{user_id}"), InlineKeyboardButton("رفض ❌", callback_data=f"deny_{user_id}")]])
await control_bot.send_message(ADMINS[0], f"طلب تفعيل جديد:\nالمستخدم: @{db['users'][user_id]['username']}\nالآيدي: {user_id}", reply_markup=kb)
elif data == "toggle_gender":
if user_id in db["users"] and db["users"][user_id]["status"] == "active":
current = db["users"][user_id]["gender"]
db["users"][user_id]["gender"] = "female" if current == "male" else "male"
gender_btn = "ذكر 🧍‍♂️ ✅" if db["users"][user_id]["gender"] == "male" else "أنثى 🧍‍♀️ ✅"
await callback_query.edit_message_reply_markup(InlineKeyboardMarkup([[InlineKeyboardButton(gender_btn, callback_data="toggle_gender")]]))
@control_bot.on_message(filters.command("start") & filters.user(ADMINS))
async def admin_start(client, message):
await message.reply_text("مرحباً بك في لوحة تحكم البوت الشاملة:", reply_markup=get_admin_keyboard())
@control_bot.on_callback_query(filters.user(ADMINS))
async def admin_callbacks(client, callback_query):
data = callback_query.data
if data == "toggle_status":
db["is_active"] = not db["is_active"]
await callback_query.edit_message_reply_markup(get_admin_keyboard())
elif data == "manage_speed":
kb = InlineKeyboardMarkup([
[InlineKeyboardButton("بطيء 🐢", callback_data="spd_slow"), InlineKeyboardButton("متوسط 🏃", callback_data="spd_medium")],
[InlineKeyboardButton("سريع 💨", callback_data="spd_fast"), InlineKeyboardButton("شخص خارجي 💻", callback_data="spd_external")],
[InlineKeyboardButton("سرعة قصوى ⚡️", callback_data="spd_max")],
[InlineKeyboardButton("عودة 🔙", callback_data="main_menu")]
])
await callback_query.edit_message_text("اختر سرعة إرسال السطور الحالية:", reply_markup=kb)
elif data.startswith("spd_"):
db["speed"] = data.split("_")[1]
await callback_query.edit_message_text("تم تحديث السرعة بنجاح!", reply_markup=get_admin_keyboard())
elif data == "main_menu":
await callback_query.edit_message_text("مرحباً بك في لوحة تحكم البوت الشاملة:", reply_markup=get_admin_keyboard())
elif data.startswith("accept_"):
uid = int(data.split("")[1])
kb = InlineKeyboardMarkup([
[InlineKeyboardButton("يوم واحد", callback_data=f"dur_1{uid}"), InlineKeyboardButton("أسبوع", callback_data=f"dur_7_{uid}")],
[InlineKeyboardButton("شهر", callback_data=f"dur_30_{uid}"), InlineKeyboardButton("إلى أن أطرده", callback_data=f"dur_inf_{uid}")]
])
await callback_query.edit_message_text(f"حدد مدة تفعيل المستخدم {uid}:", reply_markup=kb)
elif data.startswith("dur_"):
, dur, uid = data.split("")
uid = int(uid)
seconds = {"1": 86400, "7": 604800, "30": 2592000, "inf": None}[dur]
exp = time.time() + seconds if seconds else None
if uid in db["users"]:
db["users"][uid]["status"] = "active"
db["users"][uid]["expires_at"] = exp
await callback_query.edit_message_text(f"تم تفعيل المشترك {uid} بنجاح.")
await user_bot.send_message(uid, "تم قبولك من قبل الإدارة والبوت شغال عندك الآن! أرسل /start لتحديد الجنس.")
elif data.startswith("deny_"):
uid = int(data.split("_")[1])
db["rejected"][uid] = time.time() + 300
if uid in db["users"]: db["users"].pop(uid)
await callback_query.edit_message_text(f"تم رفض المستخدم {uid}. لن يتمكن من الطلب لمدة 5 دقائق.")
await user_bot.send_message(uid, "تم رفض طلب تفعيلك. يمكنك إعادة المحاولة بعد 5 دقائق.")
elif data == "remove_name":
db["global_name"] = None
await callback_query.edit_message_text("تم إزالة اسم الشخص بنجاح.", reply_markup=get_admin_keyboard())
elif data == "view_users":
text = "👥 قائمة المشتركين الحالية:\n\n"
has_users = False
for uid, udata in db["users"].items():
if udata["status"] == "active":
has_users = True
time_diff = int(time.time() - udata["last_seen"])
text += f"المستخدم: @{udata['username']}\nرقمه: {udata['phone']}\nحالة النشاط: تم استخدام البوت قبل {time_diff} ثانية.\n"
kb = InlineKeyboardMarkup([[InlineKeyboardButton("طرد ❌", callback_data=f"kick_{uid}")]])
await callback_query.message.reply_text(text, reply_markup=kb)
if not has_users:
await callback_query.answer("لا يوجد مشتركين نشطين حالياً.", show_alert=True)
elif data.startswith("kick_"):
uid = int(data.split("_")[1])
if uid in db["users"]: db["users"].pop(uid)
await callback_query.edit_message_text(f"تم طرد المستخدم {uid} بنجاح وإيقاف الصلاحية.")
await user_bot.send_message(uid, "تم إنهاء صلاحية حسابك وطردك من البوت من قبل المالك.")
async def send_sequences(client, message, lines):
chat_id = message.chat.id
speed_delay = SPEED_MAP.get(db["speed"], 5)
local_lines = lines.copy()
if db["global_name"]:
local_lines.append(db["global_name"])
random.shuffle(local_lines)
try:
await message.delete()
for line in local_lines:
if not db["is_active"] or chat_id not in db["active_loops"]:
break
await client.send_message(chat_id, line)
await asyncio.sleep(speed_delay)
if db["is_active"] and chat_id in db["active_loops"]:
extra_word_1 = random.choice(local_lines)
extra_word_2 = random.choice(local_lines)
await client.send_message(chat_id, f"{extra_word_1} {extra_word_2}")
except Exception as e:
print(f"Error in loop: {e}")
finally:
db["active_loops"].pop(chat_id, None)
@user_bot.on_message(filters.text & ~filters.private)
async def monitor_user_chats(client, message):
user_id = message.from_user.id
chat_id = message.chat.id
if not db["is_active"] or user_id not in db["users"] or db["users"][user_id]["status"] != "active":
return
db["users"][user_id]["last_seen"] = time.time()
gender = db["users"][user_id]["gender"]
chosen_lines = db["lines_male"] if gender == "male" else db["lines_female"]
if message.text == db["start_cmd"]:
if chat_id in db["active_loops"]: return
task = asyncio.create_task(send_sequences(client, message, chosen_lines))
db["active_loops"][chat_id] = task
elif message.text == db["stop_cmd"]:
if chat_id in db["active_loops"]:
db["active_loops"][chat_id].cancel()
db["active_loops"].pop(chat_id, None)
await message.reply_text("⏹️ تم إيقاف عملية الإرسال التكراري في هذا الشات.")
if name == "main":
asyncio.run(main())
