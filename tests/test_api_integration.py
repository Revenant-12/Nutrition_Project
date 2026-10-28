"""Full API Integration test suite for the Nutrition & Workout application."""
import unittest
from fastapi.testclient import TestClient
from app import app
from data.db import init_db

class TestApiIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

    def test_01_onboarding_and_profile(self):
        payload = {
            "height_cm": 178.0,
            "weight_kg": 75.0,
            "age": 28,
            "sex": "female",
            "hrt_status": True,
            "hrt_type": "feminizing",
            "hrt_months": 15,  # >12 months -> female formula
            "body_fat_pct": 22.0,
            "activity_level": "Moderately active",
            "goal": "Weight loss",
            "display_preference": "both",
            "safe_food_tracker_enabled": True,
            "safe_foods": [
                {"name": "Oatmeal", "ranking": "always_safe"},
                {"name": "Chicken Breast", "ranking": "always_safe"},
                {"name": "Rice", "ranking": "safe"}
            ]
        }
        resp = self.client.post("/api/profile/onboarding", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        profile = data["profile"]

        # With body fat 22% provided: Katch-McArdle: 370 + 21.6 * (75 * (1 - 0.22))
        # LBM = 58.5 kg -> 370 + 21.6 * 58.5 = 1633.6 kcal
        self.assertAlmostEqual(profile["bmr"], 1633.6, places=1)

        # Moderately active multiplier = 1.55 -> 1633.6 * 1.55 = 2532.08
        self.assertAlmostEqual(profile["baseline_tdee"], 2532.1, places=0)

        # Weight loss = -20% -> 2532.08 * 0.8 = 2025.66 kcal
        self.assertAlmostEqual(profile["daily_target_calories"], 2026.0, places=0)

    def test_02_dashboard(self):
        resp = self.client.get("/api/dashboard")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["onboarded"])
        self.assertIn("target", data)
        self.assertIn("consumed", data)
        self.assertIn("remaining", data)

    def test_03_meal_logging_and_copy(self):
        log_payload = {
            "name": "Morning Oats & Whey",
            "calories": 420.0,
            "protein_g": 35.0,
            "carbs_g": 52.0,
            "fat_g": 6.5
        }
        resp = self.client.post("/api/meals", json=log_payload)
        self.assertEqual(resp.status_code, 200)

        dash = self.client.get("/api/dashboard").json()
        self.assertEqual(dash["consumed"]["calories"], 420.0)
        self.assertEqual(len(dash["meals"]), 1)
        meal_id = dash["meals"][0]["id"]

        # Test copying the meal
        copy_resp = self.client.post("/api/meals/copy", json={"meal_id": meal_id})
        self.assertEqual(copy_resp.status_code, 200)

        dash2 = self.client.get("/api/dashboard").json()
        self.assertEqual(len(dash2["meals"]), 2)
        self.assertEqual(dash2["consumed"]["calories"], 840.0)

    def test_04_workout_logging_and_comparison_table(self):
        workout_payload = {
            "duration_minutes": 45.0,
            "muscles_worked": ["Chest", "Triceps"],
            "exercises": [
                {
                    "exercise_name": "Bench Press",
                    "category": "strength",
                    "sets": [
                        {"set_number": 1, "weight_lbs": 200.0, "reps": 10},
                        {"set_number": 2, "weight_lbs": 200.0, "reps": 10},
                        {"set_number": 3, "weight_lbs": 200.0, "reps": 10}
                    ]
                }
            ]
        }
        # Total weight lifted: 3 * 200 * 10 = 6,000 lbs
        # Pseudocode Table tier: 5000-7499 lbs -> "an adult white rhinoceros"
        resp = self.client.post("/api/workouts", json=workout_payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_weight_lifted_lbs"], 6000.0)
        self.assertIn("adult white rhinoceros", data["comparison_text"])

    def test_05_recipe_batch_scaling_and_portion_logging(self):
        # Create recipe: Batch Weight = 300g (Chicken 200g + Rice 100g)
        recipe_payload = {
            "name": "Chicken Rice Bowl",
            "meal_type": "meal",
            "ingredients": [
                {"name": "Chicken Breast", "weight_g": 200.0, "calories": 330.0, "protein_g": 62.0, "carbs_g": 0.0, "fat_g": 7.2},
                {"name": "Rice", "weight_g": 100.0, "calories": 130.0, "protein_g": 2.7, "carbs_g": 28.2, "fat_g": 0.3}
            ],
            "add_to_safe_foods": True,
            "safe_ranking": "always_safe"
        }
        resp = self.client.post("/api/recipes", json=recipe_payload)
        self.assertEqual(resp.status_code, 200)
        r_data = resp.json()
        self.assertEqual(r_data["batch_weight_g"], 300.0)
        self.assertEqual(r_data["total_calories"], 460.0)
        recipe_id = r_data["recipe_id"]

        # Log a 150g portion (50% of the batch)
        portion_resp = self.client.post(
            "/api/meals/log-recipe-portion",
            data={"recipe_id": recipe_id, "portion_weight_g": 150.0}
        )
        self.assertEqual(portion_resp.status_code, 200)
        scaled = portion_resp.json()["scaled"]
        self.assertEqual(scaled["fraction"], 0.5)
        self.assertEqual(scaled["calories"], 230.0)
        self.assertEqual(scaled["protein_g"], 32.4)

    def test_06_recipe_recommendation_with_safe_foods(self):
        rec_payload = {
            "meal_type": "meal",
            "use_safe_foods": True,
            "safe_rank_required": "safe",
            "filter_mode": "soft",
            "prioritize": "calories"
        }
        resp = self.client.post("/api/recipes/recommend", json=rec_payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreaterEqual(data["count"], 1)
        self.assertEqual(data["recipes"][0]["name"], "Chicken Rice Bowl")

if __name__ == "__main__":
    unittest.main()

