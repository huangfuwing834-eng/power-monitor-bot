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
    
    def get_stats(self):
        """Детальна статистика"""
        if not self.outages_today:
            return None
        
        total_duration = sum([o['duration'] for o in self.outages_today], timedelta(0))
        avg_duration = total_duration / len(self.outages_today)
        longest = max(self.outages_today, key=lambda x: x['duration'])
        shortest = min(self.outages_today, key=lambda x: x['duration'])
        
        return {
            'count': len(self.outages_today),
            'total': total_duration,
            'avg': avg_duration,
            'longest': longest,
            'shortest': shortest
        }

monitor = PowerMonitor()

def format_duration(td):
    """Форматує timedelta"""
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    if hours > 0:
        return f"{hours}г {minutes}хв"
    return f"{minutes}хв"

# ========== МЕНЮ ==========

def get_main_menu_keyboard():
    """Головне меню з кнопками"""
    keyboard = [
        [
            InlineKeyboardButton("⚡ Статус", callback_data='status'),
            InlineKeyboardButton("📊 Статистика", callback_data='stats')
        ],
        [
            InlineKeyboardButton("📅 График ДТЕК", callback_data='schedule'),
            InlineKeyboardButton("🕐 Історія", callback_data='history')
        ],
        [
            InlineKeyboardButton("📈 Аналітика", callback_data='analytics'),
            InlineKeyboardButton("🔔 Прогноз", callback_data='forecast')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# ========== КОМАНДИ ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    await update.message.reply_text(
        f"👋 <b>Вітаю!</b>\n\n"
        f"Я бот для моніторингу електроенергії в Києві.\n\n"
        f"🏠 Ваша група: <b>{DTEK_GROUP}</b>\n"
        f"📍 Місто: <b>Київ</b>\n\n"
        f"<b>Що я вмію:</b>\n"
        f"⚡ Відстежую відключення в реальному часі\n"
        f"📊 Веду детальну статистику\n"
        f"📈 Аналізую тренди та закономірності\n"
        f"🔔 Прогнозую наступні відключення\n"
        f"🕐 Показую історію за день\n\n"
        f"Виберіть дію з меню:",
        parse_mode='HTML',
        reply_markup=get_main_menu_keyboard()
    )

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /menu"""
    await update.message.reply_text(
        "📋 <b>ГОЛОВНЕ МЕНЮ</b>\n\nВиберіть потрібну опцію:",
        parse_mode='HTML',
        reply_markup=get_main_menu_keyboard()
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stats"""
    stats = monitor.get_stats()
    
    if not stats:
        await update.message.reply_text(
            "📊 Сьогодні ще не було відключень 🎉",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    msg = "📊 <b>СТАТИСТИКА ЗА СЬОГОДНІ</b>\n\n"
    msg += f"📈 Кількість відключень: <b>{stats['count']}</b>\n"
    msg += f"⏱ Загальний час без світла: <b>{format_duration(stats['total'])}</b>\n"
    msg += f"⌀ Середня тривалість: <b>{format_duration(stats['avg'])}</b>\n\n"
    msg += f"⏰ Найдовше відключення:\n"
    msg += f"   {stats['longest']['start'].strftime('%H:%M')} • {format_duration(stats['longest']['duration'])}\n\n"
    msg += f"⚡ Найкоротше відключення:\n"
    msg += f"   {stats['shortest']['start'].strftime('%H:%M')} • {format_duration(stats['shortest']['duration'])}"
    
    await update.message.reply_text(
        msg,
        parse_mode='HTML',
        reply_markup=get_main_menu_keyboard()
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /status"""
    if monitor.power_status:
        msg = "🟢 <b>СВІТЛО Є</b>\n\n"
        msg += f"⏰ Зараз: {datetime.now().strftime('%H:%M:%S')}\n\n"
        
        if monitor.outages_today:
            last = monitor.outages_today[-1]
            msg += f"Останнє відключення:\n"
            msg += f"   {last['start'].strftime('%H:%M')} • {format_duration(last['duration'])}\n\n"
        
        total = len(monitor.outages_today)
        if total > 0:
            msg += f"📊 Відключень сьогодні: {total}"
    else:
        duration = monitor.get_current_duration()
        msg = "🔴 <b>СВІТЛА НЕМАЄ</b>\n\n"
        msg += f"⏰ Зараз: {datetime.now().strftime('%H:%M:%S')}\n"
        msg += f"⏱ Без світла: <b>{format_duration(duration)}</b>\n"
        msg += f"🔌 Зникло о: {monitor.last_outage_start.strftime('%H:%M:%S')}\n"
    
    await update.message.reply_text(
        msg,
        parse_mode='HTML',
        reply_markup=get_main_menu_keyboard()
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробник кнопок"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'status':
        # Поточний статус
        if monitor.power_status:
            msg = "🟢 <b>СВІТЛО Є</b>\n\n"
            msg += f"⏰ {datetime.now().strftime('%H:%M:%S')}"
            
            if monitor.outages_today:
                last = monitor.outages_today[-1]
                msg += f"\n\nОстаннє відключення:\n{last['start'].strftime('%H:%M')} • {format_duration(last['duration'])}"
        else:
            duration = monitor.get_current_duration()
            msg = f"🔴 <b>СВІТЛА НЕМАЄ</b>\n\n"
            msg += f"⏱ Вже {format_duration(duration)}\n"
            msg += f"🔌 Зникло о {monitor.last_outage_start.strftime('%H:%M')}"
        
        await query.edit_message_text(
            msg,
            parse_mode='HTML',
            reply_markup=get_main_menu_keyboard()
        )
    
    elif query.data == 'stats':
        # Статистика
        stats = monitor.get_stats()
        if stats:
            msg = "📊 <b>СТАТИСТИКА</b>\n\n"
            msg += f"Відключень: <b>{stats['count']}</b>\n"
            msg += f"Загальний час: {format_duration(stats['total'])}\n"
            msg += f"Середня тривалість: {format_duration(stats['avg'])}"
        else:
            msg = "📊 Сьогодні без відключень 🎉"
        
        await query.edit_message_text(
            msg,
            parse_mode='HTML',
            reply_markup=get_main_menu_keyboard()
        )
    
    elif query.data == 'schedule':
        # График ДТЕК - просто посилання
        msg = f"📅 <b>ГРАФИК ВІДКЛЮЧЕНЬ ДТЕК</b>\n\n"
        msg += f"🏠 Ваша група: <b>{DTEK_GROUP}</b>\n"
        msg += f"📍 Місто: <b>Київ</b>\n\n"
        msg += f"🔗 Актуальний графік дивіться тут:\n"
        msg += f"https://www.dtek-krem.com.ua/ua/shutdowns\n\n"
        msg += f"💡 <b>Порада:</b> Додайте сайт в закладки для швидкого доступу!"
        
        await query.edit_message_text(
            msg,
            parse_mode='HTML',
            reply_markup=get_main_menu_keyboard()
        )
    
    elif query.data == 'history':
        # Історія за день
        if not monitor.outages_today:
            msg = "🕐 <b>ІСТОРІЯ СЬОГОДНІ</b>\n\nВідключень ще не було 🎉"
        else:
            msg = "🕐 <b>ІСТОРІЯ СЬОГОДНІ</b>\n\n"
            for i, outage in enumerate(monitor.outages_today, 1):
                start = outage['start'].strftime('%H:%M')
                end = (outage['start'] + outage['duration']).strftime('%H:%M')
                duration = format_duration(outage['duration'])
                msg += f"{i}. {start} - {end} ({duration})\n"
            
            total = sum([o['duration'] for o in monitor.outages_today], timedelta(0))
            msg += f"\n⏱ <b>Всього:</b> {format_duration(total)}"
        
        await query.edit_message_text(
            msg,
            parse_mode='HTML',
            reply_markup=get_main_menu_keyboard()
        )
    
    elif query.data == 'analytics':
        # Аналітика
        stats = monitor.get_stats()
        
        if not stats:
            msg = "📈 <b>АНАЛІТИКА</b>\n\nНедостатньо даних для аналізу."
        else:
            # Визначаємо найгіршу годину
            hours = [o['start'].hour for o in monitor.outages_today]
            if hours:
                from collections import Counter
                hour_counts = Counter(hours)
                worst_hour = hour_counts.most_common(1)[0]
                
                msg = "📈 <b>АНАЛІТИКА</b>\n\n"
                msg += f"🔴 Найгірша година: <b>{worst_hour[0]}:00 - {worst_hour[0]+1}:00</b>\n"
                msg += f"   ({worst_hour[1]} відключень)\n\n"
                
                # Середній інтервал між відключеннями
                if len(monitor.outages_today) > 1:
                    intervals = []
                    for i in range(1, len(monitor.outages_today)):
                        prev_end = monitor.outages_today[i-1]['start'] + monitor.outages_today[i-1]['duration']
                        curr_start = monitor.outages_today[i]['start']
                        interval = curr_start - prev_end
                        intervals.append(interval)
                    
                    avg_interval = sum(intervals, timedelta(0)) / len(intervals)
                    msg += f"⏱ Середній інтервал:\n"
                    msg += f"   {format_duration(avg_interval)}\n\n"
                
                # Процент часу без світла
                now = datetime.now()
                day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                total_time = now - day_start
                percent = (stats['total'].total_seconds() / total_time.total_seconds()) * 100
                msg += f"⚡ Без світла сьогодні:\n"
                msg += f"   <b>{percent:.1f}%</b> часу ({format_duration(stats['total'])})"
            else:
                msg = "📈 <b>АНАЛІТИКА</b>\n\nНедостатньо даних."
        
        await query.edit_message_text(
            msg,
            parse_mode='HTML',
            reply_markup=get_main_menu_keyboard()
        )
    
    elif query.data == 'forecast':
        # Прогноз на основі історії
        msg = "🔔 <b>ПРОГНОЗ НАСТУПНОГО ВІДКЛЮЧЕННЯ</b>\n\n"
        
        if len(monitor.outages_today) >= 2:
            # Розраховуємо середній інтервал
            intervals = []
            for i in range(1, len(monitor.outages_today)):
                prev_end = monitor.outages_today[i-1]['start'] + monitor.outages_today[i-1]['duration']
                curr_start = monitor.outages_today[i]['start']
                interval = curr_start - prev_end
                intervals.append(interval)
            
            avg_interval = sum(intervals, timedelta(0)) / len(intervals)
            
            if monitor.power_status and monitor.outages_today:
                last_end = monitor.outages_today[-1]['start'] + monitor.outages_today[-1]['duration']
                predicted_next = last_end + avg_interval
                
                if predicted_next > datetime.now():
                    time_until = predicted_next - datetime.now()
                    msg += f"⏰ <b>Прогноз на основі історії:</b>\n"
                    msg += f"Можливо через: <b>{format_duration(time_until)}</b>\n"
                    msg += f"(приблизно о {predicted_next.strftime('%H:%M')})\n\n"
                    msg += f"📊 Базується на {len(monitor.outages_today)} відключеннях сьогодні\n\n"
                else:
                    msg += f"⏰ За розрахунками вже мало б відключити.\n"
                    msg += f"Можливо графік змінився.\n\n"
            else:
                msg += f"⚠️ Зараз немає світла, прогноз не доступний.\n\n"
            
            msg += f"⚠️ <b>Увага:</b> Це лише прогноз!\n"
            msg += f"Точний графік дивіться на сайті ДТЕК."
        else:
            msg += f"Недостатньо даних для прогнозу.\n"
            msg += f"Потрібно мінімум 2 відключення.\n\n"
            msg += f"📅 Дивіться графік ДТЕК натиснувши кнопку вище."
        
        await query.edit_message_text(
            msg,
            parse_mode='HTML',
            reply_markup=get_main_menu_keyboard()
        )

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
        parse_mode='HTML',
        reply_markup=get_main_menu_keyboard()
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
        parse_mode='HTML',
        reply_markup=get_main_menu_keyboard()
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
        print(f"⚠️ Keep-alive: {e}")

# ========== ГОЛОВНА ФУНКЦІЯ ==========

async def main():
    """Запуск бота"""
    print("=" * 50)
    print("🚀 Запуск Power Monitor Bot...")
    print("=" * 50)
    
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ BOT_TOKEN або CHAT_ID не встановлено!")
        return
    
    print(f"✅ BOT_TOKEN: {BOT_TOKEN[:10]}...")
    print(f"✅ CHAT_ID: {CHAT_ID}")
    print(f"✅ DTEK_GROUP: {DTEK_GROUP}")
    print(f"✅ PORT: {PORT}")
    print()
    
    # Створюємо бота
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Додаємо обробники
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    await application.initialize()
    await application.start()
    
    # Задачі
    if application.job_queue:
        application.job_queue.run_repeating(keep_alive_task, interval=600, first=60)
    
    # Запускаємо polling
    polling_task = asyncio.create_task(application.updater.start_polling())
    
    # Веб-сервер
    app = web.Application()
    app['bot_app'] = application
    
    app.router.add_post('/power_lost', webhook_power_lost)
    app.router.add_post('/power_restored', webhook_power_restored)
    app.router.add_get('/health', health_check)
    app.router.add_get('/', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    
    await site.start()
    
    if application.job_queue:
        await application.job_queue.start()
    
    print(f"✅ Веб-сервер на порті {PORT}")
    print("🤖 Telegram бот готовий!")
    print()
    print("=" * 50)
    print("✅ ВСЕ ГОТОВО!")
    print("=" * 50)
    print()
    
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
    except Exception as e:
        print(f"\n❌ Помилка: {e}")
        import traceback
        traceback.print_exc()
