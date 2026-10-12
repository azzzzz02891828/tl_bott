import sqlite3
import random
import asyncio
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from keep_alive import keep_alive

# ==================== 🔑 التوكنات والبيانات ====================
USER_BOT_TOKEN = "8838773401:AAH8gaPm2-VjOhhE6WHO-yqhw1Su1AOlb_g"
ADMIN_BOT_TOKEN = "8936206172:AAEV0LFdeUcwlfXkpIn5JyoTLsImNBnRtWI"
ADMIN_ID = 5885382011

# ملاحظة: لعمل UserBot حقيقي يدخل بالحساب، يفضل وضع API_ID و API_HASH (يمكن جلبها من my.telegram.org)
# سنقوم بتشغيل بوت إداري تفاعلي وبوت مستخدم يراقب الكلمات المفتاحية.
# ============================================================

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

user_bot_api = Bot(token=USER_BOT_TOKEN)
admin_bot_api = Bot(token=ADMIN_BOT_TOKEN)

dp_user = Dispatcher(storage=MemoryStorage())
dp_admin = Dispatcher(storage=MemoryStorage())

class AdminStates(StatesGroup):
    waiting_for_male_lines = State()
    waiting_for_female_lines = State()
    waiting_for_individuals = State()
    waiting_for_broadcast = State()

class UserStates(StatesGroup):
    waiting_for_custom_name = State()
    waiting_for_start_kw = State()
    waiting_for_stop_kw = State()

def init_db():
    conn = sqlite3.connect('bot_system.db', timeout=10)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            status TEXT DEFAULT 'pending',
            expiry_date TEXT,
            last_request_time TEXT,
            gender TEXT DEFAULT 'male',
            custom_name TEXT DEFAULT '',
            speed TEXT DEFAULT 'medium',
            start_keyword TEXT DEFAULT 'س',
            stop_keyword TEXT DEFAULT 'ق',
            is_running INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            content TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_user_markup(user_data):
    is_running = user_data[10]
    speed = user_data[7]
    gender = user_data[5]
    has_name = bool(user_data[6])

    status_btn = InlineKeyboardButton(text="إيقاف البوت 🔴" if is_running else "تشغيل البوت ✅", callback_data="toggle_run")
    speed_btn = InlineKeyboardButton(text=f"السرعة ⚡️ ({speed})", callback_data="change_speed")
    start_kw_btn = InlineKeyboardButton(text=f"كلمة التشغيل ▶️ ({user_data[8]})", callback_data="set_start_kw")
    stop_kw_btn = InlineKeyboardButton(text=f"كلمة الإيقاف ⏹️ ({user_data[9]})", callback_data="set_stop_kw")
    
    name_btn_text = "ازالة اسم الشخص ❌" if has_name else "الاسم ✏️"
    name_btn = InlineKeyboardButton(text=name_btn_text, callback_data="toggle_name")
    
    male_check = "✅" if gender == "male" else ""
    female_check = "✅" if gender == "female" else ""
    gender_btn = InlineKeyboardButton(text=f"الجنس (ذكر {male_check} / أنثى {female_check})", callback_data="toggle_gender")
    individual_btn = InlineKeyboardButton(text="فرديات 📖", callback_data="user_individuals")

    return InlineKeyboardMarkup(inline_keyboard=[
        [status_btn],
        [speed_btn],
        [start_kw_btn, stop_kw_btn],
        [name_btn, gender_btn],
        [individual_btn]
    ])

# ==================== واجهة بوت المستخدم (Aiogram) ====================
@dp_user.message(Command("start"))
async def user_start(message: types.Message):
    user_id = message.from_user.id
    conn = sqlite3.connect('bot_system.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    if row and row[2] == 'active':
        if row[3] != 'forever':
            try:
                if datetime.now() > datetime.fromisoformat(row[3]):
                    conn = sqlite3.connect('bot_system.db')
                    cursor = conn.cursor()
                    cursor.execute("UPDATE users SET status = 'expired', is_running = 0 WHERE user_id = ?", (user_id,))
                    conn.commit()
                    conn.close()
                    await message.answer("❌ انتهت فترة اشتراكك في البوت. يرجى طلب تفعيل جديد.")
                    return
            except:
                pass
        await message.answer("أهلاً بك! لوحة التحكم الخاصة بك:", reply_markup=get_user_markup(row))
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="تفعيل ✅", callback_data="request_activation")]
        ])
        await message.answer("مرحباً بك! اضغط على زر (تفعيل ✅) لطلب التفعيل من المالك:", reply_markup=keyboard)

@dp_user.callback_query(F.data == "request_activation")
async def process_activation(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    username = callback.from_user.username or "بدون_يوزر"
    now = datetime.now()
    
    conn = sqlite3.connect('bot_system.db')
    cursor = conn.cursor()
    cursor.execute("SELECT last_request_time, status FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if row and row[1] == 'active':
        await callback.answer("البوت مفعل لديك بالفعل! ✅", show_alert=True)
        conn.close()
        return
        
    if row and row[0]:
        last_req = datetime.fromisoformat(row[0])
        diff = (now - last_req).total_seconds()
        if diff < 300: # 5 دقائق كولداون إجباري
            remaining = int(300 - diff)
            mins, secs = divmod(remaining, 60)
            await callback.answer(f"⏳ يجب الانتظار {mins} دقيقة و {secs} ثانية لإعادة إرسال الطلب.", show_alert=True)
            conn.close()
            return

    cursor.execute('''
        INSERT INTO users (user_id, username, status, last_request_time) 
        VALUES (?, ?, 'pending', ?)
        ON CONFLICT(user_id) DO UPDATE SET status='pending', last_request_time=?
    ''', (user_id, username, now.isoformat(), now.isoformat()))
    conn.commit()
    conn.close()
    
    await callback.message.edit_text("⏳ تم إرسال طلبك للمالك بنجاح. يرجى الانتظار لحين الموافقة.")
    
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="قبول ✅", callback_data=f"accept_{user_id}"),
            InlineKeyboardButton(text="رفض ❌", callback_data=f"reject_{user_id}")
        ]
    ])
    try:
        await admin_bot_api.send_message(
            ADMIN_ID, 
            f"📢 طلب تفعيل جديد:\n👤 المستخدم: @{username}\n🆔 الآيدي: `{user_id}`", 
            reply_markup=admin_kb,
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Error notifying admin: {e}")

@dp_user.callback_query(F.data == "toggle_run")
async def toggle_run_status(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    conn = sqlite3.connect('bot_system.db')
    cursor = conn.cursor()
    cursor.execute("SELECT is_running FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    if res:
        new_val = 0 if res[0] == 1 else 1
        cursor.execute("UPDATE users SET is_running = ? WHERE user_id = ?", (new_val, user_id))
        conn.commit()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    await callback.message.edit_text("حالة البوت تم تحديثها:", reply_markup=get_user_markup(row))

@dp_user.callback_query(F.data == "change_speed")
async def speed_menu(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="بطيء 🐢 (10 ثواني)", callback_data="setspeed_slow")],
        [InlineKeyboardButton(text="متوسط 🏃 (5 ثواني)", callback_data="setspeed_medium")],
        [InlineKeyboardButton(text="سريع 💨 (3 ثواني)", callback_data="setspeed_fast")],
        [InlineKeyboardButton(text="شخص خارجي 💻 (ثانية واحدة)", callback_data="setspeed_pro")],
        [InlineKeyboardButton(text="سرعة قصوى ⚡️ (سطرين بالثانية)", callback_data="setspeed_max")],
        [InlineKeyboardButton(text="عودة ↩️", callback_data="back_home")]
    ])
    await callback.message.edit_text("اختر السرعة المطلوبة:", reply_markup=kb)

@dp_user.callback_query(F.data.startswith("setspeed_"))
async def set_speed_val(callback: types.CallbackQuery):
    spd = callback.data.split("_")[1]
    user_id = callback.from_user.id
    conn = sqlite3.connect('bot_system.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET speed = ? WHERE user_id = ?", (spd, user_id))
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    await callback.message.edit_text("✅ تم تحديث السرعة بنجاح!", reply_markup=get_user_markup(row))

@dp_user.callback_query(F.data == "set_start_kw")
async def ask_start_kw(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.waiting_for_start_kw)
    await callback.message.answer("أرسل كلمة التشغيل المفتاحية الجديدة:")

@dp_user.message(UserStates.waiting_for_start_kw)
async def save_start_kw(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    kw = message.text
    conn = sqlite3.connect('bot_system.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET start_keyword = ? WHERE user_id = ?", (kw, user_id))
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    await state.clear()
    await message.answer(f"✅ تم تحديث كلمة التشغيل إلى: ({kw})", reply_markup=get_user_markup(row))

@dp_user.callback_query(F.data == "set_stop_kw")
async def ask_stop_kw(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.waiting_for_stop_kw)
    await callback.message.answer("أرسل كلمة الإيقاف المفتاحية الجديدة:")

@dp_user.message(UserStates.waiting_for_stop_kw)
async def save_stop_kw(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    kw = message.text
    conn = sqlite3.connect('bot_system.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET stop_keyword = ? WHERE user_id = ?", (kw, user_id))
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    await state.clear()
    await message.answer(f"✅ تم تحديث كلمة الإيقاف إلى: ({kw})", reply_markup=get_user_markup(row))

@dp_user.callback_query(F.data == "toggle_gender")
async def toggle_gender_fn(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    conn = sqlite3.connect('bot_system.db')
    cursor = conn.cursor()
    cursor.execute("SELECT gender FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row:
        new_g = "female" if row[0] == "male" else "male"
        cursor.execute("UPDATE users SET gender = ? WHERE user_id = ?", (new_g, user_id))
        conn.commit()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    updated_row = cursor.fetchone()
    conn.close()
    await callback.message.edit_text("تم تغيير الجنس بنجاح:", reply_markup=get_user_markup(updated_row))

@dp_user.callback_query(F.data == "toggle_name")
async def toggle_name_fn(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    conn = sqlite3.connect('bot_system.db')
    cursor = conn.cursor()
    cursor.execute("SELECT custom_name FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row and row[0]:
        cursor.execute("UPDATE users SET custom_name = '' WHERE user_id = ?", (user_id,))
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        updated = cursor.fetchone()
        conn.close()
        await callback.message.edit_text("❌ تم إزالة الاسم بنجاح.", reply_markup=get_user_markup(updated))
    else:
        conn.close()
        await state.set_state(UserStates.waiting_for_custom_name)
        await callback.message.answer("✏️ أرسل الاسم الذي تريد إضافته للسطور:")

@dp_user.message(UserStates.waiting_for_custom_name)
async def save_custom_name(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    name_val = message.text
    conn = sqlite3.connect('bot_system.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET custom_name = ? WHERE user_id = ?", (name_val, user_id))
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    await state.clear()
    await message.answer("✅ تم حفظ الاسم بنجاح!", reply_markup=get_user_markup(row))

@dp_user.callback_query(F.data == "user_individuals")
async def show_user_individuals(callback: types.CallbackQuery):
    conn = sqlite3.connect('bot_system.db')
    cursor = conn.cursor()
    cursor.execute("SELECT content FROM admin_content WHERE category = 'individuals'")
    res = cursor.fetchone()
    conn.close()
    content = res[0] if res else "لا توجد فرديات مضافة حالياً."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="عودة ↩️", callback_data="back_home")]
    ])
    await callback.message.edit_text(f"📖 الفرديات:\n\n{content}", reply_markup=kb)

@dp_user.callback_query(F.data == "back_home")
async def back_home_fn(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    conn = sqlite3.connect('bot_system.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    await callback.message.edit_text("لوحة التحكم الخاصة بك:", reply_markup=get_user_markup(row))


# ==================== بوت التحكم (الإدارة) ====================
@dp_admin.message(Command("start"))
async def admin_start(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 السطور", callback_data="admin_lines"),
         InlineKeyboardButton(text="📖 الفرديات", callback_data="admin_individuals")],
        [InlineKeyboardButton(text="👥 المشتركين", callback_data="admin_subscribers"),
         InlineKeyboardButton(text="📢 كلمة عامة", callback_data="admin_broadcast")]
    ])
    await message.answer("أهلاً بك في لوحة تحكم المالك 👑:", reply_markup=keyboard)

@dp_admin.callback_query(F.data.startswith("reject_"))
async def admin_reject(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    conn = sqlite3.connect('bot_system.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET status = 'rejected', last_request_time = ? WHERE user_id = ?", (datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()
    await callback.message.edit_text("❌ تم رفض المستخدم.")
    try:
        await user_bot_api.send_message(user_id, "❌ تم رفض طلبك. يمكنك إعادة الإرسال بعد 5 دقائق.")
    except:
        pass

@dp_admin.callback_query(F.data.startswith("accept_"))
async def admin_accept(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="يوم واحد 📅", callback_data=f"dur_1_{user_id}"),
         InlineKeyboardButton(text="أسبوع 📆", callback_data=f"dur_7_{user_id}")],
        [InlineKeyboardButton(text="شهر 🗓️", callback_data=f"dur_30_{user_id}"),
         InlineKeyboardButton(text="للابد ♾️", callback_data=f"dur_forever_{user_id}")],
        [InlineKeyboardButton(text="عودة ↩️", callback_data="admin_home")]
    ])
    await callback.message.edit_text("اختر مدة الاشتراك للمستخدم:", reply_markup=kb)

@dp_admin.callback_query(F.data.startswith("dur_"))
async def set_duration(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    dur_type = parts[1]
    user_id = int(parts[2])
    expiry = "forever" if dur_type == "forever" else (datetime.now() + timedelta(days=int(dur_type))).isoformat()

    conn = sqlite3.connect('bot_system.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET status = 'active', expiry_date = ? WHERE user_id = ?", (expiry, user_id))
    conn.commit()
    conn.close()
    
    await callback.message.edit_text("✅ تم قبول وتفعيل المستخدم بنجاح!")
    try:
        await user_bot_api.send_message(user_id, "🎉 تم قبول طلبك وتفعيل البوت لديك بنجاح!")
    except:
        pass

@dp_admin.callback_query(F.data == "admin_lines")
async def admin_lines_menu(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ذكر 🧍‍♂️", callback_data="set_male_lines"),
         InlineKeyboardButton(text="أنثى 🧍‍♀️", callback_data="set_female_lines")],
        [InlineKeyboardButton(text="عودة ↩️", callback_data="admin_home")]
    ])
    await callback.message.edit_text("اختر القسم لإضافة السطور:", reply_markup=kb)

@dp_admin.callback_query(F.data == "admin_home")
async def admin_home(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 السطور", callback_data="admin_lines"),
         InlineKeyboardButton(text="📖 الفرديات", callback_data="admin_individuals")],
        [InlineKeyboardButton(text="👥 المشتركين", callback_data="admin_subscribers"),
         InlineKeyboardButton(text="📢 كلمة عامة", callback_data="admin_broadcast")]
    ])
    await callback.message.edit_text("لوحة تحكم المالك 👑:", reply_markup=keyboard)

@dp_admin.callback_query(F.data == "set_male_lines")
async def prompt_male(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_male_lines)
    await callback.message.answer("أرسل كلمات (ذكر) مفصولة بفواصل (مثال: هاي, السلام عليكم, شخبارك):")

@dp_admin.message(AdminStates.waiting_for_male_lines)
async def save_male_lines(message: types.Message, state: FSMContext):
    conn = sqlite3.connect('bot_system.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM admin_content WHERE category = 'male_lines'")
    cursor.execute("INSERT INTO admin_content (category, content) VALUES ('male_lines', ?)", (message.text,))
    conn.commit()
    conn.close()
    await state.clear()
    await message.answer("✅ تم حفظ سطور الذكر بنجاح!")

@dp_admin.callback_query(F.data == "set_female_lines")
async def prompt_female(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_female_lines)
    await callback.message.answer("أرسل كلمات (أنثى) مفصولة بفواصل:")

@dp_admin.message(AdminStates.waiting_for_female_lines)
async def save_female_lines(message: types.Message, state: FSMContext):
    conn = sqlite3.connect('bot_system.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM admin_content WHERE category = 'female_lines'")
    cursor.execute("INSERT INTO admin_content (category, content) VALUES ('female_lines', ?)", (message.text,))
    conn.commit()
    conn.close()
    await state.clear()
    await message.answer("✅ تم حفظ سطور الأنثى بنجاح!")

@dp_admin.callback_query(F.data == "admin_individuals")
async def prompt_individuals(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_individuals)
    await callback.message.answer("أرسل الفرديات:")

@dp_admin.message(AdminStates.waiting_for_individuals)
async def save_individuals(message: types.Message, state: FSMContext):
    conn = sqlite3.connect('bot_system.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM admin_content WHERE category = 'individuals'")
    cursor.execute("INSERT INTO admin_content (category, content) VALUES ('individuals', ?)", (message.text,))
    conn.commit()
    conn.close()
    await state.clear()
    await message.answer("✅ تم حفظ الفرديات بنجاح!")

@dp_admin.callback_query(F.data == "admin_subscribers")
async def show_subscribers(callback: types.CallbackQuery):
    conn = sqlite3.connect('bot_system.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, last_request_time FROM users WHERE status = 'active'")
    users = cursor.fetchall()
    conn.close()

    if not users:
        await callback.message.answer("لا توجد اشتراكات نشطة حالياً.")
        return

    for u in users:
        uid, uname, last_time = u
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="طرد 🚫", callback_data=f"kick_{uid}")]
        ])
        msg = f"👤 المستخدم: @{uname}\n🆔 الآيدي: `{uid}`\n📅 آخر نشاط: {str(last_time)[:16]}"
        await callback.message.answer(msg, reply_markup=kb, parse_mode="Markdown")

@dp_admin.callback_query(F.data.startswith("kick_"))
async def kick_user(callback: types.CallbackQuery):
    uid = int(callback.data.split("_")[1])
    conn = sqlite3.connect('bot_system.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET status = 'banned', is_running = 0 WHERE user_id = ?", (uid,))
    conn.commit()
    conn.close()
    await callback.message.edit_text("🚫 تم طرد المستخدم نهائياً وإيقافه.")
    try:
        await user_bot_api.send_message(uid, "🚫 تم طردك وإيقاف البوت من قبل المالك.")
    except:
        pass

@dp_admin.callback_query(F.data == "admin_broadcast")
async def broadcast_prompt(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_broadcast)
    await callback.message.answer("أرسل الكلمة العامة لنشرها لجميع المشتركين النشطين:")

@dp_admin.message(AdminStates.waiting_for_broadcast)
async def do_broadcast(message: types.Message, state: FSMContext):
    text = message.text
    conn = sqlite3.connect('bot_system.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE status = 'active'")
    users = cursor.fetchall()
    conn.close()

    count = 0
    for u in users:
        try:
            await user_bot_api.send_message(u[0], text)
            count += 1
        except:
            pass

    await state.clear()
    await message.answer(f"📢 تم إرسال الكلمة العامة لـ ({count}) مشترك بنجاح!")


# --- تشغيل Flask وسيرفر الويب وبوتات الإدارة والتشغيل التلقائي ---
keep_alive()

async def main():
    print("🚀 جاري إقلاع البوتين وسيرفر الويب...")
    await asyncio.gather(
        dp_user.start_polling(user_bot_api, drop_pending_updates=True),
        dp_admin.start_polling(admin_bot_api, drop_pending_updates=True)
    )

if __name__ == "__main__":
    asyncio.run(main())
