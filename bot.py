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

user_states = {}
pending_requests = {}
approved_users = set()
admin_lines_data = {"words": [], "count": 1}
temp_login_data = {}  # لتخزين بيانات تسجيل الدخول المؤقتة للمستخدمين

# تعريف بوت التحكم الإداري
control_client = TelegramClient('control_bot_session', API_ID, API_HASH)

# --- دوال بوت التحكم (Control Bot) ---
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
    await event.respond("أهلاً بك يا مالك البوت في لوحة التحكم الإدارية:", buttons=get_control_menu())

@control_client.on(events.CallbackQuery)
async def control_callbacks(event):
    if event.sender_id != ADMIN_ID:
        return
    data = event.data.decode('utf-8')
    if data == "admin_subs":
        await event.answer(f"عدد المشتركين المفعلين: {len(approved_users)}", alert=True)
    elif data == "admin_lines":
        user_states[ADMIN_ID] = "waiting_for_admin_words"
        await event.respond("📝 أرسل الآن الكلمات للسطور:")
        await event.answer()
    elif data == "admin_broadcast":
        user_states[ADMIN_ID] = "waiting_for_broadcast"
        await event.respond("📢 أرسل نص الإذاعة (سيُرسل مباشرة بدون أي ملحقات):")
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
        # الإذاعة ترسل النص صافياً ومباشرة بدون ملحقات لكل المستخدمين المعتمدين
        for uid in approved_users:
            try:
                # ملاحظة: سنقوم بإرسالها عبر بوت التحكم أو تخزينها لتصل عبر حساباتهم
                await control_client.send_message(uid, text)
                success_count += 1
            except:
                pass
        await event.respond(f"✅ تم إرسال الإذاعة مباشرة إلى {success_count} مشترك.", buttons=get_control_menu())

# معالجة أزرار قبول أو رفض طلبات التفعيل من الأدمن
@control_client.on(events.CallbackQuery)
async def admin_approval_callbacks(event):
    if event.sender_id != ADMIN_ID:
        return
    data = event.data.decode('utf-8')
    if data.startswith("acc_"):
        user_id = int(data.split("_")[1])
        approved_users.add(user_id)
        await control_client.send_message(user_id, "✅ تم قبول طلبك من الإدارة. يرجى إرسال رقم هاتفك لبدء ربط الحساب (مع مفتاح الدولة، مثل: +966...):")
        user_states[user_id] = "waiting_for_phone"
        await event.edit("✅ تم قبول المستخدم وطلب رقمه.")
    elif data.startswith("rej_"):
        user_id = int(data.split("_")[1])
        await control_client.send_message(user_id, "❌ تم رفض طلب تفعيلك من الإدارة.")
        await event.edit("❌ تم رفض المستخدم.")

# التعامل مع خطوات إدخال رقم الجوال وكود التحقق عبر بوت التحكم للمستخدمين
@control_client.on(events.NewMessage(incoming=True))
async def user_login_steps(event):
    sender_id = event.sender_id
    if sender_id == ADMIN_ID or sender_id not in user_states:
        return
    
    state = user_states[sender_id]
    text = event.raw_text.strip()
    
    if state == "waiting_for_phone":
        phone = text
        user_states[sender_id] = "waiting_for_code"
        await event.respond("⏳ جاري إرسال كود التحقق من تيليجرام...\nيرجى إرسال الكود الذي وصلك على تطبيق تيليجرام (مع مسافات إن وجدت أو أرقام متصلة):")
        
        # إنشاء جلسة مستقلة للمستخدم وتسجيل الدخول برقم جواله
        try:
            client_session_name = f"user_session_{sender_id}"
            client = TelegramClient(client_session_name, API_ID, API_HASH)
            await client.connect()
            sent_code = await client.send_code_request(phone)
            temp_login_data[sender_id] = {"client": client, "phone": phone, "phone_code_hash": sent_code.phone_code_hash}
        except Exception as e:
            user_states.pop(sender_id, None)
            await event.respond(f"❌ حدث خطأ أثناء إرسال الكود: {str(e)}\nحاول البدء من جديد بـ /start")

    elif state == "waiting_for_code":
        code = text
        login_info = temp_login_data.get(sender_id)
        if not login_info:
            await event.respond("❌ انتهت الجلسة أو حدث خطأ. أرسل /start للبدء من جديد.")
            user_states.pop(sender_id, None)
            return
        
        client = login_info["client"]
        phone = login_info["phone"]
        phone_code_hash = login_info["phone_code_hash"]
        
        try:
            await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
            user_states.pop(sender_id, None)
            temp_login_data.pop(sender_id, None)
            
            # إرسال أزرار الإيقاف والتشغيل بعد نجاح الدخول بحسابه الفعلي
            user_menu = [
                [Button.inline("🔴 الإيقاف (#22)", b"btn_stop"), Button.inline("🟢 التشغيل (#11)", b"btn_start")]
            ]
            await event.respond("✅ تم تسجيل الدخول لحسابك بنجاح الربط كامل!\nاختر الأمر المطلوب:", buttons=user_menu)
        except Exception as e:
            # احتمال يتطلب التحقق بخطوتين (Password)
            if "Password" in str(e) or "two-step" in str(e).lower():
                user_states[sender_id] = "waiting_for_2fa"
                await event.respond("🔐 حسابك محمي بالتحقق بخطوتين. يرجى إرسال كلمة مرور الحساب (Password):")
            else:
                await event.respond(f"❌ الكود غير صحيح أو حدث خطأ: {str(e)}\nأعد إرسال الكود الصحيح:")

    elif state == "waiting_for_2fa":
        password = text
        login_info = temp_login_data.get(sender_id)
        if not login_info:
            await event.respond("❌ انتهت الجلسة. أرسل /start للبدء من جديد.")
            user_states.pop(sender_id, None)
            return
        
        client = login_info["client"]
        try:
            await client.sign_in(password=password)
            user_states.pop(sender_id, None)
            temp_login_data.pop(sender_id, None)
            
            user_menu = [
                [Button.inline("🔴 الإيقاف (#22)", b"btn_stop"), Button.inline("🟢 التشغيل (#11)", b"btn_start")]
            ]
            await event.respond("✅ تم تسجيل الدخول وتخطي التحقق بخطوتين بنجاح!\nاختر الأمر المطلوب:", buttons=user_menu)
        except Exception as e:
            await event.respond(f"❌ كلمة المرور غير صحيحة: {str(e)}\nأعد إرسال كلمة المرور الصحيحة:")

    elif state == "waiting_for_stop_word":
        user_states.pop(sender_id, None)
        word = text
        await event.respond(f"✅ تم تنفيذ أمر الإيقاف (#22) للكلمة: {word}")

    elif state == "waiting_for_start_word":
        user_states.pop(sender_id, None)
        word = text
        await event.respond(f"✅ تم تنفيذ أمر التشغيل (#11) للكلمة: {word}")

# طلب البداية للمستخدمين عبر بوت التحكم
@control_client.on(events.NewMessage(pattern='/start'))
async def user_request_start(event):
    sender_id = event.sender_id
    if sender_id == ADMIN_ID:
        return
    
    if sender_id in approved_users:
        user_menu = [
            [Button.inline("🔴 الإيقاف (#22)", b"btn_stop"), Button.inline("🟢 التشغيل (#11)", b"btn_start")]
        ]
        await event.respond("أهلاً بك مجدداً. حسابك مرتبط بالفعل:", buttons=user_menu)
        return

    # إرسال زر طلب التفعيل للإدارة
    await event.respond("أهلاً بك. انقر أدناه لطلب تفعيل حسابك:", buttons=[[Button.inline("🔓 طلب تفعيل الحساب", f"req_act_{sender_id}".encode())]])

@control_client.on(events.CallbackQuery)
async def user_button_actions(event):
    data = event.data.decode('utf-8')
    sender_id = event.sender_id
    
    if data.startswith("req_act_"):
        user_id = int(data.split("_")[2])
        pending_requests[user_id] = True
        # إرسال إشعار للأدمن بطلب التفعيل مع أزرار القبول والرفض
        await control_client.send_message(
            ADMIN_ID, 
            f"🔔 طلب تفعيل جديد من المستخدم: `{user_id}`", 
            buttons=[[Button.inline("✅ قبول", f"acc_{user_id}".encode()), Button.inline("❌ رفض", f"rej_{user_id}".encode())]]
        )
        await event.answer("تم إرسال طلب التفعيل إلى المالك بنجاح.", alert=True)
        return

    if data == "btn_stop":
        user_states[sender_id] = "waiting_for_stop_word"
        await event.respond("🔴 يرجى إرسال الكلمة التي تريدها لكي توقفها (#22):")
        await event.answer()
    elif data == "btn_start":
        user_states[sender_id] = "waiting_for_start_word"
        await event.respond("🟢 يرجى إرسال الكلمة التي تريدها لكي تشغلها (#11):")
        await event.answer()

# --- التشغيل الأساسي ---
async def main():
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    print("Flask server started in background thread.")

    print("Starting Control client...")
    await control_client.start(bot_token=CONTROL_BOT_TOKEN)
    print("Control bot is running successfully!")

    await control_client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
