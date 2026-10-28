"""FastAPI Application for Nutrition & Workout Tracker.
Exposes REST API endpoints and serves the mobile-first PWA frontend.
"""
import os
import json
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from pydantic import BaseModel, Field

from data.db import get_connection, init_db
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
from services.food_api import search_foods, lookup_barcode
from services.gemini_vision import identify_gym_machine, scan_nutrition_label
from services.recipe_engine import recommend_recipes

app = FastAPI(title="Adaptive Nutrition & Fitness Tracker", version="1.0.0")

# Prevent stale browser caching during development and updates
@app.middleware("http")
async def add_no_cache_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# Initialize database on startup
init_db()

# --- Pydantic Request Models ---

class OnboardingRequest(BaseModel):
    height_cm: float
    weight_kg: float
    age: int
    sex: str
    hrt_status: bool = False
    hrt_type: Optional[str] = None
    hrt_months: int = 0
    body_fat_pct: Optional[float] = None
    activity_level: str
    activity_mode: str = "basic"
    goal: str
    calorie_offset: Optional[float] = None
    activity_goal_type: str = "maintenance"
    activity_goal_detail: Optional[str] = None
    safe_food_tracker_enabled: bool = False
    safe_foods: Optional[List[Dict[str, str]]] = None  # [{name, ranking}]
    display_preference: str = "both"  # 'calories', 'macros', 'both'
    gemini_api_key: Optional[str] = None


class ProfileUpdateRequest(BaseModel):
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    age: Optional[int] = None
    sex: Optional[str] = None
    hrt_status: Optional[bool] = None
    hrt_type: Optional[str] = None
    hrt_months: Optional[int] = None
    body_fat_pct: Optional[float] = None
    activity_level: Optional[str] = None
    goal: Optional[str] = None
    calorie_offset: Optional[float] = None
    display_preference: Optional[str] = None
    safe_food_tracker_enabled: Optional[bool] = None
    gemini_api_key: Optional[str] = None


class RecipeIngredient(BaseModel):
    name: str
    weight_g: float
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float


class CreateRecipeRequest(BaseModel):
    name: str
    meal_type: str
    ingredients: List[RecipeIngredient]
    notes: Optional[str] = None
    add_to_safe_foods: bool = False
    safe_ranking: Optional[str] = "safe"


class RecommendRecipeRequest(BaseModel):
    meal_type: Optional[str] = None
    use_safe_foods: bool = False
    safe_rank_required: str = "mostly_safe"
    filter_mode: str = "soft"
    specific_ingredients: Optional[List[str]] = None
    prefer_familiar: bool = False
    prioritize: str = "calories"


class LogRecipePortionRequest(BaseModel):
    recipe_id: int
    portion_weight_g: float
    date_str: Optional[str] = None


class LogMealRequest(BaseModel):
    name: str
    meal_type: str = "meal"
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    portion_weight_g: Optional[float] = None
    recipe_id: Optional[int] = None
    date_str: Optional[str] = None


class CopyMealRequest(BaseModel):
    meal_id: int
    target_date_str: Optional[str] = None


class ExerciseSet(BaseModel):
    set_number: int
    weight_lbs: Optional[float] = None
    reps: Optional[int] = None
    distance_miles: Optional[float] = None
    duration_minutes: Optional[float] = None


class LoggedExercise(BaseModel):
    exercise_name: str
    category: str = "strength"  # 'strength' or 'cardio'
    sets: List[ExerciseSet]


class LogWorkoutRequest(BaseModel):
    duration_minutes: float
    exercises: List[LoggedExercise]
    muscles_worked: Optional[List[str]] = None
    date_str: Optional[str] = None


class SafeFoodRequest(BaseModel):
    name: str
    ranking: str  # 'always_safe', 'safe', 'mostly_safe'


# --- Helper to get user profile ---

def get_current_profile_dict() -> Optional[Dict[str, Any]]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM user_profile ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return dict(row)


# --- API Routes ---

@app.get("/api/profile")
async def get_profile():
    profile = get_current_profile_dict()
    if not profile:
        return {"onboarded": False, "profile": None}
    return {"onboarded": True, "profile": profile}


@app.post("/api/profile/onboarding")
async def save_onboarding(data: OnboardingRequest):
    # Calculate BMR
    bmr = calculate_bmr(
        weight_kg=data.weight_kg,
        height_cm=data.height_cm,
        age=data.age,
        sex=data.sex,
        hrt_status=data.hrt_status,
        hrt_type=data.hrt_type,
        hrt_months=data.hrt_months,
        body_fat_pct=data.body_fat_pct,
    )
    baseline_tdee = calculate_tdee(bmr, data.activity_level)
    daily_target_calories = calculate_target_calories(baseline_tdee, data.goal, data.calorie_offset)
    macro_cat = determine_macro_category_from_onboarding(data.goal, data.activity_level)
    macros = calculate_macros(
        weight_kg=data.weight_kg,
        daily_calories=daily_target_calories,
        macro_category=macro_cat,
        body_fat_pct=data.body_fat_pct,
        sex=data.sex,
        hrt_status=data.hrt_status,
        hrt_type=data.hrt_type,
        hrt_months=data.hrt_months,
    )

    now_iso = datetime.now().isoformat()
    today_str = date.today().isoformat()

    conn = get_connection()
    c = conn.cursor()

    # Clear previous user profiles (single user mode)
    c.execute("DELETE FROM user_profile")

    c.execute("""
    INSERT INTO user_profile (
        height_cm, weight_kg, age, sex, hrt_status, hrt_type, hrt_months,
        body_fat_pct, activity_level, activity_mode, goal, calorie_offset,
        activity_goal_type, activity_goal_detail, safe_food_tracker_enabled,
        display_preference, bmr, baseline_tdee, daily_target_calories,
        macro_category, target_protein_g, target_fat_g, target_carbs_g,
        last_rebalance_date, gemini_api_key, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.height_cm, data.weight_kg, data.age, data.sex,
        1 if data.hrt_status else 0, data.hrt_type, data.hrt_months,
        data.body_fat_pct, data.activity_level, data.activity_mode, data.goal,
        data.calorie_offset or 0.0, data.activity_goal_type, data.activity_goal_detail,
        1 if data.safe_food_tracker_enabled else 0, data.display_preference,
        round(bmr, 1), round(baseline_tdee, 1), round(daily_target_calories, 0),
        macro_cat, macros["protein_g"], macros["fat_g"], macros["carbs_g"],
        today_str, data.gemini_api_key, now_iso, now_iso
    ))

    # Add safe foods if supplied
    if data.safe_food_tracker_enabled and data.safe_foods:
        for sf in data.safe_foods:
            name = sf.get("name", "").strip()
            rank = sf.get("ranking", "safe")
            if name:
                c.execute(
                    "INSERT OR REPLACE INTO safe_foods (name, ranking, created_at) VALUES (?, ?, ?)",
                    (name, rank, now_iso)
                )

    conn.commit()
    conn.close()

    return {"success": True, "message": "Onboarding complete!", "profile": get_current_profile_dict()}


@app.put("/api/profile")
async def update_profile(data: ProfileUpdateRequest):
    profile = get_current_profile_dict()
    if not profile:
        raise HTTPException(status_code=404, detail="No profile found. Complete onboarding first.")

    height_cm = data.height_cm if data.height_cm is not None else profile["height_cm"]
    weight_kg = data.weight_kg if data.weight_kg is not None else profile["weight_kg"]
    age = data.age if data.age is not None else profile["age"]
    sex = data.sex if data.sex is not None else profile["sex"]
    hrt_status = data.hrt_status if data.hrt_status is not None else bool(profile["hrt_status"])
    hrt_type = data.hrt_type if data.hrt_type is not None else profile["hrt_type"]
    hrt_months = data.hrt_months if data.hrt_months is not None else profile["hrt_months"]
    body_fat_pct = data.body_fat_pct if data.body_fat_pct is not None else profile["body_fat_pct"]
    activity_level = data.activity_level if data.activity_level is not None else profile["activity_level"]
    goal = data.goal if data.goal is not None else profile["goal"]
    calorie_offset = data.calorie_offset if data.calorie_offset is not None else profile["calorie_offset"]
    display_preference = data.display_preference if data.display_preference is not None else profile["display_preference"]
    safe_food_tracker_enabled = (
        data.safe_food_tracker_enabled if data.safe_food_tracker_enabled is not None
        else bool(profile["safe_food_tracker_enabled"])
    )
    gemini_api_key = data.gemini_api_key if data.gemini_api_key is not None else profile["gemini_api_key"]

    bmr = calculate_bmr(
        weight_kg=weight_kg,
        height_cm=height_cm,
        age=age,
        sex=sex,
        hrt_status=hrt_status,
        hrt_type=hrt_type,
        hrt_months=hrt_months,
        body_fat_pct=body_fat_pct,
    )
    baseline_tdee = calculate_tdee(bmr, activity_level)
    daily_target_calories = calculate_target_calories(baseline_tdee, goal, calorie_offset)
    macro_cat = determine_macro_category_from_onboarding(goal, activity_level)
    macros = calculate_macros(
        weight_kg=weight_kg,
        daily_calories=daily_target_calories,
        macro_category=macro_cat,
        body_fat_pct=body_fat_pct,
        sex=sex,
        hrt_status=hrt_status,
        hrt_type=hrt_type,
        hrt_months=hrt_months,
    )

    now_iso = datetime.now().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
    UPDATE user_profile SET
        height_cm = ?, weight_kg = ?, age = ?, sex = ?, hrt_status = ?, hrt_type = ?, hrt_months = ?,
        body_fat_pct = ?, activity_level = ?, goal = ?, calorie_offset = ?, display_preference = ?,
        safe_food_tracker_enabled = ?, gemini_api_key = ?, bmr = ?, baseline_tdee = ?,
        daily_target_calories = ?, macro_category = ?, target_protein_g = ?, target_fat_g = ?,
        target_carbs_g = ?, updated_at = ?
    WHERE id = ?
    """, (
        height_cm, weight_kg, age, sex, 1 if hrt_status else 0, hrt_type, hrt_months,
        body_fat_pct, activity_level, goal, calorie_offset, display_preference,
        1 if safe_food_tracker_enabled else 0, gemini_api_key, round(bmr, 1),
        round(baseline_tdee, 1), round(daily_target_calories, 0), macro_cat,
        macros["protein_g"], macros["fat_g"], macros["carbs_g"], now_iso, profile["id"]
    ))
    conn.commit()
    conn.close()

    return {"success": True, "profile": get_current_profile_dict()}


@app.get("/api/dashboard")
async def get_dashboard(target_date: Optional[str] = None):
    profile = get_current_profile_dict()
    if not profile:
        return {"onboarded": False}

    date_str = target_date or date.today().isoformat()

    conn = get_connection()
    c = conn.cursor()

    # Get meals logged for date
    c.execute(
        "SELECT * FROM meals_logged WHERE date_str = ? ORDER BY id ASC",
        (date_str,)
    )
    meals = [dict(r) for r in c.fetchall()]

    # Sum consumed calories and macros
    calories_eaten = sum(m["calories"] for m in meals)
    protein_eaten = sum(m["protein_g"] for m in meals)
    carbs_eaten = sum(m["carbs_g"] for m in meals)
    fat_eaten = sum(m["fat_g"] for m in meals)

    target_cal = profile["daily_target_calories"] or 2000.0
    target_p = profile["target_protein_g"] or 150.0
    target_c = profile["target_carbs_g"] or 200.0
    target_f = profile["target_fat_g"] or 60.0

    calories_remaining = target_cal - calories_eaten
    protein_remaining = target_p - protein_eaten
    carbs_remaining = target_c - carbs_eaten
    fat_remaining = target_f - fat_eaten

    # Workouts for date
    c.execute(
        "SELECT * FROM workouts WHERE date_str = ? ORDER BY id ASC",
        (date_str,)
    )
    workouts = [dict(r) for r in c.fetchall()]

    # Unread notifications
    c.execute("SELECT * FROM notifications WHERE is_read = 0 ORDER BY id DESC")
    notifications = [dict(r) for r in c.fetchall()]

    conn.close()

    return {
        "onboarded": True,
        "date": date_str,
        "display_preference": profile["display_preference"],
        "target": {
            "calories": target_cal,
            "protein_g": target_p,
            "carbs_g": target_c,
            "fat_g": target_f,
        },
        "consumed": {
            "calories": round(calories_eaten, 1),
            "protein_g": round(protein_eaten, 1),
            "carbs_g": round(carbs_eaten, 1),
            "fat_g": round(fat_eaten, 1),
        },
        "remaining": {
            "calories": round(calories_remaining, 1),
            "protein_g": round(protein_remaining, 1),
            "carbs_g": round(carbs_remaining, 1),
            "fat_g": round(fat_remaining, 1),
        },
        "meals": meals,
        "workouts": workouts,
        "notifications": notifications,
    }


# --- Workouts & Adaptive Rebalancing Engine ---

@app.get("/api/workouts")
async def list_workouts():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM workouts ORDER BY id DESC LIMIT 50")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return {"workouts": rows}


@app.post("/api/workouts")
async def log_workout(data: LogWorkoutRequest):
    profile = get_current_profile_dict()
    user_weight_kg = profile["weight_kg"] if profile else 70.0

    total_weight_lifted_lbs = 0.0
    has_strength = False
    has_cardio = False

    muscles_worked = set(data.muscles_worked or [])

    for ex in data.exercises:
        cat = ex.category.lower()
        if cat == "strength":
            has_strength = True
            for s in ex.sets:
                w = s.weight_lbs or 0.0
                r = s.reps or 0
                total_weight_lifted_lbs += (w * r)
        else:
            has_cardio = True

    # Calculate calories burned
    # Strength = duration * (weight_kg * 0.06 kcal/min)
    # Cardio = MET(7.0) * weight_kg * (duration / 60)
    calories_burned = 0.0
    if has_strength and not has_cardio:
        calories_burned = estimate_workout_energy_burn(True, data.duration_minutes, user_weight_kg)
    elif has_cardio and not has_strength:
        calories_burned = estimate_workout_energy_burn(False, data.duration_minutes, user_weight_kg)
    else:
        # Mixed workout: split duration
        half_dur = data.duration_minutes / 2.0
        calories_burned = (
            estimate_workout_energy_burn(True, half_dur, user_weight_kg) +
            estimate_workout_energy_burn(False, half_dur, user_weight_kg)
        )

    comparison_text = get_workout_comparison(total_weight_lifted_lbs)
    date_str = data.date_str or date.today().isoformat()
    now_iso = datetime.now().isoformat()

    conn = get_connection()
    c = conn.cursor()
    c.execute("""
    INSERT INTO workouts (
        date_str, duration_minutes, is_strength, total_weight_lifted_lbs,
        calories_burned, muscles_worked_json, exercises_json, comparison_text, logged_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        date_str, data.duration_minutes, 1 if has_strength else 0,
        round(total_weight_lifted_lbs, 1), round(calories_burned, 1),
        json.dumps(list(muscles_worked)),
        json.dumps([ex.model_dump() for ex in data.exercises]),
        comparison_text, now_iso
    ))
    conn.commit()
    conn.close()

    # Trigger rebalance check
    await check_adaptive_rebalance()

    return {
        "success": True,
        "total_weight_lifted_lbs": round(total_weight_lifted_lbs, 1),
        "comparison_text": comparison_text,
        "calories_burned": round(calories_burned, 1),
    }


@app.delete("/api/workouts/{workout_id}")
async def delete_workout(workout_id: int):
    """Deletes a logged workout."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM workouts WHERE id = ?", (workout_id,))
    conn.commit()
    conn.close()
    return {"success": True}


@app.get("/api/workouts/rebalance-check")
async def check_adaptive_rebalance():
    """
    Evaluates rolling activity & TDEE rebalance every 7 days (Pseudocode Section 6.c).
    """
    profile = get_current_profile_dict()
    if not profile:
        return {"rebalanced": False, "reason": "No profile"}

    last_rebalance_str = profile.get("last_rebalance_date")
    today = date.today()

    if last_rebalance_str:
        last_rebalance = date.fromisoformat(last_rebalance_str)
        days_since = (today - last_rebalance).days
        if days_since < 7:
            return {"rebalanced": False, "days_until_next": 7 - days_since}

    # Fetch workout calories burned over the previous 14 days
    fourteen_days_ago = (today - timedelta(days=14)).isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT calories_burned FROM workouts WHERE date_str >= ?",
        (fourteen_days_ago,)
    )
    burn_records = [r["calories_burned"] for r in c.fetchall()]

    rebalance_result = evaluate_rolling_tdee_rebalance(
        bmr=profile["bmr"],
        current_baseline_tdee=profile["baseline_tdee"],
        past_14_days_burns=burn_records,
        goal=profile["goal"],
        custom_offset=profile["calorie_offset"],
    )

    new_baseline_tdee = rebalance_result["new_baseline_tdee"]
    new_target_calories = rebalance_result["new_target_calories"]
    notification_msg = rebalance_result["notification"]

    # Re-calculate macros
    macros = calculate_macros(
        weight_kg=profile["weight_kg"],
        daily_calories=new_target_calories,
        macro_category=profile["macro_category"] or "Active / Fitness",
        body_fat_pct=profile["body_fat_pct"],
        sex=profile["sex"],
        hrt_status=bool(profile["hrt_status"]),
        hrt_type=profile["hrt_type"],
        hrt_months=profile["hrt_months"],
    )

    now_iso = datetime.now().isoformat()
    today_str = today.isoformat()

    c.execute("""
    UPDATE user_profile SET
        baseline_tdee = ?,
        daily_target_calories = ?,
        target_protein_g = ?,
        target_fat_g = ?,
        target_carbs_g = ?,
        last_rebalance_date = ?,
        updated_at = ?
    WHERE id = ?
    """, (
        new_baseline_tdee, new_target_calories,
        macros["protein_g"], macros["fat_g"], macros["carbs_g"],
        today_str, now_iso, profile["id"]
    ))

    # Insert notification for user
    c.execute(
        "INSERT INTO notifications (message, type, created_at) VALUES (?, 'rebalance', ?)",
        (notification_msg, now_iso)
    )

    conn.commit()
    conn.close()

    return {"rebalanced": True, "details": rebalance_result}


# --- Recipes & Smart Cookbook ---

@app.get("/api/recipes")
async def list_recipes():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM recipes ORDER BY id DESC")
    recipes = []
    for r in c.fetchall():
        item = dict(r)
        try:
            item["ingredients"] = json.loads(item["ingredients_json"])
        except Exception:
            item["ingredients"] = []
        recipes.append(item)
    conn.close()
    return {"recipes": recipes}


@app.post("/api/recipes")
async def create_recipe(data: CreateRecipeRequest):
    # Total Batch Weight = sum of raw ingredients (Pseudocode Section 4.1.4.1)
    batch_weight_g = sum(i.weight_g for i in data.ingredients)
    total_cal = sum(i.calories for i in data.ingredients)
    total_p = sum(i.protein_g for i in data.ingredients)
    total_c = sum(i.carbs_g for i in data.ingredients)
    total_f = sum(i.fat_g for i in data.ingredients)

    now_iso = datetime.now().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
    INSERT INTO recipes (
        name, meal_type, batch_weight_g, total_calories, total_protein_g,
        total_carbs_g, total_fat_g, ingredients_json, notes, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.name, data.meal_type, round(batch_weight_g, 1),
        round(total_cal, 1), round(total_p, 1), round(total_c, 1), round(total_f, 1),
        json.dumps([i.model_dump() for i in data.ingredients]), data.notes, now_iso
    ))
    recipe_id = c.lastrowid

    # Optional: add ingredients to safe food tracker
    if data.add_to_safe_foods and data.safe_ranking:
        for i in data.ingredients:
            if i.name.strip():
                c.execute(
                    "INSERT OR REPLACE INTO safe_foods (name, ranking, created_at) VALUES (?, ?, ?)",
                    (i.name.strip(), data.safe_ranking, now_iso)
                )

    conn.commit()
    conn.close()

    return {
        "success": True,
        "recipe_id": recipe_id,
        "batch_weight_g": batch_weight_g,
        "total_calories": total_cal,
        "total_protein_g": total_p,
        "total_carbs_g": total_c,
        "total_fat_g": total_f,
    }


@app.delete("/api/recipes/{recipe_id}")
async def delete_recipe(recipe_id: int):
    """Deletes a saved recipe."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
    conn.commit()
    conn.close()
    return {"success": True}


@app.post("/api/recipes/recommend")
async def get_recipe_recommendations(req: RecommendRecipeRequest):
    profile = get_current_profile_dict()
    today_str = date.today().isoformat()

    # Calculate remaining targets for today
    dash = await get_dashboard(today_str)
    rem = dash.get("remaining", {})
    target_cal_rem = rem.get("calories", 500.0)
    target_p_rem = rem.get("protein_g", 30.0)
    target_c_rem = rem.get("carbs_g", 50.0)
    target_f_rem = rem.get("fat_g", 15.0)

    use_safe = req.use_safe_foods or (bool(profile["safe_food_tracker_enabled"]) if profile else False)

    recommendations = recommend_recipes(
        meal_type=req.meal_type,
        use_safe_foods=use_safe,
        safe_rank_required=req.safe_rank_required,
        filter_mode=req.filter_mode,
        specific_ingredients=req.specific_ingredients,
        prefer_familiar=req.prefer_familiar,
        prioritize=req.prioritize,
        target_calories_remaining=target_cal_rem,
        target_protein_remaining=target_p_rem,
        target_carbs_remaining=target_c_rem,
        target_fat_remaining=target_f_rem,
    )

    return {"count": len(recommendations), "recipes": recommendations}


# --- Meals Logging ---

@app.post("/api/meals")
async def log_meal(data: LogMealRequest):
    date_str = data.date_str or date.today().isoformat()
    now_iso = datetime.now().isoformat()

    conn = get_connection()
    c = conn.cursor()
    c.execute("""
    INSERT INTO meals_logged (
        date_str, name, meal_type, calories, protein_g, carbs_g, fat_g,
        portion_weight_g, recipe_id, logged_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        date_str, data.name, data.meal_type,
        round(data.calories, 1), round(data.protein_g, 1),
        round(data.carbs_g, 1), round(data.fat_g, 1),
        data.portion_weight_g, data.recipe_id, now_iso
    ))
    conn.commit()
    conn.close()

    return {"success": True, "message": "Meal logged successfully"}


@app.post("/api/meals/log-recipe-portion")
async def log_recipe_portion(data: LogRecipePortionRequest):
    """
    Logs a portion of a recipe per Pseudocode Section 4.1.4:
    Portion Consumed (g) / Total Batch Weight (g) = Fraction of total macros to log
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM recipes WHERE id = ?", (data.recipe_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Recipe not found")

    scaled = scale_recipe_portion(
        portion_consumed_g=data.portion_weight_g,
        total_batch_weight_g=row["batch_weight_g"],
        total_calories=row["total_calories"],
        total_protein_g=row["total_protein_g"],
        total_carbs_g=row["total_carbs_g"],
        total_fat_g=row["total_fat_g"],
    )

    d_str = data.date_str or date.today().isoformat()
    now_iso = datetime.now().isoformat()

    c.execute("""
    INSERT INTO meals_logged (
        date_str, name, meal_type, calories, protein_g, carbs_g, fat_g,
        portion_weight_g, recipe_id, logged_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        d_str, f"{row['name']} ({int(data.portion_weight_g)}g)", row["meal_type"],
        scaled["calories"], scaled["protein_g"], scaled["carbs_g"], scaled["fat_g"],
        data.portion_weight_g, data.recipe_id, now_iso
    ))
    conn.commit()
    conn.close()

    return {"success": True, "scaled": scaled}


@app.post("/api/meals/copy")
async def copy_meal(data: CopyMealRequest):
    """Copies a previously logged meal to target date (Pseudocode Section 5.3)."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM meals_logged WHERE id = ?", (data.meal_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Meal not found")

    target_d = data.target_date_str or date.today().isoformat()
    now_iso = datetime.now().isoformat()

    c.execute("""
    INSERT INTO meals_logged (
        date_str, name, meal_type, calories, protein_g, carbs_g, fat_g,
        portion_weight_g, recipe_id, logged_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        target_d, row["name"], row["meal_type"],
        row["calories"], row["protein_g"], row["carbs_g"], row["fat_g"],
        row["portion_weight_g"], row["recipe_id"], now_iso
    ))
    conn.commit()
    conn.close()

    return {"success": True, "message": "Meal copied successfully"}


@app.delete("/api/meals/{meal_id}")
async def delete_meal(meal_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM meals_logged WHERE id = ?", (meal_id,))
    conn.commit()
    conn.close()
    return {"success": True}


# --- Safe Food Tracker ---

@app.get("/api/safe-foods")
async def list_safe_foods():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM safe_foods ORDER BY ranking DESC, name ASC")
    foods = [dict(r) for r in c.fetchall()]
    conn.close()
    return {"safe_foods": foods}


@app.post("/api/safe-foods")
async def add_safe_food(data: SafeFoodRequest):
    now_iso = datetime.now().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO safe_foods (name, ranking, created_at) VALUES (?, ?, ?)",
        (data.name.strip(), data.ranking, now_iso)
    )
    conn.commit()
    conn.close()
    return {"success": True}


@app.delete("/api/safe-foods/{food_id}")
async def delete_safe_food(food_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM safe_foods WHERE id = ?", (food_id,))
    conn.commit()
    conn.close()
    return {"success": True}


# --- Food Database Search & Barcode ---

@app.get("/api/foods/search")
async def search_food_items(q: str = Query(...)):
    results = await search_foods(q)
    return {"query": q, "results": results}


@app.get("/api/foods/barcode/{barcode}")
async def get_barcode_item(barcode: str):
    res = await lookup_barcode(barcode)
    if not res:
        raise HTTPException(status_code=404, detail="Barcode not found")
    return {"item": res}


# --- Exercise Library ---

@app.get("/api/exercises")
async def get_exercises(muscle: Optional[str] = None, q: Optional[str] = None):
    conn = get_connection()
    c = conn.cursor()
    query = "SELECT * FROM exercise_library WHERE 1=1"
    params = []
    if q:
        query += " AND name LIKE ?"
        params.append(f"%{q}%")
    if muscle:
        query += " AND target_muscles_json LIKE ?"
        params.append(f"%{muscle}%")

    c.execute(query + " ORDER BY name ASC", params)
    exercises = []
    for r in c.fetchall():
        item = dict(r)
        item["target_muscles"] = json.loads(item["target_muscles_json"])
        exercises.append(item)
    conn.close()
    return {"exercises": exercises}


@app.get("/api/exercises/previous-performance")
async def get_previous_exercise_performance(name: str = Query(...)):
    """
    Finds the sets and reps performed during the most recent workout where this exercise was logged.
    """
    clean_name = name.lower().strip()
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT date_str, exercises_json FROM workouts ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()

    for r in rows:
        try:
            ex_list = json.loads(r["exercises_json"])
            for ex in ex_list:
                if ex.get("exercise_name", "").lower().strip() == clean_name:
                    sets = ex.get("sets", [])
                    if sets:
                        return {
                            "found": True,
                            "last_date": r["date_str"],
                            "exercise_name": ex.get("exercise_name"),
                            "category": ex.get("category", "strength"),
                            "sets": sets,
                        }
        except Exception:
            continue

    return {"found": False, "sets": []}


# --- Gemini Vision Endpoints ---

@app.post("/api/vision/identify-machine")
async def identify_machine_endpoint(
    image: UploadFile = File(...),
    api_key: Optional[str] = Form(None),
):
    profile = get_current_profile_dict()
    key = api_key or (profile.get("gemini_api_key") if profile else None)

    contents = await image.read()
    res = await identify_gym_machine(contents, mime_type=image.content_type or "image/jpeg", api_key=key)
    return res


@app.post("/api/vision/scan-label")
async def scan_label_endpoint(
    image: UploadFile = File(...),
    api_key: Optional[str] = Form(None),
):
    profile = get_current_profile_dict()
    key = api_key or (profile.get("gemini_api_key") if profile else None)

    contents = await image.read()
    res = await scan_nutrition_label(contents, mime_type=image.content_type or "image/jpeg", api_key=key)
    return res


# --- Notifications ---

@app.post("/api/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notification_id,))
    conn.commit()
    conn.close()
    return {"success": True}


# --- Static files & PWA Serving ---

static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def root():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse("<h1>Nutrition & Workout Tracker PWA</h1><p>Frontend static files initializing...</p>")
