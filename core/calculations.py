"""Core calculation engine for Nutrition & Fitness app.
Strictly implements the logic defined in Nutrition Pseudocode.txt.
"""
from typing import Dict, Any, Optional, Tuple, List
import math

# Volume Comparison Table defined in Pseudocode Section 3.5.2
VOLUME_COMPARISON_TABLE = [
    (249, "an adult giant panda"),
    (499, "a vending machine"),
    (999, "a concert grand piano"),
    (1999, "a thoroughbred racehorse"),
    (3499, "a classic VW Beetle"),
    (4999, "a full-grown wild hippo"),
    (7499, "an adult white rhinoceros"),
    (9999, "a competition monster truck"),
    (14999, "an African bush elephant"),
    (19999, "an adult T-Rex"),
    (29999, "a London double-decker bus"),
    (44999, "a fully loaded city fire truck"),
    (59999, "an Abrams battle tank turret"),
    (79999, "an adult humpback whale"),
    (99999, "a fully loaded commercial 18-wheeler"),
    (float("inf"), "the NASA Space Shuttle Orbiter"),
]


def calculate_bmr(
    weight_kg: float,
    height_cm: float,
    age: int,
    sex: str,
    hrt_status: bool = False,
    hrt_type: Optional[str] = None,  # "feminizing" or "masculinizing"
    hrt_months: int = 0,
    body_fat_pct: Optional[float] = None,
) -> float:
    """
    Calculate Basal Metabolic Rate (BMR) per Pseudocode Section 1.1.4.1:
    - If body fat % is provided:
        BMR = 370 + (21.6 * lean body mass in kg)
        Lean body mass = weight_kg * (1 - (body_fat_pct / 100))
    - If no body fat %:
        - Male profile:
          Men, masculinizing HRT > 12 months, or feminizing HRT < 12 months:
          BMR = (10 * weight in kg) + (6.25 * height in cm) - (5 * age in years) + 5
        - Female profile:
          Women, feminizing HRT > 12 months, or masculinizing HRT < 12 months:
          BMR = (10 * weight in kg) + (6.25 * height in cm) - (5 * age in years) - 161
    """
    if body_fat_pct is not None and body_fat_pct > 0:
        lean_body_mass_kg = weight_kg * (1.0 - (body_fat_pct / 100.0))
        return 370.0 + (21.6 * lean_body_mass_kg)

    # Determine hormonal sex profile
    is_male_profile = False
    sex_lower = sex.lower().strip()

    if hrt_status and hrt_type:
        hrt_lower = hrt_type.lower().strip()
        if hrt_lower == "masculinizing":
            # > 12 months -> male profile; < 12 months -> female profile
            is_male_profile = (hrt_months >= 12)
        elif hrt_lower == "feminizing":
            # > 12 months -> female profile; < 12 months -> male profile
            is_male_profile = (hrt_months < 12)
        else:
            is_male_profile = (sex_lower == "male" or sex_lower == "m")
    else:
        is_male_profile = (sex_lower == "male" or sex_lower == "m")

    base = (10.0 * weight_kg) + (6.25 * height_cm) - (5.0 * age)
    if is_male_profile:
        return base + 5.0
    else:
        return base - 161.0


def calculate_tdee(bmr: float, activity_level: str) -> float:
    """
    Calculate Total Daily Energy Expenditure (TDEE) per Pseudocode Section 1.1.4.2:
    - Sedentary: BMR * 1.2
    - Lightly active: BMR * 1.375
    - Moderately active: BMR * 1.55
    - Active: BMR * 1.725
    - Very active: BMR * 1.9
    """
    multipliers = {
        "sedentary": 1.2,
        "lightly active": 1.375,
        "light": 1.375,
        "moderately active": 1.55,
        "moderate": 1.55,
        "active": 1.725,
        "very active": 1.9,
    }
    normalized = activity_level.lower().strip()
    multiplier = multipliers.get(normalized, 1.2)
    return bmr * multiplier


def calculate_target_calories(tdee: float, goal: str, custom_offset: Optional[float] = None) -> float:
    """
    Calculate Daily Target Calories per Pseudocode Section 1.1.5:
    - Weight loss: TDEE - 20%
    - Weight maintenance: TDEE
    - Keep current musculature: TDEE
    - Gain muscle: TDEE + (300 to 500 kcal, default 400)
    - Weight gain: TDEE + (300 to 500 kcal, default 400)
    """
    g = goal.lower().strip()
    if "loss" in g:
        return tdee * 0.80
    elif "gain muscle" in g or "muscle" in g:
        offset = custom_offset if custom_offset is not None else 400.0
        return tdee + offset
    elif "weight gain" in g or "gain" in g:
        offset = custom_offset if custom_offset is not None else 400.0
        return tdee + offset
    else:
        # Weight maintenance or keep current musculature
        return tdee


def get_hormonal_profile_sex(
    sex: str,
    hrt_status: bool = False,
    hrt_type: Optional[str] = None,
    hrt_months: int = 0
) -> str:
    """
    Returns effective hormonal profile ('male' or 'female')
    following the >12 months rule.
    """
    if hrt_status and hrt_type:
        hrt_lower = hrt_type.lower().strip()
        if hrt_lower == "masculinizing":
            return "male" if hrt_months >= 12 else "female"
        elif hrt_lower == "feminizing":
            return "female" if hrt_months >= 12 else "male"
    sex_lower = sex.lower().strip()
    return "male" if sex_lower in ("male", "m") else "female"


def calculate_macros(
    weight_kg: float,
    daily_calories: float,
    macro_category: str,
    body_fat_pct: Optional[float] = None,
    sex: str = "male",
    hrt_status: bool = False,
    hrt_type: Optional[str] = None,
    hrt_months: int = 0,
) -> Dict[str, float]:
    """
    Calculate Macro Target Allocation per Pseudocode Section 2.2:
    
    1. Base Reference Weight:
       - If body fat % provided AND (body fat > 30% for men OR > 38% for women):
           Use Lean Body Mass (LBM) in kg as Reference Weight.
       - Otherwise: Use Total Scale Weight in kg.
       (HRT uses effective hormone profile if >12 months)
       
    2. Baseline Gram Targets:
       - Sedentary:
           Protein = 0.8 g/kg, Fat = 0.8 g/kg,
           Carbs = (Daily Calories - (Protein*4 + Fat*9)) / 4
       - Active / Fitness:
           Protein = 1.6 g/kg, Fat = 0.8 g/kg,
           Carbs = (Daily Calories - (Protein*4 + Fat*9)) / 4
       - Resistance / Strength:
           Protein = 2.0 g/kg, Fat = 1.0 g/kg,
           Carbs = (Daily Calories - (Protein*4 + Fat*9)) / 4
       - Endurance:
           Protein = 1.4 g/kg, Carbs = 6.0 g/kg,
           Fat = (Daily Calories - (Protein*4 + Carbs*4)) / 9
       - Weight Loss (Hypoenergetic):
           Protein = 2.2 g/kg, Fat = 0.5 g/kg,
           Carbs = (Daily Target Calories - (Protein*4 + Fat*9)) / 4
    """
    effective_sex = get_hormonal_profile_sex(sex, hrt_status, hrt_type, hrt_months)
    bf_threshold = 30.0 if effective_sex == "male" else 38.0

    reference_weight = weight_kg
    if body_fat_pct is not None and body_fat_pct > bf_threshold:
        reference_weight = weight_kg * (1.0 - (body_fat_pct / 100.0))

    cat = macro_category.lower().strip()

    if "weight loss" in cat or "hypoenergetic" in cat:
        protein_g = 2.2 * reference_weight
        fat_g = 0.5 * reference_weight
        remaining_kcal = daily_calories - (protein_g * 4.0 + fat_g * 9.0)
        carbs_g = max(0.0, remaining_kcal / 4.0)

    elif "endurance" in cat:
        protein_g = 1.4 * reference_weight
        carbs_g = 6.0 * reference_weight
        remaining_kcal = daily_calories - (protein_g * 4.0 + carbs_g * 4.0)
        fat_g = max(0.0, remaining_kcal / 9.0)

    elif "resistance" in cat or "strength" in cat or "gain muscle" in cat:
        protein_g = 2.0 * reference_weight
        fat_g = 1.0 * reference_weight
        remaining_kcal = daily_calories - (protein_g * 4.0 + fat_g * 9.0)
        carbs_g = max(0.0, remaining_kcal / 4.0)

    elif "sedentary" in cat:
        protein_g = 0.8 * reference_weight
        fat_g = 0.8 * reference_weight
        remaining_kcal = daily_calories - (protein_g * 4.0 + fat_g * 9.0)
        carbs_g = max(0.0, remaining_kcal / 4.0)

    else:
        # Default: Active / Fitness
        protein_g = 1.6 * reference_weight
        fat_g = 0.8 * reference_weight
        remaining_kcal = daily_calories - (protein_g * 4.0 + fat_g * 9.0)
        carbs_g = max(0.0, remaining_kcal / 4.0)

    return {
        "protein_g": round(protein_g, 1),
        "fat_g": round(fat_g, 1),
        "carbs_g": round(carbs_g, 1),
        "reference_weight_kg": round(reference_weight, 1),
        "target_calories": round(daily_calories, 0),
    }


def determine_macro_category_from_onboarding(goal: str, activity_level: str) -> str:
    """
    Maps onboarding goal & activity tier to one of the 5 macro tiers:
    - Weight loss -> Weight Loss (Hypoenergetic)
    - Gain muscle or Keep current musculature -> Resistance / Strength
    - Sedentary -> Sedentary
    - Active / Very Active -> Active / Fitness (or Resistance if goal is muscle)
    """
    g = goal.lower().strip()
    a = activity_level.lower().strip()

    if "loss" in g:
        return "Weight Loss (Hypoenergetic)"
    if "muscle" in g or "musculature" in g:
        return "Resistance / Strength"
    if "endurance" in g or "runner" in g:
        return "Endurance"
    if a == "sedentary":
        return "Sedentary"
    return "Active / Fitness"


def get_workout_comparison(total_weight_lifted_lbs: float) -> str:
    """
    Returns fun volume comparison per Pseudocode Section 3.5.2.
    """
    for max_w, comp in VOLUME_COMPARISON_TABLE:
        if total_weight_lifted_lbs <= max_w:
            return f"You lifted {int(round(total_weight_lifted_lbs)):,} lbs! That's like lifting {comp}!"
    return f"You lifted {int(round(total_weight_lifted_lbs)):,} lbs! That's like lifting the NASA Space Shuttle Orbiter!"


def estimate_workout_energy_burn(
    is_strength: bool,
    duration_minutes: float,
    user_weight_kg: float,
    cardio_met: float = 7.0,  # default moderate cardio MET
) -> float:
    """
    Estimate calories burned per Pseudocode Section 6.b:
    - Strength Training: (duration in minutes) * (user weight in kg * 0.06 kcal/min)
    - Cardio: MET * weight_kg * (duration_minutes / 60.0)
    """
    if is_strength:
        return duration_minutes * (user_weight_kg * 0.06)
    else:
        # Cardio MET equation: kcal = MET * weight_kg * time_in_hours
        return cardio_met * user_weight_kg * (duration_minutes / 60.0)


def evaluate_rolling_tdee_rebalance(
    bmr: float,
    current_baseline_tdee: float,
    past_14_days_burns: List[float],
    goal: str,
    custom_offset: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Pseudocode Section 6.c: Adaptive Activity & TDEE Rebalancing Engine (Weekly Update):
    1. Average Daily Workout Burn = Sum(previous 14 days) / 14
    2. Sedentary Baseline = BMR * 1.2
    3. Calculated TDEE = Sedentary Baseline + Average Daily Exercise Burn
    4. Cap change to max +/- 150 kcal per week vs current baseline TDEE
    5. New Baseline TDEE = Current Baseline TDEE + Clamped Difference
    6. Re-calculate Daily Target Calories
    7. Generate notification message
    """
    total_burn_14_days = sum(past_14_days_burns)
    avg_daily_exercise_burn = total_burn_14_days / 14.0

    sedentary_baseline = bmr * 1.2
    calculated_tdee = sedentary_baseline + avg_daily_exercise_burn

    diff = calculated_tdee - current_baseline_tdee
    clamped_diff = max(-150.0, min(150.0, diff))
    new_baseline_tdee = current_baseline_tdee + clamped_diff

    new_target_calories = calculate_target_calories(new_baseline_tdee, goal, custom_offset)
    change_sign = f"+{int(round(clamped_diff))}" if clamped_diff >= 0 else f"{int(round(clamped_diff))}"

    notification = (
        f"Based on your last 2 weeks of workouts, your daily baseline has been adjusted by "
        f"{change_sign} calories to match your real activity level."
    )

    return {
        "avg_daily_exercise_burn": round(avg_daily_exercise_burn, 1),
        "sedentary_baseline": round(sedentary_baseline, 1),
        "calculated_tdee": round(calculated_tdee, 1),
        "diff": round(diff, 1),
        "clamped_diff": round(clamped_diff, 1),
        "new_baseline_tdee": round(new_baseline_tdee, 1),
        "new_target_calories": round(new_target_calories, 0),
        "notification": notification,
    }


def scale_recipe_portion(
    portion_consumed_g: float,
    total_batch_weight_g: float,
    total_calories: float,
    total_protein_g: float,
    total_carbs_g: float,
    total_fat_g: float,
) -> Dict[str, float]:
    """
    Portion logging per Pseudocode Section 4.1.4:
    Portion Consumed (g) / Total Batch Weight (g) = Fraction of total macros to log
    """
    if total_batch_weight_g <= 0:
        fraction = 1.0
    else:
        fraction = portion_consumed_g / total_batch_weight_g

    return {
        "fraction": round(fraction, 4),
        "portion_weight_g": round(portion_consumed_g, 1),
        "calories": round(total_calories * fraction, 1),
        "protein_g": round(total_protein_g * fraction, 1),
        "carbs_g": round(total_carbs_g * fraction, 1),
        "fat_g": round(total_fat_g * fraction, 1),
    }

