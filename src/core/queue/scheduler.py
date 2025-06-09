import asyncio
import logging
from datetime import date, timedelta

from aiogram import Bot
from apscheduler.schedulers.background import BackgroundScheduler
from asgiref.sync import sync_to_async
from django.conf import settings

from core.utils.constants import CONSTANTS
from order.models import PrivateChannel, UserCourseSubscription

scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)
scheduler.start()

logger = logging.getLogger(__name__)
from bot.misc import bot


async def remove_user_from_channels(user_id, course_id):
    """Remove user from all channels related to a course"""
    # Get all private channels for this course
    private_channels = await sync_to_async(list)(PrivateChannel.objects.filter(course_id=course_id))

    for channel in private_channels:
        try:
            # Remove user from channel
            await bot.kick_chat_member(
                chat_id=channel.chat_id,
                user_id=user_id
            )
            # Immediately unban to allow them to rejoin if they resubscribe
            await bot.unban_chat_member(
                chat_id=channel.chat_id,
                user_id=user_id,
                only_if_banned=False
            )
            logger.info(f"Removed user {user_id} from channel {channel.chat_id} due to expired subscription")

        except Exception as e:
            logger.error(f"Failed to remove user {user_id} from channel {channel.chat_id}: {e}")


def check_expired_subscriptions():
    """
    Check for expired subscriptions and remove users from channels
    Only removes users from channels if subscription expired 2 days ago
    """
    today = date.today()

    # Find newly expired subscriptions (expired today)
    newly_expired = UserCourseSubscription.objects.filter(
        end_date=today,  # Expired today
        status=CONSTANTS.MembershipStatus.ACTIVE
    )

    # Mark these as expired but don't kick users yet
    for subscription in newly_expired:
        subscription.status = CONSTANTS.MembershipStatus.EXPIRED
        subscription.save()

    logger.info(f"Marked {newly_expired.count()} subscriptions as expired")

    # Find subscriptions that expired 2 days ago and kick users from channels
    grace_period_expired = UserCourseSubscription.objects.filter(
        end_date=today - timedelta(days=2),  # Expired 2 days ago
        status=CONSTANTS.MembershipStatus.EXPIRED
    )

    # Create tasks for each subscription to remove users
    tasks = []
    for subscription in grace_period_expired:
        user_id = subscription.user.telegram_id
        course_id = subscription.course.id

        if not UserCourseSubscription.objects.filter(user_id=user_id, status=CONSTANTS.MembershipStatus.ACTIVE).exists():
            tasks.append(remove_user_from_channels(user_id, course_id))

    # Run all tasks asynchronously if there are any
    if tasks:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(asyncio.gather(*tasks))
        loop.close()

    logger.info(f"Processed {grace_period_expired.count()} grace period expired subscriptions")

async def send_subscription_ending_notification(user_id, course_name):
    """Send notification to user about their subscription ending today"""
    try:
        # Send message to user
        await bot.send_message(
            chat_id=user_id,
            text=(
                f"⚠️ <b>Muhim eslatma!</b>\n\n"
                f"Sizning <b>{course_name}</b> kursiga obunangiz bugun yakunlanadi. "
                f"Agar kursni davom ettirmoqchi bo'lsangiz, iltimos yangi to'lovni amalga oshiring.\n\n"
                f"Aks holda 2 kun ichida shaxsiy kanaldan chiqarib yuborilasiz\n\n"
                f"Savol va takliflar uchun: {settings.ADMIN_USERNAME}"
            ),
            parse_mode="HTML"
        )
        logger.info(f"Sent subscription ending notification to user {user_id} for course {course_name}")
    except Exception as e:
        logger.error(f"Failed to send subscription ending notification to user {user_id}: {e}")


def check_ending_subscriptions():
    """Check for subscriptions ending today and notify users"""
    today = date.today()

    # Find subscriptions that end today and are still active
    ending_subscriptions = UserCourseSubscription.objects.filter(
        end_date=today,
        status=CONSTANTS.MembershipStatus.ACTIVE
    )

    # Create tasks for each ending subscription
    tasks = []
    for subscription in ending_subscriptions:
        user_id = subscription.user.telegram_id
        course_name = subscription.course.name

        # Add task to send notification
        tasks.append(send_subscription_ending_notification(user_id, course_name))

    # Run all tasks asynchronously if there are any
    if tasks:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(asyncio.gather(*tasks))
        loop.close()

    logger.info(f"Processed {ending_subscriptions.count()} ending subscriptions notifications")