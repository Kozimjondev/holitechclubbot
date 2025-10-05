import phonenumbers
from aiogram import types
from aiogram.fsm.context import FSMContext
from django.conf import settings

from bot.data.states import UserStates
from users.models import User


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