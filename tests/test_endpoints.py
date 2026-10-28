"""Direct async endpoint test runner."""
import asyncio
import unittest
from app import (
    save_onboarding,
    get_profile,
    get_dashboard,
    log_meal,
    copy_meal,
    log_workout,
    delete_workout,
    list_workouts,
    create_recipe,
    delete_recipe,
    list_recipes,
    log_recipe_portion,
    get_recipe_recommendations,
    list_safe_foods,
    add_safe_food,
    get_previous_exercise_performance,
    OnboardingRequest,
    LogMealRequest,
    CopyMealRequest,
    LogWorkoutRequest,
    LoggedExercise,
    ExerciseSet,
    CreateRecipeRequest,
    RecipeIngredient,
    LogRecipePortionRequest,
    RecommendRecipeRequest,
    SafeFoodRequest,
)
from data.db import init_db

class TestEndpointsAsync(unittest.TestCase):
    def setUp(self):
        init_db()
        from data.db import get_connection
        conn = get_connection()
        c = conn.cursor()
        c.execute("DELETE FROM meals_logged")
        c.execute("DELETE FROM workouts")
        c.execute("DELETE FROM recipes")
        c.execute("DELETE FROM safe_foods")
        c.execute("DELETE FROM user_profile")
        conn.commit()
        conn.close()

    def test_all_flows(self):
        async def run_suite():
            # 1. Onboarding
            ob_req = OnboardingRequest(
                height_cm=180.0,
                weight_kg=80.0,
                age=26,
                sex="male",
                body_fat_pct=15.0,
                activity_level="Moderately active",
                goal="Weight loss",
                safe_food_tracker_enabled=True,
                safe_foods=[
                    {"name": "Chicken Breast", "ranking": "always_safe"},
                    {"name": "Brown Rice", "ranking": "safe"},
                    {"name": "Broccoli", "ranking": "always_safe"}
                ]
            )
            ob_res = await save_onboarding(ob_req)
            self.assertTrue(ob_res["success"])
            p = ob_res["profile"]
            self.assertEqual(p["goal"], "Weight loss")

            # 2. Profile fetch
            prof_res = await get_profile()
            self.assertTrue(prof_res["onboarded"])

            # 3. Dashboard
            dash_res = await get_dashboard()
            self.assertTrue(dash_res["onboarded"])
            self.assertGreater(dash_res["target"]["calories"], 0)

            # 4. Log Meal
            meal_res = await log_meal(LogMealRequest(
                name="Chicken & Rice",
                calories=500.0,
                protein_g=45.0,
                carbs_g=55.0,
                fat_g=8.0
            ))
            self.assertTrue(meal_res["success"])

            dash_after_meal = await get_dashboard()
            self.assertEqual(dash_after_meal["consumed"]["calories"], 500.0)
            self.assertEqual(len(dash_after_meal["meals"]), 1)
            meal_id = dash_after_meal["meals"][0]["id"]

            # 5. Copy Meal
            copy_res = await copy_meal(CopyMealRequest(meal_id=meal_id))
            self.assertTrue(copy_res["success"])
            dash_after_copy = await get_dashboard()
            self.assertEqual(dash_after_copy["consumed"]["calories"], 1000.0)

            # 6. Log Workout with Volume Comparison Table
            workout_res = await log_workout(LogWorkoutRequest(
                duration_minutes=60.0,
                muscles_worked=["Legs", "Quads"],
                exercises=[
                    LoggedExercise(
                        exercise_name="Leg Press",
                        category="strength",
                        sets=[
                            ExerciseSet(set_number=1, weight_lbs=400.0, reps=10), # 4,000 lbs
                            ExerciseSet(set_number=2, weight_lbs=450.0, reps=10), # 4,500 lbs
                            ExerciseSet(set_number=3, weight_lbs=450.0, reps=10), # 4,500 lbs
                        ]
                    )
                ]
            ))
            # Total weight lifted: 13,000 lbs -> "an African bush elephant" (tier 10,000 - 14,999 lbs)
            self.assertTrue(workout_res["success"])
            self.assertEqual(workout_res["total_weight_lifted_lbs"], 13000.0)
            self.assertIn("African bush elephant", workout_res["comparison_text"])

            # 7. Create Recipe & Batch Weight
            rec_res = await create_recipe(CreateRecipeRequest(
                name="Protein Power Oats",
                meal_type="breakfast",
                ingredients=[
                    RecipeIngredient(name="Oats", weight_g=100.0, calories=389.0, protein_g=16.9, carbs_g=66.3, fat_g=6.9),
                    RecipeIngredient(name="Whey", weight_g=30.0, calories=114.0, protein_g=23.4, carbs_g=1.8, fat_g=1.2)
                ],
                add_to_safe_foods=True,
                safe_ranking="always_safe"
            ))
            self.assertTrue(rec_res["success"])
            self.assertEqual(rec_res["batch_weight_g"], 130.0)
            rec_id = rec_res["recipe_id"]

            # 8. Log Portion of Recipe
            portion_res = await log_recipe_portion(LogRecipePortionRequest(recipe_id=rec_id, portion_weight_g=65.0))
            self.assertTrue(portion_res["success"])
            self.assertEqual(portion_res["scaled"]["fraction"], 0.5)

            # 9. Recipe Recommendation with Safe Foods
            recs = await get_recipe_recommendations(RecommendRecipeRequest(
                meal_type="breakfast",
                use_safe_foods=True,
                safe_rank_required="safe",
                filter_mode="soft"
            ))
            self.assertGreaterEqual(recs["count"], 1)

            # 10. Safe Foods
            sf_list = await list_safe_foods()
            self.assertGreaterEqual(len(sf_list["safe_foods"]), 1)

            # 11. Previous Exercise Performance Lookup (sets & reps pre-population)
            # The workout logged in step 6 had Leg Press with sets: 400x10, 450x10, 450x10
            perf = await get_previous_exercise_performance(name="Leg Press")
            self.assertTrue(perf["found"])
            self.assertEqual(len(perf["sets"]), 3)
            self.assertEqual(perf["sets"][0]["weight_lbs"], 400.0)
            self.assertEqual(perf["sets"][0]["reps"], 10)
            self.assertEqual(perf["sets"][1]["weight_lbs"], 450.0)

            # Query an exercise never performed yet
            perf_none = await get_previous_exercise_performance(name="Nonexistent Exercise")
            self.assertFalse(perf_none["found"])
            self.assertEqual(len(perf_none["sets"]), 0)

            # 12. Delete Workout
            workouts_before = await list_workouts()
            self.assertEqual(len(workouts_before["workouts"]), 1)
            w_id = workouts_before["workouts"][0]["id"]
            del_w_res = await delete_workout(workout_id=w_id)
            self.assertTrue(del_w_res["success"])
            workouts_after = await list_workouts()
            self.assertEqual(len(workouts_after["workouts"]), 0)

            # 13. Delete Recipe
            recipes_before = await list_recipes()
            self.assertEqual(len(recipes_before["recipes"]), 1)
            del_r_res = await delete_recipe(recipe_id=rec_id)
            self.assertTrue(del_r_res["success"])
            recipes_after = await list_recipes()
            self.assertEqual(len(recipes_after["recipes"]), 0)

        asyncio.run(run_suite())

if __name__ == "__main__":
    unittest.main()
