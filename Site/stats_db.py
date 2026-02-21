import json
import os
import time
from datetime import datetime
import re
from config import Config

class StatsDB:
    """
    Класс для управления базой данных в формате JSON.
    Хранит статистику посещений, логинов, прокси и т.д.
    """
    def __init__(self, db_file):
        self.db_file = db_file
        self.data = self._load()

    def _load(self):
        """Загружает данные из JSON-файла или создает пустую структуру."""
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return self._get_empty_data()
        return self._get_empty_data()

    def _get_empty_data(self):
        """Возвращает пустую структуру данных для новой БД."""
        return {
            'visits': [], 'phone_entries': [], 'code_entries': [],
            'successful_logins': [], 'proxies': [], 'blacklist': []
        }

    def save(self):
        """Сохраняет текущие данные в JSON-файл."""
        with open(self.db_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def add_entry(self, entry_type, **kwargs):
        """Добавляет новую запись (визит, телефон и т.д.) в БД."""
        if entry_type not in self.data:
            self.data[entry_type] = []
        
        entry = {**kwargs, 'time': time.time(), 'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        self.data[entry_type].append(entry)
        self.save()

    def get_stats(self):
        """Собирает и возвращает общую и дневную статистику."""
        daily_stats = {}
        for entry_type, key in [('visits', 'visits'), ('phone_entries', 'phones'), 
                                ('code_entries', 'codes'), ('successful_logins', 'success')]:
            for entry in self.data.get(entry_type, []):
                date = datetime.fromtimestamp(entry['time']).strftime('%Y-%m-%d')
                if date not in daily_stats:
                    daily_stats[date] = {'visits': 0, 'phones': 0, 'codes': 0, 'success': 0}
                daily_stats[date][key] += 1
        
        daily_list = [{'date': date, **stats} for date, stats in sorted(daily_stats.items(), reverse=True)]

        return {
            'visits': len(self.data.get('visits', [])),
            'phone_entries': len(self.data.get('phone_entries', [])),
            'successful_logins': len(self.data.get('successful_logins', [])),
            'daily': daily_list
        }

    def get_proxies(self):
        return self.data.get('proxies', [])

    def add_proxy(self, proxy_data):
        proxies = self.get_proxies()
        new_id = max([p.get('id', 0) for p in proxies] + [0]) + 1
        proxy_data.update({'id': new_id, 'last_check': None, 'status': 'unknown'})
        proxies.append(proxy_data)
        self.save()
        return new_id
    
    def add_proxies_bulk(self, proxies_text):
        lines = proxies_text.strip().split('\n')
        added_count, errors = 0, []
        for line in lines:
            if not line.strip(): continue
            proxy_data = self._parse_proxy_string(line)
            if proxy_data:
                self.add_proxy(proxy_data)
                added_count += 1
            else:
                errors.append(line)
        return {'added': added_count, 'errors': errors}

    def _parse_proxy_string(self, proxy_str):
        """Парсит строку прокси формата [type://][user:pass@]host:port."""
        match = re.match(r'(?:(socks5|http)://)?(?:([^:@]+):([^:@]+)@)?([^:@]+):(\d+)', proxy_str.strip())
        if not match: return None
        
        p_type, p_user, p_pass, p_host, p_port = match.groups()
        return {
            'type': p_type or 'socks5', 'username': p_user, 'password': p_pass,
            'host': p_host, 'port': int(p_port), 'enabled': True
        }

    def update_proxy_status(self, proxy_id, status):
        for p in self.get_proxies():
            if p.get('id') == proxy_id:
                p['status'] = status
                p['last_check'] = time.time()
                self.save()
                return True
        return False

    def delete_proxy(self, proxy_id):
        self.data['proxies'] = [p for p in self.get_proxies() if p.get('id') != proxy_id]
        self.save()

    def toggle_proxy(self, proxy_id):
        for p in self.get_proxies():
            if p.get('id') == proxy_id:
                p['enabled'] = not p.get('enabled', True)
                self.save()
                return p['enabled']
        return None

    def is_blacklisted(self, ip):
        return any(b['ip'] == ip for b in self.data.get('blacklist', []))

# Создаем единый глобальный экземпляр для импорта в других модулях.
stats_db = StatsDB(Config.STATS_DB_PATH)

