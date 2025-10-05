from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from typing import Callable, Dict, Any, Awaitable
import logging

logger = logging.getLogger(__name__)

class ErrorHandlerMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
        try:
            return await handler(event, data)
        except TelegramForbiddenError:
            # User blocked bot - ignore silently
            logger.info(f"Bot blocked by user")
            return
        except TelegramBadRequest as e:
            # Handle common Telegram errors
            if "query is too old" in str(e) or "query ID is invalid" in str(e):
                logger.info(f"Old callback query ignored")
                return
            logger.error(f"Telegram error: {e}")
            return
        except Exception as e:
            logger.exception(f"Unhandled error: {e}")
            # Don't raise - webhook must return 200
            return
