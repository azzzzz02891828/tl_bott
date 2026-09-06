import os
import asyncio
import random
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from telethon import TelegramClient, events, Button

# --- خادم وهمي لإبقاء الخدمة المجانية شغالة على Render ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is Running!")

def start_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

threading.Thread(target=start_health_check_server, daemon=True).start()

# --- الثوابت الأساسية ---
API_ID = 39378042
API_HASH = "d7358ec9f283c4151b0910efe90fdf8c"

# --- بيانات التوثيق الجديدة المحدثة ---
CLIENT_BOT_TOKEN = "8876259033:AAHePjnxAJ90Ha6zZEEOIhdw6pVdV1Ecy50"
ADMIN_BOT_TOKEN = "8965092843:AAHIjwMKVQQ0oDGEXysZTNsDQxX7dYGB0TU"
ADMIN_ID = 5885382011

# --- الكلمات والخصائص العامة للإدارة ---
admin_words_pool = ["السلام", "عليكم", "ورحمة", "الله", "وبركاته", "يا", "سادة", "باي"]
generation_word_count = 2  # عدد الكلمات الافتراضي في كل سطر

user_sessions = {}
pending_approvals = {}
user_settings = {}

admin_bot = TelegramClient('admin_bot_session', API_ID, API_HASH)
client_bot = TelegramClient('client_bot_session', API_ID, API_HASH)


# --- دالة توليد السطور الفريدة بدون تكرار ---
def generate_unique_sentences(words_list, words_per_line, total_lines=5):
    if not words_list:
        return ["لا توجد كلمات مضافة حالياً."]
    
    pool = words_list.copy()
    random.shuffle(pool)
    
    sentences = []
    i = 0
    while i < len(pool):
        chunk = pool[i:i + words_per_line]
        if len(chunk) < words_per_line and len(pool) >= words_per_line:
            needed = words_per_line - len(chunk)
            chunk.extend(pool[:needed])
        sentences.append(" ".join(chunk))
        i += words_per_line
        if len(sentences) >= total_lines:
            break
    return sentences


# --- بوت التحكم (الإدارة): إضافة كلمات، تحديد العدد، إدارة المشتركين ---
@admin_bot.on(events.NewMessage(pattern='/lines'))
async def manage_lines(event):
    if event.sender_id != ADMIN_ID:
        return
    
    global generation_word_count
    args = event.raw_text.split(maxsplit=2)
    if len(args) < 2:
        words_str = ", ".join(admin_words_pool) if admin_words_pool else "فارغة"
        await event.respond(
            f"📋 **لوحة تحكم الكلمات:**\n\n"
            f"🔤 **الكلمات الحالية:** [{words_str}]\n"
            f"🔢 **عدد الكلمات في كل سطر:** `{generation_word_count}`\n\n"
            f"**الأوامر المتاحة:**\n"
            f"1️⃣ لإضافة كلمة: `/lines add كلمة`\n"
            f"2️⃣ لتحديد عدد الكلمات بالسطر: `/lines count 2`\n"
            f"3️⃣ لمسح جميع الكلمات: `/lines clear`"
        )
        return

    command = args[1]
    if command == "add" and len(args) > 2:
        new_word = args[2].strip()
        admin_words_pool.append(new_word)
        await event.respond(f"✅ تمت إضافة الكلمة بنجاح: `{new_word}`")
    elif command == "count" and len(args) > 2:
        try:
            cnt = int(args[2])
            generation_word_count = cnt
            await event.respond(f"✅ تم تحديث عدد الكلمات في كل سطر إلى: `{cnt}`")
        except ValueError:
            await event.respond("❌ يرجى إدخال رقم صحيح (مثال: `/lines count 2`)")
    elif command == "clear":
        admin_words_pool.clear()
        await event.respond("🗑️ تم مسح جميع الكلمات بنجاح.")
    else:
        await event.respond("❌ أمر غير معروف. اكتب `/lines` لعرض القائمة.")


@admin_bot.on(events.NewMessage(pattern='/users'))
async def list_approved_users(event):
    if event.sender_id != ADMIN_ID:
        return
    
    approved_list = [uid for uid, data in user_sessions.items() if data.get("status") == "approved"]
    if not approved_list:
        await event.respond("📂 لا يوجد أي مشتركين مفعلين حالياً.")
        return
    
    text = "👥 **المشتركون الحاليون (اضغط لطرد أي منهم):**\n\n"
    buttons = []
    for uid in approved_list:
        phone = user_sessions[uid].get("phone", "غير متوفر")
        text += f"- الآيدي: `{uid}` (الرقم: {phone})\n"
        buttons.append([Button.inline(f"طرد المشترك {uid}", data=f"kick_user_{uid}".encode())])
    
    await event.respond(text, buttons=buttons)


@admin_bot.on(events.CallbackQuery(pattern=b"kick_user_"))
async def kick_user(event):
    if event.sender_id != ADMIN_ID:
        await event.answer("غير مسموح.", alert=True)
        return
    
    try:
        user_id = int(event.data.decode().split("_")[2])
        if user_id in user_sessions:
            del user_sessions[user_id]
            if user_id in user_settings:
                del user_settings[user_id]
            await event.edit(f"🚫 تم طرد المستخدم `{user_id}` وإلغاء صلاحياته بنجاح.")
            try:
                await client_bot.send_message(user_id, "⚠️ عذراً، تم إلغاء تفعيل حسابك بواسطة الإدارة.")
            except:
                pass
        else:
            await event.answer("المستخدم غير موجود أو تم حذفه مسبقاً.", alert=True)
    except Exception as e:
        await event.answer(f"حدث خطأ: {e}", alert=True)


# --- بوت العميل: طلب تسجيل الدخول ---
@client_bot.on(events.NewMessage(pattern='/start'))
async def client_start(event):
    user_id = event.sender_id
    if user_id in user_sessions and user_sessions[user_id]["status"] == "approved":
        await event.respond("✨ حسابك مفعل وجاهز للعمل بالفعل!")
        return
    
    await event.respond("أهلاً بك! يرجى إرسال رقم هاتفك مع الرمز الدولي (مثال: `+9665xxxxxxxx`) لتسجيل الدخول:")
    user_sessions[user_id] = {"status": "waiting_phone"}


@client_bot.on(events.NewMessage(func=lambda e: e.is_private))
async def handle_phone(event):
    user_id = event.sender_id
    if user_id not in user_sessions or user_sessions[user_id].get("status") != "waiting_phone":
        return

    phone = event.raw_text.strip()
    user_sessions[user_id]["phone"] = phone
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

        try:
            await temp_client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
        except Exception as sign_in_error:
            if "Password" in str(sign_in_error) or "two-step" in str(sign_in_error):
                data["code"] = code
                user_sessions[user_id]["status"] = "waiting_password"
                await event.respond("🔒 حسابك محمي التحقق بخطوتين. يرجى إرسال كلمة المرور الآن:")
                return
            else:
                raise sign_in_error

        user_sessions[user_id]["userbot"] = temp_client
        user_sessions[user_id]["status"] = "pending_admin"
        
        await admin_bot.send_message(
            ADMIN_ID,
            f"🔔 **طلب تفعيل مستخدم جديد:**\n- آيدي المستخدم: `{user_id}`\n- الرقم: `{phone}`",
            buttons=[Button.inline(b"Accept Login", data=f"accept_login_{user_id}".encode())]
        )
        await event.respond("⏳ تم التحقق من الكود بنجاح! بانتظار موافقة الإدارة لتفعيل حسابك.")

    except Exception as e:
        await event.respond(f"❌ خطأ في الكود أو تسجيل الدخول: {e}")


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
        await temp_client.sign_in(password=password)
        
        user_sessions[user_id]["userbot"] = temp_client
        user_sessions[user_id]["status"] = "pending_admin"
        
        await admin_bot.send_message(
            ADMIN_ID,
            f"🔔 **طلب تفعيل مستخدم جديد:**\n- آيدي المستخدم: `{user_id}`\n- الرقم: `{data['phone']}`",
            buttons=[Button.inline(b"Accept Login", data=f"accept_login_{user_id}".encode())]
        )
        await event.respond("⏳ تم تسجيل الدخول بنجاح! بانتظار موافقة الإدارة.")
    except Exception as e:
        await event.respond(f"❌ كلمة المرور غير صحيحة: {e}")


@admin_bot.on(events.CallbackQuery(pattern=b"accept_login_"))
async def admin_approve(event):
    if event.sender_id != ADMIN_ID:
        await event.answer("غير مسموح لك.", alert=True)
        return

    try:
        user_id = int(event.data.decode().split("_")[2])
        if user_id in user_sessions:
            user_sessions[user_id]["status"] = "approved"
            user_settings[user_id] = {"speed": 2, "trigger": ".مرسل"}
            
            await event.edit("✅ تمت الموافقة على تفعيل المستخدم بنجاح!")
            await client_bot.send_message(
                user_id,
                "🎉 تمت الموافقة على حسابك بنجاح!\n\nيمكنك الآن إرسال كلمتك المفتاحية في أي شات لبدء إرسال الكلمات.\nالأوامر المتاحة:\n`/speed [ثواني]`\n`/trigger [الكلمة]`"
            )
        else:
            await event.answer("انتهت الجلسة أو تم طرد المستخدم.", alert=True)
    except Exception as e:
        await event.answer(f"حدث خطأ: {e}", alert=True)


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


# --- إرسال الكلمات الفريدة عند كتابة الكلمة المفتاحية ---
@client_bot.on(events.NewMessage(func=lambda e: e.is_private is False))
async def auto_sender(event):
    user_id = event.sender_id
    if user_id not in user_sessions or user_sessions[user_id].get("status") != "approved":
        return

    settings = user_settings.get(user_id, {"speed": 2, "trigger": ".مرسل"})
    current_trigger = settings["trigger"]

    if event.raw_text.strip() == current_trigger:
        try:
            await event.delete()
            speed = settings["speed"]
            chat = await event.get_chat()
            userbot = user_sessions[user_id]["userbot"]

            dynamic_lines = generate_unique_sentences(admin_words_pool, generation_word_count, total_lines=len(admin_words_pool))

            for line in dynamic_lines:
                await userbot.send_message(chat, line)
                await asyncio.sleep(speed)

        except Exception as e:
            print(f"⚠️ خطأ أثناء الإرسال الآلي: {e}")


# --- التشغيل ---
async def start_bots():
    await admin_bot.start(bot_token=ADMIN_BOT_TOKEN)
    await client_bot.start(bot_token=CLIENT_BOT_TOKEN)
    print("🚀 جاري تشغيل بوتات التليجرام بنجاح...")
    await asyncio.gather(
        admin_bot.run_until_disconnected(),
        client_bot.run_until_disconnected()
    )

if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_bots())
