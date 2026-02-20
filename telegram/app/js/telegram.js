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
        // Принудительно устанавливаем тёмную тему через Telegram WebApp API
        const darkColors = {
            bg_color: '#2C241B',
            text_color: '#EFEBE9',
            hint_color: '#A1887F',
            link_color: '#A0785A',
            button_color: '#A0785A',
            button_text_color: '#F5EDE0',
            secondary_bg_color: '#3E3428'
        };

        // Применяем цвета через Telegram WebApp API
        if (this.webApp.setHeaderColor) {
            this.webApp.setHeaderColor('#2C241B');
        }
        if (this.webApp.setBackgroundColor) {
            this.webApp.setBackgroundColor('#2C241B');
        }

        // Удаляем инлайн-стили, которые Telegram может применить к body
        setTimeout(() => {
            const body = document.body;
            if (body && body.style) {
                // Удаляем инлайн-стили от Telegram
                body.style.removeProperty('background-color');
                body.style.removeProperty('color');
                body.style.removeProperty('background-image');

                // Добавляем наш класс для темной темы
                body.classList.add('force-dark-theme');
            }

            // Удаляем инлайн-стили из html
            const html = document.documentElement;
            if (html && html.style) {
                html.style.removeProperty('background-color');
                html.style.removeProperty('color');
            }

            // Запускаем наблюдатель для перезаписи стилей Telegram
            this.forceDarkTheme();

            console.log('Принудительно применена тёмная тема (стили Telegram перезаписаны)');
        }, 100);
    }

    /**
     * Принудительное применение темной темы с MutationObserver
     * Следит за изменениями стилей от Telegram и перезаписывает их
     */
    forceDarkTheme() {
        const forceDarkColors = () => {
            // Применяем к html
            const html = document.documentElement;
            if (html) {
                html.style.setProperty('background-color', '#2a1f1a', 'important');
                html.style.setProperty('--tg-theme-bg-color', '#2a1f1a', 'important');
                html.style.setProperty('--tg-theme-text-color', '#faf5ed', 'important');
            }

            // Применяем к body
            const body = document.body;
            if (body) {
                body.style.setProperty('background-color', '#2a1f1a', 'important');
                body.style.setProperty('color', '#faf5ed', 'important');
                body.style.setProperty('--tg-theme-bg-color', '#2a1f1a', 'important');
                body.style.setProperty('--tg-theme-text-color', '#faf5ed', 'important');
                body.classList.add('force-dark-theme');
            }

            // Применяем ко всем элементам с инлайн-стилями
            const allElements = document.querySelectorAll('[style*="background"], [style*="color"]');
            allElements.forEach(el => {
                const style = el.getAttribute('style') || '';
                if (style.includes('background') && !style.includes('#2a1f1a')) {
                    el.style.setProperty('background-color', '#2a1f1a', 'important');
                }
                if (style.includes('color') && !style.includes('#faf5ed') && !style.includes('#e8a85c')) {
                    el.style.setProperty('color', '#faf5ed', 'important');
                }
            });
        };

        // Применяем сразу
        forceDarkColors();

        // Создаем MutationObserver для отслеживания изменений
        const observer = new MutationObserver((mutations) => {
            let needsUpdate = false;

            mutations.forEach((mutation) => {
                if (mutation.type === 'attributes' && mutation.attributeName === 'style') {
                    const target = mutation.target;
                    const style = target.getAttribute('style') || '';

                    // Если Telegram изменил фон или цвет
                    if ((style.includes('background') && !style.includes('#2C241B')) ||
                        (style.includes('color') && !style.includes('#EFEBE9') && !style.includes('#A0785A'))) {
                        needsUpdate = true;
                    }
                }
            });

            if (needsUpdate) {
                forceDarkColors();
            }
        });

        // Наблюдаем за body и html
        const body = document.body;
        const html = document.documentElement;

        if (body) {
            observer.observe(body, {
                attributes: true,
                attributeFilter: ['style']
            });
        }

        if (html) {
            observer.observe(html, {
                attributes: true,
                attributeFilter: ['style']
            });
        }

        // Периодически применяем стили (на всякий случай)
        setInterval(forceDarkColors, 1000);

        console.log('MutationObserver запущен для перезаписи стилей Telegram');
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
            // Если API недоступен, используем нативный confirm для простых случаев
            if (options.buttons && options.buttons.length === 2) {
                const result = confirm(options.message);
                return Promise.resolve(result ? { button_id: options.buttons[0].id || 'ok' } : null);
            }
            alert(options.message);
            return Promise.resolve({ button_id: 'ok' });
        }

        // showPopup возвращает Promise, но обернём для надёжности
        const result = this.webApp.showPopup({
            title: options.title || '',
            message: options.message || '',
            buttons: options.buttons || [{type: 'ok'}]
        });

        // Если result уже Promise, возвращаем его
        if (result && typeof result.then === 'function') {
            return result;
        }

        // Если результат синхронный, оборачиваем в Promise
        return Promise.resolve(result);
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

        // showConfirm возвращает boolean синхронно, оборачиваем в Promise для согласованности
        return Promise.resolve(this.webApp.showConfirm(message));
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
