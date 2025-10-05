import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Update
from django.conf import settings
from loguru import logger

from .helpers import get_bot_webhook_url
from .middleware.error_handler import ErrorHandlerMiddleware
from .routers import router
from .utils.storage import DjangoRedisStorage
from aiogram.types import BotCommand, BotCommandScopeDefault


bot = Bot(
    token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)


async def set_commands(bot: Bot):
    """Set bot commands in the menu"""
    commands = [
        BotCommand(command="start", description="Botni ishga tushirish"),
        BotCommand(command="check", description="Obunani tekshirish"),
        BotCommand(command="cancel", description="Obunani to'xtatish"),
    ]

    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())


async def on_startup():
    await set_commands(bot)

    if settings.DEBUG is False:
        webhook_info = await bot.get_webhook_info()
        if webhook_info.url != get_bot_webhook_url():
            await bot.set_webhook(
                get_bot_webhook_url(), secret_token=settings.BOT_WEBHOOK_SECRET
            )
    else:
        # 🛠 Delete webhook before polling
        # await bot.delete_webhook(drop_pending_updates=True)
        run_polling()


async def on_shutdown():
    await bot.session.close()
    logger.info("Bot shut down")


def init_dispatcher():
    dp = Dispatcher(storage=DjangoRedisStorage())

    # Register error handler middleware
    dp.update.middleware(ErrorHandlerMiddleware())

    dp.include_router(router)
    return dp


aiogram_dispatcher = init_dispatcher()


async def feed_update(update: Update):
    await aiogram_dispatcher.feed_update(bot, update)


async def feed_raw_update(update: dict):
    await aiogram_dispatcher.feed_raw_update(bot, update)


def run_polling():
    asyncio.create_task(aiogram_dispatcher.start_polling(bot, handle_signals=False))
