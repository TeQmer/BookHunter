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
        this.recentBooksPage = 1; // Текущая страница недавних книг на главной
        this.recentBooksTotal = 0; // Общее количество недавних книг
        this.savedScrollPosition = 0; // Сохраненная позиция скролла (задача #3)
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
            case 'book-detail':
                this.showBookDetailPage();
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

        // Загружаем данные для страницы (кроме book-detail, он загружается отдельно)
        if (route !== 'book-detail') {
            this.loadPageData(route, params);
        }
    }

    /**
     * Скрыть все страницы
     */
    hideAllPages() {
        console.log('[hideAllPages] Скрываем все страницы');

        const mainContent = document.getElementById('main-content');
        console.log('[hideAllPages] mainContent:', mainContent);

        // Скрываем страницы, которые имеют display: none по умолчанию
        const booksPage = document.getElementById('books-page');
        const alertsPage = document.getElementById('alerts-page');
        const profilePage = document.getElementById('profile-page');

        console.log('[hideAllPages] booksPage:', booksPage);
        console.log('[hideAllPages] alertsPage:', alertsPage);
        console.log('[hideAllPages] profilePage:', profilePage);

        if (booksPage) booksPage.style.display = 'none';
        if (alertsPage) alertsPage.style.display = 'none';
        if (profilePage) profilePage.style.display = 'none';

        // Скрываем элементы домашней страницы
        const heroSection = document.getElementById('hero-section'); // (задача #8)
        const statsSection = mainContent.querySelector('.stats');
        const quickActionsSection = mainContent.querySelectorAll('.card')[1]; // Второй блок card
        const recentBooksSection = document.getElementById('recent-books-container');
        const recentPagination = document.getElementById('recent-pagination');
        const statsHeader = mainContent.querySelectorAll('h3')[0]; // Статистика заголовок
        const quickActionsHeader = mainContent.querySelectorAll('h3')[1]; // Быстрые действия заголовок
        const recentBooksHeader = mainContent.querySelectorAll('h3')[2]; // Недавние книги заголовок

        console.log('[hideAllPages] heroSection:', heroSection);
        console.log('[hideAllPages] statsSection:', statsSection);
        console.log('[hideAllPages] quickActionsSection:', quickActionsSection);
        console.log('[hideAllPages] recentBooksSection:', recentBooksSection);

        if (heroSection) heroSection.style.display = 'none';
        if (statsSection) statsSection.style.display = 'none';
        if (quickActionsSection) quickActionsSection.style.display = 'none';
        if (recentBooksSection) recentBooksSection.style.display = 'none';
        if (recentPagination) recentPagination.style.display = 'none';
        if (statsHeader) statsHeader.style.display = 'none';
        if (quickActionsHeader) quickActionsHeader.style.display = 'none';
        if (recentBooksHeader) recentBooksHeader.style.display = 'none';
    }

    /**
     * Показать домашнюю страницу
     */
    showHomePage() {
        console.log('[showHomePage] Показываем домашнюю страницу');

        const mainContent = document.getElementById('main-content');

        // Показываем элементы домашней страницы
        const heroSection = document.getElementById('hero-section'); // (задача #8)
        const statsSection = mainContent.querySelector('.stats');
        const quickActionsSection = mainContent.querySelectorAll('.card')[1]; // Второй блок card
        const recentBooksSection = document.getElementById('recent-books-container');
        const recentPagination = document.getElementById('recent-pagination');
        const statsHeader = mainContent.querySelectorAll('h3')[0]; // Статистика заголовок
        const quickActionsHeader = mainContent.querySelectorAll('h3')[1]; // Быстрые действия заголовок
        const recentBooksHeader = mainContent.querySelectorAll('h3')[2]; // Недавние книги заголовок

        if (heroSection) heroSection.style.display = 'block';
        if (statsSection) statsSection.style.display = 'flex';
        if (quickActionsSection) quickActionsSection.style.display = 'block';
        if (recentBooksSection) recentBooksSection.style.display = 'block';
        if (recentPagination) recentPagination.style.display = 'block';
        if (statsHeader) statsHeader.style.display = 'block';
        if (quickActionsHeader) quickActionsHeader.style.display = 'block';
        if (recentBooksHeader) recentBooksHeader.style.display = 'block';
    }

    /**
     * Показать страницу книг
     */
    showBooksPage() {
        console.log('[showBooksPage] Показываем страницу книг');

        const booksPage = document.getElementById('books-page');
        console.log('[showBooksPage] booksPage:', booksPage);

        if (booksPage) {
            booksPage.style.display = 'block';
            console.log('[showBooksPage] booksPage.style.display:', booksPage.style.display);
        } else {
            console.error('[showBooksPage] booksPage не найден!');
        }
    }

    /**
     * Показать страницу подписок
     */
    showAlertsPage() {
        console.log('[showAlertsPage] Показываем страницу подписок');

        const alertsPage = document.getElementById('alerts-page');
        console.log('[showAlertsPage] alertsPage:', alertsPage);

        if (alertsPage) {
            alertsPage.style.display = 'block';
        } else {
            console.error('[showAlertsPage] alertsPage не найден!');
        }
    }

    /**
     * Показать страницу профиля
     */
    showProfilePage() {
        console.log('[showProfilePage] Показываем страницу профиля');

        const profilePage = document.getElementById('profile-page');
        console.log('[showProfilePage] profilePage:', profilePage);

        if (profilePage) {
            profilePage.style.display = 'block';
        } else {
            console.error('[showProfilePage] profilePage не найден!');
        }
    }

    /**
     * Показать страницу деталей книги
     */
    showBookDetailPage() {
        console.log('[showBookDetailPage] Показываем страницу деталей книги');

        const bookDetailPage = document.getElementById('book-detail-page');
        console.log('[showBookDetailPage] bookDetailPage:', bookDetailPage);

        if (bookDetailPage) {
            bookDetailPage.style.display = 'block';

            // Удаляем старые обработчики клика перед добавлением нового (задача #4)
            const newBookDetailPage = bookDetailPage.cloneNode(true);
            bookDetailPage.parentNode.replaceChild(newBookDetailPage, bookDetailPage);

            // Добавляем обработчик клика на страницу деталей для закрытия
            newBookDetailPage.onclick = (e) => {
                // Закрываем только если клик не на интерактивные элементы
                if (e.target === newBookDetailPage) {
                    this.closeBookDetail();
                }
            };
        } else {
            console.error('[showBookDetailPage] bookDetailPage не найден!');
        }
    }

    /**
     * Загрузка данных страницы
     */
    async loadPageData(route, params) {
        console.log('[loadPageData] Загрузка данных для страницы:', route, 'params:', params);

        switch (route) {
            case 'home':
                await this.loadStats();
                break;
            case 'books':
                // Всегда загружаем книги - все или с фильтрами/поиском
                console.log('[loadPageData] Загружаем книги для страницы books');
                await this.loadBooks(params);
                break;
            case 'alerts':
                await this.loadAlerts();
                break;
            case 'profile':
                // Загружаем профиль пользователя (задача #7)
                await this.loadUserProfile();
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
            // Сбрасываем страницу недавних книг на 1
            this.recentBooksPage = 1;

            // Загружаем статистику
            await this.loadStats();

            // Загружаем недавние книги
            await this.loadRecentBooks(1);
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
     * Загрузка недавних книг с пагинацией
     */
    async loadRecentBooks(page = 1) {
        try {
            const limit = 15; // 15 книг на странице
            const offset = (page - 1) * limit;

            // Загружаем книги с сортировкой по цене по возрастанию
            const response = await fetch(`${this.apiBaseUrl}/web/books/api/all?limit=${limit}&offset=${offset}`);
            if (!response.ok) throw new Error('Ошибка загрузки книг');

            const data = await response.json();
            const books = data.books || [];
            const total = data.total || 0;

            // Сортируем книги по цене по возрастанию
            books.sort((a, b) => (a.current_price || 0) - (b.current_price || 0));

            this.recentBooksTotal = total;
            this.recentBooksPage = page;

            const container = document.getElementById('recent-books-container');
            const pagination = document.getElementById('recent-pagination');

            if (books.length === 0) {
                container.innerHTML = `
                    <div class="empty">
                        <div class="empty__icon"><i class="fas fa-inbox"></i></div>
                        <h3 class="empty__title">Нет книг</h3>
                        <p class="empty__text">Начните поиск книг в каталоге</p>
                    </div>
                `;
                if (pagination) pagination.style.display = 'none';
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
                        this.showBookDetails(bookId);
                    });
                });

                // Обновляем пагинацию
                if (pagination) {
                    const totalPages = Math.ceil(total / limit);
                    const pageInfo = document.getElementById('recent-page-info');
                    const prevBtn = document.getElementById('recent-prev-btn');
                    const nextBtn = document.getElementById('recent-next-btn');

                    if (pageInfo) pageInfo.textContent = `Страница ${page} из ${totalPages}`;
                    if (prevBtn) prevBtn.disabled = page <= 1;
                    if (nextBtn) nextBtn.disabled = page >= totalPages;

                    pagination.style.display = 'block';
                }

                // Прокрутка к началу блока недавних книг отключена (задача #2)
                // const recentHeader = document.querySelector('h3:has(i.fa-clock)');
                // if (recentHeader) {
                //     recentHeader.scrollIntoView({ behavior: 'smooth', block: 'start' });
                // }
            }
        } catch (error) {
            console.error('Ошибка загрузки недавних книг:', error);
            const container = document.getElementById('recent-books-container');
            const pagination = document.getElementById('recent-pagination');
            container.innerHTML = `
                <div class="empty">
                    <div class="empty__icon"><i class="fas fa-exclamation-triangle"></i></div>
                    <h3 class="empty__title">Ошибка загрузки</h3>
                    <p class="empty__text">Не удалось загрузить список книг</p>
                </div>
            `;
            if (pagination) pagination.style.display = 'none';
        }
    }

    /**
     * Загрузка страницы недавних книг (пагинация)
     */
    async loadRecentBooksPage(direction) {
        console.log('[loadRecentBooksPage] Загрузка страницы:', direction);

        // Получаем текущую страницу
        let currentPage = this.recentBooksPage || 1;

        if (direction === 'prev') {
            currentPage = Math.max(1, currentPage - 1);
        } else if (direction === 'next') {
            currentPage = currentPage + 1;
        }

        // Загружаем новую страницу
        await this.loadRecentBooks(currentPage);
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
     * Загрузка списка книг с умным поиском
     */
    async loadBooks(params = {}) {
        try {
            console.log('[loadBooks] Начинаем загрузку книг, params:', params);
            console.log('[loadBooks] apiBaseUrl:', this.apiBaseUrl);

            let url;
            let useSmartSearch = false;

            if (params.query) {
                // Умный поиск: сначала база данных, потом парсинг
                useSmartSearch = true;
                url = `${this.apiBaseUrl}/web/books/api/search?q=${encodeURIComponent(params.query)}`;
                if (params.source) {
                    url += `&source=${params.source}`;
                }
                if (params.discount) {
                    url += `&min_discount=${params.discount}`;
                }
                if (params.price) {
                    url += `&max_price=${params.price}`;
                }
            } else {
                // Если нет запроса, загружаем все книги с сортировкой по цене
                url = `${this.apiBaseUrl}/web/books/api/all`;
                const queryParams = [];
                if (params.source) {
                    queryParams.push(`source=${params.source}`);
                }
                if (params.discount) {
                    queryParams.push(`min_discount=${params.discount}`);
                }
                if (params.price) {
                    queryParams.push(`max_price=${params.price}`);
                }
                if (queryParams.length > 0) {
                    url += `?${queryParams.join('&')}`;
                }
            }

            console.log('[loadBooks] URL запроса:', url);

            // Добавляем таймаут для запроса (задача #5)
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 25000);

            const response = await fetch(url, { signal: controller.signal });
            clearTimeout(timeoutId);

            console.log('[loadBooks] Статус ответа:', response.status, response.statusText);

            if (!response.ok) {
                let errorMessage = 'Ошибка загрузки книг';
                try {
                    const errorData = await response.json();
                    errorMessage = errorData.detail || errorData.message || errorMessage;
                } catch (e) {
                    const errorText = await response.text();
                    console.error('[loadBooks] Текст ошибки:', errorText);
                }
                throw new Error(errorMessage);
            }

            const data = await response.json();
            console.log('[loadBooks] Получены данные:', data);

            // Обрабатываем разные форматы ответа
            // API парсера: {success: true, books: [...]}
            // Веб API: {books: [...]}
            if (data.success && data.books) {
                this.data.books = data.books;
            } else if (data.books) {
                this.data.books = data.books;
            } else {
                this.data.books = [];
            }

            console.log('[loadBooks] Книги для рендеринга:', this.data.books.length);

            // Если книг нет и это поиск - запускаем парсинг
            if (useSmartSearch && this.data.books.length === 0) {
                console.log('[loadBooks] Книг нет в базе, запускаем парсинг...');
                await this.startParsing(params.query, params.source || 'chitai-gorod');
                return;
            }

            this.renderBooks(this.data.books);
        } catch (error) {
            console.error('[loadBooks] Ошибка загрузки книг:', error);

            if (error.name === 'AbortError') {
                this.showError('Превышено время ожидания запроса');
            } else {
                this.showError(error.message || 'Не удалось загрузить книги');
            }

            // Показываем пустое состояние при ошибке
            const container = document.getElementById('books-container');
            if (container) {
                container.innerHTML = this.getEmptyState('Ошибка загрузки', error.message || 'Попробуйте изменить параметры поиска');
            }
        }
    }

    /**
     * Запуск парсинга книг
     */
    async startParsing(query, source = 'chitai-gorod') {
        try {
            console.log('[startParsing] Запускаем парсинг для:', query);

            // Получаем telegram_id для проверки лимитов (задача #6)
            let telegramId = window.tg.getChatId();
            if (!telegramId) {
                telegramId = window.tg.getQueryId();
            }

            const requestBody = {
                query,
                source,
                fetch_details: false
            };

            // Добавляем telegram_id если есть
            if (telegramId) {
                requestBody.telegram_id = telegramId;
            }

            const response = await fetch(`${this.apiBaseUrl}/api/parser/parse-body`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestBody)
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || 'Ошибка запуска парсинга');
            }

            const data = await response.json();
            console.log('[startParsing] Ответ:', data);

            // Показываем сообщение о парсинге
            if (data.task_id) {
                this.showParsingStatus(data.task_id, query);
            } else {
                this.showError('Не удалось запустить поиск книг');
            }
        } catch (error) {
            console.error('[startParsing] Ошибка:', error);
            this.showError(error.message || 'Не удалось запустить поиск книг');
        }
    }

    /**
     * Показать статус парсинга и периодически обновлять
     */
    async showParsingStatus(taskId, query) {
        console.log('[showParsingStatus] Показываем статус парсинга:', taskId);

        const container = document.getElementById('books-container');
        if (!container) return;

        container.innerHTML = `
            <div class="card" style="text-align: center; padding: 24px;">
                <div class="loading__spinner" style="margin: 0 auto 16px;"></div>
                <h4 style="margin-bottom: 8px;">Поиск книг...</h4>
                <p style="color: var(--text-secondary); font-size: 0.9rem;">
                    Ищем книги по запросу "${query}" на сайте магазина...
                </p>
                <p style="color: var(--text-muted); font-size: 0.8rem; margin-top: 12px;">
                    Это может занять несколько секунд
                </p>
            </div>
        `;

        // Периодически проверяем статус
        const checkInterval = setInterval(async () => {
            try {
                const response = await fetch(`${this.apiBaseUrl}/api/parser/parse/${taskId}`);
                const data = await response.json();

                console.log('[showParsingStatus] Статус:', data.status);

                if (data.status === 'completed') {
                    clearInterval(checkInterval);
                    console.log('[showParsingStatus] Парсинг завершен, загружаем книги');
                    await this.loadBooks({ query });
                } else if (data.status === 'error') {
                    clearInterval(checkInterval);
                    container.innerHTML = this.getEmptyState('Ошибка поиска', 'Не удалось найти книги. Попробуйте другой запрос.');
                }
            } catch (error) {
                console.error('[showParsingStatus] Ошибка проверки статуса:', error);
            }
        }, 2000);

        // Таймаут 30 секунд
        setTimeout(() => {
            clearInterval(checkInterval);
        }, 30000);
    }

    /**
     * Отрисовка списка книг
     */
    renderBooks(books) {
        console.log('[renderBooks] Начинаем отрисовку книг:', books.length);

        // Ищем контейнер для книг - может быть books-container или другой
        let container = document.getElementById('books-container');
        if (!container) {
            // Пробуем найти контейнер на странице поиска
            container = document.getElementById('search-results-container');
        }

        console.log('[renderBooks] Контейнер:', container);

        if (!container) {
            console.error('[renderBooks] Контейнер для книг не найден!');
            return;
        }

        if (!books || books.length === 0) {
            console.log('[renderBooks] Книг нет, показываем пустое состояние');
            container.innerHTML = this.getEmptyState('Книги не найдены', 'Попробуйте изменить параметры поиска');
            return;
        }

        // Сортируем книги по цене по возрастанию
        const sortedBooks = [...books].sort((a, b) => (a.current_price || 0) - (b.current_price || 0));

        console.log('[renderBooks] Рендеринг', sortedBooks.length, 'книг');
        container.innerHTML = sortedBooks.map(book => this.createBookCard(book)).join('');
        console.log('[renderBooks] HTML обновлен');

        // Добавляем обработчики событий
        container.querySelectorAll('.book-card').forEach(card => {
            card.addEventListener('click', (e) => {
                if (!e.target.closest('.btn')) {
                    const bookId = card.dataset.bookId;
                    this.showBookDetails(bookId);
                }
            });
        });

        console.log('[renderBooks] Отрисовка завершена');
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
     * Загрузка профиля пользователя (задача #7)
     */
    async loadUserProfile() {
        try {
            console.log('[loadUserProfile] Загрузка профиля пользователя');

            // Получаем telegram_id и данные пользователя из Telegram
            const user = window.tg.getUser();
            if (!user) {
                console.error('[loadUserProfile] Не удалось получить данные пользователя из Telegram');
                this.showError('Не удалось получить информацию о пользователе');
                return;
            }

            const telegramId = user.id;

            // Собираем параметры запроса
            const params = new URLSearchParams({
                telegram_id: telegramId
            });

            // Добавляем данные пользователя если они есть
            if (user.username) {
                params.append('username', user.username);
            }
            if (user.first_name) {
                params.append('first_name', user.first_name);
            }
            if (user.last_name) {
                params.append('last_name', user.last_name);
            }

            console.log('[loadUserProfile] Запрос статистики с параметрами:', params.toString());

            // Загружаем статистику пользователя
            const response = await fetch(`${this.apiBaseUrl}/api/users/stats?${params.toString()}`);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || 'Ошибка загрузки профиля');
            }

            const data = await response.json();
            console.log('[loadUserProfile] Получены данные:', data);

            if (data.success && data.stats) {
                this.renderUserProfile(data.stats);
            }
        } catch (error) {
            console.error('[loadUserProfile] Ошибка:', error);
            this.showError(error.message || 'Не удалось загрузить профиль');
        }
    }

    /**
     * Отрисовка профиля пользователя (задача #7)
     */
    renderUserProfile(stats) {
        const container = document.getElementById('profile-content');
        if (!container) {
            console.error('[renderUserProfile] Контейнер профиля не найден');
            return;
        }

        const requestsUsed = stats.daily_requests_used || 0;
        const requestsLimit = stats.daily_requests_limit || 15;
        const requestsRemaining = Math.max(0, requestsLimit - requestsUsed);
        const requestsPercentage = (requestsUsed / requestsLimit) * 100;

        // Форматируем дату обновления
        let updatedAtText = 'Нет данных';
        if (stats.requests_updated_at) {
            try {
                const updatedAt = new Date(stats.requests_updated_at);
                updatedAtText = updatedAt.toLocaleString('ru-RU');
            } catch (e) {
                updatedAtText = stats.requests_updated_at;
            }
        }

        container.innerHTML = `
            <div class="profile__info">
                ${stats.display_name || stats.username ? `
                    <h2 class="profile__name">${this.escapeHtml(stats.display_name || stats.username)}</h2>
                ` : ''}

                <div class="card">
                    <h3 style="margin-bottom: 16px;">📊 Статистика</h3>

                    <div class="profile__stat">
                        <div class="profile__stat-label">Книг в подписках</div>
                        <div class="profile__stat-value">${stats.total_alerts || 0}</div>
                    </div>

                    <div class="profile__stat">
                        <div class="profile__stat-label">Отправлено уведомлений</div>
                        <div class="profile__stat-value">${stats.notifications_sent || 0}</div>
                    </div>
                </div>

                <div class="card">
                    <h3 style="margin-bottom: 16px;">🔍 Лимиты запросов</h3>

                    <div class="profile__stat">
                        <div class="profile__stat-label">Использовано сегодня</div>
                        <div class="profile__stat-value">${requestsUsed} / ${requestsLimit}</div>
                    </div>

                    <div class="profile__stat">
                        <div class="profile__stat-label">Осталось сегодня</div>
                        <div class="profile__stat-value" style="color: ${requestsRemaining <= 3 ? 'var(--danger)' : 'var(--success)'};">
                            ${requestsRemaining}
                        </div>
                    </div>

                    <div style="margin-top: 16px;">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 0.9rem;">
                            <span style="color: var(--text-secondary);">Прогресс</span>
                            <span style="font-weight: 600;">${requestsPercentage.toFixed(0)}%</span>
                        </div>
                        <div style="width: 100%; height: 8px; background: var(--bg-secondary); border-radius: 4px; overflow: hidden;">
                            <div style="width: ${requestsPercentage}%; height: 100%; background: ${requestsPercentage >= 90 ? 'var(--danger)' : requestsPercentage >= 70 ? 'var(--warning)' : 'var(--success)'}; transition: width 0.3s ease;"></div>
                        </div>
                    </div>

                    <p style="color: var(--text-muted); font-size: 0.8rem; margin-top: 16px;">
                        Обновлено: ${updatedAtText}
                    </p>
                </div>

                <div class="card">
                    <h3 style="margin-bottom: 16px;">ℹ️ Информация</h3>

                    ${stats.username ? `
                        <div class="profile__stat">
                            <div class="profile__stat-label">Никнейм</div>
                            <div class="profile__stat-value">@${this.escapeHtml(stats.username)}</div>
                        </div>
                    ` : ''}

                    ${stats.first_name ? `
                        <div class="profile__stat">
                            <div class="profile__stat-label">Имя</div>
                            <div class="profile__stat-value">${this.escapeHtml(stats.first_name)}</div>
                        </div>
                    ` : ''}

                    <p style="color: var(--text-muted); font-size: 0.8rem; margin-top: 16px;">
                        Зарегистрирован: ${stats.created_at ? new Date(stats.created_at).toLocaleDateString('ru-RU') : 'Нет данных'}
                    </p>
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

        // Переключаемся на страницу books
        // navigate автоматически вызовет loadPageData, который загрузит книги
        console.log('[searchBooks] Переключаемся на страницу books с query:', query);
        this.navigate('books', { query });
    }

    /**
     * Применение фильтров
     */
    async applyFilters() {
        console.log('[applyFilters] Применение фильтров');

        const source = document.getElementById('filter-source');
        const discount = document.getElementById('filter-discount');
        const price = document.getElementById('filter-price');
        const searchInput = document.getElementById('search-input');

        if (!source || !discount || !price || !searchInput) {
            console.error('[applyFilters] Не все элементы фильтров найдены');
            this.showError('Ошибка применения фильтров');
            return;
        }

        const sourceValue = source.value;
        const discountValue = discount.value;
        const priceValue = price.value;
        const queryValue = searchInput.value;

        console.log('[applyFilters] Параметры фильтров:', {
            source: sourceValue,
            discount: discountValue,
            price: priceValue,
            query: queryValue
        });

        this.showLoading('Применение фильтров...');

        try {
            // Загружаем книги с фильтрацией с таймаутом (задача #5)
            await Promise.race([
                this.loadBooks({ query: queryValue, source: sourceValue, discount: discountValue, price: priceValue }),
                new Promise((_, reject) =>
                    setTimeout(() => reject(new Error('Таймаут загрузки')), 30000)
                )
            ]);
        } catch (error) {
            console.error('[applyFilters] Ошибка:', error);
            this.showError(error.message || 'Не удалось применить фильтры');
        }
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
    async showBookDetails(bookId) {
        console.log('[showBookDetails] Показ деталей книги:', bookId);
        window.tg.hapticClick();

        // Сохраняем текущую позицию скролла (задача #3)
        this.savedScrollPosition = window.scrollY || window.pageYOffset || document.documentElement.scrollTop;
        console.log('[showBookDetails] Сохранена позиция скролла:', this.savedScrollPosition);

        // Переключаемся на страницу деталей
        this.hideAllPages();
        this.showBookDetailPage();

        // Показываем кнопку назад
        window.tg.showBackButton();

        // Загружаем детали книги
        await this.loadBookDetail(bookId);
    }

    /**
     * Загрузка деталей книги
     */
    async loadBookDetail(bookId) {
        try {
            console.log('[loadBookDetail] Загрузка деталей книги:', bookId);

            const response = await fetch(`${this.apiBaseUrl}/api/parser/book/${bookId}`);
            console.log('[loadBookDetail] Статус ответа:', response.status);

            if (!response.ok) {
                // Пытаемся получить детали ошибки
                let errorMessage = 'Книга не найдена';
                try {
                    const errorData = await response.json();
                    errorMessage = errorData.detail || errorMessage;
                    console.error('[loadBookDetail] Ошибка сервера:', errorData);
                } catch (e) {
                    console.error('[loadBookDetail] Не удалось прочитать ошибку:', e);
                }
                throw new Error(errorMessage);
            }

            const data = await response.json();
            console.log('[loadBookDetail] Получены данные:', data);

            if (data.success && data.book) {
                this.renderBookDetail(data.book);
            } else if (data.book) {
                // Альтернативный формат ответа
                this.renderBookDetail(data.book);
            } else {
                throw new Error('Неверный формат ответа');
            }
        } catch (error) {
            console.error('[loadBookDetail] Ошибка:', error);
            this.showError('Не удалось загрузить информацию о книге');

            // Показываем сообщение об ошибке в контейнере
            const container = document.getElementById('book-detail-content');
            if (container) {
                container.innerHTML = `
                    <div style="text-align: center; padding: 32px;">
                        <div style="font-size: 48px; margin-bottom: 16px;">😕</div>
                        <h4 style="margin-bottom: 8px;">Ошибка загрузки</h4>
                        <p style="color: var(--text-secondary); font-size: 0.9rem; margin-bottom: 16px;">
                            ${this.escapeHtml(error.message || 'Не удалось загрузить информацию о книге')}
                        </p>
                        <button class="btn btn--secondary" onclick="app.navigate('books')">
                            <i class="fas fa-arrow-left"></i> Вернуться к списку
                        </button>
                    </div>
                `;
            }
        }
    }

    /**
     * Отрисовка деталей книги
     */
    renderBookDetail(book) {
        console.log('[renderBookDetail] Рендеринг деталей книги:', book.title);

        const container = document.getElementById('book-detail-content');
        if (!container) {
            console.error('[renderBookDetail] Контейнер не найден');
            return;
        }

        const discount = book.discount_percent || 0;
        const hasDiscount = discount > 0;

        // Декодируем жанры если это JSON-массив
        let genresDisplay = '';
        if (book.genres) {
            try {
                if (book.genres.startsWith('[')) {
                    // Это JSON-массив
                    const genres = JSON.parse(book.genres);
                    genresDisplay = genres.join(', ');
                } else {
                    // Это обычная строка
                    genresDisplay = book.genres;
                }
            } catch (e) {
                console.error('[renderBookDetail] Ошибка парсинга жанров:', e);
                genresDisplay = book.genres;
            }
        }

        container.innerHTML = `
            <div style="position: relative; display: flex; gap: 16px; flex-direction: column;">
                <!-- Кнопка закрытия -->
                <button
                    onclick="app.closeBookDetail()"
                    style="position: absolute; top: 0; right: 0; background: var(--bg-card); border: none; width: 40px; height: 40px; border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center; color: var(--text-secondary); font-size: 20px; z-index: 10;"
                >
                    <i class="fas fa-times"></i>
                </button>

                <!-- Изображение книги -->
                <div style="display: flex; justify-content: center; margin-bottom: 16px; padding-top: 8px;">
                    ${book.image_url
                        ? `<img src="${book.image_url}" alt="${book.title}" style="max-width: 200px; max-height: 280px; border-radius: 8px;">`
                        : `<div style="width: 200px; height: 280px; background: var(--bg-card); display: flex; align-items: center; justify-content: center; border-radius: 8px;">
                            <i class="fas fa-book" style="font-size: 64px; color: var(--text-muted);"></i>
                           </div>`
                    }
                </div>

                <!-- Информация о книге -->
                <div>
                    <h2 style="font-size: 1.4rem; font-weight: 700; margin-bottom: 8px; line-height: 1.3;">
                        ${this.escapeHtml(book.title)}
                    </h2>

                    ${book.author ? `
                        <p style="color: var(--text-secondary); font-size: 1.1rem; margin-bottom: 16px;">
                            ${this.escapeHtml(book.author)}
                        </p>
                    ` : ''}

                    <!-- Цена и скидка -->
                    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
                        <span style="font-size: 1.8rem; font-weight: 700; color: var(--success);">
                            ${book.current_price || 0} ₽
                        </span>
                        ${hasDiscount && book.original_price && book.original_price > book.current_price ? `
                            <span style="font-size: 1.2rem; color: var(--text-muted); text-decoration: line-through;">
                                ${book.original_price} ₽
                            </span>
                        ` : ''}
                        ${hasDiscount ? `
                            <span style="background: var(--danger); color: white; padding: 4px 12px; border-radius: 16px; font-weight: 600;">
                                -${discount}%
                            </span>
                        ` : ''}
                    </div>

                    <!-- Дополнительная информация -->
                    <div style="background: var(--bg-secondary); padding: 16px; border-radius: 12px; margin-bottom: 16px;">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                            <span style="color: var(--text-secondary);">Магазин:</span>
                            <span style="font-weight: 600;">${this.escapeHtml(book.source || 'Неизвестно')}</span>
                        </div>
                        ${book.isbn ? `
                            <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                                <span style="color: var(--text-secondary);">ISBN:</span>
                                <span style="font-weight: 600;">${this.escapeHtml(book.isbn)}</span>
                            </div>
                        ` : ''}
                        ${genresDisplay ? `
                            <div style="display: flex; justify-content: space-between;">
                                <span style="color: var(--text-secondary);">Жанры:</span>
                                <span style="font-weight: 600; text-align: right; max-width: 60%;">${this.escapeHtml(genresDisplay)}</span>
                            </div>
                        ` : ''}
                    </div>

                    <!-- Кнопки действий -->
                    <div style="display: flex; flex-direction: column; gap: 12px;">
                        <a href="${book.url}" target="_blank" class="btn btn--primary" style="text-align: center; text-decoration: none; display: block; padding: 12px 24px; border-radius: 12px; font-weight: 600;">
                            <i class="fas fa-external-link-alt"></i> <span style="color: #FFFFFF;">Перейти в магазин</span>
                        </a>

                        <button class="btn btn--secondary" onclick="app.toggleAlertForBook(${book.id})" style="padding: 12px 24px; border-radius: 12px; font-weight: 600;">
                            <i class="fas fa-bell"></i> <span style="color: #FFFFFF;">Подписаться на скидку</span>
                        </button>
                    </div>

                    <!-- Информация о парсинге -->
                    ${book.parsed_at ? `
                        <p style="color: var(--text-muted); font-size: 0.8rem; margin-top: 16px; text-align: center;">
                            Информация обновлена: ${new Date(book.parsed_at).toLocaleString('ru-RU')}
                        </p>
                    ` : ''}
                </div>
            </div>
        `;

        // Сохраняем текущую книгу для подписки
        this.currentBook = book;

        console.log('[renderBookDetail] Рендеринг завершен');
    }

    /**
     * Закрыть страницу деталей книги
     */
    closeBookDetail() {
        console.log('[closeBookDetail] Закрытие деталей книги');
        window.tg.hapticClick();

        // Полностью скрываем и очищаем модальное окно (задача #4)
        const bookDetailPage = document.getElementById('book-detail-page');
        if (bookDetailPage) {
            bookDetailPage.style.display = 'none';

            // Очищаем контент
            const content = document.getElementById('book-detail-content');
            if (content) {
                content.innerHTML = '';
            }

            // Удаляем все обработчики событий
            const newBookDetailPage = bookDetailPage.cloneNode(true);
            bookDetailPage.parentNode.replaceChild(newBookDetailPage, bookDetailPage);
        }

        // Очищаем текущую книгу
        this.currentBook = null;

        // Скрываем кнопку назад
        window.tg.hideBackButton();

        // Возвращаемся на предыдущую страницу
        if (this.currentRoute === 'book-detail') {
            this.navigate('books');
        } else {
            this.navigate('home');
        }

        // Восстанавливаем позицию скролла (задача #3)
        if (this.savedScrollPosition > 0) {
            console.log('[closeBookDetail] Восстанавливаем позицию скролла:', this.savedScrollPosition);
            setTimeout(() => {
                window.scrollTo({
                    top: this.savedScrollPosition,
                    behavior: 'smooth'
                });
            }, 100); // Небольшая задержка для корректного рендеринга
        }
    }

    /**
     * Переключение подписки на книгу
     */
    async toggleAlertForBook(bookId) {
        console.log('[toggleAlertForBook] Переключение подписки для книги:', bookId);

        try {
            // Проверяем, есть ли уже подписка
            const checkResponse = await fetch(`${this.apiBaseUrl}/api/alerts/book/${bookId}`);
            const checkData = await checkResponse.json();

            if (checkData.alert) {
                // Подписка уже есть - удаляем
                const deleteResponse = await fetch(`${this.apiBaseUrl}/api/alerts/${checkData.alert.id}/`, {
                    method: 'DELETE'
                });

                if (deleteResponse.ok) {
                    window.tg.hapticSuccess();
                    this.showSuccess('Подписка удалена');
                } else {
                    throw new Error('Не удалось удалить подписку');
                }
            } else {
                // Создаем новую подписку
                await this.createAlertFromBook(bookId);
            }
        } catch (error) {
            console.error('[toggleAlertForBook] Ошибка:', error);
            this.showError(error.message || 'Не удалось изменить подписку');
        }
    }

    /**
     * Создание подписки на книгу
     */
    async createAlertFromBook(bookId) {
        try {
            console.log('[createAlertFromBook] Создание подписки на книгу:', bookId);

            // Получаем user_id
            let userId = window.tg.getChatId();

            if (!userId) {
                userId = window.tg.getQueryId();
            }

            if (!userId) {
                throw new Error('Не удалось получить ID пользователя');
            }

            // Получаем информацию о книге
            const book = this.currentBook;
            if (!book) {
                throw new Error('Информация о книге не найдена');
            }

            const response = await fetch(`${this.apiBaseUrl}/api/alerts/create-from-book`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    book_id: bookId,
                    user_id: userId,
                    target_price: book.current_price,
                    min_discount: book.discount_percent || 0
                })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || 'Ошибка создания подписки');
            }

            const data = await response.json();
            console.log('[createAlertFromBook] Ответ:', data);

            window.tg.hapticSuccess();
            this.showSuccess('Подписка создана!');
        } catch (error) {
            console.error('[createAlertFromBook] Ошибка:', error);
            window.tg.hapticError();
            throw error;
        }
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
