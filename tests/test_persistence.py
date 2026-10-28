"""Test verifying that user inputs and changes persist across app shutdowns and database reopens."""
import unittest
import sqlite3
import os
import asyncio
from data.db import DB_PATH, init_db, get_connection
from app import (
    save_onboarding,
    update_profile,
    get_profile,
    get_dashboard,
    log_meal,
    log_workout,
    create_recipe,
    list_workouts,
    list_recipes,
    OnboardingRequest,
    ProfileUpdateRequest,
    LogMealRequest,
    LogWorkoutRequest,
    LoggedExercise,
    ExerciseSet,
    CreateRecipeRequest,
    RecipeIngredient,
)

class TestAppShutdownPersistence(unittest.TestCase):
    def test_persistence_across_app_lifecycle(self):
        async def run_lifecycle():
            # Clean slate for test
            init_db()
            conn = get_connection()
            c = conn.cursor()
            c.execute("DELETE FROM meals_logged")
            c.execute("DELETE FROM workouts")
            c.execute("DELETE FROM recipes")
            c.execute("DELETE FROM safe_foods")
            c.execute("DELETE FROM user_profile")
            conn.commit()
            conn.close()

            # 1. User completes onboarding
            ob = OnboardingRequest(
                height_cm=182.0,
                weight_kg=85.0,
                age=29,
                sex="female",
                hrt_status=True,
                hrt_type="feminizing",
                hrt_months=18,
                body_fat_pct=21.0,
                activity_level="Active",
                goal="Gain muscle",
                safe_food_tracker_enabled=True,
                safe_foods=[
                    {"name": "Salmon", "ranking": "always_safe"},
                    {"name": "Sweet Potato", "ranking": "safe"}
                ]
            )
            res1 = await save_onboarding(ob)
            self.assertTrue(res1["success"])

            # 2. User logs a meal
            m_res = await log_meal(LogMealRequest(
                name="Post-Workout Salmon & Sweet Potato",
                calories=650.0,
                protein_g=50.0,
                carbs_g=60.0,
                fat_g=18.0
            ))
            self.assertTrue(m_res["success"])

            # 3. User logs a workout
            w_res = await log_workout(LogWorkoutRequest(
                duration_minutes=50.0,
                muscles_worked=["Back", "Biceps"],
                exercises=[
                    LoggedExercise(
                        exercise_name="Barbell Deadlift",
                        category="strength",
                        sets=[
                            ExerciseSet(set_number=1, weight_lbs=275.0, reps=8),
                            ExerciseSet(set_number=2, weight_lbs=315.0, reps=5),
                        ]
                    )
                ]
            ))
            self.assertTrue(w_res["success"])

            # 4. User saves a recipe
            r_res = await create_recipe(CreateRecipeRequest(
                name="Overnight Protein Oats",
                meal_type="breakfast",
                ingredients=[
                    RecipeIngredient(name="Rolled Oats", weight_g=80.0, calories=300.0, protein_g=10.0, carbs_g=50.0, fat_g=5.0),
                    RecipeIngredient(name="Greek Yogurt", weight_g=150.0, calories=90.0, protein_g=15.0, carbs_g=5.0, fat_g=0.5)
                ]
            ))
            self.assertTrue(r_res["success"])

            # --- SIMULATE COMPLETE APP SHUTDOWN ---
            # All in-memory state is abandoned. We open a fresh connection directly to the persistent SQLite file.
            conn2 = sqlite3.connect(DB_PATH)
            conn2.row_factory = sqlite3.Row
            c2 = conn2.cursor()

            # Verify profile survived shutdown
            c2.execute("SELECT * FROM user_profile LIMIT 1")
            prof_row = c2.fetchone()
            self.assertIsNotNone(prof_row)
            self.assertEqual(prof_row["height_cm"], 182.0)
            self.assertEqual(prof_row["weight_kg"], 85.0)
            self.assertEqual(prof_row["hrt_type"], "feminizing")
            self.assertEqual(prof_row["hrt_months"], 18)
            self.assertEqual(prof_row["goal"], "Gain muscle")

            # Verify meal survived shutdown
            c2.execute("SELECT * FROM meals_logged")
            meals_rows = c2.fetchall()
            self.assertEqual(len(meals_rows), 1)
            self.assertEqual(meals_rows[0]["name"], "Post-Workout Salmon & Sweet Potato")
            self.assertEqual(meals_rows[0]["calories"], 650.0)

            # Verify workout survived shutdown
            c2.execute("SELECT * FROM workouts")
            workout_rows = c2.fetchall()
            self.assertEqual(len(workout_rows), 1)
            self.assertEqual(workout_rows[0]["duration_minutes"], 50.0)

            # Verify recipe survived shutdown
            c2.execute("SELECT * FROM recipes")
            recipe_rows = c2.fetchall()
            self.assertEqual(len(recipe_rows), 1)
            self.assertEqual(recipe_rows[0]["name"], "Overnight Protein Oats")
            self.assertEqual(recipe_rows[0]["batch_weight_g"], 230.0)

            # Verify safe foods survived shutdown
            c2.execute("SELECT * FROM safe_foods")
            sf_rows = c2.fetchall()
            self.assertEqual(len(sf_rows), 2)

            conn2.close()

            # 5. User updates settings (e.g. body fat drops, new target)
            up_res = await update_profile(ProfileUpdateRequest(
                weight_kg=83.0,
                body_fat_pct=19.5,
                goal="Weight maintenance"
            ))
            self.assertTrue(up_res["success"])
            self.assertEqual(up_res["profile"]["weight_kg"], 83.0)
            self.assertEqual(up_res["profile"]["goal"], "Weight maintenance")

            # --- SIMULATE SECOND APP SHUTDOWN ---
            conn3 = sqlite3.connect(DB_PATH)
            conn3.row_factory = sqlite3.Row
            c3 = conn3.cursor()
            c3.execute("SELECT weight_kg, body_fat_pct, goal FROM user_profile LIMIT 1")
            updated_prof = c3.fetchone()
            self.assertEqual(updated_prof["weight_kg"], 83.0)
            self.assertEqual(updated_prof["body_fat_pct"], 19.5)
            self.assertEqual(updated_prof["goal"], "Weight maintenance")
            conn3.close()

        asyncio.run(run_lifecycle())

if __name__ == "__main__":
    unittest.main()

