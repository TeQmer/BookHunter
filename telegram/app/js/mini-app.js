/**
 * BookHunter Mini App
 * Основная логика Telegram Mini App
 */

class BookHunterApp {
    constructor() {
        this.apiBaseUrl = window.location.origin;
        this.currentRoute = 'home';
        this.user = null;
        this.data = {
            books: [],
            alerts: [],
            stats: null
        };
        this.init();
    }

    /**
     * Инициализация приложения
     */
    async init() {
        console.log('BookHunter Mini App инициализация...');

        // Получаем данные пользователя из Telegram
        this.user = window.tg.getUser();
        console.log('Пользователь:', this.user);

        // Настраиваем навигацию
        this.setupNavigation();

        // Загружаем начальные данные
        await this.loadInitialData();

        // Настраиваем главную кнопку
        this.setupMainButton();

        // Применяем тему
        this.applyTheme();

        console.log('BookHunter Mini App инициализирован');
    }

    /**
     * Настройка навигации
     */
    setupNavigation() {
        // Обработка кликов по навигации
        document.querySelectorAll('.nav__item').forEach(item => {
            item.addEventListener('click', (e) => {
                const route = e.target.dataset.route;
                if (route) {
                    this.navigate(route);
                    window.tg.hapticClick();
                }
            });
        });

        // Обработка кнопки назад в заголовке
        const backBtn = document.querySelector('.header__back');
        if (backBtn) {
            backBtn.addEventListener('click', () => {
                window.history.back();
                window.tg.hapticClick();
            });
        }
    }

    /**
     * Навигация между страницами
     */
    navigate(route, params = {}) {
        console.log('Навигация на:', route, params);

        // Обновляем активный пункт меню
        document.querySelectorAll('.nav__item').forEach(item => {
            item.classList.toggle('active', item.dataset.route === route);
        });

        // Показываем/скрываем кнопку назад
        if (route === 'home') {
            window.tg.hideBackButton();
        } else {
            window.tg.showBackButton();
        }

        // Сохраняем состояние в history
        const url = new URL(window.location);
        url.searchParams.set('route', route);
        Object.keys(params).forEach(key => {
            url.searchParams.set(key, params[key]);
        });
        window.history.pushState({ route, params }, '', url);

        this.currentRoute = route;

        // Загружаем данные для страницы
        this.loadPageData(route, params);
    }

    /**
     * Загрузка данных страницы
     */
    async loadPageData(route, params) {
        switch (route) {
            case 'home':
                await this.loadStats();
                break;
            case 'books':
                await this.loadBooks(params);
                break;
            case 'alerts':
                await this.loadAlerts();
                break;
            case 'profile':
                // Профиль - заглушка
                break;
            case 'search':
                // Поиск
                break;
        }
    }

    /**
     * Загрузка начальных данных
     */
    async loadInitialData() {
        try {
            // Загружаем статистику
            await this.loadStats();
        } catch (error) {
            console.error('Ошибка загрузки начальных данных:', error);
            this.showError('Не удалось загрузить данные. Проверьте соединение.');
        }
    }

    /**
     * Загрузка статистики
     */
    async loadStats() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/api/stats/main`);
            if (!response.ok) throw new Error('Ошибка загрузки статистики');

            const data = await response.json();
            this.data.stats = data;

            this.updateStatsUI(data);
        } catch (error) {
            console.error('Ошибка загрузки статистики:', error);
            this.showError('Не удалось загрузить статистику');
        }
    }

    /**
     * Обновление UI статистики
     */
    updateStatsUI(stats) {
        const totalBooksEl = document.getElementById('stat-total-books');
        const activeAlertsEl = document.getElementById('stat-active-alerts');
        const avgDiscountEl = document.getElementById('stat-avg-discount');

        if (totalBooksEl) totalBooksEl.textContent = stats.total_books || 0;
        if (activeAlertsEl) activeAlertsEl.textContent = stats.active_alerts || 0;
        if (avgDiscountEl) avgDiscountEl.textContent = (stats.avg_discount || 0) + '%';
    }

    /**
     * Загрузка списка книг
     */
    async loadBooks(params = {}) {
        try {
            let url = `${this.apiBaseUrl}/api/books?page=${params.page || 1}&limit=${params.limit || 20}`;

            if (params.query) {
                url += `&q=${encodeURIComponent(params.query)}`;
            }
            if (params.source) {
                url += `&source=${params.source}`;
            }

            const response = await fetch(url);
            if (!response.ok) throw new Error('Ошибка загрузки книг');

            const data = await response.json();
            this.data.books = data.books || [];

            this.renderBooks(this.data.books);
        } catch (error) {
            console.error('Ошибка загрузки книг:', error);
            this.showError('Не удалось загрузить книги');
        }
    }

    /**
     * Отрисовка списка книг
     */
    renderBooks(books) {
        const container = document.getElementById('books-container');
        if (!container) return;

        if (!books || books.length === 0) {
            container.innerHTML = this.getEmptyState('Книги не найдены', 'Попробуйте изменить параметры поиска');
            return;
        }

        container.innerHTML = books.map(book => this.createBookCard(book)).join('');

        // Добавляем обработчики событий
        container.querySelectorAll('.book-card').forEach(card => {
            card.addEventListener('click', (e) => {
                if (!e.target.closest('.btn')) {
                    const bookId = card.dataset.bookId;
                    this.showBookDetails(bookId);
                }
            });
        });
    }

    /**
     * Создание карточки книги
     */
    createBookCard(book) {
        const discount = book.discount_percent || 0;
        const hasDiscount = discount > 0;

        return `
            <div class="book-card" data-book-id="${book.id}">
                <div class="book-card__cover">
                    ${book.image_url
                        ? `<img src="${book.image_url}" alt="${book.title}">`
                        : `<div class="book-card__cover-placeholder"><i class="fas fa-book"></i></div>`
                    }
                </div>
                <div class="book-card__info">
                    <div class="book-card__source">${book.source || 'Неизвестно'}</div>
                    <h3 class="book-card__title">${this.escapeHtml(book.title)}</h3>
                    <div class="book-card__author">${this.escapeHtml(book.author || 'Неизвестный автор')}</div>
                    <div class="book-card__price">
                        ${hasDiscount
                            ? `<span class="original">${book.original_price || 0} ₽</span>${book.current_price || 0} ₽`
                            : `${book.current_price || 0} ₽`
                        }
                    </div>
                    ${hasDiscount ? `<div class="book-card__discount">-${discount}%</div>` : ''}
                </div>
            </div>
        `;
    }

    /**
     * Загрузка подписок
     */
    async loadAlerts() {
        try {
            const chatId = window.tg.getChatId();
            const response = await fetch(`${this.apiBaseUrl}/api/alerts?user_id=${chatId}`);

            if (!response.ok) throw new Error('Ошибка загрузки подписок');

            const data = await response.json();
            this.data.alerts = data.alerts || [];

            this.renderAlerts(this.data.alerts);
        } catch (error) {
            console.error('Ошибка загрузки подписок:', error);
            this.showError('Не удалось загрузить подписки');
        }
    }

    /**
     * Отрисовка списка подписок
     */
    renderAlerts(alerts) {
        const container = document.getElementById('alerts-container');
        if (!container) return;

        if (!alerts || alerts.length === 0) {
            container.innerHTML = this.getEmptyState('Подписок нет', 'Создайте первую подписку на интересующую книгу');
            return;
        }

        container.innerHTML = alerts.map(alert => this.createAlertItem(alert)).join('');
    }

    /**
     * Создание элемента подписки
     */
    createAlertItem(alert) {
        return `
            <div class="alert-item" data-alert-id="${alert.id}">
                <h4 class="alert-item__title">${this.escapeHtml(alert.book_title || 'Без названия')}</h4>
                <div class="alert-item__info">
                    ${alert.book_author ? `Автор: ${this.escapeHtml(alert.book_author)}` : ''}
                    ${alert.target_price ? `<br>Цена до: ${alert.target_price} ₽` : ''}
                    ${alert.min_discount ? `<br>Скидка от: ${alert.min_discount}%` : ''}
                </div>
                <span class="alert-item__status ${alert.is_active ? 'alert-item__status--active' : 'alert-item__status--inactive'}">
                    ${alert.is_active ? 'Активна' : 'Неактивна'}
                </span>
                <div class="alert-item__actions">
                    <button class="btn btn--small btn--secondary" onclick="app.editAlert(${alert.id})">
                        <i class="fas fa-edit"></i> Изменить
                    </button>
                    <button class="btn btn--small btn--danger" onclick="app.deleteAlert(${alert.id})">
                        <i class="fas fa-trash"></i> Удалить
                    </button>
                </div>
            </div>
        `;
    }

    /**
     * Настройка главной кнопки
     */
    setupMainButton() {
        // Главная кнопка будет настраиваться динамически на каждой странице
    }

    /**
     * Применение темы
     */
    applyTheme() {
        // Тема уже применяется в telegram.js
    }

    /**
     * Поиск книг
     */
    async searchBooks(query) {
        if (!query.trim()) {
            this.showError('Введите поисковый запрос');
            return;
        }

        this.showLoading('Поиск книг...');

        try {
            await this.loadBooks({ query });
            this.navigate('books', { query });
            window.tg.hapticSuccess();
        } catch (error) {
            console.error('Ошибка поиска:', error);
            this.showError('Не удалось выполнить поиск');
        }
    }

    /**
     * Создание подписки
     */
    async createAlert(bookData) {
        try {
            const chatId = window.tg.getChatId();

            const response = await fetch(`${this.apiBaseUrl}/api/alerts`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    user_id: chatId,
                    book_id: bookData.id,
                    book_title: bookData.title,
                    book_author: bookData.author,
                    book_source: bookData.source,
                    target_price: bookData.current_price,
                    min_discount: bookData.discount_percent || 0
                })
            });

            if (!response.ok) throw new Error('Ошибка создания подписки');

            window.tg.hapticSuccess();
            this.showSuccess('Подписка создана!');

            // Обновляем список подписок
            if (this.currentRoute === 'alerts') {
                await this.loadAlerts();
            }
        } catch (error) {
            console.error('Ошибка создания подписки:', error);
            window.tg.hapticError();
            this.showError('Не удалось создать подписку');
        }
    }

    /**
     * Удаление подписки
     */
    async deleteAlert(alertId) {
        try {
            const confirmed = await window.tg.showConfirm('Удалить эту подписку?');
            if (!confirmed) return;

            const response = await fetch(`${this.apiBaseUrl}/api/alerts/${alertId}`, {
                method: 'DELETE'
            });

            if (!response.ok) throw new Error('Ошибка удаления подписки');

            window.tg.hapticSuccess();
            this.showSuccess('Подписка удалена');

            // Обновляем список
            await this.loadAlerts();
        } catch (error) {
            console.error('Ошибка удаления подписки:', error);
            window.tg.hapticError();
            this.showError('Не удалось удалить подписку');
        }
    }

    /**
     * Показать детали книги
     */
    showBookDetails(bookId) {
        // TODO: Реализовать показ деталей книги
        console.log('Показ деталей книги:', bookId);
        window.tg.hapticClick();
    }

    /**
     * Показать сообщение об успехе
     */
    showSuccess(message) {
        this.showToast(message, 'success');
    }

    /**
     * Показать ошибку
     */
    showError(message) {
        this.showToast(message, 'error');
    }

    /**
     * Показать toast сообщение
     */
    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = 'toast';
        toast.textContent = message;
        toast.style.background = type === 'error' ? 'var(--danger)' : type === 'success' ? 'var(--success)' : 'var(--text-primary)';
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.remove();
        }, 3000);
    }

    /**
     * Показать состояние загрузки
     */
    showLoading(message = 'Загрузка...') {
        const container = document.getElementById('main-content');
        if (container) {
            container.innerHTML = `
                <div class="loading">
                    <div class="loading__spinner"></div>
                    <div class="loading__text">${message}</div>
                </div>
            `;
        }
    }

    /**
     * Получить HTML для пустого состояния
     */
    getEmptyState(title, text) {
        return `
            <div class="empty">
                <div class="empty__icon"><i class="fas fa-inbox"></i></div>
                <h3 class="empty__title">${title}</h3>
                <p class="empty__text">${text}</p>
            </div>
        `;
    }

    /**
     * Экранирование HTML
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Создаем глобальный экземпляр приложения
window.app = new BookHunterApp();

// Обработка навигации через history
window.addEventListener('popstate', (event) => {
    if (event.state) {
        window.app.currentRoute = event.state.route;
        window.app.loadPageData(event.state.route, event.state.params);
    }
});

// Инициализация при загрузке DOM
document.addEventListener('DOMContentLoaded', () => {
    // Проверяем маршрут из URL
    const params = new URLSearchParams(window.location.search);
    const route = params.get('route') || 'home';

    const routeParams = {};
    for (const [key, value] of params.entries()) {
        if (key !== 'route') {
            routeParams[key] = value;
        }
    }

    // Навигация на начальную страницу
    window.app.navigate(route, routeParams);
});
