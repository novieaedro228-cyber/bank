from aiogram.types import (ReplyKeyboardMarkup, KeyboardButton, 
                          InlineKeyboardMarkup, InlineKeyboardButton,
                          WebAppInfo)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

def main_keyboard():
    builder = ReplyKeyboardBuilder()
    
    builder.add(KeyboardButton(text="💰 Мой Банк"))
    builder.add(KeyboardButton(text="🖱 Кликнуть +10₽"))
    builder.add(KeyboardButton(text="📊 Профиль"))
    builder.add(KeyboardButton(text="💸 Перевести"))
    
    builder.adjust(2, 2)
    return builder.as_markup(resize_keyboard=True)

def profile_keyboard():
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="💰 Мой Банк (WebApp)",
        web_app=WebAppInfo(url="https://yourdomain.com/webapp")
    ))
    
    builder.add(InlineKeyboardButton(
        text="🔄 Обновить баланс",
        callback_data="refresh_balance"
    ))
    
    builder.adjust(1)
    return builder.as_markup()

def transfer_keyboard():
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="📱 Открыть в Mini App",
        web_app=WebAppInfo(url="https://yourdomain.com/webapp?page=transfer")
    ))
    
    return builder.as_markup()

def auto_clicker_keyboard(user_id, is_active):
    builder = InlineKeyboardBuilder()
    
    if is_active:
        builder.add(InlineKeyboardButton(
            text="⏹ Остановить автокликер",
            callback_data=f"stop_autoclicker_{user_id}"
        ))
    else:
        builder.add(InlineKeyboardButton(
            text="▶️ Включить автокликер (каждые 30 сек)",
            callback_data=f"start_autoclicker_{user_id}"
        ))
    
    return builder.as_markup()