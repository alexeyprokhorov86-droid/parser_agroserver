"""
Парсер цен на ингредиенты с Agroserver.ru
Фильтрация по региону: Москва и Московская область
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
from datetime import datetime

class AgroserverParser:
    """Парсер для извлечения цен с Agroserver.ru"""
    
    def __init__(self):
        self.base_url = "https://agroserver.ru"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }
        
        # Категории для парсинга (можно расширять)
        self.categories = {
            'мука_пшеничная': '/muka-pshenichnaya/',
            'сахар': '/sakhar/',
            'масло_сливочное': '/maslo-slivochnoe/',
            'молоко': '/moloko/',
        }
        
        # Регионы Москвы и МО для фильтрации
        self.moscow_regions = [
            'москва', 'московская', 'мо', 'moscow',
            'подмосковье', 'химки', 'балашиха', 'одинцово',
            'мытищи', 'люберцы', 'королев', 'красногорск'
        ]
    
    def extract_price(self, text):
        """
        Извлекает цену из текста
        Примеры:
        - "25.50 руб / кг" -> 25.50
        - "25 000 руб/т" -> 25.0 (конвертирует в руб/кг)
        - "от 30 руб" -> 30.0
        """
        if not text:
            return None
        
        # Убираем лишние пробелы
        text = ' '.join(text.split())
        
        # Ищем цену в рублях
        # Паттерны: "25.50 руб", "25,50 руб", "25 000 руб"
        patterns = [
            r'(\d+[\s,.]?\d*)\s*(?:руб|₽)',  # Основной паттерн
            r'от\s+(\d+[\s,.]?\d*)',          # "от 25"
            r'(\d+[\s,.]?\d*)\s*р\b',         # "25 р"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                price_str = match.group(1)
                # Убираем пробелы и заменяем запятую на точку
                price_str = price_str.replace(' ', '').replace(',', '.')
                try:
                    price = float(price_str)
                    
                    # Проверяем единицы измерения
                    if '/т' in text.lower() or 'руб/т' in text.lower():
                        # Конвертируем из руб/т в руб/кг
                        price = price / 1000
                    
                    return price
                except ValueError:
                    continue
        
        return None
    
    def is_moscow_region(self, text):
        """
        Проверяет, относится ли текст к Москве/МО
        """
        if not text:
            return False
        
        text_lower = text.lower()
        return any(region in text_lower for region in self.moscow_regions)
    
    def parse_category_page(self, category_url, max_pages=5):
        """
        Парсит страницы категории
        
        Args:
            category_url: URL категории (например, '/muka-pshenichnaya/')
            max_pages: Максимальное количество страниц для парсинга
        
        Returns:
            list: Список словарей с данными об объявлениях
        """
        results = []
        
        for page_num in range(1, max_pages + 1):
            # Формируем URL страницы
            if page_num == 1:
                url = f"{self.base_url}{category_url}"
            else:
                url = f"{self.base_url}{category_url}p{page_num}.htm"
            
            print(f"Парсинг: {url}")
            
            try:
                # Делаем запрос
                response = requests.get(url, headers=self.headers, timeout=10)
                response.raise_for_status()
                
                # Парсим HTML
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Ищем блоки с объявлениями
                # ВАЖНО: структура может меняться, нужно адаптировать селекторы
                ads = soup.find_all('div', class_='b-item')  # Примерный класс
                
                if not ads:
                    # Пробуем альтернативные селекторы
                    ads = soup.find_all('div', class_='item')
                    
                if not ads:
                    print(f"  Не найдены объявления на странице {page_num}")
                    break
                
                print(f"  Найдено объявлений: {len(ads)}")
                
                # Парсим каждое объявление
                for ad in ads:
                    try:
                        # Извлекаем данные (структура может отличаться!)
                        title = ad.find('a', class_='title')
                        title_text = title.get_text(strip=True) if title else None
                        
                        price = ad.find('span', class_='price')
                        price_text = price.get_text(strip=True) if price else None
                        
                        location = ad.find('span', class_='location')
                        location_text = location.get_text(strip=True) if location else None
                        
                        company = ad.find('span', class_='company')
                        company_text = company.get_text(strip=True) if company else None
                        
                        # Фильтр по Москве/МО
                        if location_text and not self.is_moscow_region(location_text):
                            continue
                        
                        # Извлекаем цену
                        price_value = self.extract_price(price_text) if price_text else None
                        
                        if price_value and price_value > 0:
                            results.append({
                                'название': title_text,
                                'цена_руб_кг': price_value,
                                'регион': location_text,
                                'поставщик': company_text,
                                'дата_парсинга': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            })
                    
                    except Exception as e:
                        print(f"  Ошибка при парсинге объявления: {e}")
                        continue
                
                # Задержка между запросами (чтобы не заблокировали)
                time.sleep(2)
            
            except requests.RequestException as e:
                print(f"  Ошибка при загрузке страницы: {e}")
                break
        
        return results
    
    def parse_ingredient(self, ingredient_name, category_url):
        """
        Парсит цены на конкретный ингредиент
        
        Args:
            ingredient_name: Название ингредиента для отчета
            category_url: URL категории на Agroserver
        
        Returns:
            dict: Статистика по ценам
        """
        print(f"\n{'='*70}")
        print(f"Парсинг: {ingredient_name}")
        print(f"{'='*70}")
        
        # Парсим объявления
        results = self.parse_category_page(category_url, max_pages=3)
        
        if not results:
            print(f"❌ Не найдены цены для: {ingredient_name}")
            return None
        
        # Создаем DataFrame для анализа
        df = pd.DataFrame(results)
        
        # Статистика
        stats = {
            'ингредиент': ingredient_name,
            'найдено_предложений': len(df),
            'мин_цена': df['цена_руб_кг'].min(),
            'макс_цена': df['цена_руб_кг'].max(),
            'средняя_цена': df['цена_руб_кг'].mean(),
            'медианная_цена': df['цена_руб_кг'].median(),
            'рекомендуемая_цена': df['цена_руб_кг'].median(),  # Используем медиану
            'дата_обновления': datetime.now().strftime('%Y-%m-%d')
        }
        
        print(f"\n📊 Статистика по ценам:")
        print(f"  Найдено предложений: {stats['найдено_предложений']}")
        print(f"  Минимальная цена: {stats['мин_цена']:.2f} руб/кг")
        print(f"  Максимальная цена: {stats['макс_цена']:.2f} руб/кг")
        print(f"  Средняя цена: {stats['средняя_цена']:.2f} руб/кг")
        print(f"  Медианная цена: {stats['медианная_цена']:.2f} руб/кг")
        print(f"  ✅ Рекомендуемая цена: {stats['рекомендуемая_цена']:.2f} руб/кг")
        
        return stats, df
    
    def update_prices_in_database(self, csv_path='ingredients_v2.csv'):
        """
        Обновляет цены в базе данных ингредиентов
        
        Args:
            csv_path: Путь к CSV файлу с ингредиентами
        """
        print(f"\n{'='*70}")
        print("ОБНОВЛЕНИЕ ЦЕН В БАЗЕ ДАННЫХ")
        print(f"{'='*70}")
        
        # Загружаем базу
        try:
            df_ingredients = pd.read_csv(csv_path, encoding='utf-8')
            print(f"✅ Загружено ингредиентов: {len(df_ingredients)}")
        except FileNotFoundError:
            print(f"❌ Файл {csv_path} не найден")
            return
        
        # Маппинг ингредиентов на категории Agroserver
        # Это нужно расширять под твои ингредиенты
        ingredient_mapping = {
            'Мука пшеничная в/с': '/muka-pshenichnaya/',
            'Мука пшеничная 1 с': '/muka-pshenichnaya/',
            'Сахар': '/sakhar/',
            'Масло сливочное 82,5%': '/maslo-slivochnoe/',
            'Масло сливочное 72,5%': '/maslo-slivochnoe/',
        }
        
        updated_count = 0
        
        for ingredient_name, category_url in ingredient_mapping.items():
            # Проверяем, есть ли этот ингредиент в базе
            if ingredient_name not in df_ingredients['Ингредиент'].values:
                print(f"⚠️ Ингредиент '{ingredient_name}' не найден в базе")
                continue
            
            # Парсим цены
            result = self.parse_ingredient(ingredient_name, category_url)
            
            if result:
                stats, _ = result
                recommended_price = stats['рекомендуемая_цена']
                
                # Обновляем цену в базе
                mask = df_ingredients['Ингредиент'] == ingredient_name
                old_price = df_ingredients.loc[mask, 'Стоимость, руб/кг'].values[0]
                df_ingredients.loc[mask, 'Стоимость, руб/кг'] = recommended_price
                
                print(f"  💰 Старая цена: {old_price:.2f} руб/кг")
                print(f"  💰 Новая цена: {recommended_price:.2f} руб/кг")
                print(f"  📈 Изменение: {((recommended_price - old_price) / old_price * 100):.1f}%")
                
                updated_count += 1
            
            # Задержка между ингредиентами
            time.sleep(3)
        
        # Сохраняем обновленную базу
        if updated_count > 0:
            df_ingredients.to_csv(csv_path, index=False, encoding='utf-8')
            print(f"\n✅ Обновлено цен: {updated_count}")
            print(f"✅ База сохранена: {csv_path}")
        else:
            print(f"\n⚠️ Цены не были обновлены")


# ============================================================================
# ПРИМЕР ИСПОЛЬЗОВАНИЯ
# ============================================================================

if __name__ == "__main__":
    parser = AgroserverParser()
    
    # Вариант 1: Парсинг одного ингредиента
    print("\n" + "="*70)
    print("ВАРИАНТ 1: Парсинг конкретного ингредиента")
    print("="*70)
    
    result = parser.parse_ingredient(
        ingredient_name='Мука пшеничная',
        category_url='/muka-pshenichnaya/'
    )
    
    if result:
        stats, df = result
        print(f"\n📄 Детальная информация по предложениям:")
        print(df.to_string(index=False))
    
    # Вариант 2: Обновление всей базы
    print("\n" + "="*70)
    print("ВАРИАНТ 2: Обновление цен в базе данных")
    print("="*70)
    
    # Раскомментируй когда будешь готов обновлять базу
    # parser.update_prices_in_database('ingredients_v2.csv')
