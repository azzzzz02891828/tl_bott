import sqlite3
import random
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from keep_alive import keep_alive

# ==================== 🔑 التوكنات المدمجة ====================
USER_BOT_TOKEN = "8838773401:AAH8gaPm2-VjOhhE6WHO-yqhw1Su1AOlb_g"
ADMIN_BOT_TOKEN = "8936206172:AAEV0LFdeUcwlfXkpIn5JyoTLsImNBnRtWI"
ADMIN_ID = 5885382011
# ============================================================

user_bot = Bot(token=USER_BOT_TOKEN)
admin_bot = Bot(token=ADMIN_BOT_TOKEN)

dp_user = Dispatcher(storage=MemoryStorage())
dp_admin = Dispatcher(storage=MemoryStorage())

class AdminStates(StatesGroup):
    waiting_for_male_lines = State()
    waiting_for_female_lines = State()
    waiting_for_individuals = State()
    waiting_for_broadcast = State()

class UserStates(StatesGroup):
    waiting_for_custom_name = State()

def init_db():
    conn = sqlite3.connect('bot_system.db', timeout=10)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            gender TEXT DEFAULT 'male',
            custom_name TEXT DEFAULT '',
            speed TEXT DEFAULT 'medium',
            start_keyword TEXT DEFAULT 'السلام',
            stop_keyword TEXT DEFAULT 'إيقاف',
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
    # user_data structure: (user_id, username, gender, custom_name, speed, start_keyword, stop_keyword, is_running)
    is_running = user_data[7]
    speed = user_data[4]
    gender = user_data[2]
    has_name = bool(user_data[3])

    status_btn = InlineKeyboardButton(text="إيقاف البوت 🔴" if is_running else "تشغيل البوت ✅", callback_data="toggle_run")
    speed_btn = InlineKeyboardButton(text=f"السرعة ⚡️ ({speed})", callback_data="change_speed")
    start_kw_btn = InlineKeyboardButton(text="كلمة التشغيل ▶️", callback_data="set_start_kw")
    stop_kw_btn = InlineKeyboardButton(text="كلمة الإيقاف ⏹️", callback_data="set_stop_kw")
    
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

@dp_user.message(Command("start"))
async def user_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "بدون_يوزر"
    
    conn = sqlite3.connect('bot_system.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if not row:
        cursor.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
    conn.close()
    await message.answer("أهلاً بك! لوحة التحكم الخاصة بك تعمل بكامل المميزات:", reply_markup=get_user_markup(row))

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
        [InlineKeyboardButton(text="سرعة قصوى ⚡️ (سطرين بالثانية)", callback_data="setspeed_max")]
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
        await callback.message.answer("✏️ أرسل الاسم الذي تريد إضافته:")

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

# ==============================================================
# 👑 بوت التحكم (للإدارة وتعبئة المحتوى فقط)
# ==============================================================

@dp_admin.message(Command("start"))
async def admin_start(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 السطور", callback_data="admin_lines"),
         InlineKeyboardButton(text="📖 الفرديات", callback_data="admin_individuals")],
        [InlineKeyboardButton(text="📢 كلمة عامة", callback_data="admin_broadcast")]
    ])
    await message.answer("أهلاً بك في لوحة تحكم المالك 👑:", reply_markup=keyboard)

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
        [InlineKeyboardButton(text="📢 كلمة عامة", callback_data="admin_broadcast")]
    ])
    await callback.message.edit_text("لوحة تحكم المالك 👑:", reply_markup=keyboard)

@dp_admin.callback_query(F.data == "set_male_lines")
async def prompt_male(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_male_lines)
    await callback.message.answer("أرسل كلمات (ذكر):")

@dp_admin.message(AdminStates.waiting_for_male_lines)
async def save_male_lines(message: types.Message, state: FSMContext):
    conn = sqlite3.connect('bot_system.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM admin_content WHERE category = 'male_lines'")
    cursor.execute("INSERT INTO admin_content (category, content) VALUES ('male_lines', ?)", (message.text,))
    conn.commit()
    conn.close()
    await state.clear()
    await message.answer("✅ تم الحفظ بنجاح!")

@dp_admin.callback_query(F.data == "set_female_lines")
async def prompt_female(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_female_lines)
    await callback.message.answer("أرسل كلمات (أنثى):")

@dp_admin.message(AdminStates.waiting_for_female_lines)
async def save_female_lines(message: types.Message, state: FSMContext):
    conn = sqlite3.connect('bot_system.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM admin_content WHERE category = 'female_lines'")
    cursor.execute("INSERT INTO admin_content (category, content) VALUES ('female_lines', ?)", (message.text,))
    conn.commit()
    conn.close()
    await state.clear()
    await message.answer("✅ تم الحفظ بنجاح!")

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
    await message.answer("✅ تم الحفظ بنجاح!")

@dp_admin.callback_query(F.data == "admin_broadcast")
async def broadcast_prompt(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_broadcast)
    await callback.message.answer("أرسل الكلمة العامة لنشرها لجميع المستخدمين:")

@dp_admin.message(AdminStates.waiting_for_broadcast)
async def do_broadcast(message: types.Message, state: FSMContext):
    text = message.text
    conn = sqlite3.connect('bot_system.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()

    count = 0
    for u in users:
        try:
            await user_bot.send_message(u[0], text)
            count += 1
        except:
            pass

    await state.clear()
    await message.answer(f"📢 تم الإرسال لـ ({count}) مستخدم بنجاح!")

keep_alive()

async def main():
    print("🚀 جاري إقلاع البوتين وسيرفر الويب...")
    await asyncio.gather(
        dp_user.start_polling(user_bot, drop_pending_updates=True),
        dp_admin.start_polling(admin_bot, drop_pending_updates=True)
    )

if __name__ == "__main__":
    asyncio.run(main())
