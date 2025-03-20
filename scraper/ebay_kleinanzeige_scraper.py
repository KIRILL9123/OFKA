import requests
from bs4 import BeautifulSoup
import json
import csv
import time
import random
import logging
import os
from datetime import datetime
from fake_useragent import UserAgent
from urllib.parse import urljoin

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("ebay_scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class EbayKleinanzeigeScraper:
    def __init__(self, delay_min=2, delay_max=5, max_retries=3, progress_callback=None):
        """
        Инициализация скрапера
        Args:
            delay_min (int): Минимальная задержка между запросами (в секундах)
            delay_max (int): Максимальная задержка между запросами (в секундах)
            max_retries (int): Максимальное количество повторных попыток при ошибке
            progress_callback (function): Функция обратного вызова для отслеживания прогресса
        """
        self.base_url = "https://www.ebay-kleinanzeigen.de"
        self.user_agent = UserAgent()
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.max_retries = max_retries
        self.session = requests.Session()
        self.progress_callback = progress_callback

        # Создаем директорию для сохранения данных
        self.data_dir = "ebay_kleinanzeige_data"
        os.makedirs(self.data_dir, exist_ok=True)

    def _get_random_user_agent(self):
        """Возвращает случайный User-Agent"""
        return self.user_agent.random

    def _random_delay(self):
        """Вводит случайную задержку между запросами"""
        delay = random.uniform(self.delay_min, self.delay_max)
        logger.info(f"Задержка {delay:.2f} секунд")
        time.sleep(delay)

    def _make_request(self, url, params=None):
        """
        Выполняет HTTP запрос с ротацией User-Agent и обработкой ошибок
        Args:
            url (str): URL для запроса
            params (dict, optional): Параметры запроса
        Returns:
            BeautifulSoup: Объект BeautifulSoup или None в случае ошибки
        """
        headers = {
            "User-Agent": self._get_random_user_agent(),
            "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Referer": self.base_url,
            "DNT": "1",
        }

        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url, headers=headers, params=params, timeout=10)
                if response.status_code == 200:
                    return BeautifulSoup(response.text, 'html.parser')
                elif response.status_code == 403:
                    logger.error(f"Доступ запрещен (код 403). Возможно, сайт обнаружил скрапинг.")
                    # Увеличиваем задержку при обнаружении блокировки
                    time.sleep(self.delay_max * 2)
                else:
                    logger.error(f"Ошибка HTTP: {response.status_code}")
            except requests.exceptions.RequestException as e:
                logger.error(f"Ошибка запроса: {str(e)}")

            logger.warning(f"Повторная попытка {attempt+1}/{self.max_retries}")
            time.sleep(self.delay_max * (attempt + 1))

        return None

    def search_by_category(self, category, location="", max_pages=5):
        """
        Поиск объявлений по категории
        Args:
            category (str): Категория для поиска
                Примеры: "elektronik", "computer", "handy", "auto", "immobilien"
            location (str, optional): Местоположение для поиска
            max_pages (int): Максимальное количество страниц для скрапинга
        Returns:
            list: Список словарей с данными объявлений
        """
        results = []
        logger.info(f"Начинаем поиск в категории: {category}, локация: {location}")

        for page in range(1, max_pages + 1):
            logger.info(f"Обработка страницы {page}/{max_pages}")

            # Обновляем прогресс, если указан callback
            if self.progress_callback:
                progress = int((page - 1) / max_pages * 100)
                self.progress_callback(progress)

            url = f"{self.base_url}/s-{category}/seite:{page}"
            params = {"locationStr": location} if location else None

            soup = self._make_request(url, params)
            if not soup:
                logger.error(f"Не удалось получить страницу {page}")
                continue

            # Находим все объявления на странице
            ad_elements = soup.select("article.aditem")
            if not ad_elements:
                logger.warning("Объявления не найдены на странице. Возможно изменилась структура сайта.")
                break

            for ad in ad_elements:
                try:
                    # Извлекаем URL объявления
                    ad_url_elem = ad.select_one("a.ellipsis")
                    if not ad_url_elem:
                        continue

                    ad_url = urljoin(self.base_url, ad_url_elem.get("href"))

                    # Получаем данные объявления
                    ad_data = self._scrape_ad_details(ad_url)
                    if ad_data:
                        results.append(ad_data)
                except Exception as e:
                    logger.error(f"Ошибка при обработке объявления: {str(e)}")

            # Задержка перед следующей страницей
            self._random_delay()

            # Проверка на наличие следующей страницы
            next_button = soup.select_one("a.pagination-next")
            if not next_button:
                logger.info("Достигнут конец списка объявлений")
                break

        # Обновляем прогресс до 100%
        if self.progress_callback:
            self.progress_callback(100)

        logger.info(f"Найдено {len(results)} объявлений")
        return results

    def _scrape_ad_details(self, ad_url):
        """
        Извлекает детальную информацию об объявлении
        Args:
            ad_url (str): URL объявления
        Returns:
            dict: Словарь с данными объявления
        """
        logger.info(f"Извлечение информации из: {ad_url}")

        soup = self._make_request(ad_url)
        if not soup:
            return None

        try:
            # Извлечение информации
            title = soup.select_one("h1#viewad-title")
            title = title.text.strip() if title else "Название не найдено"

            price_elem = soup.select_one("h2.boxedarticle--price")
            price = price_elem.text.strip() if price_elem else "Цена не указана"

            description_elem = soup.select_one("div#viewad-description-text")
            description = description_elem.text.strip() if description_elem else "Описание отсутствует"

            location_elem = soup.select_one("span#viewad-locality")
            location = location_elem.text.strip() if location_elem else "Местоположение не указано"

            date_elem = soup.select_one("div#viewad-extra-info")
            date_str = date_elem.text.strip() if date_elem else ""

            # Извлекаем дату публикации из строки
            date_published = ""
            if date_str:
                import re
                date_match = re.search(r'\d{2}\.\d{2}\.\d{4}', date_str)
                if date_match:
                    date_published = date_match.group(0)

            # Извлекаем URL всех изображений
            image_urls = []
            gallery = soup.select("div#viewad-image-box img")
            for img in gallery:
                img_url = img.get("src")
                if img_url:
                    # Заменяем миниатюры на полноразмерные изображения
                    img_url = img_url.replace("_35.", "_57.")
                    img_url = img_url.replace("_72.", "_57.")
                    image_urls.append(img_url)

            # Формируем результат
            ad_data = {
                "title": title,
                "price": price,
                "description": description,
                "location": location,
                "date_published": date_published,
                "image_urls": image_urls,
                "url": ad_url,
                "scrape_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            return ad_data
        except Exception as e:
            logger.error(f"Ошибка при извлечении данных: {str(e)}")
            return None
        finally:
            # Задержка перед следующим запросом
            self._random_delay()

    def save_to_json(self, data, filename=None, custom_path=None):
        """
        Сохраняет данные в формате JSON
        Args:
            data (list): Список данных для сохранения
            filename (str, optional): Имя файла (без расширения)
            custom_path (str, optional): Пользовательский путь для сохранения
        Returns:
            str: Путь к сохраненному файлу
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ebay_kleinanzeige_{timestamp}"

        # Определяем путь сохранения
        save_dir = custom_path if custom_path else self.data_dir
        os.makedirs(save_dir, exist_ok=True)

        file_path = os.path.join(save_dir, f"{filename}.json")

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

            logger.info(f"Данные сохранены в JSON: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Ошибка при сохранении JSON: {str(e)}")
            return None

    def save_to_csv(self, data, filename=None, custom_path=None):
        """
        Сохраняет данные в формате CSV
        Args:
            data (list): Список данных для сохранения
            filename (str, optional): Имя файла (без расширения)
            custom_path (str, optional): Пользовательский путь для сохранения
        Returns:
            str: Путь к сохраненному файлу
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ebay_kleinanzeige_{timestamp}"

        # Определяем путь сохранения
        save_dir = custom_path if custom_path else self.data_dir
        os.makedirs(save_dir, exist_ok=True)

        file_path = os.path.join(save_dir, f"{filename}.csv")

        try:
            if not data:
                logger.warning("Нет данных для сохранения в CSV")
                return None

            # Определяем заголовки по ключам первого объявления
            fieldnames = list(data[0].keys())

            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for item in data:
                    # Преобразуем список URL изображений в строку для CSV
                    if "image_urls" in item and isinstance(item["image_urls"], list):
                        item["image_urls"] = "|".join(item["image_urls"])

                    writer.writerow(item)

            logger.info(f"Данные сохранены в CSV: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Ошибка при сохранении CSV: {str(e)}")
            return None

# Пример использования при запуске файла как основного
if __name__ == "__main__":
    # Создаем экземпляр скрапера
    scraper = EbayKleinanzeigeScraper(delay_min=3, delay_max=8)

    # Список категорий для скрапинга
    categories = ["elektronik", "computer", "handy", "fahrrad"]

    for category in categories:
        try:
            # Скрапим данные по категории (макс. 3 страницы)
            results = scraper.search_by_category(
                category=category,
                location="Berlin", # Можно указать нужный город
                max_pages=3
            )

            if results:
                # Сохраняем результаты в JSON и CSV
                file_prefix = f"{category}_{datetime.now().strftime('%Y%m%d')}"
                scraper.save_to_json(results, filename=file_prefix)
                scraper.save_to_csv(results, filename=file_prefix)
        except Exception as e:
            logger.error(f"Ошибка при скрапинге категории {category}: {str(e)}")
