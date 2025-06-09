from aiogram.utils.keyboard import InlineKeyboardBuilder

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from core.utils.constants import CONSTANTS

MENU_TRANSLATIONS = {
    'uz': {
        'subscription': "💳 Obuna",
        'motivation': "🎥 Motivatsiya",
        'support': "❓ Qo'llab-quvvatlash"
    },
    'ru': {
        'subscription': "💳 Подписка",
        'motivation': "🎥 Мотивация",
        'support': "❓ Поддержка"
    },
    'en': {
        'subscription': "💳 Subscription",
        'motivation': "🎥 Motivation",
        'support': "❓ Support"
    }
}


def get_main_menu(language: str = 'uz'):
    """
    Create main menu keyboard with inline buttons based on language

    Args:
        language (str): Language code ('uz', 'ru', 'en')

    Returns:
        InlineKeyboardMarkup: Keyboard markup with localized buttons
    """
    # Get translations for the specified language, fallback to Uzbek
    translations = MENU_TRANSLATIONS.get(language, MENU_TRANSLATIONS['uz'])

    builder = InlineKeyboardBuilder()

    # Add buttons with localized text
    builder.button(
        text=translations['subscription'],
        callback_data="subscription"
    )
    builder.button(
        text=translations['motivation'],
        callback_data="motivation"
    )
    builder.button(
        text=translations['support'],
        callback_data="support"
    )

    builder.adjust(1)
    return builder.as_markup()


def get_language():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text='Uz', callback_data='lang_uz'),
        InlineKeyboardButton(text='Ru', callback_data='lang_ru'),
        width=2
    )
    return builder.as_markup()


def get_menu_back_keyboard(user_lang=CONSTANTS.LANGUAGES.UZ):
    keyboard = InlineKeyboardBuilder()

    if user_lang == CONSTANTS.LANGUAGES.RU:
        keyboard.button(text="🔙 Назад", callback_data="main_menu")
    else:
        keyboard.button(text="🔙 Orqaga", callback_data="main_menu")

    return keyboard.as_markup()
