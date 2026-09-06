async def main():
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    print("Flask server started in background thread.")

    print("Starting Main Telegram client...")
    while True:
        try:
            await client.start(bot_token=CONTROL_BOT_TOKEN)
            print("Bot is running successfully!")
            await client.run_until_disconnected()
            break
        except Exception as e:
            if "FloodWait" in str(type(e).__name__):
                import re
                seconds = int(re.search(r'\d+', str(e)).group()) if re.search(r'\d+', str(e)) else 60
                print(f"FloodWait detected! Waiting for {seconds} seconds...")
                await asyncio.sleep(seconds + 5)
            else:
                print(f"Error occurred: {e}. Retrying in 10 seconds...")
                await asyncio.sleep(10)

if __name__ == '__main__':
    asyncio.run(main())
