import asyncio
import html
import logging
import os
from typing import Any, Awaitable, Callable, Dict, List
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from config import NOTION_DATABASE_ID, NOTION_PROJECT, NOTION_TOKEN
from notion_tasks import parse_task_prefix, send_task

logger = logging.getLogger(__name__)


class NotionTaskMiddleware(BaseMiddleware):
    """
    Глобальний middleware для перехоплення завдань у Notion.
    Спрацьовує на найвищому рівні обробки повідомлень до будь-яких валідацій
    та роутерів (handle_link, команди тощо).
    Підтримує як звичайні текстові повідомлення, так і підписи (caption) до фото/відео.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        try:
            if isinstance(event, Message):
                raw_text = (event.text or event.caption or "").strip()

                if raw_text:
                    try:
                        task_info = parse_task_prefix(raw_text)
                    except Exception as e:
                        logger.error("Помилка парсингу тригера для Notion: %s", e)
                        task_info = None

                    if task_info:
                        title = task_info["title"]
                        task_type = task_info["type"]
                        rice_score = task_info.get("rice_score")
                        desc = task_info.get("description")

                        # Збір медіафайлів (фото / відео)
                        media_urls: List[str] = []
                        bot = event.bot

                        if event.photo and bot:
                            try:
                                best_photo = event.photo[-1]
                                file_info = await bot.get_file(best_photo.file_id)
                                if file_info.file_path:
                                    photo_url = f"https://api.telegram.org/file/bot{bot.token}/{file_info.file_path}"
                                    media_urls.append(photo_url)
                            except Exception as photo_err:
                                logger.warning("Не вдалося отримати URL фото: %s", photo_err)

                        elif event.video and bot:
                            try:
                                file_info = await bot.get_file(event.video.file_id)
                                if file_info.file_path:
                                    video_url = f"https://api.telegram.org/file/bot{bot.token}/{file_info.file_path}"
                                    media_urls.append(video_url)
                            except Exception as video_err:
                                logger.warning("Не вдалося отримати URL відео: %s", video_err)

                        logger.info(
                            "Перехоплено повідомлення для Notion: [%s] '%s' (RICE: %s, Media: %d)",
                            task_type,
                            title,
                            rice_score,
                            len(media_urls)
                        )

                        active_token = (os.getenv("NOTION_TOKEN") or "").strip() or NOTION_TOKEN
                        active_db = (os.getenv("NOTION_DATABASE_ID") or "").strip() or NOTION_DATABASE_ID
                        active_project = (os.getenv("NOTION_PROJECT") or "").strip() or NOTION_PROJECT

                        if not active_token or active_token == "your_notion_token_here":
                            err_msg = "⚠️ <b>Помилка Notion:</b> відсутній або некоректний <code>NOTION_TOKEN</code> у змінних оточення (Variables на Railway)!"
                            await event.reply(err_msg, parse_mode="HTML")
                            return

                        if not active_db or active_db == "your_database_id_here":
                            err_msg = "⚠️ <b>Помилка Notion:</b> відсутній або некоректний <code>NOTION_DATABASE_ID</code> у змінних оточення!"
                            await event.reply(err_msg, parse_mode="HTML")
                            return

                        try:
                            await asyncio.to_thread(
                                send_task,
                                name=title,
                                status="Inbox",
                                task_type=task_type,
                                project=active_project,
                                rice_score=rice_score,
                                description=desc,
                                media_urls=media_urls if media_urls else None,
                                token=active_token,
                                database_id=active_db,
                            )
                            safe_title = html.escape(title)
                            media_badge = " 📸" if media_urls else ""
                            await event.reply(f"⚡ Завдання додано в Notion Inbox: <b>{safe_title}</b>{media_badge}", parse_mode="HTML")
                            return
                        except Exception as e:
                            logger.error("Помилка при створенні картки в Notion: %s", e, exc_info=True)
                            safe_err = html.escape(str(e))
                            try:
                                await event.reply(f"⚠️ <b>Помилка Notion:</b> {safe_err}", parse_mode="HTML")
                            except Exception:
                                await event.reply(f"⚠️ Помилка Notion: {str(e)[:300]}", parse_mode=None)
                            return
        except Exception as outer_err:
            logger.error("Несподівана помилка в NotionTaskMiddleware: %s", outer_err, exc_info=True)

        return await handler(event, data)
