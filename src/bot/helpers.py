import time
import logging
from datetime import datetime

import phonenumbers
from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from django.conf import settings

from bot.data.states import UserStates
from bot.functions import get_main_menu_keyboard
from bot.keyboards import back_menu_button
from order.models import PrivateChannel
from users.models import User

logger = logging.getLogger(__name__)


def get_bot_webhook_url():
    return f"{settings.BASE_URL}/v1/bot/webhook/"


def validate_phone_number(phone_number, region='UZ'):
    z = phonenumbers.parse(phone_number, region=region)
    if phonenumbers.is_valid_number(z):
        return str(z.country_code) + str(z.national_number)
    return None


async def get_or_create_user_with_state(message: types.Message, state: FSMContext):
    """
    Get existing user or initiate registration.
    Returns user object or None if registration started.
    """
    await state.clear()

    telegram_id = message.from_user.id
    user = await User.objects.filter(telegram_id=telegram_id).afirst()

    if not user:
        await state.set_state(UserStates.name)
        await message.answer('Ismingizni kiriting:')
        return None

    return user


# helpers.py

async def get_subscription_status(user, telegram_id, bot):
    """
    Check user subscription status and return text + keyboard.
    Returns: (text, keyboard, needs_invite_link)
    """
    today = datetime.today().date()

    if not user.subscription_end_date:
        text = "Siz obuna sotib olmagansiz, sotib olish uchun pastdagi tugmani bosing:"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Obuna sotib olish", callback_data="mini_menu")],
            [back_menu_button()]
        ])
        return text, keyboard, False

    period = (user.subscription_end_date - today).days

    if not user.is_subscribed or period <= 0:
        text = "Sizning obunangiz tugagan! Yangi obuna sotib olish uchun pastdagi tugmani bosing:"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Obuna sotib olish", callback_data="mini_menu")],
            [back_menu_button()]
        ])
        return text, keyboard, False

    base_text = (
        f"Sizning a'zoligingiz tugashiga {period} kun qoldi.\n"
        f"Obuna tugash sanasi: {user.subscription_end_date.strftime('%Y-%m-%d')}\n\n"
    )

    if user.is_auto_subscribe:
        text = base_text + "Obuna tugash sanasida kartangizdan avtomat yechib olinadi!"
    else:
        text = base_text + "Siz obuna bo'lishni bekor qilgansiz. Obuna tugaganidan so'ng yopiq kanaldan chiqarib yuborilasiz!"

    channel = await PrivateChannel.objects.afirst()
    if not channel:
        return text, get_main_menu_keyboard(), False

    try:
        member = await bot.get_chat_member(chat_id=channel.private_channel_id, user_id=telegram_id)

        # User already in channel
        if member.status in ["creator", "administrator", "member", "restricted"]:
            return text, get_main_menu_keyboard(), False

        # User needs invite link
        invite_link = await bot.create_chat_invite_link(
            chat_id=channel.private_channel_id,
            name=f"User_{telegram_id}",
            member_limit=1,
            creates_join_request=False,
            expire_date=int(time.time() + 3600)
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Yopiq Kanalga ulanish", url=invite_link.invite_link)],
            [back_menu_button()]
        ])
        return text, keyboard, True

    except Exception as e:
        logger.error(f"Error checking membership: {e}")
        return text, get_main_menu_keyboard(), False
