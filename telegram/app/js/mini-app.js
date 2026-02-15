/**
 * BookHunter Mini App
 * Основная логика Telegram Mini App
 */

class BookHunterApp {
    constructor() {
        this.apiBaseUrl = typeof API_BASE_URL !== 'undefined' ? API_BASE_URL : window.location.origin;
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
        console.log('[navigate] Навигация на:', route, params);

        // Скрываем все страницы
        this.hideAllPages();

        // Показываем нужную страницу
        switch (route) {
            case 'home':
                this.showHomePage();
                break;
            case 'books':
                this.showBooksPage();
                break;
            case 'alerts':
                this.showAlertsPage();
                break;
            case 'profile':
                this.showProfilePage();
                break;
        }

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
     * Скрыть все страницы
     */
    hideAllPages() {
        const mainContent = document.getElementById('main-content');

        // Скрываем страницы, которые имеют display: none по умолчанию
        const booksPage = document.getElementById('books-page');
        const alertsPage = document.getElementById('alerts-page');
        const profilePage = document.getElementById('profile-page');

        if (booksPage) booksPage.style.display = 'none';
        if (alertsPage) alertsPage.style.display = 'none';
        if (profilePage) profilePage.style.display = 'none';

        // Скрываем элементы домашней страницы
        const heroSection = mainContent.querySelector('.card[style*="gradient-primary"]');
        const statsSection = mainContent.querySelector('.stats');
        const quickActionsSection = mainContent.querySelectorAll('.card')[1]; // Второй блок card
        const recentBooksSection = document.getElementById('recent-books-container');
        const statsHeader = mainContent.querySelectorAll('h3')[0]; // Статистика заголовок
        const quickActionsHeader = mainContent.querySelectorAll('h3')[1]; // Быстрые действия заголовок
        const recentBooksHeader = mainContent.querySelectorAll('h3')[2]; // Недавние книги заголовок

        if (heroSection) heroSection.style.display = 'none';
        if (statsSection) statsSection.style.display = 'none';
        if (quickActionsSection) quickActionsSection.style.display = 'none';
        if (recentBooksSection) recentBooksSection.style.display = 'none';
        if (statsHeader) statsHeader.style.display = 'none';
        if (quickActionsHeader) quickActionsHeader.style.display = 'none';
        if (recentBooksHeader) recentBooksHeader.style.display = 'none';
    }

    /**
     * Показать домашнюю страницу
     */
    showHomePage() {
        const mainContent = document.getElementById('main-content');

        // Показываем элементы домашней страницы
        const heroSection = mainContent.querySelector('.card[style*="gradient-primary"]');
        const statsSection = mainContent.querySelector('.stats');
        const quickActionsSection = mainContent.querySelectorAll('.card')[1]; // Второй блок card
        const recentBooksSection = document.getElementById('recent-books-container');
        const statsHeader = mainContent.querySelectorAll('h3')[0]; // Статистика заголовок
        const quickActionsHeader = mainContent.querySelectorAll('h3')[1]; // Быстрые действия заголовок
        const recentBooksHeader = mainContent.querySelectorAll('h3')[2]; // Недавние книги заголовок

        if (heroSection) heroSection.style.display = 'block';
        if (statsSection) statsSection.style.display = 'flex';
        if (quickActionsSection) quickActionsSection.style.display = 'block';
        if (recentBooksSection) recentBooksSection.style.display = 'block';
        if (statsHeader) statsHeader.style.display = 'block';
        if (quickActionsHeader) quickActionsHeader.style.display = 'block';
        if (recentBooksHeader) recentBooksHeader.style.display = 'block';
    }

    /**
     * Показать страницу книг
     */
    showBooksPage() {
        const booksPage = document.getElementById('books-page');
        if (booksPage) {
            booksPage.style.display = 'block';
        }
    }

    /**
     * Показать страницу подписок
     */
    showAlertsPage() {
        const alertsPage = document.getElementById('alerts-page');
        if (alertsPage) {
            alertsPage.style.display = 'block';
        }
    }

    /**
     * Показать страницу профиля
     */
    showProfilePage() {
        const profilePage = document.getElementById('profile-page');
        if (profilePage) {
            profilePage.style.display = 'block';
        }
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

            // Загружаем недавние книги
            await this.loadRecentBooks();
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
     * Загрузка недавних книг
     */
    async loadRecentBooks() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/web/books/api/all?limit=5`);
            if (!response.ok) throw new Error('Ошибка загрузки книг');

            const data = await response.json();
            const books = data.books || [];

            const container = document.getElementById('recent-books-container');

            if (books.length === 0) {
                container.innerHTML = `
                    <div class="empty">
                        <div class="empty__icon"><i class="fas fa-inbox"></i></div>
                        <h3 class="empty__title">Нет книг</h3>
                        <p class="empty__text">Начните поиск книг в каталоге</p>
                    </div>
                `;
            } else {
                container.innerHTML = books.map(book => `
                    <div class="book-card" data-book-id="${book.id}" style="cursor: pointer;">
                        <div class="book-card__cover" style="width: 60px; height: 80px;">
                            ${book.image_url
                                ? `<img src="${book.image_url}" alt="${book.title}">`
                                : `<div class="book-card__cover-placeholder"><i class="fas fa-book"></i></div>`
                            }
                        </div>
                        <div class="book-card__info">
                            <h4 style="font-size: 0.9rem; font-weight: 600; margin-bottom: 4px;">
                                ${this.escapeHtml(book.title)}
                            </h4>
                            <div style="font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 4px;">
                                ${this.escapeHtml(book.author || 'Неизвестный автор')}
                            </div>
                            <div style="font-size: 0.95rem; font-weight: 700; color: var(--accent-primary);">
                                ${book.current_price || 0} ₽
                                ${(book.original_price || 0) > 0 && book.original_price > book.current_price
                                    ? `<span style="font-size: 0.8rem; color: var(--text-secondary); text-decoration: line-through; margin-left: 8px;">${book.original_price} ₽</span>`
                                    : ''
                                }
                                ${(book.discount_percent || 0) > 0
                                    ? `<span style="font-size: 0.75rem; background: var(--danger); color: white; padding: 2px 6px; border-radius: 8px; margin-left: 8px;">-${book.discount_percent}%</span>`
                                    : ''
                                }
                            </div>
                        </div>
                    </div>
                `).join('');

                // Добавляем обработчики кликов
                container.querySelectorAll('.book-card').forEach(card => {
                    card.addEventListener('click', () => {
                        const bookId = card.dataset.bookId;
                        this.navigate('books');
                        window.tg.hapticClick();
                    });
                });
            }
        } catch (error) {
            console.error('Ошибка загрузки недавних книг:', error);
            const container = document.getElementById('recent-books-container');
            container.innerHTML = `
                <div class="empty">
                    <div class="empty__icon"><i class="fas fa-exclamation-triangle"></i></div>
                    <h3 class="empty__title">Ошибка загрузки</h3>
                    <p class="empty__text">Не удалось загрузить список книг</p>
                </div>
            `;
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
            console.log('[loadBooks] Начинаем загрузку книг, params:', params);
            console.log('[loadBooks] apiBaseUrl:', this.apiBaseUrl);

            let url;

            if (params.query) {
                // Если есть поисковый запрос, используем API парсера
                url = `${this.apiBaseUrl}/api/parser/books/${encodeURIComponent(params.query)}`;
                if (params.source) {
                    url += `?source=${params.source}`;
                }
            } else {
                // Если нет запроса, используем веб API для получения всех книг
                url = `${this.apiBaseUrl}/web/books/api/all`;
            }

            console.log('[loadBooks] URL запроса:', url);

            const response = await fetch(url);
            console.log('[loadBooks] Статус ответа:', response.status, response.statusText);

            if (!response.ok) {
                const errorText = await response.text();
                console.error('[loadBooks] Текст ошибки:', errorText);
                throw new Error('Ошибка загрузки книг');
            }

            const data = await response.json();
            console.log('[loadBooks] Получены данные:', data);

            // Обрабатываем разные форматы ответа
            this.data.books = data.books || [];

            this.renderBooks(this.data.books);
        } catch (error) {
            console.error('[loadBooks] Ошибка загрузки книг:', error);
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
            console.log('[loadAlerts] Начинаем загрузку подписок');
            console.log('[loadAlerts] apiBaseUrl:', this.apiBaseUrl);

            // Пробуем получить user_id, если не получилось - используем query_id
            let userId = window.tg.getChatId();

            if (!userId) {
                console.warn('[loadAlerts] Chat ID не получен, пробуем query_id...');
                userId = window.tg.getQueryId();
            }

            if (!userId) {
                console.error('[loadAlerts] Не удалось получить ни Chat ID, ни Query ID');
                this.showError('Не удалось получить ID пользователя. Откройте приложение через Telegram.');
                this.renderAlerts([]);
                return;
            }

            const url = `${this.apiBaseUrl}/api/alerts/?user_id=${userId}`;
            console.log('[loadAlerts] URL запроса:', url);

            const response = await fetch(url);
            console.log('[loadAlerts] Статус ответа:', response.status, response.statusText);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                console.error('[loadAlerts] Ошибка:', errorData);
                throw new Error(errorData.detail || 'Ошибка загрузки подписок');
            }

            const data = await response.json();
            console.log('[loadAlerts] Получены данные:', data);

            this.data.alerts = data || [];

            this.renderAlerts(this.data.alerts);
        } catch (error) {
            console.error('[loadAlerts] Ошибка загрузки подписок:', error);
            this.showError(error.message || 'Не удалось загрузить подписок');
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
            window.tg.hapticSuccess();
        } catch (error) {
            console.error('Ошибка поиска:', error);
            this.showError('Не удалось выполнить поиск');
        }
    }

    /**
     * Применение фильтров
     */
    async applyFilters() {
        const source = document.getElementById('filter-source').value;
        const discount = document.getElementById('filter-discount').value;
        const price = document.getElementById('filter-price').value;
        const query = document.getElementById('search-input').value;

        this.showLoading('Применение фильтров...');

        // TODO: Добавить логику фильтрации на сервере
        setTimeout(() => {
            this.loadBooks({ query, source, discount, price });
        }, 500);
    }

    /**
     * Загрузить еще книг
     */
    loadMoreBooks() {
        // TODO: Реализовать подгрузку следующих страниц
        this.showToast('Функция в разработке', 'info');
    }

    /**
     * Создание подписки
     */
    async createAlert(bookData) {
        try {
            // Пробуем получить user_id, если не получилось - используем query_id
            let userId = window.tg.getChatId();

            if (!userId) {
                console.warn('Chat ID не получен, пробуем query_id...');
                userId = window.tg.getQueryId();
            }

            if (!userId) {
                throw new Error('Не удалось получить ID пользователя. Убедитесь, что вы открыли приложение через Telegram.');
            }

            const response = await fetch(`${this.apiBaseUrl}/api/alerts/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    user_id: userId,
                    book_id: bookData.id,
                    book_title: bookData.title,
                    book_author: bookData.author,
                    book_source: bookData.source,
                    target_price: bookData.current_price,
                    min_discount: bookData.discount_percent || 0
                })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || 'Ошибка создания подписки');
            }

            window.tg.hapticSuccess();
            this.showSuccess('Подписка создана!');

            // Обновляем список подписок
            if (this.currentRoute === 'alerts') {
                await this.loadAlerts();
            }
        } catch (error) {
            console.error('Ошибка создания подписки:', error);
            window.tg.hapticError();
            this.showError(error.message || 'Не удалось создать подписку');
        }
    }

    /**
     * Удаление подписки
     */
    async deleteAlert(alertId) {
        try {
            const confirmed = await window.tg.showConfirm('Удалить эту подписку?');
            if (!confirmed) return;

            const response = await fetch(`${this.apiBaseUrl}/api/alerts/${alertId}/`, {
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

    // Обработка Enter в поиске
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                app.searchBooks(e.target.value);
            }
        });
    }
});
