from aiogram.utils.keyboard import InlineKeyboardBuilder

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from core.utils.constants import CONSTANTS

MENU_TRANSLATIONS = {
    'uz': {
        'subscription': "💳 Obuna",
        'motivation': "🎥 Motivatsiya",
        'support': "❓ Qo'llab-quvvatlash",
        "subscription_period": "🗓️ Azolik muddati"
    },
    'ru': {
        'subscription': "💳 Подписка",
        'motivation': "🎥 Мотивация",
        'support': "❓ Поддержка",
        "subscription_period": "🗓️ Azolik muddati"
    },
    'en': {
        'subscription': "💳 Subscription",
        'motivation': "🎥 Motivation",
        'support': "❓ Support",
        "subscription_period": "🗓️ Azolik muddati"
    },
}


def get_main_menu(language: str = 'uz'):
    """
    Create main menu keyboard with inline buttons based on language
    """

    builder = InlineKeyboardBuilder()

    # builder.button(
    #     text="Kurslar ro`yhati",
    #     callback_data="active_courses"
    # )
    # builder.button(
    #     text="Mening kartalarim",
    #     callback_data="my_cards"
    # )
    builder.button(
        text="Obunani tekshirish",
        callback_data="check_membership_info"
    )
    builder.button(
        text="Obunani bekor qilish",
        callback_data="cancel_membership"
    )
    # builder.button(
    #     text="Karta qo'shish",
    #     callback_data="add_card"
    # )
    builder.button(
        text="Savol berish",
        url="https://t.me/orif_aka"
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


def back_menu_button():
    return InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")


def get_mini_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Yopiq kanalga to'lov qilish",
                callback_data="subscribe_private_channel"
            )
        ],
        [
            InlineKeyboardButton(
                text="Yopiq kanal haqida ma'lumot",
                callback_data="subscription_info"
            )
        ],
        [
            InlineKeyboardButton(
                text="Savol berish",
                url='https://t.me/yolda_korishamiz_support'
            )
        ]
    ])


def get_mini_back_keyboard(user_lang=CONSTANTS.LANGUAGES.UZ):
    keyboard = InlineKeyboardBuilder()

    if user_lang == CONSTANTS.LANGUAGES.RU:
        keyboard.button(text="Оплата закрытого канала", callback_data='subscribe_private_channel')
        keyboard.button(text="🔙 Назад", callback_data="mini_menu")
        keyboard.adjust(1)
    else:
        keyboard.button(text="Yopiq kanalga to'lov qilish", callback_data='subscribe_private_channel')
        keyboard.button(text="🔙 Orqaga", callback_data="mini_menu")
        keyboard.adjust(1)

    return keyboard.as_markup()