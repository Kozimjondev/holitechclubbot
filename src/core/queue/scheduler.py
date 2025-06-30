import asyncio
import logging
import os
from datetime import date, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from django.utils import timezone
from django.conf import settings
import aiohttp

from order.models import Transaction, Course, PrivateChannel
from users.models import User, UserCard

scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)

logger = logging.getLogger(__name__)

from bot.misc import bot


async def process_auto_payment(user, course, user_card):
    """Process automatic payment for a user"""
    transaction = await Transaction.objects.acreate(
        user=user,
        amount=course.amount,
    )

    url = 'https://api.click.uz/v2/merchant/card_token/payment'
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Auth": generate_auth_header(),
    }
    payload = {
        "service_id": int(settings.CLICK_SERVICE_ID),
        "card_token": str(user_card.card_token),
        "amount": float(course.amount),
        "transaction_parameter": str(transaction.id)
    }

    try:
        # Use aiohttp for async HTTP requests
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                res_json = await response.json()

        error_code = res_json.get("error_code")
        payment_id = res_json.get("payment_id")

        if error_code == -5017:  # Insufficient funds
            transaction.state = Transaction.CANCELED_DURING_INIT
            transaction.transaction_id = payment_id
            await transaction.asave()
            return False, "insufficient_funds"

        elif error_code and error_code != 0:  # Other errors
            transaction.state = Transaction.CANCELED_DURING_INIT
            transaction.transaction_id = payment_id
            await transaction.asave()
            return False, "payment_error"

        # Payment successful
        transaction.state = Transaction.SUCCESSFULLY
        transaction.transaction_id = payment_id
        await transaction.asave()

        # Update user subscription
        user.subscription_end_date = timezone.now().date() + timedelta(days=course.period)
        if not user.is_subscribed:
            user.subscription_start_date = timezone.now().date()
            user.is_subscribed = True
        await user.asave()

        logger.info(f"Successfully renewed subscription for user {user.telegram_id}")
        return True, "success"

    except Exception as e:
        logger.error(f"Payment processing failed for user {user.telegram_id}: {e}")
        transaction.state = Transaction.CANCELED_DURING_INIT
        await transaction.asave()
        return False, "network_error"


async def remove_user_from_channels():
    """
    First scheduler task (22:30): Try payment for auto-subscribe users
    If payment fails, send warning message about retry in 1 hour
    """
    try:
        course = await Course.objects.afirst()
        private_channel = await PrivateChannel.objects.filter(course_id=course.id).afirst()

        if not course or not private_channel:
            logger.error("Course or private channel not found")
            return

        today = date.today()
        expired_users = User.objects.filter(is_subscribed=True, subscription_end_date=today)

        processed_count = 0
        async for user in expired_users:
            try:
                telegram_id = user.telegram_id

                if not user.is_auto_subscribe:
                    # Users without auto-subscribe: kick immediately
                    await bot.send_message(
                        telegram_id,
                        "Sizning obunangiz tugaganligi uchun yopiq kanaldan chiqarildingiz!"
                    )
                    await bot.ban_chat_member(
                        chat_id=private_channel.private_channel_id,
                        user_id=telegram_id,
                        until_date=120
                    )
                    # Mark as unsubscribed
                    user.is_subscribed = False
                    await user.asave()
                    logger.info(f"Removed non-auto-subscribe user {telegram_id}")

                else:
                    # Users with auto-subscribe: try payment
                    user_card = await UserCard.objects.filter(user_id=telegram_id).afirst()

                    if not user_card:
                        # No card available: kick immediately
                        await bot.send_message(
                            telegram_id,
                            "Sizning obunangiz tugaganligi uchun yopiq kanaldan chiqarildingiz!"
                        )
                        await bot.ban_chat_member(
                            chat_id=private_channel.private_channel_id,
                            user_id=telegram_id
                        )
                        user.is_subscribed = False
                        await user.asave()
                        logger.info(f"Removed user {telegram_id} - no card available")
                    else:
                        # Try automatic payment
                        success, error_type = await process_auto_payment(user, course, user_card)

                        if success:
                            await bot.send_message(telegram_id, "Kartadan pul yechib olindi. Obuna uzaytirildi.")
                            logger.info(f"Successfully renewed subscription for user {telegram_id}")
                        else:
                            # Payment failed: send warning, keep user for 1 hour retry
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
                            # Don't change subscription status - keep for retry

                processed_count += 1

            except Exception as e:
                logger.error(f"Error processing user {user.telegram_id}: {e}")
                continue

        logger.info(f"First attempt: Processed {processed_count} expired subscriptions")

    except Exception as e:
        logger.error(f"Error in remove_user_from_channels: {e}")


def remove_user_from_channels_sync():
    """Sync wrapper for the async function"""
    try:
        print("salom shox")
        asyncio.run(remove_user_from_channels())
    except Exception as e:
        logger.error(f"Error in sync wrapper: {e}")


async def kick_unpaid_users_handler():
    """
    Second scheduler task (23:30): Retry payment for failed users
    If payment still fails, kick them from channel
    """
    try:
        course = await Course.objects.afirst()
        private_channel = await PrivateChannel.objects.filter(course_id=course.id).afirst()

        if not course or not private_channel:
            logger.error("Course or private channel not found")
            return

        today = date.today()
        # Find users whose subscription expired today and are still subscribed
        # (these are users from the first attempt who failed payment)
        expired_users = User.objects.filter(is_subscribed=True, subscription_end_date=today)

        processed_count = 0
        async for user in expired_users:
            try:
                telegram_id = user.telegram_id

                # Only process auto-subscribe users (non-auto users were already kicked in first attempt)
                if user.is_auto_subscribe:
                    user_card = await UserCard.objects.filter(user_id=telegram_id).afirst()

                    if not user_card:
                        # No card: kick user
                        await bot.send_message(
                            telegram_id,
                            "Sizning obunangiz tugaganligi uchun yopiq kanaldan chiqarildingiz!"
                        )
                        await bot.ban_chat_member(
                            chat_id=private_channel.private_channel_id,
                            user_id=telegram_id
                        )
                        user.is_subscribed = False
                        await user.asave()
                        logger.info(f"Final removal: User {telegram_id} - no card")
                    else:
                        # Second payment attempt
                        success, error_type = await process_auto_payment(user, course, user_card)

                        if success:
                            await bot.send_message(telegram_id, "Kartadan pul yechib olindi. Obuna uzaytirildi.")
                            logger.info(f"Second attempt successful for user {telegram_id}")
                        else:
                            # Second attempt failed: kick user
                            if error_type == "insufficient_funds":
                                message = (
                                    "Obunani avtomat uzaytirish uchun kartada yetarli mablag` mavjud emas. "
                                    "Yopiq kanaldan chiqarildingiz!"
                                )
                            else:
                                message = "To'lov amalga oshmadi. Yopiq kanaldan chiqarildingiz!"

                            await bot.send_message(telegram_id, message)
                            await bot.ban_chat_member(
                                chat_id=private_channel.private_channel_id,
                                user_id=telegram_id
                            )
                            user.is_subscribed = False
                            await user.asave()
                            logger.info(f"Final removal: User {telegram_id} after failed second attempt")

                processed_count += 1

            except Exception as e:
                logger.error(f"Error processing user {user.telegram_id} in second attempt: {e}")
                continue

        logger.info(f"Second attempt: Processed {processed_count} users")

    except Exception as e:
        logger.error(f"Error in kick_unpaid_users_handler: {e}")


def kick_unpaid_users_handler_sync():
    """Sync wrapper for the async function"""
    try:
        asyncio.run(kick_unpaid_users_handler())
    except Exception as e:
        logger.error(f"Error in sync wrapper: {e}")


def setup_scheduler():
    """Setup and start the scheduler with jobs - only run once per application"""
    # Check if we should start the scheduler
    # This prevents multiple scheduler instances in multi-worker setups
    if os.environ.get('RUN_SCHEDULER', '').lower() in ('true', '1', 'yes'):
        try:
            # First attempt: Try payment, send warning if fails (22:30)
            scheduler.add_job(
                remove_user_from_channels_sync,  # Use sync wrapper
                trigger='cron',
                hour=22,
                minute=30,
                id='first_payment_attempt'
            )

            # Second attempt: Retry payment, kick if fails again (23:30)
            scheduler.add_job(
                kick_unpaid_users_handler_sync,  # Use sync wrapper
                trigger='cron',
                hour=23,
                minute=30,
                id='second_payment_attempt_and_kick'
            )

            # Start scheduler
            scheduler.start()
            logger.info("Scheduler started successfully with two-stage payment system")

        except Exception as e:
            logger.error(f"Failed to setup scheduler: {e}")
    else:
        logger.info("Scheduler not started - RUN_SCHEDULER environment variable not set")


def shutdown_scheduler():
    """Gracefully shutdown the scheduler"""
    try:
        if scheduler.running:
            scheduler.shutdown()
            logger.info("Scheduler shutdown successfully")
    except Exception as e:
        logger.error(f"Error shutting down scheduler: {e}")


def generate_auth_header():
    """Generate authentication header for Click API"""
    # Your implementation here
    pass


# Only setup scheduler if explicitly enabled
setup_scheduler()
