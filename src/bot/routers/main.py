import time
import uuid

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from django.core.cache import cache
from django.conf import settings

from aiogram.fsm.context import FSMContext
from aiogram import Router, types
from aiogram.filters.command import CommandStart, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import ReplyKeyboardRemove
from asgiref.sync import sync_to_async
from aiogram.filters import StateFilter

from bot.keyboards import get_language, get_main_menu, get_menu_back_keyboard
from core.utils.constants import CONSTANTS
from order.models import Course, UserCourseSubscription, Order, PrivateChannel
from users.models import User

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

    user, _ = await sync_to_async(User.objects.get_or_create)(
        telegram_id=telegram_id,
        defaults={
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name
        }
    )
    # await message.answer("Tilni tanlang:", reply_markup=get_language())
    await message.answer('Asosiy menyu:', reply_markup=get_main_menu())


@router.callback_query(F.data == 'lang_uz')
async def set_uzbek_language(callback: types.CallbackQuery):
    user_id = callback.from_user.id

    cache.set(f"user_lang:{user_id}", CONSTANTS.LANGUAGES.UZ, timeout=None)
    user = await User.objects.aget(telegram_id=user_id)
    user.language = CONSTANTS.LANGUAGES.UZ
    await user.asave()

    await callback.message.edit_text('Asosiy menyu:', reply_markup=get_main_menu())
    await callback.answer()


@router.callback_query(F.data == 'lang_ru')
async def set_russian_language(callback: types.CallbackQuery):
    user_id = callback.from_user.id

    cache.set(f"user_lang:{user_id}", CONSTANTS.LANGUAGES.RU, timeout=None)
    user = await User.objects.aget(telegram_id=user_id)
    user.language = CONSTANTS.LANGUAGES.RU
    await user.asave()

    await callback.message.edit_text('Главное меню:', reply_markup=get_main_menu('ru'))
    await callback.answer()


@router.callback_query(F.data == "main_menu")
async def return_to_main_menu(callback: types.CallbackQuery, state: FSMContext):
    """Return to main menu"""
    user_id = callback.from_user.id

    user_lang = cache.get(f"user_lang:{user_id}")
    if not user_lang:
        user = await User.objects.aget(telegram_id=user_id)
        user_lang = user.language
        cache.set(f"user_lang:{user_id}", user_lang, timeout=None)

    if user_lang == CONSTANTS.LANGUAGES.RU:
        message_text = "Главное меню:"
    else:
        message_text = "Asosiy menyu:"

    await callback.answer()
    await callback.message.edit_text(message_text, reply_markup=get_main_menu(user_lang))


@router.callback_query(F.data == "courses")
async def cmd_courses(callback: types.CallbackQuery, state: FSMContext):
    """Handle /courses command"""
    try:
        # Delete previous message
        await callback.message.delete()
    except Exception:
        pass

    # Check if user has subscription
    customer_subs = await UserCourseSubscription.objects.filter(
        user__telegram_id=callback.from_user.id,
        is_active=True
    ).afirst()

    if not customer_subs:
        await callback.message.answer(
            "Siz obuna sotib olmagansiz. Kursni ko'rish uchun iltimos obuna sotib oling!",
            reply_markup=get_back_keyboard()
        )
        return

    # Create keyboard with day buttons
    keyboard = InlineKeyboardBuilder()

    # Add buttons for days 1-10
    for day in range(1, 11):
        keyboard.button(
            text=f"🏋️‍♂️ {day} - kun",
            callback_data=f"course_day_{day}"
        )

    # Add back button to main menu
    keyboard.button(text="🏠 Asosiy menyu", callback_data="main_menu")

    # Adjust to 1 button per row
    keyboard.adjust(1)

    text = (
        "📚 <b>Notiqlik kursi - 10 kunlik dastur</b>\n\n"
        "Quyida kurs kunlari ro'yxati keltirilgan. "
        "O'rganmoqchi bo'lgan kunni tanlang:"
    )

    await callback.message.answer(text, reply_markup=keyboard.as_markup(), parse_mode="HTML")


@router.callback_query(F.data == "subscription")
async def cmd_subscription(callback: types.CallbackQuery, state: FSMContext):
    """Handle /subscription command"""

    user_id = callback.from_user.id

    user_lang = cache.get(f"user_lang:{user_id}")
    if not user_lang:
        user = await User.objects.aget(telegram_id=user_id)
        user_lang = user.language
        cache.set(f"user_lang:{user_id}", user_lang, timeout=None)

    course_amounts = Course.objects.all()

    keyboard = InlineKeyboardBuilder()

    async for course in course_amounts:
        keyboard.button(text=f"{course.name}", callback_data=f"select_amount_{course.id}")

    if user_lang == CONSTANTS.LANGUAGES.RU:
        keyboard.button(text='Главное меню', callback_data="main_menu")
        message_text = "Пожалуйста, выберите курс:"
    else:
        keyboard.button(text='Asosiy menyu', callback_data="main_menu")
        message_text = "Iltimos, kursni tanlang:"

    keyboard.adjust(1)

    await callback.message.answer(
        message_text,
        reply_markup=keyboard.as_markup()
    )

@router.callback_query(F.data.startswith("select_amount_"))
async def select_amount(callback: types.CallbackQuery, state: FSMContext):
    """Handle amount selection"""

    amount_id = int(callback.data.split("_")[-1])

    await state.update_data(selected_amount_id=amount_id)

    course_amount = await Course.objects.filter(id=amount_id).afirst()

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="💳 Click", callback_data="click_payment")
    keyboard.button(text="✅ To'lovni tekshirish", callback_data=f"verify_payment_{course_amount.id}")
    keyboard.button(text='Orqaga', callback_data="subscription")
    keyboard.button(text='Asosiy menyu', callback_data="main_menu")
    keyboard.adjust(1)

    formatted_amount = f"{course_amount.amount:,}".replace(',', ' ')

    message_text = (
        f"<b>{course_amount.name}</b>\n\n"
        f"{course_amount.description}\n\n"
        f"<b>Narxi:</b> {formatted_amount} so`m\n\n"
        f"{course_amount.period} kun davom etadi\n\n"
        "Iltimos, to'lov usulini tanlang:"
    )

    await callback.message.answer(
        message_text,
        reply_markup=keyboard.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "click_payment")
async def click_payment(callback: types.CallbackQuery, state: FSMContext):
    # Get data from state
    user_data = await state.get_data()
    amount_id = user_data.get("selected_amount_id")

    if not amount_id:
        await callback.message.answer("Xatolik yuz berdi. Iltimos qaytadan urinib ko'ring.")
        return

    course = await Course.objects.filter(id=amount_id).afirst()
    user_id = callback.from_user.id

    order = await Order.objects.acreate(
        user_id=user_id,
        course_id=course.id,
        amount=course.amount,
    )

    base_url = "https://my.click.uz/services/pay"

    paylink_url = (
        f"{base_url}?service_id={settings.CLICK_SERVICE_ID}&merchant_id={settings.CLICK_MERCHANT_ID}"  # noqa
        f"&amount={course.amount}&transaction_param={order.id}"
        f"&return_url="
    )

    await callback.answer(url=paylink_url)

    await callback.message.answer(
        "Siz to'lov tizimiga yo'naltirilmoqdasiz...\n"
        "Agar avtomatik ravishda yo'naltirilmasangiz, iltimos administratorga murojaat qiling."
    )


@router.callback_query(F.data.startswith("verify_payment_"))
async def verify_payment(callback: types.CallbackQuery, state: FSMContext):
    """Verify payment and provide access to private group"""

    course_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    order = await Order.objects.filter(user_id=user_id, course_id=course_id).alast()

    if not order:
        await callback.message.answer(
            "Siz hali tolov qilmagansiz. Ilitmos tolov qiling!"
        )
        return

    if order.status == CONSTANTS.PaymentStatus.SUCCESS:
        private_channels = await sync_to_async(list)(PrivateChannel.objects.filter(course_id=course_id))

        keyboard = InlineKeyboardBuilder()

        for i, channel in enumerate(private_channels, start=1):
            keyboard.button(
                text=f"🔔 {i} - kanal",
                callback_data=f"join_channel_{channel.id}"
            )

        keyboard.button(text='Asosiy menyu', callback_data="main_menu")

        keyboard.adjust(1)

        await callback.message.answer(
            f"Tabriklaymiz! Siz <b>{order.course.name}</b> kursiga muvaffaqiyatli a'zo bo'ldingiz.\n\n"
            "Quyidagi tugmalar orqali maxsus guruhlarga qo'shilishingiz mumkin:",
            reply_markup=keyboard.as_markup(),
            parse_mode="HTML",
            protect_content=True
        )
    else:
        await callback.message.answer(
            "Agar muammolar bo'lsa, administratorga murojaat qiling."
        )


@router.callback_query(F.data.startswith("join_channel_"))
async def join_channel(callback: types.CallbackQuery, state: FSMContext):
    """Handle channel join request with verification"""
    from bot.misc import bot

    # Get channel ID from callback data
    channel_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id

    try:
        # Get the channel info
        channel = await PrivateChannel.objects.get(id=channel_id)
        course_id = channel.course_id

        # Verify user has a successful payment for this course
        order = await Order.objects.filter(
            user_id=user_id,
            course_id=course_id,
            status=CONSTANTS.PaymentStatus.SUCCESS
        ).afirst()

        if order:
            # User has paid - generate a temporary invite link or add them directly
            try:
                # Option 1: If bot has invite_users permission, add user directly
                # await bot.add_chat_member(channel.chat_id, user_id)

                # Option 2: Generate a one-time invite link
                invite_link = await bot.create_chat_invite_link(
                    chat_id=channel.chat_id,
                    name=f"User {user_id}",
                    creates_join_request=False,
                    expire_date=int(time.time() + 360),
                    member_limit=1
                )

                # Send the invite link to the user
                keyboard = InlineKeyboardBuilder()
                keyboard.button(text="Guruhga kirish", url=invite_link.invite_link)
                keyboard.adjust(1)

                await callback.message.answer(
                    f"Marhamat, guruhga kirish uchun havola:\n"
                    f"Bu havola faqat bir marta ishlatilishi mumkin va 10 daqiqa ichida amal qiladi.",
                    reply_markup=keyboard.as_markup()
                )

            except Exception as e:
                await callback.message.answer(
                    f"Guruhga qo'shishda xatolik yuz berdi. Administrator bilan bog'laning."
                )
        else:
            # User hasn't paid or payment not successful
            await callback.message.answer(
                "Siz ushbu kurs uchun to'lovni amalga oshirmagansiz yoki to'lov tasdiqlanmagan."
            )

    except Exception as e:
        await callback.message.answer("Xatolik yuz berdi. Iltimos qaytadan urinib ko'ring.")

    await callback.answer()


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

    await message.answer(result_text, reply_markup=get_main_menu(user_lang))


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

    await message.answer(result_text, reply_markup=get_main_menu(user_lang))


@router.message(Command('help'))
async def on_help_command(message: types.Message):
    help_text = """
🤖 **Bot haqida ma'lumot**

Bu bot orqali siz kanal uchun obuna xizmatlarini sotib olishingiz mumkin.

📋 **Asosiy funksiyalar:**
- Oylik obuna sotib olish
- Motivatsion materiallar ko'rish
- Texnik yordam olish

💳 **To'lov:**
- Click to'lov tizimi orqali
- Xavfsiz va tez to'lov jarayoni

📱 **Foydalanish:**
1. /start tugmasini bosing
2. Obuna tugmasini bosing
3. To'lovni amalga oshiring
4. Kanalga kirish linkini oling

🆘 **Yordam kerakmi?**
Savollaringiz bo'lsa, "Texnik yordam" bo'limiga murojaat qiling yoki @admin bilan bog'laning.

📞 **Aloqa:**
- Telegram: @your_support_username
- Email: support@example.com

⚡ Bot 24/7 ishlaydi va tezkor xizmat ko'rsatadi!
    """

    await message.answer(help_text, parse_mode="Markdown")

def get_course_days_keyboard():
    """Generate static keyboard with 10 course days"""
    keyboard = InlineKeyboardBuilder()

    # Add buttons for days 1-10
    for day in range(1, 11):
        keyboard.button(
            text=f"📚 Kun {day}",
            callback_data=f"course_day_{day}"
        )

    # Add back button to main menu
    keyboard.button(text="🏠 Asosiy menyu", callback_data="main_menu")

    # Adjust to 1 button per row
    keyboard.adjust(1)

    return keyboard.as_markup()


@router.callback_query(F.data == "courses")
async def show_course_catalog(callback: types.CallbackQuery, state: FSMContext):
    """Show course catalog with static days 1-10"""
    try:
        # Delete previous message
        await callback.message.delete()
    except Exception:
        pass

    # Get keyboard with static course days
    keyboard = get_course_days_keyboard()

    message_text = (
        "📚 <b>Kurs kunlari</b>\n\n"
        "O'rganmoqchi bo'lgan kunni tanlang:"
    )

    await callback.message.answer(message_text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("course_day_"))
async def show_course_day(callback: types.CallbackQuery, state: FSMContext):
    """Show content for specific course day"""
    try:
        # Extract day number from callback data
        day_number = int(callback.data.split("_")[2])

        # Hashtag to search for
        hashtag = f"#day-{day_number}"

        # Build keyboard for navigation
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="⬅️ Orqaga", callback_data="courses")
        # keyboard.button(text="🏠 Asosiy menyu", callback_data="main_menu")
        keyboard.adjust(1)

        # Send initial message while searching
        await callback.message.edit_text(
            f"📚 **Kun {day_number}** materiallari yuklanmoqda...",
            parse_mode="HTML"
        )

        course_videos = {
            1: 3,
            2: 20,
        }

        if day_number in course_videos:
            try:
                await callback.bot.copy_message(
                    chat_id=callback.from_user.id,
                    from_chat_id=COURSE_CHANNEL_ID,
                    message_id=course_videos[day_number],
                    reply_markup=keyboard.as_markup()
                )
                # await callback.message.delete()
                return
            except Exception as msg_error:
                print(f"Error copying message: {msg_error}")
                # Continue to backup approach

        # OPTION 2: Alternative approach - store videos in a database
        # Pseudocode:
        # video = await CourseVideos.objects.filter(day=day_number).afirst()
        # if video:
        #     await callback.bot.send_video(
        #         chat_id=callback.from_user.id,
        #         video=video.file_id,
        #         caption=video.caption,
        #         reply_markup=keyboard.as_markup()
        #     )
        #     await callback.message.delete()
        #     return

        # If we got here, no video was found
        await callback.message.edit_text(
            f"📚 **Kun {day_number}**\n\n"
            f"Afsuski, ushbu kun uchun video topilmadi. "
            f"Administratorga murojaat qiling.",
            parse_mode="HTML",
            reply_markup=keyboard.as_markup()
        )

    except Exception as e:
        # Handle errors
        print(f"Error fetching course video: {e}")
        await callback.message.edit_text(
            f"📚 **Kun {day_number}**\n\n"
            f"Xatolik yuz berdi: {str(e)}\n"
            f"Iltimos, keyinroq qayta urinib ko'ring.",
            parse_mode="HTML",
            reply_markup=keyboard.as_markup()
        )


# Catch any other callbacks not specified above
@router.callback_query()
async def unknown_callback(callback: types.CallbackQuery):
    await callback.answer()
    text = "Функционал в разработке. Пожалуйста, вернитесь в главное меню."
    await callback.message.edit_text(text, reply_markup=get_back_keyboard())