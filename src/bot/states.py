from aiogram.fsm.state import State, StatesGroup


class PostCreationStates(StatesGroup):
    waiting_for_media = State()
    waiting_for_format = State()
    waiting_for_approval = State()
    waiting_for_edit = State()
