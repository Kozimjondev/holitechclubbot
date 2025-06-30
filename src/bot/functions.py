import hashlib
import time

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from django.conf import settings
from django.core.cache import cache

from core.utils.constants import CONSTANTS


def get_user_language(user_id: int) -> str:
    """Get user language from cache, return default if not found"""
    return cache.get(f"user_lang:{user_id}", CONSTANTS.LANGUAGES.UZ)


def set_user_language(user_id: int, language: str):
    """Set user language in cache"""
    cache.set(f"user_lang:{user_id}", language, timeout=None)


def delete_user_language(user_id: int):
    """Delete user language from cache"""
    cache.delete(f"user_lang:{user_id}")


def mask_middle(s):
    return s[:6] + '*' * 6 + s[-4:]


def generate_auth_header() -> str:
    timestamp = str(int(time.time()))
    raw_string = timestamp + settings.CLICK_SECRET_KEY
    digest = hashlib.sha1(raw_string.encode()).hexdigest()

    auth_header = f"{settings.CLICK_MERCHANT_USER_ID}:{digest}:{timestamp}"
    return auth_header


def get_main_menu_button():
    return InlineKeyboardButton(
        text="Asosiy menyu",
        callback_data="main_menu"
    )


def get_main_menu_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Asosiy menyu", callback_data="main_menu")]
        ]
    )
