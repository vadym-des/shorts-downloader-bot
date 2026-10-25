import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from notion_tasks import parse_task_prefix, send_task

logger = logging.getLogger(__name__)


class NotionTaskMiddleware(BaseMiddleware):
    """
    Глобальний middleware для перехоплення завдань у Notion.
    Спрацьовує на найвищому рівні обробки повідомлень до будь-яких валідацій
    та роутерів (handle_link, команди тощо).
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if isinstance(event, Message) and event.text:
            task_info = parse_task_prefix(event.text)
            if task_info:
                title = task_info["title"]
                task_type = task_info["type"]
                rice_score = task_info.get("rice_score")
                desc = task_info.get("description")

                logger.info(
                    "Перехоплено повідомлення для Notion: [%s] '%s' (RICE: %s)",
                    task_type,
                    title,
                    rice_score,
                )

                try:
                    await asyncio.to_thread(
                        send_task,
                        name=title,
                        status="Inbox",
                        task_type=task_type,
                        project="Shorts Downloader",
                        rice_score=rice_score,
                        description=desc,
                        database_id="404002e3-147b-8117-8b20-f3c1d3c23c1e",
                    )
                    await event.reply(f"⚡ Завдання додано в Notion Inbox: {title}")
                    return
                except Exception as e:
                    logger.error("Помилка при створенні картки в Notion: %s", e)
                    await event.reply(f"❌ Не вдалося додати завдання в Notion: {e}")
                    return

        return await handler(event, data)
