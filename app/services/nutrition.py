from dataclasses import dataclass

ACTIVITY = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "high": 1.725,
    "very_high": 1.9,
}

@dataclass
class Macros:
    calories: int
    protein_g: int
    fat_g: int
    carbs_g: int

def bmr_mifflin(weight_kg: float, height_cm: float, age: int, gender: str) -> float:
    if gender.lower().startswith("m"):
        return 10*weight_kg + 6.25*height_cm - 5*age + 5
    return 10*weight_kg + 6.25*height_cm - 5*age - 161

def tdee(bmr: float, activity_level: str) -> float:
    return bmr * ACTIVITY[activity_level]

def target_calories(tdee_val: float, target: str) -> float:
    if target == "cut":
        return tdee_val * 0.85
    if target == "gain":
        return tdee_val * 1.12
    return tdee_val

def clamp_min_calories(cal: float, gender: str) -> float:
    min_cal = 1500 if gender.lower().startswith("m") else 1200
    return max(cal, min_cal)

def macros(weight_kg: float, calories: float, target: str) -> Macros:
    # protein
    if target == "cut":
        p = 1.8 * weight_kg
    elif target == "gain":
        p = 1.7 * weight_kg
    else:
        p = 1.6 * weight_kg

    # fats
    f = 0.9 * weight_kg

    # calories to grams
    p_cal = p * 4
    f_cal = f * 9
    c_cal = max(calories - (p_cal + f_cal), 0)
    c = c_cal / 4

    # округление до удобных целых
    return Macros(
        calories=int(round(calories / 10) * 10),
        protein_g=int(round(p / 5) * 5),
        fat_g=int(round(f / 5) * 5),
        carbs_g=int(round(c / 5) * 5),
    )

def compute_kbju(height_cm: float, weight_kg: float, age: int, gender: str, activity_level: str, target: str) -> Macros:
    bmr = bmr_mifflin(weight_kg, height_cm, age, gender)
    t = tdee(bmr, activity_level)
    cal = target_calories(t, target)
    cal = clamp_min_calories(cal, gender)
    return macros(weight_kg, cal, target)
