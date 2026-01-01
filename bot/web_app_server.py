from aiohttp import web
import aiohttp
from datetime import datetime
import json
import hmac
import hashlib
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio

from database import AsyncSessionLocal
from models import User, Transaction
from config import WEBAPP_HOST, WEBAPP_PORT, BOT_TOKEN

class WebAppServer:
    def __init__(self):
        self.app = web.Application()
        self.setup_routes()
        
    def setup_routes(self):
        self.app.router.add_get('/', self.handle_index)
        self.app.router.add_get('/webapp', self.handle_webapp)
        self.app.router.add_post('/api/get_balance', self.handle_get_balance)
        self.app.router.add_post('/api/get_transactions', self.handle_get_transactions)
        self.app.router.add_post('/api/transfer', self.handle_transfer)
        self.app.router.add_static('/static', 'mini_app')
    
    async def verify_telegram_init_data(self, init_data: str):
        """Проверка подлинности данных от Telegram"""
        try:
            parsed_data = dict(
                param.split("=") 
                for param in init_data.split("&") 
                if "=" in param
            )
            
            hash_str = parsed_data.pop("hash", "")
            data_check_string = "\n".join(
                f"{key}={value}" 
                for key, value in sorted(parsed_data.items())
            )
            
            secret_key = hmac.new(
                b"WebAppData", 
                BOT_TOKEN.encode(), 
                hashlib.sha256
            ).digest()
            
            calculated_hash = hmac.new(
                secret_key, 
                data_check_string.encode(), 
                hashlib.sha256
            ).hexdigest()
            
            return calculated_hash == hash_str
        except:
            return False
    
    async def handle_index(self, request):
        return web.FileResponse('mini_app/index.html')
    
    async def handle_webapp(self, request):
        return web.FileResponse('mini_app/index.html')
    
    async def handle_get_balance(self, request):
        try:
            data = await request.json()
            init_data = request.headers.get('X-Telegram-Init-Data', '')
            
            if not await self.verify_telegram_init_data(init_data):
                return web.json_response({'error': 'Invalid init data'}, status=401)
            
            # Извлекаем user_id из init_data
            import urllib.parse
            parsed = urllib.parse.parse_qs(init_data)
            user_id = int(parsed.get('user', [{}])[0].get('id', 0))
            
            if not user_id:
                return web.json_response({'error': 'User not found'}, status=400)
            
            async with AsyncSessionLocal() as session:
                user = await session.get(User, user_id)
                if not user:
                    return web.json_response({'error': 'User not found'}, status=404)
                
                return web.json_response({
                    'success': True,
                    'balance': user.balance,
                    'user': {
                        'id': user.user_id,
                        'username': user.username,
                        'first_name': user.first_name
                    }
                })
                
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def handle_get_transactions(self, request):
        try:
            data = await request.json()
            init_data = request.headers.get('X-Telegram-Init-Data', '')
            page = data.get('page', 1)
            limit = data.get('limit', 20)
            
            if not await self.verify_telegram_init_data(init_data):
                return web.json_response({'error': 'Invalid init data'}, status=401)
            
            # Извлекаем user_id из init_data
            import urllib.parse
            parsed = urllib.parse.parse_qs(init_data)
            user_id = int(parsed.get('user', [{}])[0].get('id', 0))
            
            async with AsyncSessionLocal() as session:
                offset = (page - 1) * limit
                
                # Получаем транзакции
                result = await session.execute(
                    select(Transaction).where(
                        (Transaction.from_user_id == user_id) | 
                        (Transaction.to_user_id == user_id)
                    )
                    .order_by(Transaction.created_at.desc())
                    .offset(offset)
                    .limit(limit)
                )
                
                transactions = result.scalars().all()
                
                transaction_list = []
                for t in transactions:
                    # Определяем тип транзакции для пользователя
                    if t.from_user_id == user_id and t.to_user_id != user_id:
                        transaction_type = 'outgoing'
                        amount_display = f"-{t.amount}"
                    elif t.to_user_id == user_id and t.from_user_id != user_id:
                        transaction_type = 'incoming'
                        amount_display = f"+{t.amount}"
                    else:
                        transaction_type = 'system'
                        amount_display = f"+{t.amount}"
                    
                    # Получаем информацию о втором участнике
                    other_user_id = t.to_user_id if t.from_user_id == user_id else t.from_user_id
                    other_user = await session.get(User, other_user_id) if other_user_id > 0 else None
                    
                    transaction_list.append({
                        'id': t.id,
                        'type': transaction_type,
                        'amount': t.amount,
                        'amount_display': amount_display,
                        'description': t.description or '',
                        'created_at': t.created_at.isoformat(),
                        'other_user': {
                            'id': other_user.user_id if other_user else 0,
                            'username': other_user.username if other_user else 'Система',
                            'first_name': other_user.first_name if other_user else 'Система'
                        } if other_user else {
                            'id': 0,
                            'username': 'Система',
                            'first_name': 'Система'
                        }
                    })
                
                return web.json_response({
                    'success': True,
                    'transactions': transaction_list,
                    'page': page,
                    'has_more': len(transactions) == limit
                })
                
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def handle_transfer(self, request):
        try:
            data = await request.json()
            init_data = request.headers.get('X-Telegram-Init-Data', '')
            
            if not await self.verify_telegram_init_data(init_data):
                return web.json_response({'error': 'Invalid init data'}, status=401)
            
            # Извлекаем user_id из init_data
            import urllib.parse
            parsed = urllib.parse.parse_qs(init_data)
            user_id = int(parsed.get('user', [{}])[0].get('id', 0))
            
            recipient_input = data.get('recipient')
            amount = int(data.get('amount', 0))
            
            if amount <= 0:
                return web.json_response({'error': 'Invalid amount'}, status=400)
            
            async with AsyncSessionLocal() as session:
                # Проверяем отправителя
                sender = await session.get(User, user_id)
                if not sender:
                    return web.json_response({'error': 'Sender not found'}, status=404)
                
                if sender.balance < amount:
                    return web.json_response({'error': 'Insufficient funds'}, status=400)
                
                # Ищем получателя
                if recipient_input.isdigit():
                    recipient = await session.get(User, int(recipient_input))
                else:
                    if recipient_input.startswith('@'):
                        recipient_input = recipient_input[1:]
                    result = await session.execute(
                        select(User).where(User.username == recipient_input)
                    )
                    recipient = result.scalar_one_or_none()
                
                if not recipient:
                    return web.json_response({'error': 'Recipient not found'}, status=404)
                
                if recipient.user_id == sender.user_id:
                    return web.json_response({'error': 'Cannot transfer to yourself'}, status=400)
                
                # Выполняем перевод
                sender.balance -= amount
                recipient.balance += amount
                
                # Записываем транзакцию
                transaction = Transaction(
                    from_user_id=sender.user_id,
                    to_user_id=recipient.user_id,
                    amount=amount,
                    type='transfer',
                    description=f"Перевод через Mini App"
                )
                session.add(transaction)
                
                await session.commit()
                
                # Отправляем уведомление получателю
                try:
                    bot = request.app['bot']
                    await bot.send_message(
                        recipient.user_id,
                        f"💰 Вы получили перевод через Mini App!\n"
                        f"📥 Отправитель: {sender.first_name}\n"
                        f"💵 Сумма: {amount}₽\n"
                        f"💰 Ваш баланс: {recipient.balance}₽"
                    )
                except Exception as e:
                    print(f"Failed to send notification: {e}")
                
                return web.json_response({
                    'success': True,
                    'new_balance': sender.balance,
                    'recipient': {
                        'id': recipient.user_id,
                        'username': recipient.username,
                        'first_name': recipient.first_name
                    }
                })
                
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def start(self, bot):
        """Запуск сервера с передачей экземпляра бота"""
        self.app['bot'] = bot
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, WEBAPP_HOST, WEBAPP_PORT)
        await site.start()
        print(f"WebApp server started on http://{WEBAPP_HOST}:{WEBAPP_PORT}")