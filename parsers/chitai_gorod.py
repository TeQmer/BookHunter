import asyncio
import re
import requests
from datetime import datetime
from typing import List, Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from parsers.base import BaseParser, Book
from services.logger import parser_logger

class ChitaiGorodParser(BaseParser):
    """Парсер для магазина 'Читай-город'"""
    
    def __init__(self):
        super().__init__("chitai-gorod", delay_min=2, delay_max=4)
        self.base_url = "https://www.chitai-gorod.ru"
        
    async def search_books(self, query: str, max_pages: int = 1, limit: int = None, fetch_details: bool = False) -> List[Book]:
        """Поиск книг на сайте chitai-gorod.ru
        
        Args:
            query: Поисковый запрос
            max_pages: Максимальное количество страниц для поиска
            limit: Максимальное количество книг для возврата
            fetch_details: Загружать ли детальную страницу для каждой книги (для извлечения характеристик)
        """

        await self.log_operation("search", "info", f"Поиск книг по запросу: {query}")

        # Правильная кодировка для кириллицы
        from urllib.parse import quote
        encoded_query = quote(query.encode('utf-8'))

        search_url = f"{self.base_url}/search?phrase={encoded_query}"
        await self.log_operation("search", "info", f"Формируем URL: {search_url}")

        html_content = await self._make_request(search_url)

        if not html_content:
            await self.log_operation("search", "error", "Не удалось получить страницу поиска")
            return []

        try:
            soup = BeautifulSoup(html_content, 'lxml')
            books = self._parse_search_results(soup, fetch_details=fetch_details)

            await self.log_operation("search", "success", f"Найдено книг: {len(books)}", len(books))
            return books

        except Exception as e:
            await self.log_operation("search", "error", f"Ошибка парсинга: {e}")
            return []
    
    async def get_book_details(self, url: str) -> Optional[Book]:
        """Получение детальной информации о книге"""
        
        await self.log_operation("details", "info", f"Получение деталей книги: {url}")
        
        html_content = await self._make_request(url)
        if not html_content:
            await self.log_operation("details", "error", "Не удалось получить страницу книги")
            return None
        
        try:
            soup = BeautifulSoup(html_content, 'lxml')
            book_data = self._parse_book_details(soup, url)
            
            if book_data:
                # Добавляем время парсинга
                book_data["parsed_at"] = datetime.now()
                
                # Создаем объект Book
                book = Book(**book_data)
                await self.log_operation("details", "success", f"Получены детали книги: {book.title}")
            else:
                await self.log_operation("details", "error", "Не удалось извлечь данные книги")
                book = None
            
            return book
            
        except Exception as e:
            await self.log_operation("details", "error", f"Ошибка парсинга: {e}")
            return None
        
    async def check_discounts(self) -> List[Book]:
        """Сканирование акционных предложений"""
        
        await self.log_operation("discounts", "info", "Сканирование акционных предложений")
        
        # Стратегия: Поиск книг с высокими скидками через популярные запросы
        all_discount_books = []
        
        # Популярные категории и запросы
        popular_queries = ["книги", "программирование", "python", "javascript", "java", "математика", "бизнес", "психология"]
        
        for query in popular_queries:
            try:
                await self._random_delay()
                books = await self.search_books(query)
                
                # Фильтруем только книги со скидками 15% и больше
                discount_books = [book for book in books if book.discount_percent and book.discount_percent >= 15]
                all_discount_books.extend(discount_books)
                
            except Exception as e:
                await self.log_operation("discounts", "warning", f"Ошибка при поиске '{query}': {e}")
        
        # Дополнительный поиск специально скидочных товаров
        try:
            await self._random_delay()
            # Ищем книги с ключевыми словами скидок
            discount_keywords = ["-50%", "-30%", "-25%", "распродажа"]
            for keyword in discount_keywords:
                books = await self.search_books(keyword)
                all_discount_books.extend(books)
                
        except Exception as e:
            await self.log_operation("discounts", "warning", f"Ошибка при поиске ключевых слов скидок: {e}")
        
        # Удаляем дубликаты по source_id и сортируем по размеру скидки
        unique_books = []
        seen_ids = set()
        for book in all_discount_books:
            if book.source_id not in seen_ids:
                unique_books.append(book)
                seen_ids.add(book.source_id)
        
        # Сортируем по убыванию скидки
        unique_books.sort(key=lambda x: x.discount_percent or 0, reverse=True)
        
        await self.log_operation("discounts", "success", f"Найдено акционных книг: {len(unique_books)}", len(unique_books))
        return unique_books
    
    def _parse_search_results(self, soup: BeautifulSoup, fetch_details: bool = False) -> List[Book]:
        """Парсинг результатов поиска

        Args:
            soup: BeautifulSoup объект с HTML страницы
            fetch_details: Загружать ли детальную страницу для каждой книги (для извлечения характеристик)
        """
        books = []
        
        # Ищем все ссылки на продукты с разными паттернами
        product_links = soup.find_all('a', href=re.compile(r'/product/'))
        
        # Если не нашли ссылки, попробуем найти их по другим признакам
        if not product_links:
            # Ищем по alt тексту изображений
            img_links = soup.find_all('img', alt=True)
            for img in img_links:
                parent_link = img.find_parent('a', href=re.compile(r'/product/'))
                if parent_link:
                    product_links.append(parent_link)
        
        # Удаляем дубликаты
        unique_links = []
        seen_urls = set()
        for link in product_links:
            href = link.get('href', '')
            if href not in seen_urls:
                unique_links.append(link)
                seen_urls.add(href)
        
        for link in unique_links:
            try:
                book_data = self._extract_book_data_from_link(link, fetch_details=fetch_details)
                if book_data and self.validate_book_data(book_data):
                    book_data["parsed_at"] = datetime.now()
                    book = Book(**book_data)
                    books.append(book)
                    
            except Exception as e:
                self.logger.warning(f"Ошибка при извлечении данных книги: {e}")
                continue
        
        return books
    
    def _extract_book_data_from_link(self, link, fetch_details: bool = False) -> Optional[dict]:
        """Извлечение данных книги из ссылки на продукт

        Args:
            link: HTML элемент ссылки на книгу
            fetch_details: Загружать ли детальную страницу для извлечения характеристик (издательство, переплёт, жанры)
        """
        try:
            book_data = {
                "source": "chitai-gorod",
                "genres": []
            }
            
            # Извлекаем ссылку на книгу
            product_url = urljoin(self.base_url, link.get('href', ''))
            book_data["url"] = product_url
            
            # Извлекаем ID книги из URL
            url_match = re.search(r'/product/[^/]+-(\d+)', product_url)
            if url_match:
                book_data["source_id"] = url_match.group(1)
            else:
                return None
            
            # Извлекаем название и автора из title ссылки
            title_text = link.get('title', '')
            if not title_text:
                return None
            
            # Парсим название и автора из формата "Название (Автор)"
            if " (" in title_text and ")" in title_text:
                parts = title_text.split(" (", 1)
                book_data["title"] = parts[0].strip()
                if len(parts) > 1:
                    book_data["author"] = parts[1].replace(")", "").strip()
                else:
                    book_data["author"] = None
            else:
                book_data["title"] = title_text
                book_data["author"] = None
        
            # 🔥 ФИЛЬТРАЦИЯ КОНТЕНТА: Проверяем, что это не детская книга или концтовар
            if self._is_excluded_content(book_data["title"], book_data.get("author")):
                self.logger.debug(f"Книга '{book_data.get('title')}' исключена - неподходящий контент (детская/развивающая)")
                return None
            
            # 🔥 УЛУЧШЕННЫЙ ПОИСК ИЗОБРАЖЕНИЙ: Извлекаем изображение из img внутри ссылки
            img_elem = link.find('img')
            if img_elem:
                img_src = img_elem.get('src') or img_elem.get('data-src')
                if img_src:
                    cleaned_img_url = self._clean_image_url(img_src)
                    if cleaned_img_url:
                        book_data["image_url"] = cleaned_img_url
                    else:
                        # Если изображение невалидное, не сохраняем его
                        pass
            
            # Ищем цены и скидки в более широком контексте
            # Начинаем с родителя ссылки и идем вверх по дереву
            search_element = link
            price_text = ""
            
            for _ in range(3):  # Проверяем до 3 уровней вверх
                if search_element:
                    try:
                        current_text = search_element.get_text()
                        if len(current_text) > len(price_text):
                            price_text = current_text
                        search_element = search_element.parent
                    except:
                        break
                else:
                    break
        
            # Если ничего не нашли, используем текст самой ссылки
            if not price_text:
                price_text = link.get_text()
            
            # Извлекаем цены
            price_matches = re.findall(r'(\d+(?:\s\xa0?\d+)*)\s*₽', price_text)
            if price_matches:
                # Последняя цена - это текущая цена
                current_price_str = price_matches[-1].replace(' ', '').replace('\xa0', '')
                try:
                    book_data["current_price"] = float(current_price_str)
                except ValueError:
                    return None
                
                # Если есть еще одна цена - это может быть старая цена
                if len(price_matches) >= 2:
                    old_price_str = price_matches[-2].replace(' ', '').replace('\xa0', '')
                    try:
                        book_data["original_price"] = float(old_price_str)
                    except ValueError:
                        pass
            
            # Извлекаем скидку
            discount_match = re.search(r'(-?\d+)%', price_text)
            if discount_match:
                book_data["discount_percent"] = int(discount_match.group(1))
            
            # Проверяем, что это реальная книга, а не другой товар
            if not self._is_real_book(book_data):
                self.logger.debug(f"Книга '{book_data.get('title')}' исключена - не является реальной книгой")
                return None
            
            # 🔥 ФИЛЬТРАЦИЯ: не сохраняем книги без валидных изображений
            if not book_data.get("image_url"):
                self.logger.debug(f"Книга '{book_data.get('title')}' исключена - нет валидного изображения")
                return None
        
            # 🔥 НОВОЕ: Загружаем детальную страницу для извлечения характеристик
            if fetch_details:
                try:
                    details_data = self._fetch_book_details(product_url)
                    if details_data:
                        # Обновляем базовые данные деталими
                        book_data.update({
                            "publisher": details_data.get("publisher"),
                            "binding": details_data.get("binding"),
                            "isbn": details_data.get("isbn"),
                            "genres": details_data.get("genres", [])
                        })
                        self.logger.info(f"[chitai-gorod] Извлечены характеристики для книги '{book_data.get('title')}': publisher={details_data.get('publisher')}, binding={details_data.get('binding')}, genres={details_data.get('genres')}")
                except Exception as e:
                    self.logger.warning(f"Ошибка при загрузке деталей книги '{book_data.get('title')}': {e}")

            return book_data if book_data.get("title") and book_data.get("current_price") else None
            
        except Exception as e:
            self.logger.warning(f"Ошибка при извлечении данных книги: {e}")
            return None
        
    def _fetch_book_details(self, url: str) -> Optional[dict]:
        """Загрузка и парсинг детальной страницы книги для извлечения характеристик

        Args:
            url: URL детальной страницы книги

        Returns:
            Словарь с характеристиками книги (publisher, binding, isbn, genres)
        """
        try:
            # Загружаем HTML страницы (синхронно)
            html = self._make_request_sync(url)
            if not html:
                return None
        
            # Парсим HTML
            soup = BeautifulSoup(html, 'lxml')

            # Извлекаем текст страницы для поиска ISBN
            price_text = soup.get_text()

            # Извлекаем характеристики
            characteristics = self._extract_book_characteristics(soup, price_text)

            return characteristics

        except Exception as e:
            self.logger.warning(f"Ошибка при загрузке деталей книги по URL {url}: {e}")
            return None
        
    def _make_request_sync(self, url: str) -> Optional[str]:
        """Синхронный HTTP запрос для использования в синхронном контексте

        Args:
            url: URL для запроса

        Returns:
            HTML страница или None
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }

            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                return response.text
            else:
                self.logger.warning(f"HTTP {response.status_code} for {url}")
                return None

        except Exception as e:
            self.logger.warning(f"Request error for {url}: {e}")
            return None
        
    def _clean_image_url(self, img_src: str) -> Optional[str]:
        """Очистка URL изображения от fallback изображений"""
        if not img_src:
            return None
        
        # Нормализуем URL
        full_url = urljoin(self.base_url, img_src)
        
        # Список fallback изображений, которые нужно исключить
        fallback_patterns = [
            'fallback-cover.webp',
            '_static/fallback-cover.webp',
            '/_static/fallback-cover.webp',
            'placeholder',
            'no-image',
            'default-cover',
            'no-cover'
        ]
        
        # Проверяем на наличие fallback паттернов
        for pattern in fallback_patterns:
            if pattern.lower() in full_url.lower():
                self.logger.debug(f"Отфильтровано fallback изображение: {full_url}")
                return None
        
        # Проверяем, что URL содержит реальные изображения продуктов
        valid_patterns = [
            'product',
            'cover',
            'img-gorod',
            'pim/products',
            'cdn',
            'media',
            'images',
            'content.img-gorod.ru',
            'chitai-gorod.ru/product'
        ]
        
        # Если URL не содержит ни одного валидного паттерна, это может быть fallback
        has_valid_pattern = any(pattern in full_url.lower() for pattern in valid_patterns)
        
        # Дополнительная проверка: если URL содержит параметры размеров (например, от content.img-gorod.ru)
        if '?' in full_url and ('width=' in full_url or 'height=' in full_url):
            # Это может быть валидный URL с параметрами размеров
            if has_valid_pattern or 'content.img-gorod.ru' in full_url:
                self.logger.debug(f"Принято изображение с параметрами: {full_url}")
                return full_url
        
        elif not has_valid_pattern:
            self.logger.debug(f"Отфильтровано невалидное изображение: {full_url}")
            return None
        
        self.logger.debug(f"Принято изображение: {full_url}")
        return full_url
    
    def _is_excluded_content(self, title: str, author: str = None) -> bool:
        """Проверка, является ли контент исключаемым (детские книги, концтовары и т.д.)"""
        
        # Объединяем заголовок и автора для анализа
        text_to_check = f"{title} {author or ''}".lower()
        
        # Исключаемые категории для взрослых
        excluded_keywords = [
            # Детские товары
            'для детей', 'детская', 'детские', 'дошкольник', 'дошкольная', 'дошкольное',
            'малыш', 'малыша', 'ребенок', 'детский', 'детского', 'детского', 'детских',
            'книжка-картинка', 'книжка с картинками', 'раскраска', 'раскраски',
            'прописи', 'пропись', 'азбука', 'букварь', 'слог', 'слоги',
            'детская литература', 'детская книга', 'детская литература',
            
            # Игры и игрушки
            'игра', 'игры', 'игрушка', 'игрушки', 'пазл', 'пазлы', 'конструктор',
            'кубики', 'мягкая игрушка', 'плюшевый', 'плюшевая', 'плюшевое',
            'настольная игра', 'настольные игры', 'детская игра', 'детские игры',
            
            # Канцелярские товары
            'тетрадь', 'тетради', 'планнер', 'планнеры', 'ежедневник', 'ежедневники',
            'блокнот', 'блокноты', 'записная книжка', 'записные книжки',
            'канцтовары', 'канцелярские товары', 'офисные товары',
            
            # Товары для младенцев
            'младенец', 'младенца', 'младенческий', 'для младенцев',
            'детская кроватка', 'детская мебель', 'детский стул',
            
            # Развивающие материалы для детей
            'развивающая', 'развивающие', 'для развития', 'обучающая', 'обучающие',
            'развивающая игра', 'развивающие игры', 'обучающая игра', 'обучающие игры',
            'развивающий', 'развивающего', 'развивающего', 'развивающих'
        ]
        
        # Проверяем на наличие исключаемых ключевых слов
        for keyword in excluded_keywords:
            if keyword in text_to_check:
                return True
        
        # Дополнительные проверки по возрастным группам в скобках
        age_patterns = [
            r'0\+\s*лет', r'1\+\s*лет', r'2\+\s*лет', r'3\+\s*лет', r'4\+\s*лет', r'5\+\s*лет',
            r'6\+\s*лет', r'7\+\s*лет', r'8\+\s*лет', r'9\+\s*лет', r'10\+\s*лет',
            r'0-2\s*лет', r'0-3\s*лет', r'1-3\s*лет', r'2-4\s*лет', r'3-5\s*лет',
            r'4-6\s*лет', r'5-7\s*лет', r'6-8\s*лет', r'7-9\s*лет', r'8-10\s*лет'
        ]
        
        for pattern in age_patterns:
            if re.search(pattern, text_to_check):
                return True
        
        return False
    
    def _extract_book_characteristics(self, soup: BeautifulSoup, price_text: str) -> dict:
        """Извлечение характеристик книги: издательство, переплёт, ISBN, жанры"""
        characteristics = {
            "publisher": None,
            "binding": None,
            "isbn": None,
            "genres": []
        }
        
        # 🔥 НОВЫЕ СЕЛЕКТОРЫ на основе анализа HTML страницы Читай-город

        # 1. Извлекаем издательство из itemprop="publisher"
        publisher_elem = soup.find(attrs={'itemprop': 'publisher'})
        if publisher_elem:
            # Сначала проверяем атрибут content
            characteristics["publisher"] = publisher_elem.get('content')
            # Если content нет, берем текст
            if not characteristics["publisher"]:
                characteristics["publisher"] = publisher_elem.get_text(strip=True)

        # 2. Извлекаем переплёт из itemprop="bookFormat"
        binding_elem = soup.find(attrs={'itemprop': 'bookFormat'})
        if binding_elem:
            # Ищем span внутри
            span = binding_elem.find('span')
            if span:
                characteristics["binding"] = span.get_text(strip=True)
            else:
                characteristics["binding"] = binding_elem.get_text(strip=True)

        # 3. Извлекаем ISBN из itemprop="isbn"
        isbn_elem = soup.find(attrs={'itemprop': 'isbn'})
        if isbn_elem:
            characteristics["isbn"] = isbn_elem.get('content') or isbn_elem.get_text(strip=True)

        # Если ISBN не найден, пробуем поиск по тексту
        if not characteristics["isbn"]:
            isbn_match = re.search(r'ISBN\s+([0-9-]{10,20})', price_text, re.IGNORECASE)
            if isbn_match:
                characteristics["isbn"] = isbn_match.group(1)

        # 4. Извлекаем жанры из breadcrumbs
        # Ищем все элементы с классом breadcrumbs__item--link
        genre_links = soup.find_all(class_='breadcrumbs__item--link')
        # Пропускаем первый элемент (обычно это "Главная")
        for link in genre_links[1:]:  # Пропускаем первый элемент
            span = link.find('span')
            if span:
                genre = span.get_text(strip=True)
                if genre and genre not in ['Главная', 'Книги', 'Каталог']:
                    characteristics["genres"].append(genre)

        # Если жанры не найдены в breadcrumbs, пробуем другие варианты
        if not characteristics["genres"]:
            # Ищем жанры по ссылкам на /genre/
            genre_links = soup.find_all('a', href=lambda x: x and '/genre/' in x if x else False)
            for link in genre_links:
                genre = link.get_text(strip=True)
                if genre and genre not in characteristics["genres"]:
                    characteristics["genres"].append(genre)

        # 🔥 FALLBACK: Если новые селекторы не сработали, используем старые методы
        if not characteristics["publisher"] or not characteristics["binding"]:
            # Ищем в таблице характеристик
            char_table = soup.find('table', class_=re.compile(r'characteristics|char|params|specs'))
            if char_table:
                rows = char_table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        label = cells[0].get_text(strip=True).lower()
                        value = cells[1].get_text(strip=True)

                        # Издательство
                        if not characteristics["publisher"] and any(keyword in label for keyword in ['издательство', 'изд-во', 'publisher']):
                            characteristics["publisher"] = value

                        # Переплёт
                        if not characteristics["binding"] and any(keyword in label for keyword in ['переплёт', 'обложка', 'binding', 'обложка']):
                            characteristics["binding"] = value

            # Ищем в списках характеристик (dl/dt/dd)
            if not characteristics["publisher"] or not characteristics["binding"]:
                char_list = soup.find('dl', class_=re.compile(r'characteristics|char|params|specs'))
                if char_list:
                    dts = char_list.find_all('dt')
                    dds = char_list.find_all('dd')
                    for dt, dd in zip(dts, dds):
                        label = dt.get_text(strip=True).lower()
                        value = dd.get_text(strip=True)

                        # Издательство
                        if not characteristics["publisher"] and any(keyword in label for keyword in ['издательство', 'изд-во', 'publisher']):
                            characteristics["publisher"] = value

                        # Переплёт
                        if not characteristics["binding"] and any(keyword in label for keyword in ['переплёт', 'обложка', 'binding', 'обложка']):
                            characteristics["binding"] = value

        # Нормализуем данные
        if characteristics["publisher"]:
            characteristics["publisher"] = characteristics["publisher"].strip()[:255]

        if characteristics["binding"]:
            # Приводим к стандартным значениям переплёта
            binding = characteristics["binding"].lower().strip()
            if any(k in binding for k in ['мягкий', 'мягк', 'мягкая', 'soft', 'paperback']):
                characteristics["binding"] = "Мягкий"
            elif any(k in binding for k in ['твердый', 'тверд', 'твёрдый', 'твёрд', 'hard', 'hardcover']):
                characteristics["binding"] = "Твердый"
            elif any(k in binding for k in ['супер', 'super']):
                characteristics["binding"] = "Суперобложка"
            elif any(k in binding for k in ['интегральный', 'integral']):
                characteristics["binding"] = "Интегральный"
            else:
                characteristics["binding"] = characteristics["binding"][:100]

        self.logger.info(f"[chitai-gorod] Характеристики: publisher={characteristics['publisher']}, binding={characteristics['binding']}, isbn={characteristics['isbn']}, genres={characteristics['genres']}")

        return characteristics

    def _is_real_book(self, book_data: dict) -> bool:
        """Проверка, что это реальная книга, а не другой товар"""
        
        title = book_data.get("title", "").lower()
        
        # Исключаем явно не книги
        non_book_keywords = [
            'игра', 'игрушка', 'конструктор', 'пазл', 'кубики', 'тетрадь', 'блокнот',
            'планнер', 'ежедневник', 'записная книжка', 'канцтовары', 'офисные товары',
            'детская мебель', 'детский стул', 'кроватка', 'коляска', 'автокресло',
            'одежда', 'обувь', 'игрушка', 'мягкая игрушка', 'плюшевый'
        ]
        
        for keyword in non_book_keywords:
            if keyword in title:
                return False
        
        # Проверяем, что цена разумная для книги (не слишком низкая и не слишком высокая)
        price = book_data.get("current_price", 0)
        if price < 50 or price > 5000:  # Слишком дешево или дорого для книги
            self.logger.debug(f"Книга '{title}' исключена - неподходящая цена: {price}₽")
            return False
        
        return True
        
    def _parse_book_details(self, soup: BeautifulSoup, url: str) -> Optional[dict]:
        """Парсинг детальной информации о книге"""
        
        # Извлекаем ID книги из URL
        url_match = re.search(r'/product/[^/]+-(\d+)', url)
        if not url_match:
            return None
        
        source_id = url_match.group(1)
        
        book_data = {
            "source": "chitai-gorod",
            "source_id": source_id,
            "url": url,
            "genres": []
        }
        
        # Название книги
        title_elem = soup.find('h1') or soup.find('h2', class_=re.compile(r'title|product'))
        if title_elem:
            book_data["title"] = title_elem.get_text(strip=True)
        else:
            # Альтернативный поиск названия
            title_elem = soup.find('title')
            if title_elem:
                title_text = title_elem.get_text(strip=True)
                # Убираем "Купить" и другие служебные слова
                title_text = re.sub(r'^Купить\s+', '', title_text, flags=re.IGNORECASE)
                title_text = re.sub(r'\s+в\s+Читай-городе.*$', '', title_text, flags=re.IGNORECASE)
                book_data["title"] = title_text
        
        # Автор
        author_elem = soup.find('a', href=re.compile(r'/author/')) or \
                     soup.find('span', class_=re.compile(r'author'))
        if author_elem:
            book_data["author"] = author_elem.get_text(strip=True)
        
        # 🔥 ФИЛЬТРАЦИЯ КОНТЕНТА: Проверяем, что это не детская книга или концтовар
        if self._is_excluded_content(book_data["title"], book_data.get("author")):
            self.logger.debug(f"Книга '{book_data.get('title')}' исключена - неподходящий контент (детская/развивающая)")
            return None
        
        # Цены
        price_text = soup.get_text()
        price_matches = re.findall(r'(\d+(?:\s\xa0?\d+)*)\s*₽', price_text)
        if price_matches:
            book_data["current_price"] = float(price_matches[0].replace(' ', '').replace('\xa0', ''))
            
            # Если есть вторая цена, это может быть оригинальная
            if len(price_matches) > 1:
                book_data["original_price"] = float(price_matches[1].replace(' ', '').replace('\xa0', ''))
        
        # Скидка
        discount_match = re.search(r'(-?\d+)%', price_text)
        if discount_match:
            book_data["discount_percent"] = int(discount_match.group(1))
        
        # 🔥 УЛУЧШЕННЫЙ ПОИСК ИЗОБРАЖЕНИЙ: Ищем изображение в нескольких местах
        img_src = None
        
        # 1. Ищем в основных контейнерах изображений
        img_selectors = [
            'img.product-cover',
            'img[alt*="обложка"]',
            'img[alt*="книга"]',
            '.product-image img',
            '.book-cover img',
            '.cover img'
        ]
        
        for selector in img_selectors:
            img_elem = soup.select_one(selector)
            if img_elem:
                img_src = img_elem.get('src') or img_elem.get('data-src')
                if img_src:
                    break
        
        # 2. Если не нашли, ищем любые img элементы с подходящими атрибутами
        if not img_src:
            img_elems = soup.find_all('img')
            for img in img_elems:
                src = img.get('src') or img.get('data-src')
                alt = img.get('alt', '').lower()
                
                # Ищем изображения обложек
                if src and ('cover' in alt or 'обложк' in alt or 'книга' in alt):
                    img_src = src
                    break
        
        # 3. Если все еще не нашли, ищем первое подходящее изображение
        if not img_src:
            img_elems = soup.find_all('img')
            for img in img_elems:
                src = img.get('src') or img.get('data-src')
                if src and not src.endswith('fallback-cover.webp') and 'product' in src:
                    img_src = src
                    break
        
        # Очищаем и сохраняем URL изображения
        if img_src:
            cleaned_img_url = self._clean_image_url(img_src)
            if cleaned_img_url:
                book_data["image_url"] = cleaned_img_url
            else:
                # Если изображение невалидное, не сохраняем его
                pass
        
        # Описание и характеристики
        description_elem = soup.find('div', class_=re.compile(r'description|annotation|about'))
        if description_elem:
            description = description_elem.get_text(strip=True)
            if description:
                book_data["description"] = description
        
        # ISBN
        isbn_match = re.search(r'ISBN[:\s]*([\d\-X]+)', price_text, re.IGNORECASE)
        if isbn_match:
            book_data["isbn"] = isbn_match.group(1)
        
        # Жанры
        genre_links = soup.find_all('a', href=re.compile(r'/genre/|/category/'))
        if genre_links:
            book_data["genres"] = [link.get_text(strip=True) for link in genre_links[:5]]
        
        # Извлечение издательства и переплёта из характеристик
        # Ищем характеристики книги в различных форматах
        characteristics = self._extract_book_characteristics(soup, price_text)
        book_data.update(characteristics)
        
        # Проверяем, что это реальная книга
        if not self._is_real_book(book_data):
            self.logger.debug(f"Книга '{book_data.get('title')}' исключена - не является реальной книгой")
            return None
        
        # 🔥 ФИЛЬТРАЦИЯ: не сохраняем книги без валидных изображений
        if not book_data.get("image_url"):
            self.logger.debug(f"Книга '{book_data.get('title')}' исключена - нет валидного изображения")
            return None
        
        return book_data if book_data.get("title") and book_data.get("current_price") else None
