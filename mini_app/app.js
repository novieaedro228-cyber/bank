class TelegramBankApp {
    constructor() {
        this.initData = null;
        this.user = null;
        this.currentPage = 'dashboard';
        this.transactions = [];
        this.currentPageNum = 1;
        this.isLoading = false;
        
        this.init();
    }
    
    async init() {
        // Инициализация Telegram WebApp
        if (window.Telegram && Telegram.WebApp) {
            Telegram.WebApp.ready();
            Telegram.WebApp.expand();
            Telegram.WebApp.disableVerticalSwipes();
            
            this.initData = Telegram.WebApp.initData;
            this.user = Telegram.WebApp.initDataUnsafe.user;
            
            // Настройка темы
            this.setupTheme();
            
            // Загрузка начальных данных
            await this.loadBalance();
            await this.loadTransactions();
            
            // Настройка навигации
            this.setupNavigation();
            
            // Настройка обработчиков
            this.setupEventHandlers();
            
            // Показываем приложение
            document.getElementById('loading').classList.add('hidden');
            document.getElementById('app').classList.remove('hidden');
        } else {
            console.error('Telegram WebApp не инициализирован');
            document.getElementById('loading').innerHTML = 
                '<div class="error-message">Ошибка загрузки Telegram WebApp</div>';
        }
    }
    
    setupTheme() {
        const theme = Telegram.WebApp.colorScheme;
        if (theme === 'dark') {
            document.documentElement.style.setProperty('--background', '#1C1C1E');
            document.documentElement.style.setProperty('--card-background', '#2C2C2E');
            document.documentElement.style.setProperty('--text-primary', '#FFFFFF');
            document.documentElement.style.setProperty('--text-secondary', '#8E8E93');
        }
    }
    
    async makeRequest(endpoint, data = {}) {
        try {
            const response = await fetch(`/api/${endpoint}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Telegram-Init-Data': this.initData
                },
                body: JSON.stringify(data)
            });
            
            return await response.json();
        } catch (error) {
            console.error('Request failed:', error);
            throw error;
        }
    }
    
    async loadBalance() {
        try {
            const result = await this.makeRequest('get_balance');
            if (result.success) {
                this.user = result.user;
                this.updateBalanceDisplay(result.balance);
            }
        } catch (error) {
            this.showError('Ошибка загрузки баланса');
        }
    }
    
    async loadTransactions(page = 1) {
        if (this.isLoading) return;
        
        this.isLoading = true;
        this.showLoading('transactions-list', true);
        
        try {
            const result = await this.makeRequest('get_transactions', {
                page: page,
                limit: 10
            });
            
            if (result.success) {
                if (page === 1) {
                    this.transactions = result.transactions;
                } else {
                    this.transactions = [...this.transactions, ...result.transactions];
                }
                
                this.renderTransactions();
                this.currentPageNum = page;
                
                // Показываем/скрываем кнопку "Загрузить еще"
                const loadMoreBtn = document.getElementById('load-more');
                if (result.has_more) {
                    loadMoreBtn.classList.remove('hidden');
                } else {
                    loadMoreBtn.classList.add('hidden');
                }
            }
        } catch (error) {
            this.showError('Ошибка загрузки истории');
        } finally {
            this.isLoading = false;
            this.showLoading('transactions-list', false);
        }
    }
    
    async transferMoney(recipient, amount) {
        try {
            const result = await this.makeRequest('transfer', {
                recipient: recipient,
                amount: amount
            });
            
            if (result.success) {
                this.showSuccess(`Успешно переведено ${amount}₽ пользователю ${result.recipient.first_name}`);
                await this.loadBalance();
                await this.loadTransactions(1);
                this.navigateTo('dashboard');
                return true;
            } else {
                this.showError(result.error || 'Ошибка перевода');
                return false;
            }
        } catch (error) {
            this.showError('Ошибка соединения');
            return false;
        }
    }
    
    updateBalanceDisplay(balance) {
        const balanceElement = document.getElementById('balance-amount');
        if (balanceElement) {
            balanceElement.textContent = `${balance.toLocaleString()}₽`;
        }
    }
    
    renderTransactions() {
        const container = document.getElementById('transactions-list');
        if (!container) return;
        
        if (this.transactions.length === 0) {
            container.innerHTML = `
                <div class="loading">
                    <div>Нет транзакций</div>
                </div>
            `;
            return;
        }
        
        container.innerHTML = this.transactions.map(transaction => `
            <div class="transaction-item">
                <div class="transaction-icon ${transaction.type}">
                    ${this.getTransactionIcon(transaction.type)}
                </div>
                <div class="transaction-info">
                    <div class="transaction-title">
                        ${this.getTransactionTitle(transaction)}
                    </div>
                    <div class="transaction-description">
                        ${transaction.description || ''}
                        <br>
                        <small>${new Date(transaction.created_at).toLocaleDateString()}</small>
                    </div>
                </div>
                <div class="transaction-amount ${transaction.amount_display.startsWith('+') ? 'positive' : 'negative'}">
                    ${transaction.amount_display}₽
                </div>
            </div>
        `).join('');
    }
    
    getTransactionIcon(type) {
        const icons = {
            'incoming': '📥',
            'outgoing': '📤',
            'system': '🔄'
        };
        return icons[type] || '💰';
    }
    
    getTransactionTitle(transaction) {
        const titles = {
            'incoming': `От ${transaction.other_user.first_name}`,
            'outgoing': `К ${transaction.other_user.first_name}`,
            'system': 'Система'
        };
        return titles[transaction.type] || 'Транзакция';
    }
    
    setupNavigation() {
        const navItems = document.querySelectorAll('.nav-item');
        navItems.forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const page = item.dataset.page;
                this.navigateTo(page);
            });
        });
        
        // Кнопка "Загрузить еще"
        document.getElementById('load-more')?.addEventListener('click', () => {
            this.loadTransactions(this.currentPageNum + 1);
        });
        
        // Кнопка назад
        document.getElementById('back-btn')?.addEventListener('click', () => {
            this.navigateTo('dashboard');
        });
    }
    
    setupEventHandlers() {
        // Форма перевода
        const transferForm = document.getElementById('transfer-form');
        if (transferForm) {
            transferForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const recipient = document.getElementById('recipient').value.trim();
                const amount = parseInt(document.getElementById('amount').value);
                
                if (!recipient || !amount || amount <= 0) {
                    this.showError('Заполните все поля корректно');
                    return;
                }
                
                // Показываем индикатор загрузки
                const submitBtn = transferForm.querySelector('button[type="submit"]');
                const originalText = submitBtn.textContent;
                submitBtn.textContent = 'Отправка...';
                submitBtn.disabled = true;
                
                const success = await this.transferMoney(recipient, amount);
                
                // Восстанавливаем кнопку
                submitBtn.textContent = originalText;
                submitBtn.disabled = false;
                
                if (success) {
                    transferForm.reset();
                }
            });
        }
        
        // Кнопки быстрых действий
        document.getElementById('quick-transfer')?.addEventListener('click', () => {
            this.navigateTo('transfer');
        });
        
        document.getElementById('quick-history')?.addEventListener('click', () => {
            this.navigateTo('history');
        });
    }
    
    navigateTo(page) {
        // Скрываем все страницы
        document.querySelectorAll('.page').forEach(p => {
            p.classList.add('hidden');
        });
        
        // Показываем выбранную страницу
        document.getElementById(`${page}-page`)?.classList.remove('hidden');
        
        // Обновляем активную навигацию
        document.querySelectorAll('.nav-item').forEach(item => {
            if (item.dataset.page === page) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });
        
        this.currentPage = page;
        
        // Загружаем данные если нужно
        if (page === 'history') {
            this.loadTransactions(1);
        }
    }
    
    showLoading(elementId, show) {
        const element = document.getElementById(elementId);
        if (!element) return;
        
        if (show) {
            const loadingDiv = document.createElement('div');
            loadingDiv.className = 'loading';
            loadingDiv.innerHTML = `
                <div class="spinner"></div>
                <div>Загрузка...</div>
            `;
            element.appendChild(loadingDiv);
        } else {
            const loadingDiv = element.querySelector('.loading');
            if (loadingDiv) {
                loadingDiv.remove();
            }
        }
    }
    
    showError(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.textContent = message;
        
        // Удаляем предыдущие сообщения
        document.querySelectorAll('.error-message, .success-message').forEach(msg => {
            if (msg.parentNode) {
                msg.parentNode.removeChild(msg);
            }
        });
        
        // Вставляем в начало контейнера
        const container = document.querySelector('.container');
        container.insertBefore(errorDiv, container.firstChild);
        
        // Автоматически удаляем через 5 секунд
        setTimeout(() => {
            if (errorDiv.parentNode) {
                errorDiv.parentNode.removeChild(errorDiv);
            }
        }, 5000);
    }
    
    showSuccess(message) {
        const successDiv = document.createElement('div');
        successDiv.className = 'success-message';
        successDiv.textContent = message;
        
        // Удаляем предыдущие сообщения
        document.querySelectorAll('.error-message, .success-message').forEach(msg => {
            if (msg.parentNode) {
                msg.parentNode.removeChild(msg);
            }
        });
        
        // Вставляем в начало контейнера
        const container = document.querySelector('.container');
        container.insertBefore(successDiv, container.firstChild);
        
        // Автоматически удаляем через 5 секунд
        setTimeout(() => {
            if (successDiv.parentNode) {
                successDiv.parentNode.removeChild(successDiv);
            }
        }, 5000);
    }
}

// Запуск приложения когда DOM загружен
document.addEventListener('DOMContentLoaded', () => {
    window.app = new TelegramBankApp();
});