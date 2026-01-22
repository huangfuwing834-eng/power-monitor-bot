import os
import asyncio
import aiohttp
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from aiohttp import web

# Конфігурація
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
DTEK_GROUP = os.environ.get('DTEK_GROUP', '3.2')
PORT = int(os.environ.get('PORT', 10000))

class PowerMonitor:
    """Клас для відстеження відключень"""
    def __init__(self):
        self.power_status = True
        self.last_outage_start = None
        self.outages_today = []
        
    def power_lost(self):
        self.power_status = False
        self.last_outage_start = datetime.now()
        print(f"⚠️ Світло зникло о {self.last_outage_start.strftime('%H:%M:%S')}")
        
    def power_restored(self):
        if self.last_outage_start:
            duration = datetime.now() - self.last_outage_start
            self.outages_today.append({
                'start': self.last_outage_start,
                'duration': duration
            })
            print(f"✅ Світло з'явилось. Тривалість: {duration}")
        self.power_status = True
        self.last_outage_start = None
        
    def get_current_duration(self):
        if not self.power_status and self.last_outage_start:
            return datetime.now() - self.last_outage_start
        return timedelta(0)

monitor = PowerMonitor()

def format_duration(td):
    """Форматує timedelta"""
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    if hours > 0:
        return f"{hours}г {minutes}хв"
    return f"{minutes}хв"

# ========== КОМАНДИ БОТА ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data='stats')],
        [InlineKeyboardButton("⚡ Поточний статус", callback_data='status')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"👋 Вітаю! Я бот для моніторингу електроенергії.\n\n"
        f"🏠 Відстежую групу: <b>{DTEK_GROUP}</b>\n\n"
        f"Команди:\n"
        f"/status - поточний статус\n"
        f"/stats - статистика за день\n\n"
        f"Або використовуйте кнопки:",
        parse_mode='HTML',
        reply_markup=reply_markup
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stats"""
    if not monitor.outages_today:
        await update.message.reply_text("📊 Сьогодні ще не було відключень 🎉")
        return
    
    total_duration = sum([o['duration'] for o in monitor.outages_today], timedelta(0))
    
    msg = "📊 <b>СТАТИСТИКА ЗА СЬОГОДНІ</b>\n\n"
    msg += f"📈 Кількість: <b>{len(monitor.outages_today)}</b>\n"
    msg += f"⏱ Загальний час: <b>{format_duration(total_duration)}</b>\n\n"
    msg += "📋 <b>Історія:</b>\n"
    
    for i, outage in enumerate(monitor.outages_today, 1):
        start_time = outage['start'].strftime('%H:%M')
        duration = format_duration(outage['duration'])
        msg += f"{i}. {start_time} • {duration}\n"
    
    await update.message.reply_text(msg, parse_mode='HTML')

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /status"""
    if monitor.power_status:
        msg = "🟢 <b>СВІТЛО Є</b>\n\n"
        
        if monitor.outages_today:
            last_outage = monitor.outages_today[-1]
            msg += f"⏰ Останнє відключення:\n"
            msg += f"   {last_outage['start'].strftime('%H:%M')} • {format_duration(last_outage['duration'])}\n\n"
        
        total_today = len(monitor.outages_today)
        if total_today > 0:
            msg += f"📊 Відключень сьогодні: {total_today}"
    else:
        duration = monitor.get_current_duration()
        msg = "🔴 <b>СВІТЛА НЕМАЄ</b>\n\n"
        msg += f"⏱ Без світла: <b>{format_duration(duration)}</b>\n"
        msg += f"⏰ Зникло о: {monitor.last_outage_start.strftime('%H:%M:%S')}\n"
    
    await update.message.reply_text(msg, parse_mode='HTML')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробник кнопок"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'stats':
        if monitor.outages_today:
            total = sum([o['duration'] for o in monitor.outages_today], timedelta(0))
            msg = f"📊 <b>СТАТИСТИКА</b>\n\n"
            msg += f"Відключень: {len(monitor.outages_today)}\n"
            msg += f"Загальний час: {format_duration(total)}"
        else:
            msg = "📊 Сьогодні без відключень 🎉"
        await query.edit_message_text(msg, parse_mode='HTML')
        
    elif query.data == 'status':
        if monitor.power_status:
            msg = "🟢 Світло є"
        else:
            duration = monitor.get_current_duration()
            msg = f"🔴 Світла немає\n⏱ {format_duration(duration)}"
        await query.edit_message_text(msg)

# ========== ВЕБХУКИ ==========

async def webhook_power_lost(request):
    """Світло зникло"""
    monitor.power_lost()
    
    app_bot = request.app['bot_app']
    now = datetime.now()
    
    msg = "🔴 <b>СВІТЛО ЗНИКЛО!</b>\n\n"
    msg += f"⏰ Час: {now.strftime('%H:%M:%S')}\n"
    msg += f"📅 Дата: {now.strftime('%d.%m.%Y')}\n"
    msg += f"🏠 Група: <b>{DTEK_GROUP}</b>\n\n"
    
    total_today = len(monitor.outages_today)
    if total_today > 0:
        msg += f"📊 Це {total_today + 1}-е відключення сьогодні"
    
    await app_bot.bot.send_message(
        chat_id=CHAT_ID,
        text=msg,
        parse_mode='HTML'
    )
    
    return web.Response(text="OK")

async def webhook_power_restored(request):
    """Світло з'явилось"""
    duration = monitor.get_current_duration()
    monitor.power_restored()
    
    app_bot = request.app['bot_app']
    now = datetime.now()
    
    msg = "🟢 <b>СВІТЛО З'ЯВИЛОСЬ!</b>\n\n"
    msg += f"⏰ Час: {now.strftime('%H:%M:%S')}\n"
    msg += f"📅 Дата: {now.strftime('%d.%m.%Y')}\n\n"
    
    if duration.total_seconds() > 0:
        msg += f"⏱ <b>Тривалість:</b> {format_duration(duration)}\n\n"
    
    total_today = len(monitor.outages_today)
    if total_today > 0:
        total_duration = sum([o['duration'] for o in monitor.outages_today], timedelta(0))
        msg += f"📊 <b>Сьогодні:</b>\n"
        msg += f"Відключень: {total_today}\n"
        msg += f"Без світла: {format_duration(total_duration)}"
    
    await app_bot.bot.send_message(
        chat_id=CHAT_ID,
        text=msg,
        parse_mode='HTML'
    )
    
    return web.Response(text="OK")

async def health_check(request):
    """Health check"""
    return web.Response(text="Bot is running!")

# ========== KEEP ALIVE ==========

async def keep_alive_task(context: ContextTypes.DEFAULT_TYPE):
    """Пінгує сервер щоб не засинав"""
    try:
        async with aiohttp.ClientSession() as session:
            url = f'http://localhost:{PORT}/health'
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    print("✅ Keep-alive успішний")
    except Exception as e:
        print(f"⚠️ Keep-alive помилка: {e}")

# ========== ГОЛОВНА ФУНКЦІЯ ==========

async def main():
    """Запуск бота"""
    print("=" * 50)
    print("🚀 Запуск Power Monitor Bot...")
    print("=" * 50)
    
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не встановлено!")
        return
    
    if not CHAT_ID:
        print("❌ CHAT_ID не встановлено!")
        return
    
    print(f"✅ BOT_TOKEN: {BOT_TOKEN[:10]}...")
    print(f"✅ CHAT_ID: {CHAT_ID}")
    print(f"✅ DTEK_GROUP: {DTEK_GROUP}")
    print(f"✅ PORT: {PORT}")
    print()
    
    # Створюємо бота З POLLING (щоб команди працювали!)
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Додаємо обробники
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Ініціалізуємо
    await application.initialize()
    await application.start()
    
    # Keep-alive задача
    if application.job_queue:
        application.job_queue.run_repeating(keep_alive_task, interval=600, first=60)
    
    # Запускаємо polling в окремій задачі
    polling_task = asyncio.create_task(application.updater.start_polling())
    
    # Створюємо веб-сервер
    app = web.Application()
    app['bot_app'] = application
    
    app.router.add_post('/power_lost', webhook_power_lost)
    app.router.add_post('/power_restored', webhook_power_restored)
    app.router.add_get('/health', health_check)
    app.router.add_get('/', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    
    print("🌐 Запуск веб-сервера...")
    await site.start()
    print(f"✅ Веб-сервер на порті {PORT}")
    
    # Запускаємо job queue якщо є
    if application.job_queue:
        await application.job_queue.start()
    
    print("🤖 Telegram бот готовий!")
    print()
    print("=" * 50)
    print("✅ ВСЕ ГОТОВО! Бот працює")
    print("=" * 50)
    print()
    print("📱 URL для iPhone:")
    print(f"   POST https://YOUR-APP.onrender.com/power_lost")
    print(f"   POST https://YOUR-APP.onrender.com/power_restored")
    print()
    print("💬 Напишіть боту /start в Telegram")
    print()
    
    # Тримаємо запущеним
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        print("\n👋 Зупинка...")
        await polling_task
        if application.job_queue:
            await application.job_queue.stop()
        await application.stop()
        await application.shutdown()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот зупинено")
    except Exception as e:
        print(f"\n❌ Помилка: {e}")
        import traceback
        traceback.print_exc()
