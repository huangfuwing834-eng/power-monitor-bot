import os
import asyncio
import aiohttp
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
from aiohttp import web
from collections import Counter

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
        self.outages_history = []  # ВСЯ історія
        
    def power_lost(self):
        """Світло зникло"""
        self.power_status = False
        self.last_outage_start = datetime.now()
        print(f"⚠️ Світло зникло о {self.last_outage_start.strftime('%H:%M:%S')}")
        print(f"📊 Статус збережено: power_status={self.power_status}")
        
    def power_restored(self):
        """Світло з'явилось"""
        if self.last_outage_start:
            duration = datetime.now() - self.last_outage_start
            outage_data = {
                'start': self.last_outage_start,
                'end': datetime.now(),
                'duration': duration
            }
            self.outages_history.append(outage_data)
            print(f"✅ Світло з'явилось. Тривалість: {duration}")
            print(f"📊 Збережено в історію. Всього відключень: {len(self.outages_history)}")
        else:
            print("⚠️ Немає початку відключення для збереження")
            
        self.power_status = True
        self.last_outage_start = None
        
    def get_current_duration(self):
        """Поточна тривалість відключення"""
        if not self.power_status and self.last_outage_start:
            return datetime.now() - self.last_outage_start
        return timedelta(0)
    
    def get_today_outages(self):
        """Отримати відключення за сьогодні"""
        today = datetime.now().date()
        today_outages = [o for o in self.outages_history if o['start'].date() == today]
        print(f"📅 Відключень сьогодні: {len(today_outages)}")
        return today_outages
    
    def get_stats(self):
        """Детальна статистика за сьогодні"""
        outages = self.get_today_outages()
        
        # Якщо є поточне відключення - додаємо його
        if not self.power_status and self.last_outage_start:
            current_outage = {
                'start': self.last_outage_start,
                'end': datetime.now(),
                'duration': self.get_current_duration()
            }
            outages = outages + [current_outage]
            print(f"➕ Додано поточне відключення: {current_outage['duration']}")
        
        if not outages:
            print("⚠️ Немає відключень для статистики")
            return None
        
        total_duration = sum([o['duration'] for o in outages], timedelta(0))
        avg_duration = total_duration / len(outages)
        longest = max(outages, key=lambda x: x['duration'])
        shortest = min(outages, key=lambda x: x['duration'])
        
        stats = {
            'count': len(outages),
            'total': total_duration,
            'avg': avg_duration,
            'longest': longest,
            'shortest': shortest
        }
        
        print(f"📊 Статистика: {stats['count']} відключень, загалом {stats['total']}")
        return stats

monitor = PowerMonitor()

def format_duration(td):
    """Форматує timedelta"""
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    if hours > 0:
        return f"{hours}г {minutes}хв"
    return f"{minutes}хв"

# ========== КЛАВІАТУРИ ==========

def get_main_keyboard():
    """Постійна клавіатура знизу (закріплена)"""
    keyboard = [
        [KeyboardButton("⚡ Статус"), KeyboardButton("📊 Статистика")],
        [KeyboardButton("🕐 Історія"), KeyboardButton("📈 Аналітика")],
        [KeyboardButton("📅 График ДТЕК"), KeyboardButton("🔔 Прогноз")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_inline_menu():
    """Inline меню для повідомлень"""
    keyboard = [
        [
            InlineKeyboardButton("⚡ Статус", callback_data='status'),
            InlineKeyboardButton("📊 Статистика", callback_data='stats')
        ],
        [
            InlineKeyboardButton("🕐 Історія", callback_data='history'),
            InlineKeyboardButton("📈 Аналітика", callback_data='analytics')
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
        f"📈 Аналізую тренди\n"
        f"🔔 Прогнозую відключення\n\n"
        f"Використовуйте кнопки меню знизу ⬇️",
        parse_mode='HTML',
        reply_markup=get_main_keyboard()
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробник текстових повідомлень (кнопок)"""
    text = update.message.text
    
    if text == "⚡ Статус":
        await show_status(update, context)
    elif text == "📊 Статистика":
        await show_stats(update, context)
    elif text == "🕐 Історія":
        await show_history(update, context)
    elif text == "📈 Аналітика":
        await show_analytics(update, context)
    elif text == "📅 График ДТЕК":
        await show_schedule(update, context)
    elif text == "🔔 Прогноз":
        await show_forecast(update, context)

async def show_status(update, context):
    """Показати поточний статус"""
    print(f"🔍 Перевірка статусу: power_status={monitor.power_status}")
    
    if monitor.power_status:
        msg = "🟢 <b>СВІТЛО Є</b>\n\n"
        msg += f"⏰ Зараз: {datetime.now().strftime('%H:%M:%S')}\n\n"
        
        today_outages = monitor.get_today_outages()
        if today_outages:
            last = today_outages[-1]
            msg += f"Останнє відключення:\n"
            msg += f"   {last['start'].strftime('%H:%M')} • {format_duration(last['duration'])}\n\n"
        
        total = len(today_outages)
        if total > 0:
            msg += f"📊 Відключень сьогодні: {total}"
        else:
            msg += f"🎉 Сьогодні без відключень!"
    else:
        duration = monitor.get_current_duration()
        msg = "🔴 <b>СВІТЛА НЕМАЄ</b>\n\n"
        msg += f"⏰ Зараз: {datetime.now().strftime('%H:%M:%S')}\n"
        msg += f"⏱ Без світла: <b>{format_duration(duration)}</b>\n"
        msg += f"🔌 Зникло о: {monitor.last_outage_start.strftime('%H:%M:%S')}\n"
    
    await update.message.reply_text(msg, parse_mode='HTML')

async def show_stats(update, context):
    """Показати статистику"""
    print("📊 Запит статистики...")
    stats = monitor.get_stats()
    
    if not stats:
        msg = "📊 <b>СТАТИСТИКА</b>\n\n"
        
        if not monitor.power_status:
            # Якщо зараз немає світла, але статистика порожня
            duration = monitor.get_current_duration()
            msg += f"🔴 Зараз йде відключення\n"
            msg += f"⏱ Тривалість: {format_duration(duration)}\n"
            msg += f"🔌 Почалось о {monitor.last_outage_start.strftime('%H:%M')}\n\n"
            msg += f"💡 Це перше відключення сьогодні"
        else:
            msg += "Сьогодні ще не було відключень 🎉"
        
        await update.message.reply_text(msg, parse_mode='HTML')
        return
    
    msg = "📊 <b>СТАТИСТИКА ЗА СЬОГОДНІ</b>\n\n"
    msg += f"📈 Кількість відключень: <b>{stats['count']}</b>\n"
    msg += f"⏱ Загальний час без світла: <b>{format_duration(stats['total'])}</b>\n"
    msg += f"⌀ Середня тривалість: <b>{format_duration(stats['avg'])}</b>\n\n"
    msg += f"⏰ Найдовше відключення:\n"
    msg += f"   {stats['longest']['start'].strftime('%H:%M')} • {format_duration(stats['longest']['duration'])}\n\n"
    msg += f"⚡ Найкоротше відключення:\n"
    msg += f"   {stats['shortest']['start'].strftime('%H:%M')} • {format_duration(stats['shortest']['duration'])}"
    
    await update.message.reply_text(msg, parse_mode='HTML')

async def show_history(update, context):
    """Показати історію"""
    print("🕐 Запит історії...")
    outages = monitor.get_today_outages()
    
    # Додаємо поточне відключення якщо є
    if not monitor.power_status and monitor.last_outage_start:
        current = {
            'start': monitor.last_outage_start,
            'end': datetime.now(),
            'duration': monitor.get_current_duration()
        }
        outages = outages + [current]
        print(f"➕ Додано поточне відключення до історії")
    
    if not outages:
        msg = "🕐 <b>ІСТОРІЯ СЬОГОДНІ</b>\n\n"
        msg += "Відключень ще не було 🎉"
    else:
        msg = "🕐 <b>ІСТОРІЯ СЬОГОДНІ</b>\n\n"
        for i, outage in enumerate(outages, 1):
            start = outage['start'].strftime('%H:%M')
            
            if 'end' in outage and outage['end'] > outage['start']:
                end = outage['end'].strftime('%H:%M')
                status = ""
            else:
                end = "зараз"
                status = " 🔴"
            
            duration = format_duration(outage['duration'])
            msg += f"{i}. {start} - {end} ({duration}){status}\n"
        
        total = sum([o['duration'] for o in outages], timedelta(0))
        msg += f"\n⏱ <b>Всього без світла:</b> {format_duration(total)}"
    
    await update.message.reply_text(msg, parse_mode='HTML')

async def show_analytics(update, context):
    """Показати аналітику"""
    print("📈 Запит аналітики...")
    outages = monitor.get_today_outages()
    
    # Додаємо поточне якщо є
    if not monitor.power_status and monitor.last_outage_start:
        current = {
            'start': monitor.last_outage_start,
            'end': datetime.now(),
            'duration': monitor.get_current_duration()
        }
        outages = outages + [current]
    
    if not outages:
        msg = "📈 <b>АНАЛІТИКА</b>\n\n"
        msg += "Недостатньо даних для аналізу.\n"
        msg += "Потрібно хоча б одне відключення."
    else:
        msg = "📈 <b>АНАЛІТИКА</b>\n\n"
        
        # 1. Найгірша година дня
        hours = [o['start'].hour for o in outages]
        hour_counts = Counter(hours)
        worst_hour = hour_counts.most_common(1)[0]
        
        msg += f"🔴 <b>Найгірша година:</b>\n"
        msg += f"   {worst_hour[0]}:00 - {worst_hour[0]+1}:00\n"
        msg += f"   ({worst_hour[1]} відключень)\n\n"
        
        # 2. Середній інтервал між відключеннями
        if len(outages) > 1:
            intervals = []
            for i in range(1, len(outages)):
                prev_end = outages[i-1]['start'] + outages[i-1]['duration']
                curr_start = outages[i]['start']
                interval = curr_start - prev_end
                if interval.total_seconds() > 0:
                    intervals.append(interval)
            
            if intervals:
                avg_interval = sum(intervals, timedelta(0)) / len(intervals)
                msg += f"⏱ <b>Середній інтервал між відключеннями:</b>\n"
                msg += f"   {format_duration(avg_interval)}\n\n"
        
        # 3. Процент часу без світла
        now = datetime.now()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        total_time = now - day_start
        total_outage = sum([o['duration'] for o in outages], timedelta(0))
        
        if total_time.total_seconds() > 0:
            percent = (total_outage.total_seconds() / total_time.total_seconds()) * 100
            msg += f"⚡ <b>Без світла сьогодні:</b>\n"
            msg += f"   {percent:.1f}% часу\n"
            msg += f"   ({format_duration(total_outage)} з {format_duration(total_time)})\n\n"
        
        # 4. Тренд
        if len(outages) >= 3:
            recent_3 = outages[-3:]
            avg_recent = sum([o['duration'] for o in recent_3], timedelta(0)) / 3
            
            if len(outages) >= 6:
                first_3 = outages[:3]
                avg_first = sum([o['duration'] for o in first_3], timedelta(0)) / 3
                
                if avg_recent > avg_first:
                    trend = "📈 Відключення стають довшими"
                elif avg_recent < avg_first:
                    trend = "📉 Відключення стають коротшими"
                else:
                    trend = "➡️ Стабільна ситуація"
                
                msg += f"<b>Тренд:</b> {trend}"
    
    await update.message.reply_text(msg, parse_mode='HTML')

async def show_schedule(update, context):
    """Показати графік ДТЕК"""
    msg = f"📅 <b>ГРАФИК ВІДКЛЮЧЕНЬ ДТЕК</b>\n\n"
    msg += f"🏠 Ваша група: <b>{DTEK_GROUP}</b>\n"
    msg += f"📍 Місто: <b>Київ</b>\n\n"
    msg += f"🔗 Актуальний графік:\n"
    msg += f"https://www.dtek-krem.com.ua/ua/shutdowns\n\n"
    msg += f"💡 <b>Порада:</b> Збережіть посилання в закладки!"
    
    await update.message.reply_text(msg, parse_mode='HTML')

async def show_forecast(update, context):
    """Показати прогноз"""
    print("🔔 Запит прогнозу...")
    outages = monitor.get_today_outages()
    
    msg = "🔔 <b>ПРОГНОЗ НАСТУПНОГО ВІДКЛЮЧЕННЯ</b>\n\n"
    
    if len(outages) >= 2:
        # Розраховуємо середній інтервал
        intervals = []
        for i in range(1, len(outages)):
            prev_end = outages[i-1]['start'] + outages[i-1]['duration']
            curr_start = outages[i]['start']
            interval = curr_start - prev_end
            if interval.total_seconds() > 0:
                intervals.append(interval)
        
        if intervals and monitor.power_status:
            avg_interval = sum(intervals, timedelta(0)) / len(intervals)
            last_end = outages[-1]['start'] + outages[-1]['duration']
            predicted_next = last_end + avg_interval
            
            if predicted_next > datetime.now():
                time_until = predicted_next - datetime.now()
                msg += f"⏰ <b>Прогноз:</b>\n"
                msg += f"Можливе відключення через:\n"
                msg += f"<b>{format_duration(time_until)}</b>\n\n"
                msg += f"📍 Приблизно о <b>{predicted_next.strftime('%H:%M')}</b>\n\n"
                msg += f"📊 На основі {len(outages)} відключень\n"
                msg += f"⌀ Інтервал: {format_duration(avg_interval)}\n\n"
            else:
                msg += f"⏰ За прогнозом вже мало б відключити.\n\n"
            
            msg += f"⚠️ <b>Увага:</b> Це лише прогноз!\n"
            msg += f"Точний графік на сайті ДТЕК."
        elif not monitor.power_status:
            msg += f"🔴 Зараз немає світла.\n"
            msg += f"Прогноз буде доступний після відновлення."
        else:
            msg += f"Недостатньо даних для точного прогнозу."
    else:
        msg += f"Недостатньо даних для прогнозу.\n"
        msg += f"Потрібно мінімум 2 відключення.\n\n"
        msg += f"📅 Дивіться графік ДТЕК у відповідному розділі."
    
    await update.message.reply_text(msg, parse_mode='HTML')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробник inline кнопок"""
    query = update.callback_query
    await query.answer()
    
    # Просто відповідаємо текстом, бо в нас є постійне меню
    if query.data == 'status':
        await query.message.reply_text("Використовуйте кнопку '⚡ Статус' знизу")
    elif query.data == 'stats':
        await query.message.reply_text("Використовуйте кнопку '📊 Статистика' знизу")
    elif query.data == 'history':
        await query.message.reply_text("Використовуйте кнопку '🕐 Історія' знизу")
    elif query.data == 'analytics':
        await query.message.reply_text("Використовуйте кнопку '📈 Аналітика' знизу")

# ========== ВЕБХУКИ ==========

async def webhook_power_lost(request):
    """Світло зникло"""
    print("🔴 ВЕБХУК: Світло зникло")
    monitor.power_lost()
    
    app_bot = request.app['bot_app']
    now = datetime.now()
    
    msg = "🔴 <b>СВІТЛО ЗНИКЛО!</b>\n\n"
    msg += f"⏰ Час: {now.strftime('%H:%M:%S')}\n"
    msg += f"📅 Дата: {now.strftime('%d.%m.%Y')}\n"
    msg += f"🏠 Група: <b>{DTEK_GROUP}</b>\n\n"
    
    today_count = len(monitor.get_today_outages())
    if today_count > 0:
        msg += f"📊 Це {today_count + 1}-е відключення сьогодні"
    else:
        msg += f"📊 Перше відключення сьогодні"
    
    await app_bot.bot.send_message(
        chat_id=CHAT_ID,
        text=msg,
        parse_mode='HTML'
    )
    
    return web.Response(text="OK")

async def webhook_power_restored(request):
    """Світло з'явилось"""
    print("🟢 ВЕБХУК: Світло з'явилось")
    duration = monitor.get_current_duration()
    monitor.power_restored()
    
    app_bot = request.app['bot_app']
    now = datetime.now()
    
    msg = "🟢 <b>СВІТЛО З'ЯВИЛОСЬ!</b>\n\n"
    msg += f"⏰ Час: {now.strftime('%H:%M:%S')}\n"
    msg += f"📅 Дата: {now.strftime('%d.%m.%Y')}\n\n"
    
    if duration.total_seconds() > 0:
        msg += f"⏱ <b>Тривалість відключення:</b>\n"
        msg += f"   {format_duration(duration)}\n\n"
    
    today_outages = monitor.get_today_outages()
    if today_outages:
        total_duration = sum([o['duration'] for o in today_outages], timedelta(0))
        msg += f"📊 <b>Сьогодні:</b>\n"
        msg += f"   Відключень: {len(today_outages)}\n"
        msg += f"   Без світла: {format_duration(total_duration)}"
    
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
    """Пінгує сервер"""
    try:
        async with aiohttp.ClientSession() as session:
            url = f'http://localhost:{PORT}/health'
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    print("✅ Keep-alive")
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
    
    # Обробники
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    await application.initialize()
    await application.start()
    
    # Keep-alive
    if application.job_queue:
        application.job_queue.run_repeating(keep_alive_task, interval=600, first=60)
    
    # Polling
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
    print("🤖 Бот готовий!")
    print("📊 Збереження даних активовано")
    print()
    print("=" * 50)
    print("✅ ВСЕ ГОТОВО!")
    print("=" * 50)
    
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
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
