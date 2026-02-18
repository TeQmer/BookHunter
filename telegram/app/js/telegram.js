/**
 * Telegram Web App API Wrapper
 * Обёртка для работы с Telegram Web App API
 */

class TelegramWebApp {
    constructor() {
        this.webApp = window.Telegram?.WebApp;
        this.init();
    }

    /**
     * Инициализация Telegram Web App
     */
    init() {
        if (!this.webApp) {
            console.warn('Telegram Web App API не доступен');
            return false;
        }

        // Расширяем для заполнения всего экрана
        this.webApp.ready();

        // Применяем тему Telegram
        this.applyTheme();

        // Настраиваем кнопку назад
        this.setupBackButton();

        // Настраиваем главную кнопку
        this.setupMainButton();

        // Настраиваем Haptic Feedback
        this.setupHaptic();

        console.log('Telegram Web App инициализирован');
        return true;
    }

    /**
     * Применение темы Telegram
     * Примечание: Тема фиксирована (тёмная), игнорируем тему Telegram
     */
    applyTheme() {
        // Тема фиксирована на тёмную - ничего не делаем
        // CSS переменные уже заданы в mini-app.css
        console.log('Используется фиксированная тёмная тема (тема Telegram игнорируется)');
    }

    /**
     * Настройка кнопки назад
     */
    setupBackButton() {
        if (!this.webApp.BackButton) return;

        this.webApp.BackButton.onClick(() => {
            window.history.back();
        });
    }

    /**
     * Показать кнопку назад
     */
    showBackButton() {
        if (this.webApp?.BackButton) {
            this.webApp.BackButton.show();
        }
    }

    /**
     * Скрыть кнопку назад
     */
    hideBackButton() {
        if (this.webApp?.BackButton) {
            this.webApp.BackButton.hide();
        }
    }

    /**
     * Настройка главной кнопки
     */
    setupMainButton() {
        if (!this.webApp.MainButton) return;

        this.webApp.MainButton.onClick(() => {
            // По умолчанию ничего не делаем, переопределяется в приложении
            console.log('Main button clicked');
        });
    }

    /**
     * Показать главную кнопку
     */
    showMainButton(text, onClick) {
        if (!this.webApp?.MainButton) return;

        this.webApp.MainButton.setText(text);

        if (onClick) {
            // Удаляем предыдущие обработчики
            this.webApp.MainButton.offClick(() => {});
            // Добавляем новый
            this.webApp.MainButton.onClick(onClick);
        }

        this.webApp.MainButton.show();
    }

    /**
     * Скрыть главную кнопку
     */
    hideMainButton() {
        if (this.webApp?.MainButton) {
            this.webApp.MainButton.hide();
        }
    }

    /**
     * Настройка Haptic Feedback
     */
    setupHaptic() {
        if (!this.webApp?.HapticFeedback) return;

        this.haptic = {
            impact: (style = 'medium') => {
                this.webApp.HapticFeedback.impactOccurred(style);
            },
            notification: (type = 'success') => {
                this.webApp.HapticFeedback.notificationOccurred(type);
            },
            selection: () => {
                this.webApp.HapticFeedback.selectionChanged();
            }
        };
    }

    /**
     * Вибрация при клике
     */
    hapticClick() {
        this.haptic?.selection();
    }

    /**
     * Вибрация при успешном действии
     */
    hapticSuccess() {
        this.haptic?.notification('success');
    }

    /**
     * Вибрация при ошибке
     */
    hapticError() {
        this.haptic?.notification('error');
    }

    /**
     * Вибрация при предупреждении
     */
    hapticWarning() {
        this.haptic?.notification('warning');
    }

    /**
     * Получить данные пользователя через декодирование initData
     */
    getUserFromInitData() {
        if (!this.webApp?.initData) {
            return null;
        }

        try {
            // Декодируем URL-encoded строку initData
            const params = new URLSearchParams(this.webApp.initData);
            const userParam = params.get('user');

            if (!userParam) {
                return null;
            }

            // Парсим JSON
            const user = JSON.parse(decodeURIComponent(userParam));
            console.log('User из initData:', user);
            return user;
        } catch (error) {
            console.error('Ошибка декодирования initData:', error);
            return null;
        }
    }

    /**
     * Получить данные пользователя
     */
    getUser() {
        if (!this.webApp) {
            console.warn('Telegram WebApp не доступен, пользователь не определен');
            return null;
        }

        // Сначала пробуем через initDataUnsafe
        let user = this.webApp.initDataUnsafe?.user;
        console.log('initDataUnsafe:', this.webApp.initDataUnsafe);
        console.log('User из initDataUnsafe:', user);

        // Если не нашли, пробуем через декодирование initData
        if (!user) {
            console.log('Пробуем получить user через initData...');
            user = this.getUserFromInitData();
        }

        if (!user) {
            console.warn('Пользователь не найден ни в initDataUnsafe, ни в initData');
            console.warn('initData:', this.webApp.initData);
        }

        return user || null;
    }

    /**
     * Получить ID чата
     */
    getChatId() {
        const user = this.getUser();
        const chatId = user?.id || null;

        console.log('Chat ID:', chatId);

        if (!chatId) {
            console.error('Не удалось получить Chat ID. Проверьте, что приложение открыто через Telegram.');
            console.error('WebApp доступен:', !!this.webApp);
            console.error('initData:', this.webApp?.initData || 'нет');
            console.error('initDataUnsafe:', this.webApp?.initDataUnsafe || 'нет');
        }

        return chatId;
    }

    /**
     * Получить query_id (альтернативный способ идентификации)
     */
    getQueryId() {
        if (!this.webApp?.initData) {
            return null;
        }

        try {
            const params = new URLSearchParams(this.webApp.initData);
            const queryId = params.get('query_id');
            console.log('Query ID:', queryId);
            return queryId;
        } catch (error) {
            console.error('Ошибка получения query_id:', error);
            return null;
        }
    }

    /**
     * Получить имя пользователя
     */
    getUserName() {
        const user = this.getUser();
        return user?.first_name || user?.username || 'Пользователь';
    }

    /**
     * Получить username
     */
    getUsername() {
        const user = this.getUser();
        return user?.username || null;
    }

    /**
     * Получить язык пользователя
     */
    getLanguageCode() {
        const user = this.getUser();
        return user?.language_code || 'ru';
    }

    /**
     * Получить initData для авторизации
     */
    getInitData() {
        return this.webApp?.initData || '';
    }

    /**
     * Открыть ссылку в браузере
     */
    openLink(url) {
        if (this.webApp) {
            this.webApp.openLink(url);
        } else {
            window.open(url, '_blank');
        }
    }

    /**
     * Открыть ссылку внутри Telegram
     */
    openLinkInside(url) {
        if (this.webApp) {
            this.webApp.openTelegramLink(url);
        } else {
            window.open(url, '_blank');
        }
    }

    /**
     * Закрыть Web App
     */
    close() {
        if (this.webApp) {
            this.webApp.close();
        }
    }

    /**
     * Показать всплывающее окно (Popup)
     */
    showPopup(options) {
        if (!this.webApp?.showPopup) {
            alert(options.message);
            return Promise.resolve();
        }

        return this.webApp.showPopup({
            title: options.title || '',
            message: options.message || '',
            buttons: options.buttons || [{type: 'ok'}]
        });
    }

    /**
     * Показать подтверждение (Alert)
     */
    showAlert(message) {
        if (!this.webApp?.showAlert) {
            alert(message);
            return Promise.resolve();
        }

        return this.webApp.showAlert(message);
    }

    /**
     * Показать подтверждение с кнопкой (Confirm)
     */
    showConfirm(message) {
        if (!this.webApp?.showConfirm) {
            return Promise.resolve(confirm(message));
        }

        return this.webApp.showConfirm(message);
    }

    /**
     * Показать сканер QR кода
     */
    scanQR(text) {
        if (!this.webApp?.showScanQrPopup) {
            return Promise.reject('QR scanner не поддерживается');
        }

        return this.webApp.showScanQrPopup({
            text: text || 'Сканируйте QR код'
        });
    }

    /**
     * Проверить доступность API
     */
    isAvailable() {
        return !!this.webApp;
    }

    /**
     * Получить информацию о версии Telegram
     */
    getVersion() {
        return this.webApp?.version || 'unknown';
    }

    /**
     * Проверить, открыто ли приложение в полноэкранном режиме
     */
    isFullscreen() {
        return this.webApp?.isFullscreen || false;
    }

    /**
     * Расширить приложение на весь экран
     */
    expand() {
        if (this.webApp) {
            this.webApp.expand();
        }
    }

    /**
     * Настроить цвет заголовка
     */
    setHeaderColor(color) {
        if (this.webApp?.setHeaderColor) {
            this.webApp.setHeaderColor(color);
        }
    }

    /**
     * Настроить цвет фона
     */
    setBackgroundColor(color) {
        if (this.webApp?.setBackgroundColor) {
            this.webApp.setBackgroundColor(color);
        }
    }

    /**
     * Установить обработчик кнопки назад
     */
    onBackButton(callback) {
        if (this.webApp?.BackButton) {
            this.webApp.BackButton.onClick(callback);
        }
    }

    /**
     * Показать кнопку назад
     */
    showBackButton() {
        if (this.webApp?.BackButton) {
            this.webApp.BackButton.show();
        }
    }

    /**
     * Скрыть кнопку назад
     */
    hideBackButton() {
        if (this.webApp?.BackButton) {
            this.webApp.BackButton.hide();
        }
    }
}

// Создаем глобальный экземпляр
window.tg = new TelegramWebApp();

// Экспортируем для использования в модулях
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TelegramWebApp;
}
