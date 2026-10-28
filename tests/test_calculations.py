"""Unit tests for calculations.py."""
import unittest
from core.calculations import (
    calculate_bmr,
    calculate_tdee,
    calculate_target_calories,
    calculate_macros,
    determine_macro_category_from_onboarding,
    get_workout_comparison,
    estimate_workout_energy_burn,
    evaluate_rolling_tdee_rebalance,
    scale_recipe_portion,
)

class TestCalculations(unittest.TestCase):
    def test_bmr_no_body_fat_male(self):
        # 80 kg, 180 cm, 25 yr, male: 10*80 + 6.25*180 - 5*25 + 5 = 800 + 1125 - 125 + 5 = 1805
        bmr = calculate_bmr(weight_kg=80, height_cm=180, age=25, sex="male")
        self.assertAlmostEqual(bmr, 1805.0)

    def test_bmr_no_body_fat_female(self):
        # 60 kg, 165 cm, 30 yr, female: 10*60 + 6.25*165 - 5*30 - 161 = 600 + 1031.25 - 150 - 161 = 1320.25
        bmr = calculate_bmr(weight_kg=60, height_cm=165, age=30, sex="female")
        self.assertAlmostEqual(bmr, 1320.25)

    def test_bmr_hrt_rules(self):
        # Masculinizing HRT > 12 months -> male formula (+5)
        bmr_masc_long = calculate_bmr(80, 180, 25, "female", hrt_status=True, hrt_type="masculinizing", hrt_months=14)
        self.assertAlmostEqual(bmr_masc_long, 1805.0)

        # Masculinizing HRT < 12 months -> female formula (-161)
        bmr_masc_short = calculate_bmr(80, 180, 25, "female", hrt_status=True, hrt_type="masculinizing", hrt_months=6)
        self.assertAlmostEqual(bmr_masc_short, 1639.0)

        # Feminizing HRT > 12 months -> female formula (-161)
        bmr_fem_long = calculate_bmr(80, 180, 25, "male", hrt_status=True, hrt_type="feminizing", hrt_months=18)
        self.assertAlmostEqual(bmr_fem_long, 1639.0)

        # Feminizing HRT < 12 months -> male formula (+5)
        bmr_fem_short = calculate_bmr(80, 180, 25, "male", hrt_status=True, hrt_type="feminizing", hrt_months=4)
        self.assertAlmostEqual(bmr_fem_short, 1805.0)

    def test_bmr_with_body_fat(self):
        # Katch-McArdle: 370 + (21.6 * lean body mass)
        # 100 kg, 20% body fat -> 80 kg LBM -> 370 + (21.6 * 80) = 370 + 1728 = 2098
        bmr = calculate_bmr(weight_kg=100, height_cm=180, age=30, sex="male", body_fat_pct=20.0)
        self.assertAlmostEqual(bmr, 2098.0)

    def test_tdee_and_goals(self):
        bmr = 2000.0
        # Moderate: 2000 * 1.55 = 3100
        tdee = calculate_tdee(bmr, "Moderately active")
        self.assertAlmostEqual(tdee, 3100.0)

        # Weight loss: -20% -> 3100 * 0.8 = 2480
        loss = calculate_target_calories(tdee, "Weight loss")
        self.assertAlmostEqual(loss, 2480.0)

        # Muscle gain: +400 -> 3500
        gain = calculate_target_calories(tdee, "Gain muscle")
        self.assertAlmostEqual(gain, 3500.0)

    def test_macro_allocation(self):
        # Weight loss: Protein = 2.2 g/kg, Fat = 0.5 g/kg, Carbs = (Daily Calories - (P*4 + F*9)) / 4
        # 70 kg, 2000 kcal, body fat not exceeding threshold
        macros = calculate_macros(
            weight_kg=70,
            daily_calories=2000,
            macro_category="Weight Loss (Hypoenergetic)",
            body_fat_pct=15.0,
            sex="male"
        )
        # Protein: 70 * 2.2 = 154 g -> 616 kcal
        # Fat: 70 * 0.5 = 35 g -> 315 kcal
        # Carbs: (2000 - 931) / 4 = 1069 / 4 = 267.25 g
        self.assertEqual(macros["protein_g"], 154.0)
        self.assertEqual(macros["fat_g"], 35.0)
        self.assertAlmostEqual(macros["carbs_g"], 267.2, places=1)

    def test_volume_comparison(self):
        self.assertIn("giant panda", get_workout_comparison(200))
        self.assertIn("vending machine", get_workout_comparison(400))
        self.assertIn("VW Beetle", get_workout_comparison(3000))
        self.assertIn("African bush elephant", get_workout_comparison(14000))
        self.assertIn("Space Shuttle Orbiter", get_workout_comparison(150000))

    def test_rolling_tdee_rebalance(self):
        bmr = 1800.0
        current_tdee = 2500.0
        # 14 days of workouts averaging 400 kcal/day
        past_14 = [400.0] * 14
        # Sedentary baseline = 1800 * 1.2 = 2160
        # Calculated TDEE = 2160 + 400 = 2560
        # diff = +60 kcal, within +/- 150 clamp
        result = evaluate_rolling_tdee_rebalance(bmr, current_tdee, past_14, "Weight maintenance")
        self.assertEqual(result["clamped_diff"], 60.0)
        self.assertEqual(result["new_baseline_tdee"], 2560.0)

    def test_recipe_scaling(self):
        # 500g total batch, 1000 kcal, 60g P, 100g C, 40g F. Consumed 250g (50%)
        scaled = scale_recipe_portion(250, 500, 1000, 60, 100, 40)
        self.assertEqual(scaled["fraction"], 0.5)
        self.assertEqual(scaled["calories"], 500.0)
        self.assertEqual(scaled["protein_g"], 30.0)

if __name__ == "__main__":
    unittest.main()

