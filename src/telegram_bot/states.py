from aiogram.fsm.state import State, StatesGroup


class PostCreationStates(StatesGroup):
    waiting_for_media = State()
    waiting_for_language = State()
    waiting_for_instructions = State()
    waiting_for_format = State()
    waiting_for_approval = State()
    waiting_for_edit = State()
    waiting_for_photo_text_edit = State()
    waiting_for_custom_tag = State()
    waiting_for_custom_mention = State()
    managing_preset_tags = State()
    managing_preset_mentions = State()
    adding_preset_tag = State()
    adding_preset_mention = State()
