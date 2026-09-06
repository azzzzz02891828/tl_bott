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

# قواميس حفظ الحالات والبيانات بدقة تامة
user_states = {}       
temp_login_data = {}   
approved_users = set() # المشتركين الفعليين الذين تم ربط حساباتهم بنجاح فقط
admin_lines_data = {"words": [], "count": 1}

client = TelegramClient('main_bot_session', API_ID, API_HASH)

def get_control_menu():
    return [
        [Button.inline("👥 المشتركين المفعلين", b"admin_subs"), Button.inline("📢 الإذاعة الجماعية", b"admin_broadcast")],
        [Button.inline("📝 إدارة السطور", b"admin_lines")]
    ]

@client.on(events.NewMessage(pattern='/start'))
async def main_start(event):
    sender_id = event.sender_id

    # لوحة تحكم المالك (الأدمن)
    if sender_id == ADMIN_ID:
        await event.respond("أهلاً بك يا مالك البوت في لوحة التحكم الإدارية:", buttons=get_control_menu())
        return

    # إذا كان المستخدم مفعل مسبقاً وحسابه مرتبط
    if sender_id in approved_users:
        user_menu = [
            [Button.inline("🔴 الإيقاف (#22)", b"btn_stop"), Button.inline("🟢 التشغيل (#11)", b"btn_start")]
        ]
        await event.respond("أهلاً بك مجدداً. حسابك مرتبط ومفعل:", buttons=user_menu)
        return

    # فحص حالة المستخدم الحالية لعدم تكرار الرسائل وإعادته لنفس خطوته تماماً
    current_state = user_states.get(sender_id)

    if current_state == "pending":
        await event.respond("⏳ طلب تفعيل حسابك قيد المراجعة من الإدارة، بانتظار الموافقة.")
        return
    elif current_state == "waiting_phone":
        await event.respond("يرجى إرسال رقم هاتفك مع الرمز الدولي (مثال: `+9665xxxxxxxx`) لتسجيل الدخول:")
        return
    elif current_state == "waiting_code":
        await event.respond("يرجى إرسال رمز التحقق الذي وصلك على تليجرام:")
        return
    elif current_state == "waiting_2fa":
        await event.respond("يرجى إرسال كلمة المرور (التحقق بخطوتين):")
        return

    # إذا لم يطلب من قبل، يظهر له زر طلب التفعيل لمرة واحدة
    user_states[sender_id] = "not_requested"
    await event.respond("أهلاً بك. انقر أدناه لطلب تفعيل حسابك:", buttons=[[Button.inline("🔓 طلب تفعيل الحساب", b"req_activation")]])

@client.on(events.CallbackQuery)
async def callback_handler(event):
    sender_id = event.sender_id
    data = event.data.decode('utf-8')

    # أزرار الأدمن
    if sender_id == ADMIN_ID:
        if data == "admin_subs":
            if not approved_users:
                await event.answer("لا يوجد أي مشترك مفعل ومرتبط حالياً.", alert=True)
                return
            await event.answer("جاري استعراض المشتركين المفعلين...")
            for uid in list(approved_users):
                sub_menu = [[Button.inline(f"❌ طرد / إلغاء تفعيل ({uid})", f"kick_{uid}".encode())]]
                await client.send_message(ADMIN_ID, f"👤 **معرف المشترك المفعل:** `{uid}`", buttons=sub_menu)
        elif data == "admin_lines":
            user_states[ADMIN_ID] = "waiting_for_admin_words"
            await event.respond("📝 أرسل الآن الكلمات للسطور:")
            await event.answer()
        elif data == "admin_broadcast":
            user_states[ADMIN_ID] = "waiting_for_broadcast"
            await event.respond("📢 أرسل نص الإذاعة (سيُرسل مباشرة وبدون أي ملحقات):")
            await event.answer()
        elif data.startswith("kick_"):
            uid = int(data.split("_")[1])
            if uid in approved_users:
                approved_users.remove(uid)
                user_states[uid] = "kicked"
                try:
                    await client.send_message(uid, "❌ تم إلغاء تفعيل حسابك وطردك من قبل الإدارة.")
                except:
                    pass
                await event.edit(f"✅ تم طرد المشترك `{uid}` وإزالة تفعيله بنجاح.")
            else:
                await event.answer("المشترك محذوف مسبقاً.", alert=True)
        elif data.startswith("acc_"):
            user_id = int(data.split("_")[1])
            user_states[user_id] = "waiting_phone"
            # تأكيد للأدمن في رسالته الخاصة
            await event.edit(f"✅ تم قبول الطلب للمستخدم `{user_id}`، وتم طلب رقم الهاتف منه عبر الشات الخاص به.")
            # إرسال طلب رقم الهاتف حصرياً للمستخدم صاحب الطلب
            await client.send_message(user_id, "✅ تمت الموافقة على طلبك من الإدارة!\nالآن يرجى إرسال رقم هاتفك مع الرمز الدولي (مثال: `+9665xxxxxxxx`) لتسجيل الدخول:")
        elif data.startswith("rej_"):
            user_id = int(data.split("_")[1])
            user_states[user_id] = "rejected"
            await event.edit(f"❌ تم رفض الطلب للمستخدم `{user_id}`.")
            try:
                await client.send_message(user_id, "❌ تم رفض طلب تفعيلك من الإدارة.")
            except:
                pass
        return

    # أزرار المستخدمين العاديين
    if data == "req_activation":
        if user_states.get(sender_id) == "pending":
            await event.answer("لقد أرسلت طلباً مسبقاً، بانتظار رد الإدارة.", alert=True)
            return
        user_states[sender_id] = "pending"
        await client.send_message(
            ADMIN_ID, 
            f"🔔 طلب تفعيل جديد من المستخدم: `{sender_id}`", 
            buttons=[[Button.inline("✅ قبول", f"acc_{sender_id}".encode()), Button.inline("❌ رفض", f"rej_{sender_id}".encode())]]
        )
        await event.answer("تم إرسال طلب التفعيل إلى المالك بنجاح.", alert=True)
        return

    if sender_id not in approved_users:
        await event.answer("حسابك غير مفعل أو لم يكتمل ربطه بعد!", alert=True)
        return

    if data == "btn_stop":
        user_states[sender_id] = "waiting_stop_word"
        await event.respond("🔴 يرجى إرسال الكلمة التي تريدها لكي توقفها (#22):")
        await event.answer()
    elif data == "btn_start":
        user_states[sender_id] = "waiting_start_word"
        await event.respond("🟢 يرجى إرسال الكلمة التي تريدها لكي تشغلها (#11):")
        await event.answer()

@client.on(events.NewMessage(incoming=True))
async def message_router(event):
    sender_id = event.sender_id
    text = event.raw_text.strip()
    
    if text.startswith('/'):
        return  

    # معالجة إدخالات الأدمن
    if sender_id == ADMIN_ID:
        state = user_states.get(ADMIN_ID)
        if state == "waiting_for_admin_words":
            words = [w.strip() for w in text.replace(',', ' ').split() if w.strip()]
            admin_lines_data["words"] = words
            user_states[ADMIN_ID] = "waiting_for_admin_count"
            await event.respond(f"✅ تم حفظ ({len(words)} كلمة). أرسل رقم عدد الكلمات في كل سطر:")
        elif state == "waiting_for_admin_count":
            if text.isdigit() and int(text) > 0:
                admin_lines_data["count"] = int(text)
                user_states.pop(ADMIN_ID, None)
                await event.respond("✅ تم ضبط إعدادات السطور.", buttons=get_control_menu())
            else:
                await event.respond("❌ أرسل رقماً صحيحاً أكبر من الصفر:")
        elif state == "waiting_for_broadcast":
            user_states.pop(ADMIN_ID, None)
            success_count = 0
            for uid in approved_users:
                try:
                    await client.send_message(uid, text)
                    success_count += 1
                except:
                    pass
            await event.respond(f"✅ تم إرسال الإذاعة مباشرة إلى {success_count} مشترك مفعل.", buttons=get_control_menu())
        return

    # معالجة خطوات المستخدمين بناءً على حالتهم
    state = user_states.get(sender_id)

    if state == "waiting_phone":
        phone = text
        user_states[sender_id] = "waiting_code"
        await event.respond("⏳ جاري إرسال رمز التحقق إلى حسابك في تليجرام...")
        
        try:
            user_session_client = TelegramClient(f"user_session_{sender_id}", API_ID, API_HASH)
            await user_session_client.connect()
            sent_code = await user_session_client.send_code_request(phone)
            temp_login_data[sender_id] = {
                "client": user_session_client, 
                "phone": phone, 
                "phone_code_hash": sent_code.phone_code_hash
            }
            await event.respond("✅ تم إرسال الرمز بنجاح. يرجى إرسال رمز التحقق:")
        except Exception as e:
            user_states[sender_id] = "waiting_phone"
            await event.respond(f"❌ حدث خطأ: {str(e)}\nيرجى إعادة إرسال رقم الهاتف بشكل صحيح:")

    elif state == "waiting_code":
        code = text
        login_info = temp_login_data.get(sender_id)
        if not login_info:
            user_states[sender_id] = "waiting_phone"
            await event.respond("❌ انتهت الجلسة. أرسل رقم هاتفك من جديد:")
            return
        
        sess_client = login_info["client"]
        phone = login_info["phone"]
        phone_code_hash = login_info["phone_code_hash"]
        
        try:
            await sess_client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
            approved_users.add(sender_id)
            temp_login_data.pop(sender_id, None)
            
            user_menu = [
                [Button.inline("🔴 الإيقاف (#22)", b"btn_stop"), Button.inline("🟢 التشغيل (#11)", b"btn_start")]
            ]
            await event.respond("✅ تم تسجيل الدخول وربط وتفعيل حسابك بنجاح تام!", buttons=user_menu)
        except Exception as e:
            if "Password" in str(e) or "two-step" in str(e).lower():
                user_states[sender_id] = "waiting_2fa"
                await event.respond("🔐 حسابك محمي بخطوتين. يرجى إرسال كلمة المرور:")
            else:
                await event.respond(f"❌ الرمز غير صحيح: {str(e)}\nأعد إرسال الرمز الصحيح:")

    elif state == "waiting_2fa":
        password = text
        login_info = temp_login_data.get(sender_id)
        if not login_info:
            user_states[sender_id] = "waiting_phone"
            await event.respond("❌ انتهت الجلسة. أرسل رقم هاتفك من جديد:")
            return
        
        sess_client = login_info["client"]
        try:
            await sess_client.sign_in(password=password)
            approved_users.add(sender_id)
            temp_login_data.pop(sender_id, None)
            
            user_menu = [
                [Button.inline("🔴 الإيقاف (#22)", b"btn_stop"), Button.inline("🟢 التشغيل (#11)", b"btn_start")]
            ]
            await event.respond("✅ تم التحقق وتسجيل الدخول وربط الحساب بنجاح!", buttons=user_menu)
        except Exception as e:
            await event.respond(f"❌ كلمة المرور غير صحيحة: {str(e)}\nأعد إرسال كلمة المرور:")

    elif state == "waiting_stop_word":
        word = text
        user_menu = [[Button.inline("🔴 الإيقاف (#22)", b"btn_stop"), Button.inline("🟢 التشغيل (#11)", b"btn_start")]]
        await event.respond(f"✅ تم تطبيق أمر الإيقاف (#22) للكلمة: {word}", buttons=user_menu)

    elif state == "waiting_start_word":
        word = text
        user_menu = [[Button.inline("🔴 الإيقاف (#22)", b"btn_stop"), Button.inline("🟢 التشغيل (#11)", b"btn_start")]]
        await event.respond(f"✅ تم تطبيق أمر التشغيل (#11) للكلمة: {word}", buttons=user_menu)

async def main():
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    print("Flask server started in background thread.")

    print("Starting Main Telegram client...")
    await client.start(bot_token=CONTROL_BOT_TOKEN)
    print("Bot is running successfully!")
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
