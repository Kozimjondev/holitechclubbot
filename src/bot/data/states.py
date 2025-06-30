from aiogram.filters.state import State, StatesGroup


class UserStates(StatesGroup):
    name = State()
    phone = State()


class UserCardStates(StatesGroup):
    card_number = State()
    card_pan = State()
    name = State()
    confirmation = State()
