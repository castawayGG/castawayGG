import time
import asyncio
from collections import defaultdict
from typing import Dict, List, Optional

class FloodControl:
    """
    Механизм контроля флуда для Telegram API.
    Отслеживает количество запросов и временные метки для каждого аккаунта,
    при необходимости вводит задержки.
    """
    def __init__(self):
        # Словарь: account_id -> список временных меток последних действий
        self._action_history: Dict[str, List[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def wait_if_needed(self, account_id: str, max_actions_per_minute: int = 30):
        """
        Проверяет, не превышен ли лимит действий для аккаунта.
        Если превышен, ожидает необходимое время.
        """
        async with self._lock:
            now = time.time()
            # Очищаем историю старше 60 секунд
            self._action_history[account_id] = [
                ts for ts in self._action_history[account_id]
                if now - ts < 60
            ]
            
            # Если за последнюю минуту уже было больше лимита, считаем время ожидания
            if len(self._action_history[account_id]) >= max_actions_per_minute:
                oldest = min(self._action_history[account_id])
                wait_time = 60 - (now - oldest)
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
            
            # Добавляем текущее действие в историю
            self._action_history[account_id].append(now)

    def reset(self, account_id: str):
        """Сбрасывает историю для указанного аккаунта."""
        self._action_history[account_id] = []

# Глобальный экземпляр
flood_control = FloodControl()