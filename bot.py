import os
import asyncio
from flask import Flask
from threading import Thread
from telethon import TelegramClient, events, Button

# --- 1. خادم الـ HealthCheck المستقل ---
app = Flask('')

@app.route('/')
def home():
    return "Bots are running 24/7!"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, use_reloader=False)

# --- 2. الإعدادات والتوكنات ---
API_ID = 39378042
API_HASH = 'd7358ec9f283c4151b0910efe90fdf8c'
ADMIN_ID = 5885382011

CONTROL_BOT_TOKEN = '8965092843:AAHIjwMKVQQ0oDGEXysZTNsDQxX7dYGB0TU'
USER_BOT_TOKEN = '8876259033:AAHePjnxAJ90Ha6zZEEOIhdw6pVdV1Ecy50'

user_states = {}
pending_requests = {}
approved_users = set()
user_settings = {}
admin_lines_data = {"words": [], "count": 1}

# تعريف عملاء تيليثون
control_client = TelegramClient('control_bot_session', API_ID, API_HASH)
user_client = TelegramClient('user_bot_session', API_ID, API_HASH)

# --- دوال بوت التحكم (Admin Bot) ---
def get_control_menu():
    return [
        [Button.inline("👥 عدد المشتركين", b"admin_subs"), Button.inline("📢 الإذاعة الجماعية", b"admin_broadcast")],
        [Button.inline("📝 إدارة السطور", b"admin_lines")]
    ]

@control_client.on(events.NewMessage(pattern='/start'))
async def control_start(event):
    if event.sender_id != ADMIN_ID:
        await event.respond("❌ عذراً، هذا البوت مخصص للمالك فقط.")
        return
    await event.respond("أهلاً بك يا مالك البوت في لوحة التحكم الإدارية الخاصة بك:", buttons=get_control_menu())

@control_client.on(events.CallbackQuery)
async def control_callbacks(event):
    if event.sender_id != ADMIN_ID:
        return
    data = event.data.decode('utf-8')
    if data == "admin_subs":
        await event.answer(f"عدد المستخدمين المفعلين حالياً: {len(approved_users)}", alert=True)
    elif data == "admin_lines":
        user_states[ADMIN_ID] = "waiting_for_admin_words"
        await event.respond("📝 أرسل الآن الكلمات التي تريدها للسطور:")
        await event.answer()
    elif data == "admin_broadcast":
        user_states[ADMIN_ID] = "waiting_for_broadcast"
        await event.respond("📢 أرسل الرسالة للإذاعة:")
        await event.answer()

@control_client.on(events.NewMessage(incoming=True))
async def control_messages(event):
    sender_id = event.sender_id
    if sender_id != ADMIN_ID or sender_id not in user_states:
        return
    state = user_states[sender_id]
    text = event.raw_text.strip()
    if state == "waiting_for_admin_words":
        words = [w.strip() for w in text.replace(',', ' ').split() if w.strip()]
        admin_lines_data["words"] = words
        user_states[sender_id] = "waiting_for_admin_count"
        await event.respond(f"✅ تم حفظ ({len(words)} كلمة). أرسل رقم عدد الكلمات في كل سطر:")
    elif state == "waiting_for_admin_count":
        if text.isdigit() and int(text) > 0:
            admin_lines_data["count"] = int(text)
            user_states.pop(sender_id, None)
            await event.respond("✅ تم ضبط إعدادات السطور.", buttons=get_control_menu())
        else:
            await event.respond("❌ أرسل رقماً صحيحاً أكبر من الصفر:")
    elif state == "waiting_for_broadcast":
        user_states.pop(sender_id, None)
        success_count = 0
        for uid in approved_users:
            try:
                await user_client.send_message(uid, f"📢 **إشعار من الإدارة:**\n\n{text}")
                success_count += 1
            except:
                pass
        await event.respond(f"✅ تم إرسال الإذاعة إلى {success_count} مشترك.", buttons=get_control_menu())

# --- دوال بوت المستخدمين (User Bot) ---
def get_user_menu():
    return [
        [Button.inline("⚡ السرعة", b"set_speed"), Button.inline("⚙️ تشغيل / إيقاف", b"toggle_settings")],
        [Button.inline("🏷️ البادئة", b"set_prefix"), Button.inline("📊 حالة حسابي", b"account_status")]
    ]

@user_client.on(events.NewMessage(pattern='/start'))
async def user_start(event):
    sender_id = event.sender_id
    if sender_id in approved_users:
        await event.respond("أهلاً بك مجدداً!", buttons=get_user_menu())
        return
    await event.respond("أهلاً بك. انقر أدناه لطلب تفعيل الحساب:", buttons=[[Button.inline("🔓 تفعيل البوت", f"req_act_{sender_id}".encode())]])

@user_client.on(events.CallbackQuery)
async def user_callbacks(event):
    data = event.data.decode('utf-8')
    sender_id = event.sender_id
    if data.startswith("req_act_"):
        user_id = int(data.split("_")[2])
        pending_requests[user_id] = 0
        await control_client.send_message(ADMIN_ID, f"🔔 طلب تفعيل جديد من: `{user_id}`", buttons=[[Button.inline("✅ قبول", f"acc_{user_id}".encode()), Button.inline("❌ رفض", f"rej_{user_id}".encode())]])
        await event.answer("تم إرسال طلبك للمالك.", alert=True)
        return
    if sender_id not in approved_users:
        await event.answer("حسابك غير مفعل!", alert=True)
        return
    if data == "account_status":
        await event.respond("📊 حسابك مفعل وزي الفل.", buttons=get_user_menu())
        await event.answer()

@control_client.on(events.CallbackQuery)
async def admin_decision_callbacks(event):
    if event.sender_id != ADMIN_ID:
        return
    data = event.data.decode('utf-8')
    if data.startswith("acc_"):
        user_id = int(data.split("_")[1])
        approved_users.add(user_id)
        await user_client.send_message(user_id, "✅ تم قبول حسابك!")
        await event.edit("تم قبول المستخدم.")
    elif data.startswith("rej_"):
        user_id = int(data.split("_")[1])
        await user_client.send_message(user_id, "❌ تم رفض طلبك.")
        await event.edit("تم رفض المستخدم.")

# --- التشغيل الأساسي ---
async def main():
    # تشغيل خادم الفلاسك في الخلفية بشكل آمن
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    print("Flask server started in background thread.")

    print("Starting Telegram clients...")
    await control_client.start(bot_token=CONTROL_BOT_TOKEN)
    await user_client.start(bot_token=USER_BOT_TOKEN)
    print("Both bots are running successfully!")

    await asyncio.gather(
        control_client.run_until_disconnected(),
        user_client.run_until_disconnected()
    )

if __name__ == '__main__':
    asyncio.run(main())
