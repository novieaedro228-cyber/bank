from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, WebAppData
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import json

from models import User, Transaction
from keyboards import main_keyboard, profile_keyboard, transfer_keyboard, auto_clicker_keyboard

router = Router()

# Стейты для перевода
class TransferStates(StatesGroup):
    waiting_for_recipient = State()
    waiting_for_amount = State()

# Обработчики команд
@router.message(Command("start"))
async def cmd_start(message: Message, session: AsyncSession):
    # Регистрация пользователя если не существует
    user = await session.get(User, message.from_user.id)
    
    if not user:
        user = User(
            user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            balance=1000  # Начальный бонус
        )
        session.add(user)
        await session.commit()
        
        # Создаем запись о бонусном начислении
        transaction = Transaction(
            from_user_id=0,  # Система
            to_user_id=user.user_id,
            amount=1000,
            type='bonus',
            description="Добро пожаловать!"
        )
        session.add(transaction)
        await session.commit()
        
        await message.answer(
            "👋 Добро пожаловать в Telegram Bank!\n"
            "🎁 Вам начислено 1000₽ приветственного бонуса!\n"
            "Используйте кнопки ниже для управления банком:",
            reply_markup=main_keyboard()
        )
    else:
        await message.answer(
            "С возвращением в Telegram Bank!",
            reply_markup=main_keyboard()
        )

@router.message(F.text == "💰 Мой Банк")
async def my_bank(message: Message):
    await message.answer(
        "Откройте мини-приложение для управления банком:",
        reply_markup=profile_keyboard()
    )

@router.message(F.text == "🖱 Кликнуть +10₽")
async def click_handler(message: Message, session: AsyncSession):
    user = await session.get(User, message.from_user.id)
    
    if user:
        user.balance += 10
        await session.commit()
        
        # Записываем транзакцию
        transaction = Transaction(
            from_user_id=0,  # Система
            to_user_id=user.user_id,
            amount=10,
            type='click',
            description="Клик"
        )
        session.add(transaction)
        await session.commit()
        
        await message.answer(
            f"✅ +10₽ за клик!\n"
            f"💰 Текущий баланс: {user.balance}₽",
            reply_markup=auto_clicker_keyboard(user.user_id, user.auto_clicker_active)
        )

@router.message(F.text == "📊 Профиль")
async def profile_handler(message: Message, session: AsyncSession):
    user = await session.get(User, message.from_user.id)
    
    if user:
        # Получаем количество транзакций
        transactions_count = await session.execute(
            select(Transaction).where(
                (Transaction.from_user_id == user.user_id) | 
                (Transaction.to_user_id == user.user_id)
            )
        )
        transactions_count = len(transactions_count.scalars().all())
        
        profile_text = (
            f"👤 <b>Профиль</b>\n\n"
            f"🆔 ID: {user.user_id}\n"
            f"👤 Имя: {user.first_name}\n"
            f"📛 Username: @{user.username if user.username else 'не указан'}\n"
            f"💰 Баланс: {user.balance}₽\n"
            f"📊 Транзакций: {transactions_count}\n"
            f"📅 Регистрация: {user.registered_at.strftime('%d.%m.%Y %H:%M')}"
        )
        
        await message.answer(
            profile_text,
            reply_markup=profile_keyboard(),
            parse_mode="HTML"
        )

@router.message(F.text == "💸 Перевести")
async def transfer_start(message: Message, state: FSMContext):
    await message.answer(
        "Введите username или user_id получателя:",
        reply_markup=transfer_keyboard()
    )
    await state.set_state(TransferStates.waiting_for_recipient)

@router.message(TransferStates.waiting_for_recipient)
async def process_recipient(message: Message, state: FSMContext, session: AsyncSession):
    recipient_input = message.text.strip()
    
    # Убираем @ если есть
    if recipient_input.startswith('@'):
        recipient_input = recipient_input[1:]
    
    # Ищем пользователя
    if recipient_input.isdigit():
        user = await session.get(User, int(recipient_input))
    else:
        result = await session.execute(
            select(User).where(User.username == recipient_input)
        )
        user = result.scalar_one_or_none()
    
    if not user:
        await message.answer("❌ Пользователь не найден. Попробуйте еще раз:")
        return
    
    if user.user_id == message.from_user.id:
        await message.answer("❌ Нельзя перевести самому себе. Введите другого пользователя:")
        return
    
    await state.update_data(recipient_id=user.user_id, recipient_name=user.first_name)
    await message.answer(f"✅ Получатель: {user.first_name} (@{user.username})\nВведите сумму перевода:")
    await state.set_state(TransferStates.waiting_for_amount)

@router.message(TransferStates.waiting_for_amount)
async def process_amount(message: Message, state: FSMContext, session: AsyncSession):
    try:
        amount = int(message.text)
        if amount <= 0:
            await message.answer("❌ Сумма должна быть положительной. Введите сумму:")
            return
        
        data = await state.get_data()
        recipient_id = data['recipient_id']
        recipient_name = data['recipient_name']
        
        sender = await session.get(User, message.from_user.id)
        
        if sender.balance < amount:
            await message.answer(f"❌ Недостаточно средств. Ваш баланс: {sender.balance}₽")
            await state.clear()
            return
        
        # Выполняем перевод
        sender.balance -= amount
        recipient = await session.get(User, recipient_id)
        recipient.balance += amount
        
        # Записываем транзакцию
        transaction = Transaction(
            from_user_id=sender.user_id,
            to_user_id=recipient.user_id,
            amount=amount,
            type='transfer',
            description=f"Перевод пользователю {recipient_name}"
        )
        session.add(transaction)
        
        await session.commit()
        
        await message.answer(
            f"✅ Перевод выполнен!\n"
            f"📤 Отправлено: {amount}₽\n"
            f"👤 Получатель: {recipient_name}\n"
            f"💰 Ваш новый баланс: {sender.balance}₽"
        )
        
        # Уведомляем получателя если бот у него есть
        try:
            await message.bot.send_message(
                recipient_id,
                f"💰 Вы получили перевод!\n"
                f"📥 Отправитель: {sender.first_name}\n"
                f"💵 Сумма: {amount}₽\n"
                f"💰 Ваш баланс: {recipient.balance}₽"
            )
        except:
            pass
        
    except ValueError:
        await message.answer("❌ Введите корректную сумму (только цифры):")
        return
    
    await state.clear()

# Обработка данных из Mini App
@router.message(WebAppData)
async def web_app_data_handler(message: WebAppData):
    try:
        data = json.loads(message.web_app_data.data)
        action = data.get('action')
        
        # Здесь будет обработка запросов от Mini App
        # Например: получение баланса, истории транзакций, выполнение переводов
        
        await message.answer(f"Получены данные от Mini App: {action}")
        
    except json.JSONDecodeError:
        await message.answer("❌ Ошибка обработки данных от Mini App")

# Обработчики колбэков
@router.callback_query(F.data.startswith("refresh_balance"))
async def refresh_balance(callback: CallbackQuery, session: AsyncSession):
    user = await session.get(User, callback.from_user.id)
    if user:
        await callback.message.edit_text(
            f"💰 Ваш баланс: {user.balance}₽",
            reply_markup=profile_keyboard()
        )
    await callback.answer()

@router.callback_query(F.data.startswith("start_autoclicker_"))
async def start_autoclicker(callback: CallbackQuery, session: AsyncSession):
    user_id = int(callback.data.split("_")[-1])
    
    if user_id != callback.from_user.id:
        await callback.answer("❌ Это не ваша кнопка!", show_alert=True)
        return
    
    user = await session.get(User, user_id)
    if user and not user.auto_clicker_active:
        user.auto_clicker_active = True
        await session.commit()
        
        await callback.message.edit_reply_markup(
            reply_markup=auto_clicker_keyboard(user_id, True)
        )
        
        # Запускаем автокликер (в реальном приложении нужно хранить таски отдельно)
        asyncio.create_task(run_auto_clicker(callback.bot, user_id, session))
        
        await callback.answer("✅ Автокликер запущен!")
    else:
        await callback.answer("❌ Автокликер уже запущен!", show_alert=True)

@router.callback_query(F.data.startswith("stop_autoclicker_"))
async def stop_autoclicker(callback: CallbackQuery, session: AsyncSession):
    user_id = int(callback.data.split("_")[-1])
    
    if user_id != callback.from_user.id:
        await callback.answer("❌ Это не ваша кнопка!", show_alert=True)
        return
    
    user = await session.get(User, user_id)
    if user and user.auto_clicker_active:
        user.auto_clicker_active = False
        await session.commit()
        
        await callback.message.edit_reply_markup(
            reply_markup=auto_clicker_keyboard(user_id, False)
        )
        
        await callback.answer("⏹ Автокликер остановлен!")

async def run_auto_clicker(bot, user_id: int, session: AsyncSession):
    """Функция автокликера"""
    while True:
        await asyncio.sleep(30)  # Каждые 30 секунд
        
        # Проверяем активность
        async with AsyncSession.Local() as check_session:
            user = await check_session.get(User, user_id)
            if not user or not user.auto_clicker_active:
                break
            
            # Начисляем 10₽
            user.balance += 10
            
            # Записываем транзакцию
            transaction = Transaction(
                from_user_id=0,
                to_user_id=user.user_id,
                amount=10,
                type='click',
                description="Автокликер"
            )
            check_session.add(transaction)
            await check_session.commit()
            
            # Отправляем уведомление
            try:
                await bot.send_message(
                    user_id,
                    f"🤖 Автокликер: +10₽!\n💰 Баланс: {user.balance}₽"
                )
            except:
                break