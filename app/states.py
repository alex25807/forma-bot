from aiogram.fsm.state import State, StatesGroup


class CalcForm(StatesGroup):
    gender = State()
    height = State()
    weight = State()
    age = State()
    activity = State()
    target = State()
    goal_weight = State()
    restrictions = State()
    restrictions_detail = State()
    accelerate = State()
    accelerate_level = State()
    food_prefs = State()
    food_prefs_custom = State()
    cuisine = State()
    cuisine_custom = State()
    soup_pref = State()
    menu_confirm = State()


class DailyForm(StatesGroup):
    food_log = State()


class WeightForm(StatesGroup):
    weight = State()


class ReviewForm(StatesGroup):
    text = State()


class RecipeForm(StatesGroup):
    dish_name = State()


class PhotoForm(StatesGroup):
    waiting = State()


class FitnessForm(StatesGroup):
    level = State()


class ChallengeForm(StatesGroup):
    final_feedback = State()
