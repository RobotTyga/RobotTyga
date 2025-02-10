import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from PIL import Image, ImageDraw, ImageFont
import asyncio
import logging
from datetime import datetime, timedelta
import os

# Bot token from BotFather
API_TOKEN = '7831558300:AAHIPptCxJbnTpQKRY6zKATxAl2Xn-6L-2w'

# Initialize bot and dispatcher
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Database setup
db_connection = sqlite3.connect("shifts.db")
db_cursor = db_connection.cursor()

# Create table for shifts if not exists
db_cursor.execute('''
CREATE TABLE IF NOT EXISTS shifts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    start_time TEXT,
    end_time TEXT
)
''')
db_connection.commit()

# Helper functions
def save_shift_to_db(user_id, start_time, end_time):
    db_cursor.execute('INSERT INTO shifts (user_id, start_time, end_time) VALUES (?, ?, ?)',
                       (user_id, start_time, end_time))
    db_connection.commit()

def get_user_shifts_from_db(user_id):
    db_cursor.execute('SELECT start_time, end_time FROM shifts WHERE user_id = ? ORDER BY id', (user_id,))
    return [(datetime.fromisoformat(start), datetime.fromisoformat(end) if end else None) for start, end in db_cursor.fetchall()]

def delete_user_shifts_from_db(user_id):
    db_cursor.execute('DELETE FROM shifts WHERE user_id = ?', (user_id,))
    db_connection.commit()

def calculate_total_hours(user_shifts):
    total_seconds = sum((end - start).total_seconds() for start, end in user_shifts if end is not None)
    return str(timedelta(seconds=int(total_seconds)))

# Generate image with shift information
def generate_shift_image(user_id, start_time, end_time, duration):
    img = Image.new('RGB', (400, 200), color=(73, 109, 137))
    draw = ImageDraw.Draw(img)

    # Define font (fallback to default if custom font not available)
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except IOError:
        font = ImageFont.load_default()

    draw.text((10, 10), f"Shift Summary", font=font, fill=(255, 255, 255))
    draw.text((10, 50), f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}", font=font, fill=(255, 255, 255))
    draw.text((10, 80), f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}", font=font, fill=(255, 255, 255))
    draw.text((10, 110), f"Duration: {str(duration)}", font=font, fill=(255, 255, 255))

    file_path = f"shift_summary_{user_id}.png"
    img.save(file_path)
    return file_path

@dp.message(Command("start"))
async def send_welcome(message: Message):
    await message.answer("\U0001F680 Вітаю! Я бот для відстеження твоїх робочих змін. Команди:\n" +
                         "/start_shift - почати робочу зміну\n" +
                         "/end_shift - завершити робочу зміну\n" +
                         "/summary - переглянути звіт за місяць\n" +
                         "/reset_shifts - анулювати всі робочі години")

@dp.message(Command("start_shift"))
async def start_shift(message: Message):
    user_id = message.from_user.id
    user_shifts = get_user_shifts_from_db(user_id)

    # Check if there's an unfinished shift
    if user_shifts and user_shifts[-1][1] is None:
        await message.answer("\u26A0\ufe0f Ви вже розпочали зміну. Спершу завершіть її за допомогою /end_shift.")
        return

    # Start a new shift
    start_time = datetime.now()
    save_shift_to_db(user_id, start_time.isoformat(), None)
    await message.answer(f"\u2705 Робоча зміна почалася о {start_time.strftime('%H:%M:%S')}.")

@dp.message(Command("end_shift"))
async def end_shift(message: Message):
    user_id = message.from_user.id
    user_shifts = get_user_shifts_from_db(user_id)

    if not user_shifts or user_shifts[-1][1] is not None:
        await message.answer("\u26A0\ufe0f Немає активної робочої зміни для завершення.")
        return

    # End the current shift
    end_time = datetime.now()
    start_time, _ = user_shifts[-1]

    # Update the shift in the database
    db_cursor.execute('UPDATE shifts SET end_time = ? WHERE user_id = ? AND end_time IS NULL', (end_time.isoformat(), user_id))
    db_connection.commit()

    worked_duration = end_time - start_time

    # Generate shift summary image
    image_path = generate_shift_image(user_id, start_time, end_time, worked_duration)

    await message.answer(f"\u2705 Зміна завершена. Ви відпрацювали {str(worked_duration)}.")
    with open(image_path, 'rb') as photo:
        await message.answer_photo(photo=photo)

    # Remove the image after sending to keep storage clean
    os.remove(image_path)

@dp.message(Command("summary"))
async def summary(message: Message):
    user_id = message.from_user.id
    user_shifts = get_user_shifts_from_db(user_id)

    if not user_shifts:
        await message.answer("\u2139\ufe0f Ви ще не записували робочих змін.")
        return

    total_hours = calculate_total_hours(user_shifts)
    shifts_list = "\n".join([f"{start.strftime('%Y-%m-%d %H:%M:%S')} - {(end.strftime('%H:%M:%S') if end else '---')}" for start, end in user_shifts])

    await message.answer(f"\U0001F4C5 Звіт про робочі зміни:\n{shifts_list}\n\n\U0001F552 Загальна кількість годин: {total_hours}")

@dp.message(Command("reset_shifts"))
async def reset_shifts(message: Message):
    user_id = message.from_user.id
    delete_user_shifts_from_db(user_id)
    await message.answer("\u2705 Всі робочі зміни успішно анульовано.")

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
