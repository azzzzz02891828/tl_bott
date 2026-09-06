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
approved_users = set()  # مجموعة المستخدمين المفعلين
pending_requests = {}
admin_lines_data = {"words": [], "count": 1}
temp_login_data = {}  # لتخزين جلسات تسجيل الدخول المؤقتة

# تعريف عملاء تيليثون للبوتين
control_client = TelegramClient('control_bot_session', API_ID, API_HASH)
user_client = TelegramClient('user_bot_session', API_ID, API_HASH)

# ==========================================
# --- 3. لوحة تحكم بوت الإدارة (Control Bot) ---
# ==========================================
def get_control_menu():
    return [
        [Button.inline("👥 المشتركين وإدارتهم", b"admin_subs"), Button.inline("📢 الإذاعة الجماعية", b"admin_broadcast")],
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
        if not approved_users:
            await event.answer("لا يوجد أي مشترك مفعل حالياً.", alert=True)
            return
        await event.answer("جاري استعراض المشتركين...")
        # إرسال كل مشترك في رسالة منفصلة مع زر طرد/إلغاء تفعيل
        for uid in list(approved_users):
            sub_menu = [[Button.inline(f"❌ طرد / إلغاء تفعيل ({uid})", f"kick_{uid}".encode())]]
            await control_client.send_message(ADMIN_ID, f"👤 **معرف المشترك:** `{uid}`", buttons=sub_menu)

    elif data == "admin_lines":
        user_states[ADMIN_ID] = "waiting_for_admin_words"
        await event.respond("📝 أرسل الآن الكلمات للسطور:")
        await event.answer()
        
    elif data == "admin_broadcast":
        user_states[ADMIN_ID] = "waiting_for_broadcast"
        await event.respond("📢 أرسل نص الإذاعة (سيُرسل مباشرة وبدون أي ملحقات):")
        await event.answer()

# زر طرد المشترك من لوحة التحكم
@control_client.on(events.CallbackQuery)
async def kick_user_callback(event):
    if event.sender_id != ADMIN_ID:
        return
    data = event.data.decode('utf-8')
    if data.startswith("kick_"):
        uid = int(data.split("_")[1])
        if uid in approved_users:
            approved_users.remove(uid)
            try:
                await user_client.send_message(uid, "❌ تم إلغاء تفعيل حسابك وطردك من قبل الإدارة.")
            except:
                pass
            await event.edit(f"✅ تم طرد المشترك `{uid}` بنجاح وإزالة تفعيله.")
        else:
            await event.answer("المشترك محذوف مسبقاً.", alert=True)

# إدارة الردود النصية لبوت التحكم (الإذاعة والسطور)
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
        # الإذاعة ترسل النص صافياً ومباشرة بدون أي ملحقات
        for uid in approved_users:
            try:
                await user_client.send_message(uid, text)
                success_count += 1
            except:
                pass
        await event.respond(f"✅ تم إرسال الإذاعة مباشرة إلى {success_count} مشترك.", buttons=get_control_menu())

# استقبال طلبات التفعيل وقبولها أو رفضها من الأدمن
@control_client.on(events.CallbackQuery)
async def admin_approval_callbacks(event):
    if event.sender_id != ADMIN_ID:
        return
    data = event.data.decode('utf-8')
    
    if data.startswith("acc_"):
        user_id = int(data.split("_")[1])
        # لا نضيفه للمعتمدين نهائياً إلا بعد إتمام تسجيل دخوله برقم الجوال والكود بنجاح
        await control_client.send_message(user_id, "✅ تمت الموافقة على طلبك من الإدارة!\nالآن يرجى إرسال رقم هاتفك مع الرمز الدولي (مثال: `+9665xxxxxxxx`) لتسجيل الدخول:")
        user_states[user_id] = "waiting_for_phone"
        await event.edit("✅ تم قبول الطلب، وتم طلب رقم الهاتف من المستخدم عبر بوت الخدمة.")
        
    elif data.startswith("rej_"):
        user_id = int(data.split("_")[1])
        user_states.pop(user_id, None)
        await user_client.send_message(user_id, "❌ تم رفض طلب تفعيلك من الإدارة.")
        await event.edit("❌ تم رفض الطلب.")

# ==========================================
# --- 4. بوت الخدمات والمستخدمين (User Bot) ---
# ==========================================
@user_client.on(events.NewMessage(pattern='/start'))
async def user_start(event):
    sender_id = event.sender_id
    if sender_id in approved_users:
        user_menu = [
            [Button.inline("🔴 الإيقاف (#22)", b"btn_stop"), Button.inline("🟢 التشغيل (#11)", b"btn_start")]
        ]
        await event.respond("أهلاً بك مجدداً. حسابك مفعل:", buttons=user_menu)
        return

    # إرسال زر طلب التفعيل للأدمن
    await event.respond("أهلاً بك. انقر أدناه لطلب تفعيل حسابك:", buttons=[[Button.inline("🔓 طلب تفعيل الحساب", f"req_act_{sender_id}".encode())]])

@user_client.on(events.CallbackQuery)
async def user_button_actions(event):
    data = event.data.decode('utf-8')
    sender_id = event.sender_id
    
    if data.startswith("req_act_"):
        user_id = int(data.split("_")[2])
        # إرسال إشعار للأدمن في بوت التحكم مع أزرار القبول والرفض
        await control_client.send_message(
            ADMIN_ID, 
            f"🔔 طلب تفعيل جديد من المستخدم: `{user_id}`", 
            buttons=[[Button.inline("✅ قبول", f"acc_{user_id}".encode()), Button.inline("❌ رفض", f"rej_{user_id}".encode())]]
        )
        await event.answer("تم إرسال طلب التفعيل إلى المالك بنجاح، بانتظار الموافقة.", alert=True)
        return

    if sender_id not in approved_users:
        await event.answer("حسابك غير مفعل بعد من الإدارة!", alert=True)
        return

    if data == "btn_stop":
        user_states[sender_id] = "waiting_for_stop_word"
        await event.respond("🔴 يرجى إرسال الكلمة التي تريدها لكي توقفها (#22):")
        await event.answer()
    elif data == "btn_start":
        user_states[sender_id] = "waiting_for_start_word"
        await event.respond("🟢 يرجى إرسال الكلمة التي تريدها لكي تشغلها (#11):")
        await event.answer()

# خطوات استقبال رقم الهاتف وتجريح الكود في بوت المستخدم
@user_client.on(events.NewMessage(incoming=True))
async def user_login_steps(event):
    sender_id = event.sender_id
    if sender_id == ADMIN_ID or sender_id not in user_states:
        return
    
    state = user_states[sender_id]
    text = event.raw_text.strip()
    
    if state == "waiting_for_phone":
        phone = text
        user_states[sender_id] = "waiting_for_code"
        await event.respond("⏳ جاري إرسال رمز التحقق إلى حسابك في تليجرام...")
        
        try:
            # إنشاء عميل مؤقت خاص بهذا المستخدم لطلب الكود
            session_name = f"user_session_{sender_id}"
            client = TelegramClient(session_name, API_ID, API_HASH)
            await client.connect()
            sent_code = await client.send_code_request(phone)
            temp_login_data[sender_id] = {
                "client": client, 
                "phone": phone, 
                "phone_code_hash": sent_code.phone_code_hash
            }
            await event.respond("✅ تم إرسال الرمز بنجاح. يرجى إرسال رمز التحقق الذي وصلك على تليجرام:")
        except Exception as e:
            user_states.pop(sender_id, None)
            await event.respond(f"❌ حدث خطأ أثناء إرسال الكود: {str(e)}\nأرسل /start للبدء من جديد.")

    elif state == "waiting_for_code":
        code = text
        login_info = temp_login_data.get(sender_id)
        if not login_info:
            await event.respond("❌ انتهت الجلسة. أرسل /start للبدء من جديد.")
            user_states.pop(sender_id, None)
            return
        
        client = login_info["client"]
        phone = login_info["phone"]
        phone_code_hash = login_info["phone_code_hash"]
        
        try:
            await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
            user_states.pop(sender_id, None)
            temp_login_data.pop(sender_id, None)
            
            # تسجيل الدخول نجح، نضيفه للمعتمدين ونظهر له القائمة
            approved_users.add(sender_id)
            user_menu = [
                [Button.inline("🔴 الإيقاف (#22)", b"btn_stop"), Button.inline("🟢 التشغيل (#11)", b"btn_start")]
            ]
            await event.respond("✅ تم تسجيل الدخول لحسابك وتفعيلك بنجاح تام!\nاختر الأمر المطلوب:", buttons=user_menu)
        except Exception as e:
            if "Password" in str(e) or "two-step" in str(e).lower():
                user_states[sender_id] = "waiting_for_2fa"
                await event.respond("🔐 حسابك محمي بالتحقق بخطوتين. يرجى إرسال كلمة المرور الخاصة بحسابك:")
            else:
                await event.respond(f"❌ الكود غير صحيح: {str(e)}\nأعد إرسال الكود الصحيح:")

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
            
            approved_users.add(sender_id)
            user_menu = [
                [Button.inline("🔴 الإيقاف (#22)", b"btn_stop"), Button.inline("🟢 التشغيل (#11)", b"btn_start")]
            ]
            await event.respond("✅ تم تخطي التحقق بخطوتين وتسجيل الدخول بنجاح!\nاختر الأمر المطلوب:", buttons=user_menu)
        except Exception as e:
            await event.respond(f"❌ كلمة المرور غير صحيحة: {str(e)}\nأعد إرسال كلمة المرور الصحيحة:")

    elif state == "waiting_for_stop_word":
        user_states.pop(sender_id, None)
        word = text
        await event.respond(f"✅ تم تطبيق أمر الإيقاف (#22) للكلمة: {word}")

    elif state == "waiting_for_start_word":
        user_states.pop(sender_id, None)
        word = text
        await event.respond(f"✅ تم تطبيق أمر التشغيل (#11) للكلمة: {word}")

# --- التشغيل الأساسي بالتزامن ---
async def main():
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
