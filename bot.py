import os
import asyncio
from telethon import TelegramClient, events, Button
import nest_asyncio

nest_asyncio.apply()

# --- إعدادات النظام والثوابت الثابتة للآيفون ---
API_ID = 21727
API_HASH = "338d4380b2c15904fa77cfcb251d19d6"

# بياناتك الشخصية المحدثة
CLIENT_BOT_TOKEN = "8909604485:AAHpNrrzTtu_kwp5he2wM7QvaWZMsqYM1TQ"
ADMIN_BOT_TOKEN = "8750783959:AAE4uk0MlEJF43gWmXhasoz5eCZmHkf2fL0"
ADMIN_ID = 5885382011  # الآي دي الشخصي حقك

# إنشاء العميلين (Client Bot & Admin Bot)
client_bot = TelegramClient('client_bot_session', API_ID, API_HASH).start(bot_token=CLIENT_BOT_TOKEN)
admin_bot = TelegramClient('admin_bot_session', API_ID, API_HASH).start(bot_token=ADMIN_BOT_TOKEN)

print("🚀 جاري تشغيل بوتات التليجرام بنجاح...")

# --- منطق بوت العميل (استقبال الطلبات وإرسالها للإدارة) ---
@client_bot.on(events.NewMessage(pattern='/start'))
async def client_start(event):
    await event.respond("أهلاً بك! يرجى إرسال تفاصيل طلبك أو رسالتك وسيتم تحويلها للإدارة فوراً.")

@client_bot.on(events.NewMessage(func=lambda e: e.is_private and not e.text.startswith('/')))
async def receive_client_message(event):
    sender = await event.get_sender()
    user_id = sender.id
    user_name = sender.first_name or "مستخدم"
    msg_text = event.raw_text

    # إشعار الإدارة بوجود طلب جديد مع أزرار التحكم (قبول / رفض)
    notification_text = (
        f"📩 **طلب جديد قادم:**\n\n"
        f"👤 **المستخدم:** {user_name} (`{user_id}`)\n"
        f"💬 **الرسالة:** {msg_text}"
    )
    
    await admin_bot.send_message(
        ADMIN_ID,
        notification_text,
        buttons=[
            [Button.inline(b"✅ قبول", data=f"accept_{user_id}".encode()),
             Button.inline(b"❌ رفض", data=f"reject_{user_id}".encode())]
        ]
    )
    
    await event.respond("تم إرسال طلبك للإجابة أو المراجعة بنجاح، انتظر الرد.")

# --- منطق بوت الإدارة (التعامل مع الأزرار وتوجيه الردود) ---
@admin_bot.on(events.CallbackQuery(pattern=b'accept_'))
async def admin_accept(event):
    user_id = int(event.data.decode().split('_')[1])
    await event.answer("تم قبول الطلب وإشعار العميل.")
    await event.edit(f"{event.raw_text}\n\n✅ **الحالة:** تم القبول.")
    await client_bot.send_message(user_id, "✅ تم قبول طلبك من قِبل الإدارة بنجاح!")

@admin_bot.on(events.CallbackQuery(pattern=b'reject_'))
async def admin_reject(event):
    user_id = int(event.data.decode().split('_')[1])
    await event.answer("تم رفض الطلب.")
    await event.edit(f"{event.raw_text}\n\n❌ **الحالة:** تم الرفض.")
    await client_bot.send_message(user_id, "❌ عذراً، تم رفض طلبك من قِبل الإدارة.")

# تشغيل البوتات واستمراريتها
async def main():
    print("✨ البوتات تعمل الآن وجاهزة لاستقبال الرسائل...")
    await asyncio.gather(
        client_bot.run_until_disconnected(),
        admin_bot.run_until_disconnected()
    )

if __name__ == '__main__':
    asyncio.run(main())
