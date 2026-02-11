import os
import json
from datetime import datetime
from typing import List, Optional
from services.logger import parser_logger

# Импорты Google API (с обработкой ошибок)
try:
    from googleapiclient.discovery import build
    from google.oauth2.service_account import Credentials
    from googleapiclient.errors import HttpError
    GOOGLE_SHEETS_AVAILABLE = True
except ImportError:
    GOOGLE_SHEETS_AVAILABLE = False
    parser_logger.warning("Google Sheets API недоступно - используется заглушка")

class SheetManager:
    """Менеджер для работы с Google Sheets"""
    
    def __init__(self):
        self.service = None
        self.spreadsheet_id = None
        self.worksheet_id = None
        self._initialize()
    
    def _initialize(self):
        """Инициализация подключения к Google Sheets"""
        if not GOOGLE_SHEETS_AVAILABLE:
            parser_logger.warning("Google Sheets API недоступен - используется заглушка")
            return
        
        try:
            # Получаем путь к файлу credentials
            credentials_path = os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH", "credentials.json")
            self.spreadsheet_id = os.getenv("GOOGLE_SHEET_ID")
            
            # Диагностика конфигурации
            if not credentials_path:
                parser_logger.error("Переменная GOOGLE_SHEETS_CREDENTIALS_PATH не настроена")
                return
            
            if not os.path.exists(credentials_path):
                parser_logger.error(f"Файл credentials не найден: {credentials_path}")
                # Попробуем найти файл в текущей директории
                local_creds = "./credentials.json"
                if os.path.exists(local_creds):
                    credentials_path = local_creds
                    parser_logger.info(f"Найден файл credentials в текущей директории: {local_creds}")
                else:
                    return
            
            if not self.spreadsheet_id:
                parser_logger.error("Переменная GOOGLE_SHEET_ID не настроена")
                return
            
            # Настройка авторизации
            scope = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            
            credentials = Credentials.from_service_account_file(credentials_path, scopes=scope)
            self.service = build('sheets', 'v4', credentials=credentials)
            
            # Проверяем доступ к таблице и получаем/создаем лист
            self._setup_worksheet()
            
            parser_logger.info("Google Sheets инициализирован успешно")
            
        except Exception as e:
            parser_logger.error(f"Ошибка инициализации Google Sheets: {e}")
            self.service = None
            self.spreadsheet_id = None
            self.worksheet_id = None
    
    def _setup_worksheet(self):
        """Настройка рабочего листа"""
        try:
            # Получаем информацию о таблице
            spreadsheet = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            
            # Ищем лист "Скидки на книги"
            worksheet_id = None
            for sheet in spreadsheet['sheets']:
                if sheet['properties']['title'] == 'Скидки на книги':
                    worksheet_id = sheet['properties']['sheetId']
                    break
            
            # Если лист не найден, создаем его
            if not worksheet_id:
                body = {
                    'requests': [{
                        'addSheet': {
                            'properties': {
                                'title': 'Скидки на книги',
                                'gridProperties': {
                                    'rowCount': 1000,
                                    'columnCount': 9
                                }
                            }
                        }
                    }]
                }
                
                result = self.service.spreadsheets().batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body=body
                ).execute()
                
                worksheet_id = result['replies'][0]['addSheet']['properties']['sheetId']
                
                # Добавляем заголовки
                headers = [
                    ["Время", "Магазин", "Название", "Автор", 
                     "Текущая цена", "Старая цена", "Скидка %", 
                     "Ссылка", "Обложка"]
                ]
                
                body = {
                    'values': headers
                }
                
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range='Скидки на книги!A1:I1',
                    valueInputOption='RAW',
                    body=body
                ).execute()
                
                # Форматируем заголовки
                requests = [{
                    'repeatCell': {
                        'range': {
                            'sheetId': worksheet_id,
                            'startRowIndex': 0,
                            'endRowIndex': 1,
                            'startColumnIndex': 0,
                            'endColumnIndex': 9
                        },
                        'cell': {
                            'userEnteredFormat': {
                                'textFormat': {'bold': True},
                                'backgroundColor': {
                                    'red': 0.9,
                                    'green': 0.9,
                                    'blue': 0.9
                                }
                            }
                        },
                        'fields': 'userEnteredFormat(textFormat,backgroundColor)'
                    }
                }]
                
                body = {'requests': requests}
                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body=body
                ).execute()
            
            self.worksheet_id = worksheet_id
            
        except HttpError as e:
            parser_logger.error(f"Ошибка настройки листа: {e}")
            raise
    
    async def add_book_row(self, book) -> bool:
        """Добавление строки с книгой в таблицу"""
        try:
            if not self.service or not self.spreadsheet_id:
                parser_logger.warning("Google Sheets не инициализирован - пропускаем")
                return False
            
            # Форматируем данные
            row_data = [
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                book.source,
                book.title,
                book.author or "",
                f"{book.current_price}₽",
                f"{book.original_price}₽" if book.original_price else "",
                f"{book.discount_percent}%" if book.discount_percent else "",
                book.url,
                f'=IMAGE("{book.image_url}")' if book.image_url else ""
            ]
            
            # Получаем количество строк для определения следующей позиции
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f'Скидки на книги!A:A'
            ).execute()
            
            next_row = len(result.get('values', [])) + 1
            
            # Добавляем строку
            body = {
                'values': [row_data]
            }
            
            self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f'Скидки на книги!A{next_row}:I{next_row}',
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            
            parser_logger.info(f"Книга добавлена в Google Sheets: {book.title}")
            return True
            
        except HttpError as e:
            parser_logger.error(f"Ошибка добавления книги в Google Sheets: {e}")
            return False
    
    async def get_recent_books(self, limit: int = 50) -> List[dict]:
        """Получение последних добавленных книг"""
        try:
            if not self.service or not self.spreadsheet_id:
                return []
            
            # Получаем данные
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Скидки на книги!A:I'
            ).execute()
            
            values = result.get('values', [])
            
            if not values:
                return []
            
            # Первая строка - заголовки
            headers = values[0]
            data_rows = values[1:]
            
            # Преобразуем в список словарей
            books = []
            for row in data_rows:
                if len(row) >= len(headers):
                    book_dict = dict(zip(headers, row))
                    books.append(book_dict)
            
            # Сортируем по времени (новые сначала)
            sorted_books = sorted(
                books, 
                key=lambda x: x.get('Время', ''), 
                reverse=True
            )
            
            return sorted_books[:limit]
            
        except HttpError as e:
            parser_logger.error(f"Ошибка получения данных из Google Sheets: {e}")
            return []
    
    async def update_book_info(self, book_id: str, updated_data: dict) -> bool:
        """Обновление информации о книге"""
        try:
            if not self.service or not self.spreadsheet_id:
                return False
            
            # Находим строку с книгой по URL в колонке H
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Скидки на книги!A:H'
            ).execute()
            
            values = result.get('values', [])
            if not values:
                return False
            
            headers = values[0]
            data_rows = values[1:]
            
            # Ищем строку с нужным URL
            url_column_index = headers.index('Ссылка') if 'Ссылка' in headers else -1
            if url_column_index == -1:
                parser_logger.error("Колонка 'Ссылка' не найдена")
                return False
            
            row_index = -1
            for i, row in enumerate(data_rows):
                if len(row) > url_column_index and row[url_column_index] == book_id:
                    row_index = i + 2  # +2 потому что первая строка - заголовки, и массив индексируется с 0
                    break
            
            if row_index == -1:
                parser_logger.warning(f"Книга не найдена в таблице: {book_id}")
                return False
            
            # Подготавливаем обновления
            for column, value in updated_data.items():
                column_index = self._get_column_index(column)
                if column_index != -1:
                    # Обновляем одну ячейку
                    range_name = f'Скидки на книги!{chr(64 + column_index)}{row_index}'
                    body = {'values': [[value]]}
                    
                    self.service.spreadsheets().values().update(
                        spreadsheetId=self.spreadsheet_id,
                        range=range_name,
                        valueInputOption='RAW',
                        body=body
                    ).execute()
            
            parser_logger.info(f"Информация о книге обновлена: {book_id}")
            return True
            
        except HttpError as e:
            parser_logger.error(f"Ошибка обновления книги в Google Sheets: {e}")
            return False
    
    def _get_column_index(self, column_name: str) -> Optional[int]:
        """Получение индекса колонки по названию"""
        columns = {
            "Время": 1, "Магазин": 2, "Название": 3, "Автор": 4,
            "Текущая цена": 5, "Старая цена": 6, "Скидка %": 7,
            "Ссылка": 8, "Обложка": 9
        }
        return columns.get(column_name)
    
    def get_diagnostic_info(self) -> dict:
        """Получение диагностической информации"""
        info = {
            "api_available": GOOGLE_SHEETS_AVAILABLE,
            "service_initialized": self.service is not None,
            "spreadsheet_id": self.spreadsheet_id is not None,
            "worksheet_id": self.worksheet_id is not None
        }
        
        if GOOGLE_SHEETS_AVAILABLE:
            credentials_path = os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH", "credentials.json")
            info["credentials_path"] = credentials_path
            info["credentials_exists"] = os.path.exists(credentials_path)
            info["sheet_id"] = self.spreadsheet_id
        
        return info
    
    def get_stats(self) -> dict:
        """Получение статистики по таблице"""
        try:
            if not self.service:
                return {
                    "error": "Google Sheets API не инициализирован", 
                    "total_books": 0, 
                    "active_discounts": 0,
                    "status": "not_initialized",
                    "diagnostic": self.get_diagnostic_info()
                }
            
            if not self.spreadsheet_id:
                return {
                    "error": "ID таблицы не настроен", 
                    "total_books": 0, 
                    "active_discounts": 0,
                    "status": "no_sheet_id",
                    "diagnostic": self.get_diagnostic_info()
                }
            
            # Получаем данные
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Скидки на книги!A:I'
            ).execute()
            
            values = result.get('values', [])
            
            if not values:
                return {
                    "total_books": 0, 
                    "active_discounts": 0,
                    "status": "empty_table",
                    "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            
            # Первая строка - заголовки
            data_rows = values[1:]
            
            total_books = len(data_rows)
            active_discounts = sum(1 for row in data_rows if len(row) > 6 and row[6])  # Колонка "Скидка %"
            
            return {
                "total_books": total_books,
                "active_discounts": active_discounts,
                "status": "success",
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "sheet_title": "Скидки на книги"
            }
            
        except HttpError as e:
            parser_logger.error(f"Ошибка получения статистики: {e}")
            return {
                "error": str(e), 
                "total_books": 0, 
                "active_discounts": 0,
                "status": "api_error",
                "diagnostic": self.get_diagnostic_info()
            }
