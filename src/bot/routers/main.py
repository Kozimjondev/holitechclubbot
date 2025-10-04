import asyncio
import time
from datetime import timedelta, datetime

import aiohttp
from aiogram import F
from aiogram import Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from bot.data.states import UserStates, UserCardStates
from bot.functions import mask_middle, generate_auth_header, get_main_menu_button, get_main_menu_keyboard
from bot.keyboards import get_main_menu, get_menu_back_keyboard, back_menu_button, get_mini_menu_keyboard, \
    get_mini_back_keyboard
from core.utils.constants import CONSTANTS
from order.models import Course, Order, PrivateChannel, Transaction
from users.models import User, UserCard

router = Router()

COURSE_CHANNEL_ID = -1002675291780


def get_back_keyboard():
    """Create back to main menu keyboard"""
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Asosiy menyuga qaytish", callback_data="main_menu")
    return builder.as_markup(resize_keyboard=True)


async def register_user(user_id, username, first_name, last_name):
    """Register or update user in database"""
    user, created = User.objects.acreate(
        user_id=user_id,
        defaults={
            'username': username,
            'first_name': first_name,
            'last_name': last_name
        }
    )
    return user, created


@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """Handle /start command"""
    telegram_id = message.from_user.id
    user = await User.objects.filter(telegram_id=telegram_id).afirst()
    if not user:
        await state.set_state(UserStates.name)
        await message.answer('Ismingizni kiriting:')
    else:
        if user.is_subscribed and user.subscription_end_date is not None:
            message_text = "Asosiy menyu:"
            await message.answer(message_text, reply_markup=get_main_menu())
            return
        message_text = "Menyu:"
        await message.answer(message_text, reply_markup=get_mini_menu_keyboard())


@router.message(Command('check'))
async def cmd_check(message: types.Message, state: FSMContext):
    await state.clear()

    telegram_id = message.from_user.id
    user = await User.objects.filter(telegram_id=telegram_id).afirst()

    if not user:
        await state.set_state(UserStates.name)
        await message.answer('Ismingizni kiriting:')
        return

    today = datetime.today().date()
    if user.subscription_end_date:
        period = (user.subscription_end_date - today).days

        if user.is_subscribed and period > 0:
            if user.is_auto_subscribe:
                text = (
                    f"Sizning a'zoligingiz tugashiga {period} kun qoldi.\n"
                    f"Obuna tugash sanasi: {user.subscription_end_date.strftime('%Y-%m-%d')}\n\n"
                    f"Obuna tugash sanasida kartangizdan avtomat yechib olinadi!"
                )
            else:
                text = (
                    f"Sizning a'zoligingiz tugashiga {period} kun qoldi.\n"
                    f"Obuna tugash sanasi: {user.subscription_end_date.strftime('%Y-%m-%d')}\n\n"
                    f"Siz obuna bo'lishni bekor qilgansiz. Obuna tugaganidan so'ng yopiq kanaldan chiqarib yuborilasiz!"
                )

            await message.answer(text, parse_mode="Markdown", reply_markup=get_menu_back_keyboard())
            return

        if user.is_subscribed and period <= 0:
            text = "Sizning obunangiz tugagan! Yangi obuna sotib olish uchun pastdagi tugmani bosing:"
        else:
            text = "Siz obuna sotib olmagansiz, sotib olish uchun pastdagi tugmani bosing:"
    else:
        text = "Siz obuna sotib olmagansiz, sotib olish uchun pastdagi tugmani bosing:"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Obuna sotib olish",
            callback_data="mini_menu",
        )],
        [back_menu_button()]
    ])

    await message.answer(text, reply_markup=keyboard)


@router.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    await state.clear()

    telegram_id = message.from_user.id
    user = await User.objects.aget(telegram_id=telegram_id)

    if not user:
        await state.set_state(UserStates.name)
        await message.answer('Ismingizni kiriting:')
        return

    today = datetime.today().date()

    subscription_end = user.subscription_end_date
    period = (subscription_end - today).days if subscription_end else None

    if user.is_subscribed and user.is_auto_subscribe:

        text = (
            f"⚠️ Obunani bekor qilishga ishonchingiz komilmi?\n\n"
            f"Obunani bekor qilmoqchi bo'lsangiz {user.subscription_end_date.strftime('%Y-%m-%d')} sanadan yopiq kanaldan chiqarib yuborilasiz.\n"
            f"Botga ulangan kartangiz ham o`chirib yuboriladi.\n"
            f"Obunani bekor qilasizmi?"
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="Ha", callback_data="confirm_cancel_membership")
        builder.button(text='🔙 Orqaga', callback_data="main_menu")
        builder.adjust(1)

        await message.answer(text, reply_markup=builder.as_markup())
        return

    elif user.is_subscribed and not user.is_auto_subscribe:
        text = (
            f"Sizning a'zoligingiz tugashiga {period} kun qoldi.\n"
            f"Obuna tugash sanasi: {user.subscription_end_date.strftime('%Y-%m-%d')}\n\n"
            "🔴 Obunani bekor qilgansiz."
        )
        builder = InlineKeyboardBuilder()
        builder.button(text='🔙 Orqaga', callback_data="main_menu")
        builder.adjust(1)

        await message.answer(text, parse_mode="Markdown", reply_markup=builder.as_markup())
        return

    else:
        text = (
            "Sizda aktiv obuna yoq"
        )
        builder = InlineKeyboardBuilder()
        builder.button(text='🔙 Orqaga', callback_data="main_menu")
        builder.adjust(1)
        await message.answer(text, parse_mode="Markdown", reply_markup=builder.as_markup())
        return


@router.message(UserStates.name)
async def handle_user_name(message: types.Message, state: FSMContext):
    name = message.text
    await state.update_data(
        name=name
    )
    await state.set_state(UserStates.phone)
    await message.answer('Telefon raqamingizni kiriting:\n'
                        '(Masalan: 998901234567)')


@router.message(UserStates.phone)
async def handle_user_phone(message: types.Message, state: FSMContext):
    telegram_id = message.from_user.id
    phone = message.text

    data = await state.get_data()

    user, _ = await User.objects.aget_or_create(
        telegram_id=telegram_id,
        defaults={
            "first_name": data.get('name'),
            "last_name": message.from_user.last_name,
            "phone": phone
        }
    )

    await state.clear()

    await message.answer("Menyu:", reply_markup=get_mini_menu_keyboard())


@router.callback_query(lambda c: c.data == 'subscription_info')
async def handle_subscription_info(callback_query: CallbackQuery, state: FSMContext):
    text = (
        "*Assalomu alaykum!*\n"
        "*Xush kelibsiz! 👋*\n\n"

        "Bu yerda siz:\n"
        "✅ Boshlang‘ich sport ko‘nikmalarini o‘rganasiz\n"
        "✅ To‘g‘ri ovqatlanish haqida foydali ma’lumotlarga ega bo‘lasiz\n"
        "✅ Jonli efirda savollarga javoblar\n\n"

        "📆 *Oyiga kamida 2 marotaba* barcha ishtirokchilar bilan jonli savol-javob efirlari tashkil qilinadi. Bunda o‘zingizni qiynayotgan barcha savollaringiz hamda muammolaringizga yechim olishingiz mumkin bo‘ladi.\n\n"

        "✅ Qo‘shimchasiga — o‘z sohasida ekspert bo‘lgan *urolog*, *androlog* va *endokrinolog* shifokorlardan sog‘lom turmush tarzi va salomatlik bo‘yicha kerakli tavsiyalar olasiz!\n"
        "🧠 Va albatta miyani rivojlantirish bo‘yicha ham video darslar joylangan!\n\n"

        "🎁 Shuningdek, sizni bonus darslar ham kutmoqda!\n"
        "🤓 Har oy sizning qiziqishlaringiz asosida maxsus podkastlar tayyorlaymiz.\n\n"

        "📅 *Mashqlar haftalarga bo‘lingan:*\n"
        "Haftasiga 3 martalik video darsliklar joylangan.\n\n"

        "📍 *1-hafta* – butun tanani uyg‘otishga qaratilgan umumiy mashqlar (aktivlashtiruvchi harakatlar)\n"
        "📍 *2-hafta* va undan keyin – tananing ma’lum mushak guruhlariga yo‘naltirilgan maxsus mashqlar\n\n"
    )

    await callback_query.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_mini_back_keyboard()
    )


@router.callback_query(F.data == "subscribe_private_channel")
async def handle_subscribe_click(callback: types.CallbackQuery):
    offer_url = settings.OFERTA_URL

    text = (
        "📄 Ommaviy ofertani o'qib chiqing va roziligingizni tasdiqlang.\n\n"
        f"[📎 Ommaviy oferta matni]({offer_url})"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Roziman", callback_data="accept_offer"),
            InlineKeyboardButton(text="❌ Rozi emasman", callback_data="mini_menu"),
        ]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(lambda c: c.data == 'mini_menu')
async def callback_query_mini_menu(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text("Menyu:", reply_markup=get_mini_menu_keyboard())


@router.callback_query(lambda c: c.data == "decline_offer")
async def handle_decline_offer(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Ommaviy aferta shartlariga rozi bolmaganingiz uchun botdan foydalana olmaysiz",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="subscribe_private_channel")]
            ]
        )
    )


@router.callback_query(F.data.in_(["accept_offer", "active_courses"]))
async def handle_offer_accepted(callback: types.CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    user = await User.objects.aget(telegram_id=telegram_id)

    if callback.data == "accept_offer":
        user.agreed_to_terms = True
        user.is_auto_subscribe = True
        await user.asave()

    confirmed_cards = UserCard.objects.filter(user=user, is_confirmed=True)
    has_card = await sync_to_async(confirmed_cards.exists)()

    # if not has_card:
    #     await callback.message.edit_text(
    #         "💳 Iltimos karta raqaningizni kiriting:\n"
    #         "Masalan: 8600....0509"
    #     )
    #     await state.set_state(UserCardStates.card_number)
    #     return

    courses = await sync_to_async(list)(Course.objects.all())

    if not courses:
        await callback.message.edit_text("Hozircha hech qanday kurs mavjud emas.")
        return

    text = "💰 *Yopiq kanal uchun kurslar (price list):*\n\n"
    keyboard_buttons = []

    for course in courses:
        text += f"📌 *{course.name or 'Nomsiz kurs'}*\n"
        text += f"💵 Narx: {course.amount} so'm\n"
        if course.period:
            text += f"🕒 Davomiylik: {course.period} kun\n"
        if course.description:
            text += f"📝 {course.description}\n"
        text += "\n"

        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"🔐 {course.name or 'Obuna bo\'lish'}",
                callback_data=f"check_payment_type_{course.id}"
            )
        ])

    keyboard_buttons.append([back_menu_button()])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")


@router.callback_query(F.data.startswith("check_payment_type_"))
async def handle_payment_type(callback: types.CallbackQuery, state: FSMContext):
    course_id = int(callback.data.split("_")[-1])
    course = await Course.objects.aget(id=course_id)

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Uzcard/Humo", callback_data=f"subscribe_course_{course_id}")
    keyboard.button(text="Chet eldan", url='https://t.me/tribute/app?startapp=sxww')
    keyboard.button(text="Orqaga", callback_data="active_courses")
    keyboard.adjust(1)
    await callback.message.edit_text(
        "📢 *Yopiq kanalgа obuna bo‘lish narxi:*\n"
        f"*1 oylik – narxi {course.amount} so‘m*\n"
        "*Chet el uchun – 4€*\n\n"
        "🕒 *To‘lov qilingandan so‘ng, har 30 kunda obuna uchun to‘lov avtomatik tarzda yechiladi.*\n"
        "*To‘lovni vaqtida qilmagan foydalanuvchi kanaldan chiqarib yuboriladi.*\n\n"
        "💳 *Kiritilgan kartalar ro'yxati:*\n"
        "*To‘lov uchun kartani tanlang:*",
        reply_markup=keyboard.as_markup(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("subscribe_course_"))
async def handle_course_subscription(callback: types.CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id

    try:
        course_id = int(callback.data.split("_")[-1])
        course = await Course.objects.aget(id=course_id)
    except (ValueError, Course.DoesNotExist):
        await callback.message.answer("❌ Kurs topilmadi.")
        return

    try:
        user = await User.objects.aget(telegram_id=telegram_id)
    except User.DoesNotExist:
        await callback.message.answer("❌ Foydalanuvchi topilmadi.")
        return

    confirmed_cards = UserCard.objects.filter(user=user, is_confirmed=True)
    has_card = await sync_to_async(confirmed_cards.exists)()

    if not has_card:
        await callback.message.edit_text(
            "💳 Sizda faol karta mavjud emas. Davom etish uchun iltimos 16 talik karta raqamini kiriting:\n"
            "Masalan: 8600....0509"
        )
        await state.set_state(UserCardStates.card_number)
        return

    keyboard_buttons = []

    async for card in confirmed_cards:
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{card.marked_pan} karta",
                callback_data=f"make_payment_{card.id}_{course.id}"
            )
        ])
    keyboard_buttons.append([
        InlineKeyboardButton(
            text="Asosiy menyu", callback_data="main_menu"
        )
    ])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await callback.message.edit_text(
        "📢 *Yopiq kanalgа obuna bo‘lish narxi:*\n"
        f"*1 oylik – narxi {course.amount} so‘m*\n\n"
        "🕒 *To‘lov qilingandan so‘ng har 30 kun ichida obuna uchun to‘lovi avtomatik tarzda yechiladi.*\n"
        "To‘lovni vaqtida qilmagan foydalanuvchi kanaldan chiqarib yuboriladi.\n\n"
        "💳 *Kiritilgan kartalar ro'yxati.*\n"
        "*To‘lov uchun kartani tanlang:*",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("make_payment_"))
async def handle_make_payment(callback: types.CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    await state.clear()

    try:
        course_id = int(callback.data.split("_")[-1])
        card_id = int(callback.data.split("_")[-2])
    except (ValueError, IndexError):
        await callback.message.edit_text("❌ Ma'lumotlar noto‘g‘ri.", reply_markup=get_main_menu_keyboard())
        return

    try:
        course = await Course.objects.aget(id=course_id)
    except Course.DoesNotExist:
        await callback.message.edit_text("❌ Kurs topilmadi.", reply_markup=get_main_menu_keyboard())
        return

    user = await User.objects.aget(telegram_id=telegram_id)
    card = await UserCard.objects.filter(user=user, id=card_id, is_confirmed=True).afirst()
    if not card:
        await callback.message.edit_text("❌ Karta topilmadi yoki tasdiqlanmagan.", reply_markup=get_main_menu_keyboard())
        return

    order = await Order.objects.acreate(
        user=user,
        amount=course.amount,
        course=course
    )

    url = f'{settings.CLICK_BASE_URL}/payment'

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Auth": generate_auth_header(),
    }

    payload = {
        "service_id": int(settings.CLICK_SERVICE_ID),
        "card_token": str(card.card_token),
        "amount": float(course.amount),
        "transaction_parameter": str(order.id)
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            res_json = await response.json()

    if res_json.get("error_code") == -5017:
        order.status = CONSTANTS.PaymentStatus.FAILED
        order.payment_id = res_json.get("payment_id")
        await order.asave()
        await callback.message.edit_text(
            "Kartada mablag` yetarli emas. Hisobingizdagi mablag'ni to'ldiring va qayta urinib koring", reply_markup=get_main_menu_keyboard()
        )
        return
    elif res_json.get("error_code"):
        order.status = CONSTANTS.PaymentStatus.FAILED
        order.payment_id = res_json.get("payment_id")
        await order.asave()
        await callback.message.edit_text(
            "To'lov amalga oshmadi. Qaytadan urinib koring", reply_markup=get_main_menu_keyboard()
        )
        return

    order.status = CONSTANTS.PaymentStatus.SUCCESS
    order.payment_id = res_json.get("payment_id")
    await order.asave()

    if not user.is_subscribed:
        user.subscription_start_date = timezone.now().date()
        user.is_subscribed = True

    user.subscription_end_date = timezone.now().date() + timedelta(days=course.period)
    await user.asave()

    private_channel = await PrivateChannel.objects.filter(course=course).afirst()

    if not private_channel:
        await callback.message.answer("❌ Kanal topilmadi.")
        return

    expire_timestamp = int(time.time() + 3600)

    try:
        invite_link = await callback.bot.create_chat_invite_link(
            chat_id=private_channel.private_channel_id,
            name=f"User_{telegram_id}",
            member_limit=1,
            creates_join_request=False,
            expire_date=expire_timestamp
        )
    except Exception as e:
        await callback.message.edit_text("❌ Taklif havolasini yaratishda xatolik yuz berdi.", reply_markup=get_main_menu_keyboard())
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Yopiq Kanalga ulanish",
                url=invite_link.invite_link
            )
        ],
        [
            InlineKeyboardButton(
                text="Savol berish",
                url='https://t.me/yolda_korishamiz_support'
            )
        ],
        [get_main_menu_button()]
    ])

    await callback.message.edit_text(
        "✅ *Tabriklaymiz!* Siz *\"To'xtab qolma atlet\"* kanali a'zosiga aylandingiz! 💪\n\n"
        "Sizning 1 oylik to'lovingiz muvaffaqiyatli qabul qilindi — endi yopiq kanal siz uchun ochiq!\n\n"
        "👉 Avvalo pastdagi havolani bosib kanalga o'ting.\n"
        "🔔 So'ngra kanalda *\"Подписаться\"* tugmasini bosib, a'zo bo'ling.\n\n"
        "⚡️ *Eslatma:* tugma faqat 1 soat davomida faol!\n"
        "🔁 Agar havola ishlamasa, birozdan so'ng yana urinib ko'ring.\n\n"
        "👇 Pastdagi *\"Yopiq kanalga o'tish\"* tugmasini bosing va yangi bosqichni boshlang!",
        parse_mode="Markdown",
        reply_markup=keyboard
    )


@router.message(UserCardStates.card_number)
async def handle_card_number(message: types.Message, state: FSMContext):
    raw_input = message.text
    card_number = raw_input.replace(" ", "")

    if len(card_number) != 16 or not card_number.isdigit():
        await state.set_state(UserCardStates.card_number)
        await message.answer("❌ Karta raqami 16 ta raqamdan iborat bo'lishi kerak.")
        return

    await state.update_data(card_number=card_number)
    await state.set_state(UserCardStates.card_pan)
    await message.answer("✅ Endi karta tugash muddatini kiriting. Masalan: 06/29")


@router.message(UserCardStates.card_pan)
async def handle_card_pan(message: types.Message, state: FSMContext):
    card_pan = message.text
    if '/' not in card_pan:
        await state.set_state(UserCardStates.card_pan)
        await message.answer("Iltimos tog`ri malumot kiriting, Masalan: 06/29")
        return

    card_pan = message.text.replace("/", "")
    if len(card_pan) != 4:
        await state.set_state(UserCardStates.card_pan)
        await message.answer("Iltimos togri raqamni kiriting")
        return

    data = await state.get_data()
    card_number = data.get("card_number")

    payload = {
        "service_id": int(settings.CLICK_SERVICE_ID),
        "card_number": str(card_number),
        "expire_date": str(card_pan),
        "temporary": 0
    }
    headers = {
        'Content-Type': 'application/json',
        "Accept": "application/json"
    }

    url = f'{settings.CLICK_BASE_URL}/request'

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            res_json = await response.json()

    if res_json.get('error_code'):
        await state.clear()

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔒 Obuna bo'lish", callback_data="subscribe_private_channel")]
        ])

        await message.answer("❌ Karta qoshishda xatolik yuz berdi.", reply_markup=keyboard)
        return

    if not res_json.get("card_token"):
        await message.answer("❌ Karta qoshishda xatolik yuz berdi.")
        await state.clear()
        return

    user = await User.objects.aget(telegram_id=message.from_user.id)

    marked_pan = mask_middle(card_number)

    await UserCard.objects.acreate(
        user=user,
        marked_pan=marked_pan,
        expire_date=card_pan,
        card_token=res_json['card_token'],
    )

    await message.answer("Telefon raqamingizga yuborilgan kodni kiriting:")
    await state.set_state(UserCardStates.confirmation)


@router.message(UserCardStates.confirmation)
async def handle_confirmation(message: types.Message, state: FSMContext):
    sms_code = message.text
    if not sms_code.isdigit() or len(sms_code) != 6:
        await state.set_state(UserCardStates.confirmation)
        await message.answer("❌ Faqat 6 xonali raqam kiritilishi kerak.")
        return

    user = await User.objects.aget(telegram_id=message.from_user.id)
    the_last_created_card = await UserCard.objects.filter(user=user).alast()

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Auth": generate_auth_header(),
    }
    url = f'{settings.CLICK_BASE_URL}/verify'

    payload = {
        "service_id": int(settings.CLICK_SERVICE_ID),
        "card_token": str(the_last_created_card.card_token),
        "sms_code": int(sms_code),
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            res_json = await response.json()

    if res_json.get('error_code'):
        await state.clear()

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔒 Obuna bo'lish", callback_data="subscribe_private_channel")]
        ])

        await message.answer("❌ Noto‘g‘ri ma’lumot kiritildi yoki karta qoshishda xatolik yuz berdi.", reply_markup=keyboard)
        return


    the_last_created_card.marked_pan = res_json.get('card_number')
    the_last_created_card.is_confirmed = True
    await the_last_created_card.asave()
    await state.clear()
    await message.answer(
        "Karta muvaffaqiyatli qoshildi. Kurslar royxatiga o`tib kerakli kursga tolov qiling:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Kurslarga o`tish", callback_data="active_courses")]
        ]))


@router.callback_query(lambda c: c.data == 'my_cards')
async def handle_my_cards(callback: types.CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id

    user = await User.objects.aget(telegram_id=telegram_id)

    my_cards = UserCard.objects.filter(user=user, is_confirmed=True)

    if not my_cards:
        await callback.message.edit_text("Hozircha sizda ulangan kartalar yoq.", reply_markup=get_menu_back_keyboard())

    keyboard_buttons = []

    async for card in my_cards:
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{card.marked_pan} karta",
                callback_data=f"delete_{card.id}",
            )
        ])
    keyboard_buttons.append([back_menu_button()])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await callback.message.edit_text(
        "💳 Tasdiqlangan kartalar ro`yhati. Kartani botdan o`chirish uchun ustiga bosing:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


@router.callback_query(lambda c: c.data == 'check_membership_info')
async def handle_check_membership_info(callback: types.CallbackQuery, state: FSMContext):
    try:
        telegram_id = callback.from_user.id
        user = await User.objects.filter(telegram_id=telegram_id).afirst()

        if not user:
            text = "Foydalanuvchi topilmadi. Iltimos, /start buyrug'ini bosing."
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [back_menu_button()]
            ])
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer()
            return


        today = datetime.today().date()
        if user.subscription_end_date:
            period = (user.subscription_end_date - today).days

            if user.is_subscribed and period > 0:
                base_text = (
                    f"Sizning a'zoligingiz tugashiga {period} kun qoldi.\n"
                    f"Obuna tugash sanasi: {user.subscription_end_date.strftime('%Y-%m-%d')}\n\n"
                )

                if user.is_auto_subscribe:
                    text = base_text + "Obuna tugash sanasida kartangizdan avtomat yechib olinadi!"
                else:
                    text = base_text + "Siz obuna bo'lishni bekor qilgansiz. Obuna tugaganidan so'ng yopiq kanaldan chiqarib yuborilasiz!"

                await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_menu_back_keyboard())
                await callback.answer()
                return

            if user.is_subscribed and period <= 0:
                text = "Sizning obunangiz tugagan! Yangi obuna sotib olish uchun pastdagi tugmani bosing:"
            else:
                text = "Siz obuna sotib olmagansiz, sotib olish uchun pastdagi tugmani bosing:"
        else:
            text = "Siz obuna sotib olmagansiz, sotib olish uchun pastdagi tugmani bosing:"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="Obuna sotib olish",
                callback_data="mini_menu",
            )],
            [back_menu_button()]
        ])

        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()

    except Exception as e:
        text = "Xatolik yuz berdi. Iltimos, qayta urinib ko'ring."
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [back_menu_button()]
        ])
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer("Xatolik yuz berdi")
        print(f"Error in handle_check_membership_info: {e}")


@router.callback_query(F.data == 'cancel_membership')
async def handle_cancel_membership(callback: types.CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    user = await User.objects.aget(telegram_id=telegram_id)
    today = datetime.today()

    subscription_end = user.subscription_end_date
    period = (subscription_end - today.date()).days if subscription_end else None

    if user.is_subscribed and user.is_auto_subscribe:

        text = (
            f"⚠️ Obunani bekor qilishga ishonchingiz komilmi?\n\n"
            f"Obunani bekor qilmoqchi bo'lsangiz {user.subscription_end_date.strftime('%Y-%m-%d')} sanadan yopiq kanaldan chiqarib yuborilasiz.\n"
            f"Botga ulangan kartangiz ham o`chirib yuboriladi.\n"
            f"Obunani bekor qilasizmi?"
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="Ha", callback_data="confirm_cancel_membership")
        builder.button(text='🔙 Orqaga', callback_data="main_menu")
        builder.adjust(1)

        await callback.message.edit_text(text, reply_markup=builder.as_markup())
        return

    elif user.is_subscribed and not user.is_auto_subscribe:
        text = (
            f"Sizning a'zoligingiz tugashiga {period} kun qoldi.\n"
            f"Obuna tugash sanasi: {user.subscription_end_date.strftime('%Y-%m-%d')}\n\n"
            "🔴 Obunani bekor qilgansiz."
        )
        builder = InlineKeyboardBuilder()
        builder.button(text='🔙 Orqaga', callback_data="main_menu")
        builder.adjust(1)

        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
        return

    elif not user.is_subscribed and not user.is_auto_subscribe:
        text = (
            "Sizda aktiv obuna yoq"
        )
        builder = InlineKeyboardBuilder()
        builder.button(text='🔙 Orqaga', callback_data="main_menu")
        builder.adjust(1)
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
        return


@router.callback_query(lambda c: c.data == 'confirm_cancel_membership')
async def handle_confirm_cancel_membership(callback: types.CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    user = await User.objects.aget(telegram_id=telegram_id)
    user.is_auto_subscribe = False
    await user.asave()

    builder = InlineKeyboardBuilder()
    builder.button(text='🔙 Orqaga', callback_data="main_menu")
    builder.adjust(1)

    user_card = await UserCard.objects.filter(user=user, is_confirmed=True).afirst()
    if not user_card:
        await callback.message.edit_text("Sizda ulangan kartalar yo'q", reply_markup=builder.as_markup())
        return

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Auth": generate_auth_header(),
    }
    payload = {
        "service_id": int(settings.CLICK_SERVICE_ID),
        "card_token": str(user_card.card_token),
    }

    url = f'{settings.CLICK_BASE_URL}/{payload['service_id']}/{payload["card_token"]}'

    async with aiohttp.ClientSession() as session:
        async with session.delete(url, headers=headers, json=payload) as response:
            res_json = await response.json()

    print(res_json)
    await user_card.adelete()
    await callback.message.edit_text("Obuna o`chirildi.", reply_markup=builder.as_markup())


@router.callback_query(F.data == "main_menu")
async def return_to_main_menu(callback: types.CallbackQuery, state: FSMContext):
    """Return to main menu"""
    message_text = "Asosiy menyu:"
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(message_text, reply_markup=get_main_menu())


@router.callback_query(F.data.in_(["motivation"]))
async def handle_motivation(callback: types.CallbackQuery, state: FSMContext):
    """Process inline keyboard button presses"""
    await callback.answer()

    user_id = callback.from_user.id

    # Get user language
    user_lang = cache.get(f"user_lang:{user_id}")
    if not user_lang:
        user = await User.objects.aget(telegram_id=user_id)
        user_lang = user.language
        cache.set(f"user_lang:{user_id}", user_lang, timeout=None)
    else:
        user = await User.objects.filter(telegram_id=user_id).afirst()

    if user.is_staff:
        # Staff menu - options to send motivation content
        keyboard = InlineKeyboardBuilder()

        if user_lang == CONSTANTS.LANGUAGES.RU:
            keyboard.button(text="📹 Отправить мотивационное видео", callback_data="send_motivation_video")
            keyboard.button(text="📝 Отправить мотивационный текст", callback_data="send_motivation_text")
            keyboard.button(text="🔙 Назад", callback_data="main_menu")

            text = (
                "👨‍💼 Панель администратора - Мотивация\n\n"
                "Выберите тип контента для отправки всем пользователям:"
            )
        else:  # Uzbek
            keyboard.button(text="📹 Motivatsion video yuborish", callback_data="send_motivation_video")
            keyboard.button(text="📝 Motivatsion matn yuborish", callback_data="send_motivation_text")
            keyboard.button(text="🔙 Orqaga", callback_data="main_menu")

            text = (
                "👨‍💼 Admin paneli - Motivatsiya\n\n"
                "Barcha foydalanuvchilarga yuborish uchun kontent turini tanlang:"
            )

        keyboard.adjust(1)
        await callback.message.edit_text(text, reply_markup=keyboard.as_markup())

    else:
        # Regular user - show motivation content
        if user_lang == CONSTANTS.LANGUAGES.RU:
            text = (
                "🎥 Мотивационные материалы\n\n"
                "Здесь вы найдете вдохновляющие видео успешных спикеров, "
                "которые помогут вам поверить в свои силы и преодолеть страх публичных выступлений.\n\n"
                "Регулярно посещайте этот раздел для поддержания мотивации!"
            )
        else:  # Uzbek
            text = (
                "🎥 Motivatsion materiallar\n\n"
                "Bu yerda siz muvaffaqiyatli notiqlarning ilhomlantiruvchi videolarini topasiz, "
                "ular sizga o'z kuchingizga ishonish va omma oldida nutq so'zlashdagi qo'rquvni yengishga yordam beradi.\n\n"
                "Motivatsiyani saqlab qolish uchun bu bo'limga tez-tez tashrif buyuring!"
            )

        await callback.message.edit_text(text, reply_markup=get_menu_back_keyboard(user_lang))


# Handler for sending motivation video
@router.callback_query(F.data == "send_motivation_video")
async def send_motivation_video_prompt(callback: types.CallbackQuery, state: FSMContext):
    """Prompt staff to send motivation video"""
    await callback.answer()

    user_id = callback.from_user.id
    user_lang = cache.get(f"user_lang:{user_id}")

    if user_lang == CONSTANTS.LANGUAGES.RU:
        text = "📹 Отправьте мотивационное видео для рассылки всем пользователям:"
    else:
        text = "📹 Barcha foydalanuvchilarga yuborish uchun motivatsion videoni yuboring:"

    await state.set_state("waiting_motivation_video")
    await callback.message.edit_text(text, reply_markup=get_menu_back_keyboard(user_lang))


# Handler for sending motivation text
@router.callback_query(F.data == "send_motivation_text")
async def send_motivation_text_prompt(callback: types.CallbackQuery, state: FSMContext):
    """Prompt staff to send motivation text"""
    await callback.answer()

    user_id = callback.from_user.id
    user_lang = cache.get(f"user_lang:{user_id}")

    if user_lang == CONSTANTS.LANGUAGES.RU:
        text = "📝 Отправьте мотивационный текст для рассылки всем пользователям:"
    else:
        text = "📝 Barcha foydalanuvchilarga yuborish uchun motivatsion matnni yuboring:"

    await state.set_state("waiting_motivation_text")
    await callback.message.edit_text(text, reply_markup=get_menu_back_keyboard(user_lang))


# Handler for receiving motivation video from staff
@router.message(StateFilter("waiting_motivation_video"), F.video)
async def receive_motivation_video(message: types.Message, state: FSMContext):
    """Send motivation video to all users"""
    await state.clear()

    user_id = message.from_user.id
    user_lang = cache.get(f"user_lang:{user_id}")

    # Get all users
    users = User.objects.all()
    sent_count = 0
    failed_count = 0

    async for user in users:
        try:
            await message.bot.send_video(
                chat_id=user.telegram_id,
                video=message.video.file_id,
                caption="🎥 Motivatsion video" if user.language == CONSTANTS.LANGUAGES.UZ else "🎥 Мотивационное видео"
            )
            sent_count += 1
        except Exception as e:
            failed_count += 1
            continue

    if user_lang == CONSTANTS.LANGUAGES.RU:
        result_text = f"✅ Видео отправлено!\n\nУспешно: {sent_count}\nНе удалось: {failed_count}"
    else:
        result_text = f"✅ Video yuborildi!\n\nMuvaffaqiyatli: {sent_count}\nXatolik: {failed_count}"

    await message.answer(result_text, reply_markup=get_main_menu())


# Handler for receiving motivation text from staff
@router.message(StateFilter("waiting_motivation_text"), F.text)
async def receive_motivation_text(message: types.Message, state: FSMContext):
    """Send motivation text to all users"""
    await state.clear()

    user_id = message.from_user.id
    user_lang = cache.get(f"user_lang:{user_id}")

    motivation_text = message.text

    # Get all users
    users = User.objects.all()
    sent_count = 0
    failed_count = 0

    async for user in users:
        try:
            prefix = "🎥 Motivatsion matn:\n\n" if user.language == CONSTANTS.LANGUAGES.UZ else "🎥 Мотивационный текст:\n\n"
            await message.bot.send_message(
                chat_id=user.telegram_id,
                text=prefix + motivation_text
            )
            sent_count += 1
        except Exception as e:
            failed_count += 1
            continue

    if user_lang == CONSTANTS.LANGUAGES.RU:
        result_text = f"✅ Текст отправлен!\n\nУспешно: {sent_count}\nНе удалось: {failed_count}"
    else:
        result_text = f"✅ Matn yuborildi!\n\nMuvaffaqiyatli: {sent_count}\nXatolik: {failed_count}"

    await message.answer(result_text, reply_markup=get_main_menu())


@router.message(Command("send_payment_link"))
async def send_payment_link(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user = await User.objects.filter(telegram_id=user_id).afirst()
    if not user:
        return
    elif not user.is_superuser:
        await message.answer(
            "Sizda foydalana olmaysiz, faqat admin user foydalana oladi"
        )
        return
    bot = message.bot

    successful_transactions = Transaction.objects.filter(
        state=Transaction.SUCCESSFULLY,
        payment_method=CONSTANTS.PaymentMethod.CLICK
    ) # todo: change queryset to Subscription model

    # successful_transactions = User.objects.all()
    channel = await PrivateChannel.objects.afirst()

    channel_id = channel.private_channel_id

    sent_count = 0
    already_member_count = 0
    error_count = 0

    async for transaction in successful_transactions:
        telegram_id = transaction.user_id
        # telegram_id = transaction.telegram_id
        try:
            # Check if user is already a member of the channel
            member = await bot.get_chat_member(chat_id=channel_id, user_id=telegram_id)

            # Check membership status
            # Statuses: creator, administrator, member, restricted, left, kicked
            if member.status in ["creator", "administrator", "member", "restricted"]:
                # User is already in the channel
                already_member_count += 1
                print(f"User {telegram_id} is already a member")
                continue

            # User is not a member (status is "left" or "kicked")
            # Create one-time invite link with 24-hour expiry
            expire_date = datetime.now() + timedelta(hours=24)
            expire_timestamp = int(expire_date.timestamp())

            invite_link = await bot.create_chat_invite_link(
                chat_id=channel_id,
                name=f"Payment link for user {telegram_id}",
                expire_date=expire_timestamp,
                member_limit=1,  # One-time use
                creates_join_request=False
            )

            await bot.send_message(
                chat_id=telegram_id,
                text=(
                    f"🎉 To'lovingiz tasdiqlandi!\n\n"
                    f"🔗 Premium kanalimizga maxsus havola:\n\n"
                    f"{invite_link.invite_link}\n\n"
                    f"⚠️ Muhim:\n"
                    f"• Havola 24 soat ichida amal qiladi\n"
                    f"• Faqat bir marta ishlatiladi\n"
                    f"• Darhol qo'shilish uchun havolani bosing\n\n"
                    f"Xush kelibsiz! 🚀"
                )
            )

            sent_count += 1
            print(f"Invite link sent to user {telegram_id}")
            await asyncio.sleep(0.1)
        except TelegramBadRequest as e:
            error_count += 1
            print(f"Error for user {telegram_id}: {e}")
            continue

        except Exception as e:
            error_count += 1
            print(f"Unexpected error for user {telegram_id}: {e}")
            continue

    await message.answer(
        f"✅ Havolalar yuborish yakunlandi!\n\n"
        f"📤 Yuborildi: {sent_count}\n"
        f"👥 Allaqachon a'zo: {already_member_count}\n"
        f"❌ Xatoliklar: {error_count}\n"
        f"📊 Jami tranzaksiyalar: {successful_transactions.count()}"
    )


# Catch any other callbacks not specified above
@router.callback_query()
async def unknown_callback(callback: types.CallbackQuery):
    await callback.answer()
    text = "Funksional ishlab chiqilmoqda. Iltimos, bosh menyuga qayting."
    await callback.message.edit_text(text, reply_markup=get_back_keyboard())