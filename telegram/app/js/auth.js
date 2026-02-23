/**
 * Auth Service
 * Сервис для работы с авторизацией через Telegram initData и JWT токены
 */

class AuthService {
    constructor() {
        this.apiBaseUrl = typeof API_BASE_URL !== 'undefined' ? API_BASE_URL : window.location.origin;
        this.accessToken = null;
        this.refreshToken = null;
        this.user = null;
        this.isAuthenticated = false;
        this.initPromise = null;
    }

    /**
     * Инициализация авторизации
     * Вызывается при запуске приложения
     */
    async init() {
        // Если уже идет инициализация - ждем её завершения
        if (this.initPromise) {
            return this.initPromise;
        }

        this.initPromise = this._doInit();
        return this.initPromise;
    }

    async _doInit() {
        try {
            console.log('[AuthService] Инициализация...');

            // Проверяем наличие токенов в cookies
            this.accessToken = this._getCookie('ACCESS_TOKEN');
            this.refreshToken = this._getCookie('REFRESH_TOKEN');

            if (this.accessToken || this.refreshToken) {
                console.log('[AuthService] Найдены токены, проверяем...');
                
                // Пробуем получить информацию о пользователе
                try {
                    const response = await this._fetchWithAuth('/api/auth/me');
                    if (response.success) {
                        this.user = response.user;
                        this.isAuthenticated = true;
                        console.log('[AuthService] Пользователь авторизован:', this.user);
                        return true;
                    }
                } catch (e) {
                    console.log('[AuthService] Токены недействительны, пробуем обновить...');
                    
                    // Пробуем обновить токены
                    const refreshed = await this.refresh();
                    if (refreshed) {
                        return true;
                    }
                }
            }

            // Если токенов нет или они недействительны - выполняем вход через Telegram
            console.log('[AuthService] Выполняем вход через Telegram...');
            await this.signIn();

            return this.isAuthenticated;

        } catch (error) {
            console.error('[AuthService] Ошибка инициализации:', error);
            return false;
        }
    }

    /**
     * Вход через Telegram initData
     */
    async signIn() {
        try {
            const initData = window.tg.getInitData();
            
            if (!initData) {
                console.error('[AuthService] initData не доступен');
                // Пробуем получить через getUser как запасной вариант
                const user = window.tg.getUser();
                if (!user) {
                    throw new Error('Не удалось получить данные Telegram');
                }
                // Используем старый метод для совместимости
                return await this._legacySignIn(user);
            }

            console.log('[AuthService] Отправляем initData на сервер...');

            const response = await fetch(`${this.apiBaseUrl}/api/auth/signin`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                credentials: 'include', // Важно для cookies
                body: JSON.stringify({ initData })
            });

            const data = await response.json();

            if (!response.ok) {
                console.error('[AuthService] Ошибка входа:', data);
                
                // Если ошибка валидации initData - пробуем старый метод
                if (data.detail === 'AUTH__INVALID_INITDATA') {
                    const user = window.tg.getUser();
                    if (user) {
                        return await this._legacySignIn(user);
                    }
                }
                
                throw new Error(data.detail || 'Ошибка входа');
            }

            // Сохраняем данные пользователя
            this.user = data.user;
            this.isAuthenticated = true;

            console.log('[AuthService] Вход выполнен успешно:', this.user);

            return true;

        } catch (error) {
            console.error('[AuthService] Ошибка входа:', error);
            
            // Пробуем старый метод как запасной
            const user = window.tg.getUser();
            if (user) {
                console.log('[AuthService] Пробуем старый метод авторизации...');
                return await this._legacySignIn(user);
            }
            
            return false;
        }
    }

    /**
     * Устаревший метод входа (для совместимости)
     * Использует данные напрямую без валидации initData
     */
    async _legacySignIn(user) {
        try {
            console.log('[AuthService] Используем legacy авторизацию для:', user);

            const telegramId = user.id;
            const params = new URLSearchParams({
                telegram_id: telegramId
            });

            if (user.username) params.append('username', user.username);
            if (user.first_name) params.append('first_name', user.first_name);
            if (user.last_name) params.append('last_name', user.last_name);

            const response = await fetch(`${this.apiBaseUrl}/api/users/signin?${params.toString()}`, {
                method: 'POST',
                credentials: 'include'
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Ошибка входа');
            }

            this.user = data.user || data;
            this.isAuthenticated = true;

            console.log('[AuthService] Legacy вход выполнен:', this.user);

            return true;

        } catch (error) {
            console.error('[AuthService] Ошибка legacy входа:', error);
            return false;
        }
    }

    /**
     * Обновление токенов
     */
    async refresh() {
        try {
            console.log('[AuthService] Обновление токенов...');

            const response = await fetch(`${this.apiBaseUrl}/api/auth/refresh`, {
                method: 'POST',
                credentials: 'include'
            });

            const data = await response.json();

            if (!response.ok) {
                console.log('[AuthService] Не удалось обновить токены');
                this.logout();
                return false;
            }

            // Токены обновлены автоматически через cookies
            if (data.user) {
                this.user = data.user;
                this.isAuthenticated = true;
            }

            console.log('[AuthService] Токены обновлены');

            return true;

        } catch (error) {
            console.error('[AuthService] Ошибка обновления токенов:', error);
            this.logout();
            return false;
        }
    }

    /**
     * Выход
     */
    async logout() {
        try {
            await fetch(`${this.apiBaseUrl}/api/auth/logout`, {
                method: 'POST',
                credentials: 'include'
            });
        } catch (e) {
            console.log('[AuthService] Ошибка при выходе:', e);
        }

        this.accessToken = null;
        this.refreshToken = null;
        this.user = null;
        this.isAuthenticated = false;

        console.log('[AuthService] Выход выполнен');
    }

    /**
     * Выполнение запроса с автоматическим обновлением токенов
     */
    async _fetchWithAuth(url, options = {}) {
        const fullUrl = url.startsWith('http') ? url : `${this.apiBaseUrl}${url}`;

        const defaultOptions = {
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            }
        };

        const mergedOptions = {
            ...defaultOptions,
            ...options,
            headers: {
                ...defaultOptions.headers,
                ...options.headers
            }
        };

        let response = await fetch(fullUrl, mergedOptions);

        // Если токен истек - пробуем обновить
        if (response.status === 401) {
            const refreshed = await this.refresh();
            
            if (refreshed) {
                // Повторяем запрос с новыми токенами
                response = await fetch(fullUrl, mergedOptions);
            } else {
                throw new Error('AUTH__SESSION_EXPIRED');
            }
        }

        return response.json();
    }

    /**
     * GET запрос с авторизацией
     */
    async get(endpoint, params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const url = queryString ? `${endpoint}?${queryString}` : endpoint;
        
        const response = await this._fetchWithAuth(url);
        return response;
    }

    /**
     * POST запрос с авторизацией
     */
    async post(endpoint, data = {}) {
        return await this._fetchWithAuth(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    /**
     * Получение текущего пользователя
     */
    getUser() {
        return this.user;
    }

    /**
     * Проверка авторизации
     */
    isLoggedIn() {
        return this.isAuthenticated;
    }

    /**
     * Получение cookie по имени
     */
    _getCookie(name) {
        const matches = document.cookie.match(new RegExp(
            '(?:^|; )' + name.replace(/([\.$?*|{}\(\)\[\]\\\/\+^])/g, '\\$1') + '=([^;]*)'
        ));
        return matches ? decodeURIComponent(matches[1]) : null;
    }
}

// Создаем глобальный экземпляр
window.authService = new AuthService();

// Экспортируем
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AuthService;
}
