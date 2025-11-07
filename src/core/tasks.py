import logging
import time
from datetime import date, timedelta

from aiogram.exceptions import TelegramForbiddenError
from celery import shared_task
from django.utils import timezone
from django.conf import settings
import aiohttp
from asgiref.sync import async_to_sync

from bot.functions import generate_auth_header
from order.models import Course, PrivateChannel, Order
from users.models import User, UserCard
from bot.misc import bot

logger = logging.getLogger(__name__)


GROUP_ID = -1002634576381


async def process_auto_payment(user, course, user_card):
    """Process automatic payment for a user"""
    order = await Order.objects.acreate(
        user=user,
        amount=course.amount,
        course=course,
    )

    url = f'{settings.CLICK_BASE_URL}/payment'
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Auth": generate_auth_header(),
    }
    payload = {
        "service_id": int(settings.CLICK_SERVICE_ID),
        "card_token": str(user_card.card_token),
        "amount": float(course.amount),
        "transaction_parameter": str(order.id)
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                res_json = await response.json()

        error_code = res_json.get("error_code")
        payment_id = res_json.get("payment_id")

        if error_code == -5017:
            order.payment_id = payment_id
            await order.asave()
            return False, "insufficient_funds"

        elif error_code and error_code != 0:
            order.payment_id = payment_id
            await order.asave()
            return False, "payment_error"

        user.subscription_end_date = timezone.now().date() + timedelta(days=course.period)
        if not user.is_subscribed:
            user.is_subscribed = True
        await user.asave()

        logger.info(f"Successfully renewed subscription for user {user.telegram_id}")
        return True, "success"

    except Exception as e:
        logger.error(f"Payment processing failed for user {user.telegram_id}: {e}")
        return False, "network_error"


async def _process_expired_subscriptions():
    """Process expired subscriptions - first attempt"""
    try:
        until_date = int(time.time()) + 60

        course = await Course.objects.afirst()
        private_channel = await PrivateChannel.objects.filter(course_id=course.id).afirst()

        if not course or not private_channel:
            logger.error("Course or private channel not found")
            return

        today = date.today()
        expired_users = User.objects.filter(is_subscribed=True, subscription_end_date__lte=today, is_foreigner=False)
        if not await expired_users.aexists():
            return

        processed_count = 0
        async for user in expired_users:
            try:
                telegram_id = user.telegram_id

                if not user.is_auto_subscribe:
                    await bot.send_message(
                        telegram_id,
                        "Sizning obunangiz tugaganligi uchun yopiq kanaldan chiqarildingiz!"
                    )
                    try:
                        await bot.ban_chat_member(
                            chat_id=private_channel.private_channel_id,
                            user_id=telegram_id,
                            until_date=until_date
                        )
                    except TelegramForbiddenError:
                        logger.error(f"User not found with {telegram_id}")

                    try:
                        await bot.ban_chat_member(
                            chat_id=GROUP_ID,
                            user_id=telegram_id,
                            until_date=until_date
                        )
                    except TelegramForbiddenError:
                        logger.error(f"User not found with {telegram_id}")

                    user.is_subscribed = False
                    user.is_auto_subscribe = False
                    await user.asave()
                    logger.info(f"Removed non-auto-subscribe user {telegram_id}")

                else:
                    user_card = await UserCard.objects.filter(user_id=telegram_id).afirst()

                    if not user_card:
                        await bot.send_message(
                            telegram_id,
                            "Sizning obunangiz tugaganligi uchun yopiq kanaldan chiqarildingiz!"
                        )

                        try:
                            await bot.ban_chat_member(
                                chat_id=private_channel.private_channel_id,
                                user_id=telegram_id,
                                until_date=until_date
                            )
                        except e:
                            logger.error(e)

                        try:
                            await bot.ban_chat_member(
                                chat_id=GROUP_ID,
                                user_id=telegram_id,
                                until_date=until_date
                            )
                        except TelegramForbiddenError:
                            logger.error(f"User not found")

                        user.is_subscribed = False
                        user.is_auto_subscribe = False
                        await user.asave()

                        logger.info(f"Removed user {telegram_id} - no card available")
                    else:
                        success, error_type = await process_auto_payment(user, course, user_card)

                        if success:
                            await bot.send_message(telegram_id, "Kartadan pul yechib olindi. Obuna uzaytirildi.")
                            logger.info(f"Successfully renewed subscription for user {telegram_id}")
                        else:
                            if error_type == "insufficient_funds":
                                message = (
                                    "Obunani avtomat uzaytirish uchun kartada yetarli mablag` mavjud emas. "
                                    "1 soatdan so'ng qayta yechishga urinish bo'ladi. Hisobingizni to'ldiring!"
                                )
                            else:
                                message = (
                                    "To'lov yechib olishda xatolik yuz berdi. "
                                    "1 soatdan so'ng qayta yechishga urinish bo'ladi."
                                )

                            await bot.send_message(telegram_id, message)
                            logger.warning(f"Payment failed for user {telegram_id}, will retry in 1 hour")

                processed_count += 1

            except Exception as e:
                logger.error(f"Error processing user {user.telegram_id}: {e}")
                continue

        logger.info(f"First attempt: Processed {processed_count} expired subscriptions")

    except Exception as e:
        logger.error(f"Error in _process_expired_subscriptions: {e}")


async def _kick_unpaid_users():
    """Kick users who failed payment - second attempt"""
    try:
        until_date = int(time.time()) + 60

        course = await Course.objects.afirst()
        private_channel = await PrivateChannel.objects.filter(course_id=course.id).afirst()

        if not course or not private_channel:
            logger.error("Course or private channel not found")
            return

        today = date.today()
        expired_users = User.objects.filter(is_subscribed=True, subscription_end_date__lte=today, is_foreigner=False)
        if not await expired_users.aexists():
            return

        processed_count = 0
        async for user in expired_users:
            try:
                telegram_id = user.telegram_id

                if user.is_auto_subscribe:
                    user_card = await UserCard.objects.filter(user_id=telegram_id).afirst()

                    if not user_card:
                        await bot.send_message(
                            telegram_id,
                            "Sizning obunangiz tugaganligi uchun yopiq kanaldan chiqarildingiz!"
                        )
                        try:
                            await bot.ban_chat_member(
                                chat_id=private_channel.private_channel_id,
                                user_id=telegram_id,
                                until_date=until_date
                            )
                        except TelegramForbiddenError:
                            logger.error(f"User not found with {telegram_id}")

                        try:
                            await bot.ban_chat_member(
                                chat_id=GROUP_ID,
                                user_id=telegram_id,
                                until_date=until_date
                            )
                        except TelegramForbiddenError:
                            logger.error(f"User not found with {telegram_id}")

                        user.is_subscribed = False
                        user.is_auto_subscribe = False
                        await user.asave()
                        logger.info(f"Final removal: User {telegram_id} - no card")
                    else:
                        success, error_type = await process_auto_payment(user, course, user_card)

                        if success:
                            await bot.send_message(telegram_id, "Kartadan pul yechib olindi. Obuna uzaytirildi.")
                            logger.info(f"Second attempt successful for user {telegram_id}")
                        else:
                            if error_type == "insufficient_funds":
                                message = (
                                    "Obunani avtomat uzaytirish uchun kartada yetarli mablag` mavjud emas. "
                                    "Yopiq kanaldan chiqarildingiz!"
                                )
                            else:
                                message = "To'lov amalga oshmadi. Yopiq kanaldan chiqarildingiz!"

                            await bot.send_message(telegram_id, message)

                            try:
                                await bot.ban_chat_member(
                                    chat_id=private_channel.private_channel_id,
                                    user_id=telegram_id,
                                    until_date=until_date
                                )
                            except TelegramForbiddenError:
                                logger.error(f"User not found with {telegram_id}")

                            try:
                                await bot.ban_chat_member(
                                    chat_id=GROUP_ID,
                                    user_id=telegram_id,
                                    until_date=until_date
                                )
                            except TelegramForbiddenError:
                                logger.error(f"User not found with {telegram_id}")

                            user.is_subscribed = False
                            user.is_auto_subscribe = False
                            await user.asave()
                            logger.info(f"Final removal: User {telegram_id} after failed second attempt")

                processed_count += 1

            except Exception as e:
                logger.error(f"Error processing user {user.telegram_id} in second attempt: {e}")
                continue

        logger.info(f"Second attempt: Processed {processed_count} users")

    except Exception as e:
        logger.error(f"Error in _kick_unpaid_users: {e}")


async def _send_membership_expire_notification():
    """Send notifications to users about subscription expiration"""
    try:
        three_days_before = date.today() + timedelta(days=3)
        one_day_before = date.today() + timedelta(days=1)
        today = date.today()

        # Users expiring in 3 days
        three_day_users = User.objects.filter(
            is_subscribed=True,
            is_auto_subscribe=False,
            subscription_end_date=three_days_before
        )

        # Users expiring tomorrow
        one_day_users = User.objects.filter(
            is_subscribed=True,
            is_auto_subscribe=False,
            subscription_end_date=one_day_before
        )

        # Users expiring today
        today_expired_users = User.objects.filter(
            is_subscribed=True,
            is_auto_subscribe=False,
            subscription_end_date=today
        )

        # Send 3-day warning
        count_3day = 0
        async for user in three_day_users:
            try:
                message = (
                    "⚠️ <b>Obuna tugash haqida ogohlantirish</b>\n\n"
                    "Hurmatli foydalanuvchi!\n\n"
                    "Sizning obunangiz <b>3 kun</b> ichida tugaydi.\n"
                    f"Obuna tugash sanasi: <b>{three_days_before.strftime('%d.%m.%Y')}</b>\n\n"
                    "Yopiq kanaldan chiqarilmaslik uchun obunangizni <b>vaqtida uzaytiring</b>!\n\n"
                    "📌 Obunani uzaytirish uchun to'lov qiling."
                )

                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=message,
                    parse_mode='HTML'
                )
                count_3day += 1
                logger.info(f"3-day warning sent to user {user.telegram_id}")
            except Exception as e:
                logger.error(f"Failed to send 3-day warning to user {user.telegram_id}: {e}")
                continue

        # Send 1-day warning (more urgent)
        count_1day = 0
        async for user in one_day_users:
            try:
                message = (
                    "🚨 <b>MUHIM! Obuna ertaga tugaydi</b>\n\n"
                    "Hurmatli foydalanuvchi!\n\n"
                    "Sizning obunangiz <b>ERTAGA</b> tugaydi!\n"
                    f"Obuna tugash sanasi: <b>{one_day_before.strftime('%d.%m.%Y')}</b>\n\n"
                    "⚠️ Agar ertaga soat 22:30 gacha to'lov qilmasangiz, "
                    "yopiq kanaldan <b>avtomatik chiqarilasiz</b>!\n\n"
                    "📌 Obunani davom ettirish uchun <b>HOZIROQ</b> to'lov qiling."
                )

                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=message,
                    parse_mode='HTML'
                )
                count_1day += 1
                logger.info(f"1-day warning sent to user {user.telegram_id}")
            except Exception as e:
                logger.error(f"Failed to send 1-day warning to user {user.telegram_id}: {e}")
                continue

        # Send final warning (expires today)
        count_today = 0
        async for user in today_expired_users:
            try:
                message = (
                    "🔴 <b>OXIRGI OGOHLANTIRISH!</b>\n\n"
                    "Hurmatli foydalanuvchi!\n\n"
                    "Sizning obunangiz <b>BUGUN</b> tugaydi!\n"
                    f"Obuna tugash sanasi: <b>{today.strftime('%d.%m.%Y')}</b>\n\n"
                    "⛔️ Agar bugun soat <b>22:30 gacha</b> to'lov qilmasangiz, "
                    "yopiq kanaldan <b>CHIQARILASIZ</b>!\n\n"
                    "📌 Yopiq kanalda qolish uchun <b>ZUDLIK BILAN</b> obunani uzaytiring!\n\n"
                    "⏰ Qolgan vaqt: Soat 22:30 gacha"
                )

                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=message,
                    parse_mode='HTML'
                )
                count_today += 1
                logger.info(f"Final warning sent to user {user.telegram_id}")
            except Exception as e:
                logger.error(f"Failed to send final warning to user {user.telegram_id}: {e}")
                continue

        logger.info(
            f"Expiration notifications sent: "
            f"{count_3day} (3-day), {count_1day} (1-day), {count_today} (today)"
        )

    except Exception as e:
        logger.error(f"Error in send_membership_expire_notification: {e}")


@shared_task
def process_expired_subscriptions():
    """Celery task: First payment attempt"""
    async_to_sync(_process_expired_subscriptions)()


@shared_task
def kick_unpaid_users():
    """Celery task: Second payment attempt and kick"""
    async_to_sync(_kick_unpaid_users)()


@shared_task
def send_membership_expire_notification():
    """Celery task: Send subscription expiration notifications"""
    async_to_sync(_send_membership_expire_notification)()
