import os
import asyncio
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread
from telethon import TelegramClient, events, Button

# --- 1. إعدادات خادم الـ HealthCheck للبقاء نشطاً 24/7 ---
app = Flask('')

@app.route('/')
def home():
    return "Both Bots and HealthCheck are running 24/7!"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# --- 2. المعرفات والتوكنات المعتمدة ---
API_ID = 39378042
API_HASH = 'd7358ec9f283c4151b0910efe90fdf8c'
ADMIN_ID = 5885382011

# توكنات البوتات
CONTROL_BOT_TOKEN = '8965092843:AAHIjwMKVQQ0oDGEXysZTNsDQxX7dYGB0TU'
USER_BOT_TOKEN = '8876259033:AAHePjnxAJ90Ha6zZEEOIhdw6pVdV1Ecy50'

# تخزين البيانات والحالات
user_states = {}
pending_requests = {}
approved_users = set()
user_settings = {}
admin_lines_data = {"words": [], "count": 1}

# تهيئة عملاء تيليثون للبوتين
# بوت التحكم (يدرّ الإدارة والتحكم)
control_client = TelegramClient('control_bot_session', API_ID, API_HASH)
# بوت المستخدمين (الخدمي للعملاء)
user_client = TelegramClient('user_bot_session', API_ID, API_HASH)

# ==================== بوت التحكم (Admin Bot) ====================

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
        await event.respond("📝 أرسل الآن الكلمات التي تريدها للسطور (فصل بينها بمسافة أو فاصلة، مثال:\nالسلام، عليكم، رحمة، الله)")
        await event.answer()
        
    elif data == "admin_broadcast":
        user_states[ADMIN_ID] = "waiting_for_broadcast"
        await event.respond("📢 أرسل الرسالة التي تريد إذاعتها لجميع المستخدمين المفعلين:")
        await event.answer()

@control_client.on(events.NewMessage(incoming=True))
async def control_messages(event):
    sender_id = event.sender_id
    if sender_id != ADMIN_ID or sender_id not in user_states:
        return
        
    state = user_states[sender_id]
    text = event.raw_text.strip()
    
    if state == "waiting_for_admin_words":
        # تنظيف الكلمات وفصلها
        words = [w.strip() for w in text.replace(',', ' ').split() if w.strip()]
        admin_lines_data["words"] = words
        user_states[sender_id] = "waiting_for_admin_count"
        await event.respond(f"✅ تم حفظ الكلمات ({len(words)} كلمة). الآن أرسل رقم عدد الكلمات في كل سطر (مثلاً: 2):")
        
    elif state == "waiting_for_admin_count":
        if text.isdigit() and int(text) > 0:
            count = int(text)
            admin_lines_data["count"] = count
            user_states.pop(sender_id, None)
            await event.respond(f"✅ تم ضبط إعدادات السطور بنجاح: كل سطر سيتكون من {count} كلمات (بدون أي تكرار نهائياً).", buttons=get_control_menu())
        else:
            await event.respond("❌ خطأ: يرجى إرسال رقم صحيح أكبر من الصفر:")
            
    elif state == "waiting_for_broadcast":
        user_states.pop(sender_id, None)
        success_count = 0
        for uid in approved_users:
            try:
                await user_client.send_message(uid, f"📢 **إشعار من الإدارة:**\n\n{text}")
                success_count += 1
            except:
                pass
        await event.respond(f"✅ تم إرسال الإذاعة بنجاح إلى {success_count} مشترك.", buttons=get_control_menu())


# ==================== بوت المستخدمين (User Bot) ====================

def get_user_menu():
    return [
        [Button.inline("⚡ السرعة", b"set_speed"), Button.inline("⚙️ تشغيل / إيقاف", b"toggle_settings")],
        [Button.inline("🏷️ البادئة (الاسم)", b"set_prefix"), Button.inline("📊 حالة حسابي", b"account_status")],
        [Button.inline("🛑 إيقاف التشغيل", b"stop_bot"), Button.inline("▶️ بدء التشغيل", b"start_bot")]
    ]

@user_client.on(events.NewMessage(pattern='/start'))
async def user_start(event):
    sender_id = event.sender_id
    
    if sender_id in approved_users:
        await event.respond("أهلاً بك مجدداً! اختر ما يناسبك من القائمة:", buttons=get_user_menu())
        return
        
    # فحص مهلة الدقيقة للطلبات المتكررة
    now = datetime.now()
    if sender_id in pending_requests:
        last_req = pending_requests[sender_id]
        if now - last_req < timedelta(minutes=1):
            remaining = 60 - int((now - last_req).total_seconds())
            await event.respond(f"⚠️ يرجى الانتظار {remaining} ثانية قبل إرسال طلب تفعيل جديد.")
            return

    await event.respond(
        "أهلاً بك في البوت. للبدء، يرجى النقر على زر طلب تفعيل الحساب أدناه:",
        buttons=[[Button.inline("🔓 تفعيل البوت", f"req_act_{sender_id}".encode())]]
    )

@user_client.on(events.CallbackQuery)
async def user_callbacks(event):
    data = event.data.decode('utf-8')
    sender_id = event.sender_id
    
    if data.startswith("req_act_"):
        user_id = int(data.split("_")[2])
        pending_requests[user_id] = datetime.now()
        
        # إرسال طلب للأدمن في بوت التحكم مع أزرار القبول والرفض
        await control_client.send_message(
            ADMIN_ID,
            f"🔔 طلب تفعيل جديد من المستخدم: `{user_id}`",
            buttons=[
                [Button.inline("✅ قبول", f"acc_{user_id}".encode()), Button.inline("❌ رفض", f"rej_{user_id}".encode())]
            ]
        )
        await event.answer("تم إرسال طلبك للمالك، يرجى الانتظار...", alert=True)
        return

    # تفاعلات القائمة الرئيسية للمستخدم
    if sender_id not in approved_users:
        await event.answer("حسابك غير مفعل بعد!", alert=True)
        return
        
    if data == "set_speed":
        user_states[sender_id] = "waiting_user_speed"
        await event.respond("أرسل الآن رقم السرعة (بالثواني بين كل سطر من 0 إلى 60):")
        await event.answer()
        
    elif data == "set_prefix":
        user_states[sender_id] = "waiting_user_prefix"
        await event.respond("أرسل البادئة (الاسم) التي تريدها في بداية كل سطر:")
        await event.answer()
        
    elif data == "toggle_settings":
        cfg = user_settings.get(sender_id, {"start_kw": "#1", "stop_kw": "#2"})
        msg = f"⚙️ إعدادات الكلمات المفتاحية الحالية:\n- كلمة التشغيل: {cfg['start_kw']}\n- كلمة الإيقاف: {cfg['stop_kw']}\n\nاختر ما تريد تعديله:"
        await event.respond(msg, buttons=[
            [Button.inline("تعديل كلمة التشغيل", b"ed_start"), Button.inline("تعديل كلمة الإيقاف", b"ed_stop")],
            [Button.inline("🔙 رجوع", b"usr_menu")]
        ])
        await event.answer()
        
    elif data == "ed_start":
        user_states[sender_id] = "waiting_user_start_kw"
        await event.respond("أرسل كلمة التشغيل الجديدة (لا يمكن تركها فارغة):")
        await event.answer()
        
    elif data == "ed_stop":
        user_states[sender_id] = "waiting_user_stop_kw"
        await event.respond("أرسل كلمة الإيقاف الجديدة (لا يمكن تركها فارغة):")
        await event.answer()
        
    elif data == "usr_menu":
        await event.respond("القائمة الرئيسية:", buttons=get_user_menu())
        await event.answer()

    elif data == "account_status":
        cfg = user_settings.get(sender_id, {"speed": 0, "prefix": "لا توجد", "start_kw": "#1", "stop_kw": "#2"})
        status_text = (
            f"📊 **حالة حسابك:**\n"
            f"- الحالة: ✅ مفعل\n"
            f"- السرعة: {cfg.get('speed', 0)} ثانية\n"
            f"- البادئة: {cfg.get('prefix', 'لا توجد')}\n"
            f"- كلمة التشغيل: {cfg.get('start_kw', '#1')}\n"
            f"- كلمة الإيقاف: {cfg.get('stop_kw', '#2')}"
        )
        await event.respond(status_text, buttons=get_user_menu())
        await event.answer()

# معالجة قبول أو رفض الأدمن للطلبات الواردة من بوت التحكم
@control_client.on(events.CallbackQuery)
async def admin_decision_callbacks(event):
    if event.sender_id != ADMIN_ID:
        return
    data = event.data.decode('utf-8')
    
    if data.startswith("acc_"):
        user_id = int(data.split("_")[1])
        approved_users.add(user_id)
        await user_client.send_message(user_id, "✅ تم قبول طلب تفعيل حسابك بنجاح! أرسل /start لبدء استخدام القائمة.")
        await event.edit("تم قبول المستخدم بنجاح وإشعاره.")
        
    elif data.startswith("rej_"):
        user_id = int(data.split("_")[1])
        await user_client.send_message(user_id, "❌ عذراً، تم رفض طلب تفعيل حسابك من قِبل المالك.")
        await event.edit("تم رفض المستخدم وإشعاره.")

@user_client.on(events.NewMessage(incoming=True))
async def user_messages(event):
    sender_id = event.sender_id
    if sender_id not in user_states:
        return
        
    state = user_states[sender_id]
    text = event.raw_text.strip()
    
    if state == "waiting_user_speed":
        if text.isdigit() and 0 <= int(text) <= 60:
            user_settings.setdefault(sender_id, {})['speed'] = int(text)
            user_states.pop(sender_id, None)
            await event.respond(f"✅ تمت الإفادة بحفظ السرعة: {text} ثواني.", buttons=get_user_menu())
        else:
            await event.respond("❌ خطأ: السرعة يجب أن تكون رقماً بين 0 و 60 حصراً. حاول مجدداً:")
            
    elif state == "waiting_user_prefix":
        if text:
            user_settings.setdefault(sender_id, {})['prefix'] = text
            user_states.pop(sender_id, None)
            await event.respond(f"✅ تم حفظ البادئة: `{text}`", buttons=get_user_menu())
            
    elif state == "waiting_user_start_kw":
        if text:
            user_settings.setdefault(sender_id, {})['start_kw'] = text
            user_states.pop(sender_id, None)
            await event.respond(f"✅ تم تحديث كلمة التشغيل: `{text}`", buttons=get_user_menu())
            
    elif state == "waiting_user_stop_kw":
        if text:
            user_settings.setdefault(sender_id, {})['stop_kw'] = text
            user_states.pop(sender_id, None)
            await event.respond(f"✅ تم تحديث كلمة الإيقاف: `{text}`", buttons=get_user_menu())

# --- تشغيل الخدمة بالكامل ---
if __name__ == '__main__':
    keep_alive()  # تشغيل خادم الحفاظ على البقاء 24/7
    print("Starting Control Bot and User Bot concurrently...")
    
    loop = asyncio.get_event_loop()
    loop.create_task(control_client.start(bot_token=CONTROL_BOT_TOKEN))
    loop.create_task(user_client.start(bot_token=USER_BOT_TOKEN))
    
    loop.run_forever()
