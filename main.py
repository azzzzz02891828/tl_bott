import os
import sqlite3
import threading
import time
import random
from flask import Flask
import telebot
from telebot import types

# === إعدادات البوتات المضافة مباشرة ===
ADMIN_BOT_TOKEN = "8936206172:AAEV0LFdeUcwlfXkpIn5JyoTLsImNBnRtWI"
USER_BOT_TOKEN = "8838773401:AAH8gaPm2-VjOhhE6WHO-yqhw1Su1AOlb_g"
ADMIN_ID = 5885382011

admin_bot = telebot.TeleBot(ADMIN_BOT_TOKEN)
user_bot = telebot.TeleBot(USER_BOT_TOKEN)

# === إعداد قاعدة البيانات SQLite ===
def init_db():
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            status TEXT DEFAULT 'none',
            request_time REAL DEFAULT 0,
            expiry_time REAL DEFAULT 0,
            gender TEXT DEFAULT 'ذكر',
            custom_name TEXT DEFAULT ''
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gender TEXT,
            word TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS singulars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT
        )
    """)
    
    conn.commit()
    conn.close()

init_db()

def get_setting(key, default=""):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else default

def set_setting(key, value):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

# إعداد القيم الافتراضية إذا لم تكن موجودة
if not get_setting("bot_active"): set_setting("bot_active", "1")
if not get_setting("speed"): set_setting("speed", "متوسط")
if not get_setting("start_keyword"): set_setting("start_keyword", "السلام")
if not get_setting("stop_keyword"): set_setting("stop_keyword", "إيقاف")


# ==================== بوت المستخدم (User Bot) ====================

@user_bot.message_handler(commands=['start'])
def user_start(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT status, request_time, expiry_time FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    current_time = time.time()
    
    if row:
        status, req_time, exp_time = row
        if status == 'active':
            if exp_time > 0 and current_time > exp_time:
                cursor.execute("UPDATE users SET status = 'expired' WHERE user_id = ?", (user_id,))
                conn.commit()
                user_bot.reply_to(message, "انتهت فترة اشتراكك في البوت.")
                conn.close()
                return
            user_bot.reply_to(message, "أهلاً بك! بوتك مفعل ويعمل بنجاح ✅")
            conn.close()
            return
        elif status == 'pending':
            user_bot.reply_to(message, "لقد قمت مسبقاً بإرسال طلب تفعيل، يرجى الانتظار حتى يراجع المالك طلبك ⏳")
            conn.close()
            return
        elif status == 'rejected':
            if current_time - req_time < 300: # 5 دقائق (300 ثانية)
                remaining = int(300 - (current_time - req_time))
                mins = remaining // 60
                secs = remaining % 60
                user_bot.reply_to(message, f"تم رفض طلبك سابقاً. يمكنك إعادة المحاولة بعد {mins} دقيقة و {secs} ثانية.")
                conn.close()
                return

    # إنشاء زر التفعيل
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("تفعيل ✅", callback_data=f"request_activate_{user_id}"))
    
    # تحديث البيانات كطلب جديد
    cursor.execute("""
        INSERT OR REPLACE INTO users (user_id, username, status, request_time) 
        VALUES (?, ?, 'pending', ?)
    """, (user_id, username, current_time))
    conn.commit()
    conn.close()
    
    user_bot.reply_to(message, "أهلاً بك في بوت الخدمة. اضغط على الزر أدناه لإرسال طلب تفعيل للمالك:", reply_markup=markup)

@user_bot.callback_query_handler(func=lambda call: call.data.startswith("request_activate_"))
def handle_activation_request(call):
    user_id = call.from_user.id
    username = call.from_user.username or call.from_user.first_name
    
    # إرسال إشعار لبوت التحكم عند المالك
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("قبول 1 يوم 📅", callback_data=f"accept_1d_{user_id}"),
        types.InlineKeyboardButton("قبول أسبوع 📆", callback_data=f"accept_1w_{user_id}")
    )
    markup.row(
        types.InlineKeyboardButton("قبول شهر 🗓️", callback_data=f"accept_1m_{user_id}"),
        types.InlineKeyboardButton("قبول للابد ♾️", callback_data=f"accept_forever_{user_id}")
    )
    markup.add(types.InlineKeyboardButton("رفض ❌", callback_data=f"reject_{user_id}"))
    
    admin_bot.send_message(
        ADMIN_ID,
        f"📢 طلب تفعيل جديد!\n\n👤 المستخدم: @{username}\n🆔 الآي دي: `{user_id}`",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    
    user_bot.answer_callback_query(call.id, "تم إرسال طلبك للمالك بنجاح، يرجى الانتظار...")
    user_bot.edit_message_text("تم إرسال طلبك للمالك بنجاح، يرجى الانتظار حتى يتم القبول ⏳", call.message.chat.id, call.message.message_id)


# ==================== بوت التحكم (Admin Bot) ====================

@admin_bot.message_handler(commands=['start', 'admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    is_active = get_setting("bot_active") == "1"
    toggle_text = "إيقاف البوت 🔴" if is_active else "تشغيل البوت ✅"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(toggle_text, callback_data="toggle_bot"),
        types.InlineKeyboardButton("السرعة ⚡️", callback_data="set_speed"),
        types.InlineKeyboardButton("كلمة التشغيل ▶️", callback_data="set_start_kw"),
        types.InlineKeyboardButton("كلمة الإيقاف ⏹️", callback_data="set_stop_kw"),
        types.InlineKeyboardButton("الاسم ✏️", callback_data="set_name"),
        types.InlineKeyboardButton("السطور 📝", callback_data="manage_lines"),
        types.InlineKeyboardButton("الفرديات 📖", callback_data="manage_singulars"),
        types.InlineKeyboardButton("المشتركين 👥", callback_data="list_subscribers"),
        types.InlineKeyboardButton("كلمة عامة 📢", callback_data="broadcast_msg")
    )
    
    admin_bot.send_message(message.chat.id, "🛠️ **لوحة تحكم المشرف الأساسية:**", reply_markup=markup, parse_mode="Markdown")

@admin_bot.callback_query_handler(func=lambda call: True)
def admin_callbacks(call):
    if call.from_user.id != ADMIN_ID:
        return
    
    data = call.data
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    
    if data.startswith("accept_") or data.startswith("reject_"):
        parts = data.split("_")
        action = parts[1]
        user_id = int(parts[2])
        
        current_time = time.time()
        expiry_time = 0
        
        if action == "1d":
            expiry_time = current_time + 86400
            dur_text = "يوم واحد"
        elif action == "1w":
            expiry_time = current_time + (86400 * 7)
            dur_text = "أسبوع"
        elif action == "1m":
            expiry_time = current_time + (86400 * 30)
            dur_text = "شهر"
        elif action == "forever":
            expiry_time = 0 # للأبد
            dur_text = "للأبد"
            
        if action == "reject":
            cursor.execute("UPDATE users SET status = 'rejected', request_time = ? WHERE user_id = ?", (current_time, user_id))
            conn.commit()
            user_bot.send_message(user_id, "تم رفض طلبك من قبل المالك. يمكنك المحاولة مرة أخرى بعد 5 دقائق.")
            admin_bot.edit_message_text("تم رفض الطلب بنجاح ❌", call.message.chat.id, call.message.message_id)
        else:
            cursor.execute("UPDATE users SET status = 'active', expiry_time = ? WHERE user_id = ?", (expiry_time, user_id))
            conn.commit()
            user_bot.send_message(user_id, f"تم قبول طلبك بنجاح! البوت مفعل لمدة: {dur_text} 🎉")
            admin_bot.edit_message_text(f"تم قبول المستخدم بنجاح لمدة ({dur_text}) ✅", call.message.chat.id, call.message.message_id)
            
    elif data == "toggle_bot":
        current = get_setting("bot_active")
        new_val = "0" if current == "1" else "1"
        set_setting("bot_active", new_val)
        admin_bot.answer_callback_query(call.id, "تم تغيير حالة البوت بنجاح")
        admin_panel(call.message)
        
    elif data == "set_speed":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("بطيء 🐢 (كل 10 ثواني)", callback_data="speed_slow"),
            types.InlineKeyboardButton("متوسط 🏃 (كل 5 ثواني)", callback_data="speed_med"),
            types.InlineKeyboardButton("سريع 💨 (كل 3 ثواني)", callback_data="speed_fast"),
            types.InlineKeyboardButton("شخص خارجي 💻 (كل ثانية)", callback_data="speed_ext"),
            types.InlineKeyboardButton("سرعة قصوى ⚡️ (سطرين بالثانية)", callback_data="speed_max"),
            types.InlineKeyboardButton("عودة 🔙", callback_data="back_home")
        )
        admin_bot.edit_message_text("اختر السرعة المطلوبة:", call.message.chat.id, call.message.message_id, reply_markup=markup)
        
    elif data.startswith("speed_"):
        speed_map = {
            "speed_slow": "بطيء",
            "speed_med": "متوسط",
            "speed_fast": "سريع",
            "speed_ext": "شخص خارجي",
            "speed_max": "سرعة قصوى"
        }
        set_setting("speed", speed_map[data])
        admin_bot.answer_callback_query(call.id, f"تم ضبط السرعة إلى: {speed_map[data]}")
        admin_panel(call.message)
        
    elif data == "manage_lines":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("ذكر 🧍‍♂️", callback_data="edit_words_ذكر"),
            types.InlineKeyboardButton("أنثى 🧍‍♀️", callback_data="edit_words_أنثى"),
            types.InlineKeyboardButton("عودة 🔙", callback_data="back_home")
        )
        admin_bot.edit_message_text("اختر الجنس لإدارة السطور والكلمات الخاصة به:", call.message.chat.id, call.message.message_id, reply_markup=markup)
        
    elif data.startswith("edit_words_"):
        gender = data.split("_")[2]
        msg = admin_bot.send_message(call.message.chat.id, f"أرسل الكلمات الخاصة بـ ({gender}) مفصولة بفواصل (مثال: هاي,السلام,عليكم):")
        admin_bot.register_next_step_handler(msg, save_word_list, gender)
        
    elif data == "manage_singulars":
        msg = admin_bot.send_message(call.message.chat.id, "أرسل الفرديات الجديدة المطلوبة:")
        admin_bot.register_next_step_handler(msg, save_singulars_handler)
        
    elif data == "list_subscribers":
        cursor.execute("SELECT user_id, username, status, request_time FROM users")
        users = cursor.fetchall()
        if not users:
            admin_bot.answer_callback_query(call.id, "لا يوجد مشتركين حالياً.")
            conn.close()
            return
        
        text = "👥 **قائمة المشتركين:**\n\n"
        for u in users:
            uid, uname, ustat, rtime = u
            text += f"👤 @{uname}\n🆔 `{uid}`\nحالة النشاط: {ustat}\n------------------\n"
            
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("طرد مشترك (أرسل الآي دي)", callback_data="kick_user_prompt"))
        markup.add(types.InlineKeyboardButton("عودة 🔙", callback_data="back_home"))
        admin_bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        
    elif data == "kick_user_prompt":
        msg = admin_bot.send_message(call.message.chat.id, "أرسل آي دي (ID) المستخدم المراد طرده:")
        admin_bot.register_next_step_handler(msg, kick_user_handler)
        
    elif data == "broadcast_msg":
        msg = admin_bot.send_message(call.message.chat.id, "أرسل الكلمة أو الرسالة العامة التي تريد إرسالها لجميع المشتركين:")
        admin_bot.register_next_step_handler(msg, broadcast_handler)
        
    elif data == "set_start_kw":
        msg = admin_bot.send_message(call.message.chat.id, "أرسل كلمة التشغيل الجديدة:")
        admin_bot.register_next_step_handler(msg, lambda m: update_setting_handler(m, "start_keyword"))
        
    elif data == "set_stop_kw":
        msg = admin_bot.send_message(call.message.chat.id, "أرسل كلمة الإيقاف الجديدة:")
        admin_bot.register_next_step_handler(msg, lambda m: update_setting_handler(m, "stop_keyword"))
        
    elif data == "set_name":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("إزالة اسم الشخص ❌", callback_data="remove_custom_name"))
        markup.add(types.InlineKeyboardButton("عودة 🔙", callback_data="back_home"))
        msg = admin_bot.send_message(call.message.chat.id, "أرسل الاسم الذي تريد إضافته مع السطور أو اختر إزالة:", reply_markup=markup)
        admin_bot.register_next_step_handler(msg, save_custom_name_handler)
        
    elif data == "remove_custom_name":
        cursor.execute("UPDATE users SET custom_name = ''")
        conn.commit()
        admin_bot.answer_callback_query(call.id, "تم إزالة الاسم المخصص بنجاح.")
        admin_panel(call.message)
        
    elif data == "back_home":
        admin_panel(call.message)
        
    conn.close()

def save_word_list(message, gender):
    if message.from_user.id != ADMIN_ID:
        return
    text = message.text
    words = [w.strip() for w in text.split(",") if w.strip()]
    
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM words WHERE gender = ?", (gender,))
    for w in words:
        cursor.execute("INSERT INTO words (gender, word) VALUES (?, ?)", (gender, w))
    conn.commit()
    conn.close()
    
    admin_bot.reply_to(message, f"تم حفظ السطور الخاصة بـ ({gender}) بنجاح! ✅")

def save_singulars_handler(message):
    if message.from_user.id != ADMIN_ID:
        return
    text = message.text
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO singulars (word) VALUES (?)", (text,))
    conn.commit()
    conn.close()
    admin_bot.reply_to(message, "تم حفظ الفرديات بنجاح ✅")

def kick_user_handler(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        target_id = int(message.text.strip())
        conn = sqlite3.connect("bot_database.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET status = 'kicked' WHERE user_id = ?", (target_id,))
        conn.commit()
        conn.close()
        admin_bot.reply_to(message, f"تم طرد المستخدم ذو الآي دي {target_id} بنجاح 🚫")
        user_bot.send_message(target_id, "تم طردك من البوت بواسطة المالك.")
    except Exception as e:
        admin_bot.reply_to(message, f"حدث خطأ: {e}")

def broadcast_handler(message):
    if message.from_user.id != ADMIN_ID:
        return
    text = message.text
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE status = 'active'")
    active_users = cursor.fetchall()
    conn.close()
    
    count = 0
    for u in active_users:
        try:
            user_bot.send_message(u[0], text)
            count += 1
        except:
            pass
            
    admin_bot.reply_to(message, f"تم إرسال الكلمة العامة بنجاح إلى {count} مشترك نشط 📢")

def update_setting_handler(message, key):
    if message.from_user.id != ADMIN_ID:
        return
    set_setting(key, message.text.strip())
    admin_bot.reply_to(message, "تم التحديث بنجاح ✅")

def save_custom_name_handler(message):
    if message.from_user.id != ADMIN_ID:
        return
    name = message.text.strip()
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET custom_name = ?", (name,))
    conn.commit()
    conn.close()
    admin_bot.reply_to(message, f"تم حفظ الاسم المخصص ({name}) بنجاح ✅")


# ==================== خادم Flask لمنع وضع النوم (Keep-Alive) ====================

app = Flask('')

@app.route('/')
def home():
    return "Bot is running and active!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)


# ==================== التشغيل المتزامن للبوتات وخادم الويب ====================

def run_admin_bot():
    while True:
        try:
            admin_bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            time.sleep(5)

def run_user_bot():
    while True:
        try:
            user_bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            time.sleep(5)

if __name__ == "__main__":
    # تشغيل خادم الويب في خيط مستقل (Thread) لمنع نوم التطبيق على Render
    t_flask = threading.Thread(target=run_flask)
    t_flask.daemon = True
    t_flask.start()
    
    # تشغيل بوت التحكم في خيط مستقل
    t_admin = threading.Thread(target=run_admin_bot)
    t_admin.daemon = True
    t_admin.start()
    
    # تشغيل بوت المستخدم في الخيط الرئيسي
    run_user_bot()
