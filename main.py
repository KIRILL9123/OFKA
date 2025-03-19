import sys
import qdarktheme
from PySide6.QtWidgets import QApplication

from scraper.ebay_kleinanzeige_scraper import EbayKleinanzeigeScraper
from gui.main_window import ScraperApp

if __name__ == "__main__":
    # Включаем поддержку HiDPI
    qdarktheme.enable_hi_dpi()
    
    # Создаем приложение
    app = QApplication(sys.argv)
    
    # Создаем главное окно, передаем класс скрапера
    window = ScraperApp(EbayKleinanzeigeScraper)
    window.show()
    
    # Запускаем цикл событий
    sys.exit(app.exec())
