# bot/tasks.py

from celery import shared_task
from django.contrib.auth import get_user_model
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
import asyncio

from core.utils.constants import CONSTANTS

User = get_user_model()


async def send_video_to_users_async(
    video_file_id: str,
    caption: str,
    bot_token: str,
    admin_chat_id: int
):
    """
    Send uploaded video using send_video
    Allows custom captions per user
    """
    bot = Bot(token=bot_token)

    try:
        users = await asyncio.to_thread(lambda: list(User.objects.all()))
        total_users = len(users)
        sent_count = 0
        failed_count = 0
        batch_size = 30

        status_msg = await bot.send_message(
            chat_id=admin_chat_id,
            text=f"📤 {total_users} ta foydalanuvchiga video yuborilmoqda..."
        )

        for i in range(0, total_users, batch_size):
            batch = users[i:i + batch_size]
            tasks = []

            for user in batch:
                user_caption = caption if caption else (
                    "🎥 Motivatsiya" if user.language == CONSTANTS.LANGUAGES.UZ
                    else "🎥 Мотивационное видео"
                )

                task = bot.send_video(
                    chat_id=user.telegram_id,
                    video=video_file_id,
                    caption=user_caption
                )
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, (Exception, TelegramForbiddenError)):
                    failed_count += 1
                else:
                    sent_count += 1

            processed = min(i + batch_size, total_users)
            try:
                await bot.edit_message_text(
                    chat_id=admin_chat_id,
                    message_id=status_msg.message_id,
                    text=(
                        f"📤 Video yuborilmoqda...\n\n"
                        f"Jarayon: {processed}/{total_users}\n"
                        f"✅ Muvaffaqiyatli: {sent_count}\n"
                        f"❌ Xatolik: {failed_count}"
                    )
                )
            except Exception:
                pass

            if i + batch_size < total_users:
                await asyncio.sleep(1.0)

        await bot.edit_message_text(
            chat_id=admin_chat_id,
            message_id=status_msg.message_id,
            text=(
                f"✅ Video yuborildi!\n\n"
                f"📊 Statistika:\n"
                f"Jami: {total_users}\n"
                f"✅ Muvaffaqiyatli: {sent_count}\n"
                f"❌ Xatolik: {failed_count}"
            )
        )

        return {'total': total_users, 'success': sent_count, 'failed': failed_count}

    finally:
        await bot.session.close()


async def copy_video_to_users_async(
    from_chat_id: int,
    message_id: int,
    bot_token: str,
    admin_chat_id: int
):
    """
    Copy forwarded video using copy_message
    Removes forward tag and preserves exact formatting
    """
    bot = Bot(token=bot_token)

    try:
        users = await asyncio.to_thread(lambda: list(User.objects.all()))
        total_users = len(users)
        sent_count = 0
        failed_count = 0
        batch_size = 30

        status_msg = await bot.send_message(
            chat_id=admin_chat_id,
            text=f"📤 {total_users} ta foydalanuvchiga video yuborilmoqda..."
        )

        for i in range(0, total_users, batch_size):
            batch = users[i:i + batch_size]
            tasks = []

            for user in batch:
                # ✅ Use copy_message for forwarded videos
                task = bot.copy_message(
                    chat_id=user.telegram_id,
                    from_chat_id=from_chat_id,
                    message_id=message_id
                )
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, (Exception, TelegramForbiddenError)):
                    failed_count += 1
                else:
                    sent_count += 1

            processed = min(i + batch_size, total_users)
            try:
                await bot.edit_message_text(
                    chat_id=admin_chat_id,
                    message_id=status_msg.message_id,
                    text=(
                        f"📤 Video yuborilmoqda...\n\n"
                        f"Jarayon: {processed}/{total_users}\n"
                        f"✅ Muvaffaqiyatli: {sent_count}\n"
                        f"❌ Xatolik: {failed_count}"
                    )
                )
            except Exception:
                pass

            if i + batch_size < total_users:
                await asyncio.sleep(1.0)

        await bot.edit_message_text(
            chat_id=admin_chat_id,
            message_id=status_msg.message_id,
            text=(
                f"✅ Video yuborildi!\n\n"
                f"📊 Statistika:\n"
                f"Jami: {total_users}\n"
                f"✅ Muvaffaqiyatli: {sent_count}\n"
                f"❌ Xatolik: {failed_count}"
            )
        )

        return {'total': total_users, 'success': sent_count, 'failed': failed_count}

    finally:
        await bot.session.close()


@shared_task
def copy_video_to_users_task(
    from_chat_id: int,
    message_id: int,
    bot_token: str,
    admin_chat_id: int
):
    """Celery task for forwarded videos"""
    return asyncio.run(
        copy_video_to_users_async(from_chat_id, message_id, bot_token, admin_chat_id)
    )


@shared_task
def send_video_to_users_task(
    video_file_id: str,
    caption: str,
    bot_token: str,
    admin_chat_id: int
):
    """Celery task for uploaded videos"""
    return asyncio.run(
        send_video_to_users_async(video_file_id, caption, bot_token, admin_chat_id)
    )
