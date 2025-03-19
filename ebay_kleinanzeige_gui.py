import sys
import os
import json
from datetime import datetime
import time
import qdarktheme
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QComboBox, QLabel, 
                            QLineEdit, QSpinBox, QTabWidget, QTextEdit, 
                            QTableWidget, QTableWidgetItem, QHeaderView, 
                            QCheckBox, QFileDialog, QMessageBox, QProgressBar,
                            QMenu, QMenuBar, QStatusBar, QToolBar, QSplitter)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSettings
from PyQt6.QtGui import QAction, QIcon, QPixmap, QFont, QColor

# Импортируем наш скрапер
from ebay_kleinanzeige_scraper import EbayKleinanzeigeScraper

class ScraperApp(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Настройки приложения
        self.settings = QSettings("EbayKleinanzeigeScraperApp", "Settings")
        self.dark_mode = self.settings.value("dark_mode", True, type=bool)
        
        # Применяем тему
        self.apply_theme()
        
        # Основные параметры окна
        self.setWindowTitle("eBay Kleinanzeige Scraper")
        self.setMinimumSize(1200, 800)
        
        # Инициализация UI
        self.init_ui()
        
        # Загружаем сохраненные настройки
        self.load_settings()
    
    def apply_theme(self):
        """Применяет темную или светлую тему"""
        if self.dark_mode:
            qdarktheme.setup_theme("dark", corner_shape="rounded")
            # Настраиваем цвета в стиле Airbnb для темной темы
            self.primary_color = "#FF5A5F"  # Основной цвет Airbnb
            self.secondary_color = "#00A699"  # Дополнительный цвет Airbnb
            self.text_color = "#FFFFFF"
            self.bg_color = "#222222"
        else:
            qdarktheme.setup_theme("light", corner_shape="rounded")
            # Настраиваем цвета в стиле Airbnb для светлой темы
            self.primary_color = "#FF5A5F"  # Основной цвет Airbnb
            self.secondary_color = "#00A699"  # Дополнительный цвет Airbnb
            self.text_color = "#484848"
            self.bg_color = "#FFFFFF"
    
    def init_ui(self):
        """Инициализация пользовательского интерфейса"""
        # Создаем меню
        self.create_menu()
        
        # Создаем панель инструментов
        self.create_toolbar()
        
        # Создаем строку состояния
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Готов к сбору данных")
        
        # Основной виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Основной макет
        main_layout = QVBoxLayout(central_widget)
        
        # Вкладки для разных разделов приложения
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabBar::tab:selected {{
                background-color: {self.primary_color};
                color: white;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                padding: 8px 12px;
                margin-right: 2px;
            }}
            QTabBar::tab:!selected {{
                background-color: {self.bg_color};
                padding: 8px 12px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }}
        """)
        
        # Создаем вкладки
        self.create_search_tab()
        self.create_results_tab()
        self.create_settings_tab()
        
        main_layout.addWidget(self.tabs)
        
        # Прогресс-бар для отображения прогресса скрапинга
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid #ccc;
                border-radius: 5px;
                text-align: center;
                height: 20px;
            }}
            QProgressBar::chunk {{
                background-color: {self.primary_color};
                border-radius: 5px;
            }}
        """)
        main_layout.addWidget(self.progress_bar)
    
    def create_menu(self):
        """Создание меню приложения"""
        menubar = self.menuBar()
        
        # Меню Файл
        file_menu = menubar.addMenu("Файл")
        
        export_action = QAction("Экспорт данных", self)
        export_action.triggered.connect(self.export_data)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Выход", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Меню Вид
        view_menu = menubar.addMenu("Вид")
        
        theme_action = QAction("Переключить тему", self)
        theme_action.triggered.connect(self.toggle_theme)
        view_menu.addAction(theme_action)
        
        # Меню Справка
        help_menu = menubar.addMenu("Справка")
        
        about_action = QAction("О программе", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def create_toolbar(self):
        """Создание панели инструментов"""
        toolbar = QToolBar("Панель инструментов")
        toolbar.setMovable(False)
        toolbar.setIconSize(Qt.QSize(24, 24))
        self.addToolBar(toolbar)
        
        start_action = QAction("Начать скрапинг", self)
        start_action.triggered.connect(self.start_scraping)
        toolbar.addAction(start_action)
        
        toolbar.addSeparator()
        
        stop_action = QAction("Остановить", self)
        stop_action.triggered.connect(self.stop_scraping)
        toolbar.addAction(stop_action)
        
        toolbar.addSeparator()
        
        save_action = QAction("Сохранить результаты", self)
        save_action.triggered.connect(self.save_results)
        toolbar.addAction(save_action)
    
    def create_search_tab(self):
        """Создание вкладки для настройки поиска"""
        search_tab = QWidget()
        layout = QVBoxLayout(search_tab)
        
        # Заголовок в стиле Airbnb
        header_label = QLabel("Поиск объявлений")
        header_label.setStyleSheet(f"""
            font-size: 28px;
            font-weight: bold;
            color: {self.primary_color};
            margin-bottom: 20px;
        """)
        layout.addWidget(header_label)
        
        # Описание
        description = QLabel("Введите параметры поиска для сбора данных с eBay Kleinanzeige")
        description.setStyleSheet(f"font-size: 16px; margin-bottom: 30px; color: {self.text_color};")
        layout.addWidget(description)
        
        # Форма параметров поиска
        form_layout = QVBoxLayout()
        
        # Категории
        category_layout = QHBoxLayout()
        category_label = QLabel("Категория:")
        category_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        self.category_combo = QComboBox()
        self.category_combo.addItems([
            "elektronik", "computer", "handy", "auto", 
            "fahrrad", "immobilien", "wohnung", "haus",
            "mode", "kleidung", "möbel", "garten"
        ])
        self.category_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #ccc;
                border-radius: 5px;
                padding: 8px;
                font-size: 14px;
            }
            QComboBox::drop-down {
                width: 20px;
            }
        """)
        
        category_layout.addWidget(category_label)
        category_layout.addWidget(self.category_combo)
        form_layout.addLayout(category_layout)
        
        # Местоположение
        location_layout = QHBoxLayout()
        location_label = QLabel("Местоположение:")
        location_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        self.location_input = QLineEdit()
        self.location_input.setPlaceholderText("Например: Berlin")
        self.location_input.setStyleSheet("""
            border: 1px solid #ccc;
            border-radius: 5px;
            padding: 8px;
            font-size: 14px;
        """)
        
        location_layout.addWidget(location_label)
        location_layout.addWidget(self.location_input)
        form_layout.addLayout(location_layout)
        
        # Максимальное количество страниц
        pages_layout = QHBoxLayout()
        pages_label = QLabel("Максимум страниц:")
        pages_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        self.pages_spin = QSpinBox()
        self.pages_spin.setMinimum(1)
        self.pages_spin.setMaximum(20)
        self.pages_spin.setValue(3)
        self.pages_spin.setStyleSheet("""
            border: 1px solid #ccc;
            border-radius: 5px;
            padding: 8px;
            font-size: 14px;
        """)
        
        pages_layout.addWidget(pages_label)
        pages_layout.addWidget(self.pages_spin)
        form_layout.addLayout(pages_layout)
        
        # Задержка между запросами
        delay_layout = QHBoxLayout()
        delay_label = QLabel("Задержка (секунды):")
        delay_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        delay_layout.addWidget(delay_label)
        
        self.delay_min_spin = QSpinBox()
        self.delay_min_spin.setMinimum(2)
        self.delay_min_spin.setMaximum(10)
        self.delay_min_spin.setValue(3)
        self.delay_min_spin.setStyleSheet("""
            border: 1px solid #ccc;
            border-radius: 5px;
            padding: 8px;
            font-size: 14px;
        """)
        
        delay_layout.addWidget(QLabel("от"))
        delay_layout.addWidget(self.delay_min_spin)
        
        self.delay_max_spin = QSpinBox()
        self.delay_max_spin.setMinimum(3)
        self.delay_max_spin.setMaximum(15)
        self.delay_max_spin.setValue(8)
        self.delay_max_spin.setStyleSheet("""
            border: 1px solid #ccc;
            border-radius: 5px;
            padding: 8px;
            font-size: 14px;
        """)
        
        delay_layout.addWidget(QLabel("до"))
        delay_layout.addWidget(self.delay_max_spin)
        
        form_layout.addLayout(delay_layout)
        
        layout.addLayout(form_layout)
        
        # Кнопка запуска скрапинга в стиле Airbnb
        self.start_button = QPushButton("Начать сбор данных")
        self.start_button.setStyleSheet(f"""
            background-color: {self.primary_color};
            color: white;
            border: none;
            border-radius: 5px;
            padding: 12px;
            font-size: 16px;
            font-weight: bold;
        """)
        self.start_button.clicked.connect(self.start_scraping)
        
        layout.addWidget(self.start_button)
        layout.addStretch()
        
        self.tabs.addTab(search_tab, "Поиск")
    
    def create_results_tab(self):
        """Создание вкладки для отображения результатов"""
        results_tab = QWidget()
        layout = QVBoxLayout(results_tab)
        
        # Заголовок
        header_label = QLabel("Результаты скрапинга")
        header_label.setStyleSheet(f"""
            font-size: 28px;
            font-weight: bold;
            color: {self.primary_color};
            margin-bottom: 20px;
        """)
        layout.addWidget(header_label)
        
        # Таблица результатов
        self.results_table = QTableWidget(0, 6)
        self.results_table.setHorizontalHeaderLabels([
            "Название", "Цена", "Описание", "Местоположение", 
            "Дата публикации", "URL"
        ])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.results_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #ccc;
                border-radius: 5px;
                padding: 0px;
                font-size: 14px;
            }
            QHeaderView::section {
                background-color: #f8f8f8;
                padding: 8px;
                border: 1px solid #ccc;
                font-weight: bold;
            }
        """)
        
        layout.addWidget(self.results_table)
        
        # Кнопки действий
        buttons_layout = QHBoxLayout()
        
        self.export_csv_button = QPushButton("Экспорт в CSV")
        self.export_csv_button.setStyleSheet(f"""
            background-color: {self.secondary_color};
            color: white;
            border: none;
            border-radius: 5px;
            padding: 10px;
            font-size: 14px;
        """)
        self.export_csv_button.clicked.connect(lambda: self.save_results("csv"))
        
        self.export_json_button = QPushButton("Экспорт в JSON")
        self.export_json_button.setStyleSheet(f"""
            background-color: {self.secondary_color};
            color: white;
            border: none;
            border-radius: 5px;
            padding: 10px;
            font-size: 14px;
        """)
        self.export_json_button.clicked.connect(lambda: self.save_results("json"))
        
        self.clear_results_button = QPushButton("Очистить результаты")
        self.clear_results_button.setStyleSheet("""
            background-color: #ccc;
            color: #333;
            border: none;
            border-radius: 5px;
            padding: 10px;
            font-size: 14px;
        """)
        self.clear_results_button.clicked.connect(self.clear_results)
        
        buttons_layout.addWidget(self.export_csv_button)
        buttons_layout.addWidget(self.export_json_button)
        buttons_layout.addWidget(self.clear_results_button)
        
        layout.addLayout(buttons_layout)
        
        self.tabs.addTab(results_tab, "Результаты")
    
    def create_settings_tab(self):
        """Создание вкладки настроек"""
        settings_tab = QWidget()
        layout = QVBoxLayout(settings_tab)
        
        # Заголовок
        header_label = QLabel("Настройки")
        header_label.setStyleSheet(f"""
            font-size: 28px;
            font-weight: bold;
            color: {self.primary_color};
            margin-bottom: 20px;
        """)
        layout.addWidget(header_label)
        
        # Настройка темы
        theme_layout = QHBoxLayout()
        theme_label = QLabel("Тема оформления:")
        theme_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        self.theme_checkbox = QCheckBox("Темная тема")
        self.theme_checkbox.setChecked(self.dark_mode)
        self.theme_checkbox.stateChanged.connect(self.on_theme_changed)
        
        theme_layout.addWidget(theme_label)
        theme_layout.addWidget(self.theme_checkbox)
        layout.addLayout(theme_layout)
        
        # Путь для сохранения файлов
        save_path_layout = QHBoxLayout()
        save_path_label = QLabel("Путь сохранения:")
        save_path_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        self.save_path_input = QLineEdit()
        self.save_path_input.setPlaceholderText("Путь для сохранения результатов")
        self.save_path_input.setStyleSheet("""
            border: 1px solid #ccc;
            border-radius: 5px;
            padding: 8px;
            font-size: 14px;
        """)
        
        browse_button = QPushButton("Обзор...")
        browse_button.setStyleSheet("""
            background-color: #ccc;
            color: #333;
            border: none;
            border-radius: 5px;
            padding: 8px;
            font-size: 14px;
        """)
        browse_button.clicked.connect(self.browse_save_path)
        
        save_path_layout.addWidget(save_path_label)
        save_path_layout.addWidget(self.save_path_input)
        save_path_layout.addWidget(browse_button)
        layout.addLayout(save_path_layout)
        
        # Настройки прокси (опционально)
        proxy_layout = QHBoxLayout()
        proxy_label = QLabel("Прокси (опционально):")
        proxy_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText("http://user:pass@host:port")
        self.proxy_input.setStyleSheet("""
            border: 1px solid #ccc;
            border-radius: 5px;
            padding: 8px;
            font-size: 14px;
        """)
        
        proxy_layout.addWidget(proxy_label)
        proxy_layout.addWidget(self.proxy_input)
        layout.addLayout(proxy_layout)
        
        # Кнопка сохранения настроек
        self.save_settings_button = QPushButton("Сохранить настройки")
        self.save_settings_button.setStyleSheet(f"""
            background-color: {self.primary_color};
            color: white;
            border: none;
            border-radius: 5px;
            padding: 12px;
            font-size: 16px;
            font-weight: bold;
        """)
        self.save_settings_button.clicked.connect(self.save_settings)
        
        layout.addWidget(self.save_settings_button)
        layout.addStretch()
        
        self.tabs.addTab(settings_tab, "Настройки")
    
    def load_settings(self):
        """Загрузка сохраненных настроек"""
        self.save_path_input.setText(self.settings.value("save_path", "", type=str))
        self.proxy_input.setText(self.settings.value("proxy", "", type=str))
    
    def save_settings(self):
        """Сохранение настроек"""
        self.settings.setValue("dark_mode", self.dark_mode)
        self.settings.setValue("save_path", self.save_path_input.text())
        self.settings.setValue("proxy", self.proxy_input.text())
        
        QMessageBox.information(self, "Настройки", "Настройки успешно сохранены")
    
    def on_theme_changed(self, state):
        """Обработчик изменения темы"""
        self.dark_mode = state == Qt.CheckState.Checked
        self.settings.setValue("dark_mode", self.dark_mode)
        
        # Показываем уведомление о перезапуске
        QMessageBox.information(
            self, 
            "Смена темы", 
            "Тема будет применена при следующем запуске приложения"
        )
    
    def toggle_theme(self):
        """Переключение между темной и светлой темой"""
        self.dark_mode = not self.dark_mode
        self.theme_checkbox.setChecked(self.dark_mode)
        self.settings.setValue("dark_mode", self.dark_mode)
        
        # Применяем тему
        self.apply_theme()
        
        # Обновляем UI
        self.init_ui()
    
    def browse_save_path(self):
        """Выбор пути для сохранения результатов"""
        directory = QFileDialog.getExistingDirectory(self, "Выберите путь для сохранения")
        if directory:
            self.save_path_input.setText(directory)
    
    def start_scraping(self):
        """Начать процесс скрапинга"""
        # Получаем параметры
        category = self.category_combo.currentText()
        location = self.location_input.text()
        max_pages = self.pages_spin.value()
        delay_min = self.delay_min_spin.value()
        delay_max = self.delay_max_spin.value()
        
        # Показываем прогресс-бар и блокируем кнопку
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.start_button.setEnabled(False)
        
        # Обновляем статус
        self.statusBar.showMessage(f"Сбор данных из категории: {category}")
        
        # Создаем поток для скрапинга
        self.scraping_thread = ScrapingThread(
            category=category,
            location=location,
            max_pages=max_pages,
            delay_min=delay_min,
            delay_max=delay_max,
            proxy=self.proxy_input.text() if self.proxy_input.text() else None
        )
        
        # Подключаем сигналы
        self.scraping_thread.progress_signal.connect(self.update_progress)
        self.scraping_thread.result_signal.connect(self.display_results)
        self.scraping_thread.error_signal.connect(self.handle_error)
        self.scraping_thread.finished.connect(self.scraping_finished)
        
        # Запускаем поток
        self.scraping_thread.start()
    
    def update_progress(self, value):
        """Обновление прогресс-бара"""
        self.progress_bar.setValue(value)
    
    def display_results(self, results):
        """Отображение результатов в таблице"""
        # Очищаем таблицу
        self.results_table.setRowCount(0)
        
        # Заполняем таблицу данными
        for row, item in enumerate(results):
            self.results_table.insertRow(row)
            
            self.results_table.setItem(row, 0, QTableWidgetItem(item.get("title", "")))
            self.results_table.setItem(row, 1, QTableWidgetItem(item.get("price", "")))
            
            # Обрезаем описание для таблицы
            description = item.get("description", "")
            if len(description) > 100:
                description = description[:100] + "..."
            self.results_table.setItem(row, 2, QTableWidgetItem(description))
            
            self.results_table.setItem(row, 3, QTableWidgetItem(item.get("location", "")))
            self.results_table.setItem(row, 4, QTableWidgetItem(item.get("date_published", "")))
            self.results_table.setItem(row, 5, QTableWidgetItem(item.get("url", "")))
        
        # Переключаемся на вкладку результатов
        self.tabs.setCurrentIndex(1)
        
        # Сохраняем результаты для последующего экспорта
        self.current_results = results
    
    def handle_error(self, error_message):
        """Обработка ошибок скрапинга"""
        QMessageBox.critical(self, "Ошибка", error_message)
        self.progress_bar.setVisible(False)
        self.start_button.setEnabled(True)
    
    def scraping_finished(self):
        """Обработчик завершения скрапинга"""
        self.progress_bar.setVisible(False)
        self.start_button.setEnabled(True)
        self.statusBar.showMessage("Сбор данных завершен")
    
    def stop_scraping(self):
        """Остановка процесса скрапинга"""
        if hasattr(self, 'scraping_thread') and self.scraping_thread.isRunning():
            self.scraping_thread.terminate()
            self.progress_bar.setVisible(False)
            self.start_button.setEnabled(True)
            self.statusBar.showMessage("Сбор данных остановлен")
    
    def save_results(self, format_type="json"):
        """Сохранение результатов в файл"""
        if not hasattr(self, 'current_results') or not self.current_results:
            QMessageBox.warning(self, "Ошибка", "Нет данных для сохранения")
            return
        
        # Определяем путь сохранения
        save_path = self.save_path_input.text()
        if not save_path:
            save_path = "ebay_kleinanzeige_data"
        
        # Создаем скрапер только для сохранения
        scraper = EbayKleinanzeigeScraper()
        
        # Генерируем имя файла
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        category = self.category_combo.currentText() if hasattr(self, 'category_combo') else "results"
        filename = f"{category}_{timestamp}"
        
        if format_type == "csv":
            file_path = scraper.save_to_csv(self.current_results, filename=filename, custom_path=save_path)
        else:  # json
            file_path = scraper.save_to_json(self.current_results, filename=filename, custom_path=save_path)
        
        if file_path:
            QMessageBox.information(self, "Экспорт", f"Данные успешно сохранены в {file_path}")
        else:
            QMessageBox.critical(self, "Ошибка", "Не удалось сохранить файл")
    
    def clear_results(self):
        """Очистка результатов"""
        self.results_table.setRowCount(0)
        if hasattr(self, 'current_results'):
            del self.current_results
    
    def export_data(self):
        """Экспорт данных (вызывается из меню)"""
        if not hasattr(self, 'current_results') or not self.current_results:
            QMessageBox.warning(self, "Ошибка", "Нет данных для экспорта")
            return
        
        options = QMessageBox.question(
            self, 
            "Экспорт данных", 
            "Выберите формат экспорта",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if options == QMessageBox.StandardButton.Yes:
            self.save_results("json")
        else:
            self.save_results("csv")
    
    def show_about(self):
        """Отображение информации о программе"""
        QMessageBox.about(
            self,
            "О программе",
            """<b>eBay Kleinanzeige Scraper</b>
            <p>Версия 1.0</p>
            <p>Приложение для сбора данных с eBay Kleinanzeige с элегантным интерфейсом в стиле Airbnb.</p>
            """
        )


class ScrapingThread(QThread):
    """Поток для выполнения скрапинга в фоновом режиме"""
    progress_signal = pyqtSignal(int)
    result_signal = pyqtSignal(list)
    error_signal = pyqtSignal(str)
    
    def __init__(self, category, location, max_pages, delay_min, delay_max, proxy=None):
        super().__init__()
        self.category = category
        self.location = location
        self.max_pages = max_pages
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.proxy = proxy
    
    def run(self):
        """Основной метод потока"""
        try:
            # Создаем экземпляр скрапера с функцией обратного вызова для отслеживания прогресса
            scraper = EbayKleinanzeigeScraper(
                delay_min=self.delay_min,
                delay_max=self.delay_max,
                progress_callback=self.update_progress
            )
            
            # Настраиваем прокси, если указан
            if self.proxy:
                scraper.session.proxies = {
                    "http": self.proxy,
                    "https": self.proxy
                }
            
            # Запускаем скрапинг
            results = scraper.search_by_category(
                category=self.category,
                location=self.location,
                max_pages=self.max_pages
            )
            
            # Отправляем результаты
            self.result_signal.emit(results)
            
        except Exception as e:
            # Отправляем сигнал об ошибке
            self.error_signal.emit(f"Ошибка при скрапинге: {str(e)}")
    
    def update_progress(self, value):
        """Обновление значения прогресса"""
        self.progress_signal.emit(value)


if __name__ == "__main__":
    # Включаем поддержку HiDPI
    qdarktheme.enable_hi_dpi()
    
    # Создаем приложение
    app = QApplication(sys.argv)
    
    # Создаем главное окно
    window = ScraperApp()
    window.show()
    
    # Запускаем цикл событий
    sys.exit(app.exec())
