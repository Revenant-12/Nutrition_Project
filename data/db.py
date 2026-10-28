"""Database layer for the Nutrition & Workout application.
Uses SQLite for robust local and mobile-friendly storage.
"""
import sqlite3
import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, date

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "nutrition_app.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn


def init_db():
    conn = get_connection()
    c = conn.cursor()

    # User Profile table
    c.execute("""
    CREATE TABLE IF NOT EXISTS user_profile (
        id INTEGER PRIMARY KEY,
        height_cm REAL NOT NULL,
        weight_kg REAL NOT NULL,
        age INTEGER NOT NULL,
        sex TEXT NOT NULL,
        hrt_status INTEGER DEFAULT 0,
        hrt_type TEXT,
        hrt_months INTEGER DEFAULT 0,
        body_fat_pct REAL,
        activity_level TEXT NOT NULL,
        activity_mode TEXT DEFAULT 'basic',
        goal TEXT NOT NULL,
        calorie_offset REAL DEFAULT 0,
        activity_goal_type TEXT DEFAULT 'maintenance',
        activity_goal_detail TEXT,
        safe_food_tracker_enabled INTEGER DEFAULT 0,
        display_preference TEXT DEFAULT 'both',
        bmr REAL,
        baseline_tdee REAL,
        daily_target_calories REAL,
        macro_category TEXT,
        target_protein_g REAL,
        target_fat_g REAL,
        target_carbs_g REAL,
        last_rebalance_date TEXT,
        gemini_api_key TEXT,
        created_at TEXT,
        updated_at TEXT
    )
    """)

    # Safe Foods table (Section 1.1.7)
    c.execute("""
    CREATE TABLE IF NOT EXISTS safe_foods (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        ranking TEXT NOT NULL, -- 'always_safe', 'safe', 'mostly_safe'
        created_at TEXT
    )
    """)

    # Recipes table (Section 4.1)
    c.execute("""
    CREATE TABLE IF NOT EXISTS recipes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        meal_type TEXT NOT NULL, -- 'breakfast', 'meal', 'snack', 'dessert'
        batch_weight_g REAL NOT NULL,
        total_calories REAL NOT NULL,
        total_protein_g REAL NOT NULL,
        total_carbs_g REAL NOT NULL,
        total_fat_g REAL NOT NULL,
        ingredients_json TEXT NOT NULL,
        notes TEXT,
        created_at TEXT
    )
    """)

    # Meals logged table (Section 2.1 & 5)
    c.execute("""
    CREATE TABLE IF NOT EXISTS meals_logged (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date_str TEXT NOT NULL, -- YYYY-MM-DD
        name TEXT NOT NULL,
        meal_type TEXT,
        calories REAL NOT NULL,
        protein_g REAL NOT NULL,
        carbs_g REAL NOT NULL,
        fat_g REAL NOT NULL,
        portion_weight_g REAL,
        recipe_id INTEGER,
        logged_at TEXT
    )
    """)

    # Workouts table (Section 3 & 6)
    c.execute("""
    CREATE TABLE IF NOT EXISTS workouts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date_str TEXT NOT NULL, -- YYYY-MM-DD
        duration_minutes REAL NOT NULL,
        is_strength INTEGER DEFAULT 1,
        total_weight_lifted_lbs REAL DEFAULT 0,
        calories_burned REAL NOT NULL,
        muscles_worked_json TEXT,
        exercises_json TEXT NOT NULL,
        comparison_text TEXT,
        logged_at TEXT
    )
    """)

    # Exercise Library
    c.execute("""
    CREATE TABLE IF NOT EXISTS exercise_library (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        category TEXT NOT NULL, -- 'strength' or 'cardio'
        target_muscles_json TEXT NOT NULL,
        equipment_type TEXT
    )
    """)

    # Food item cache (Open Food Facts & common foods)
    c.execute("""
    CREATE TABLE IF NOT EXISTS food_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        brand TEXT,
        calories_per_100g REAL NOT NULL,
        protein_per_100g REAL NOT NULL,
        carbs_per_100g REAL NOT NULL,
        fat_per_100g REAL NOT NULL,
        serving_size_g REAL DEFAULT 100,
        barcode TEXT UNIQUE,
        is_staple INTEGER DEFAULT 0
    )
    """)

    # Notifications table (Section 6.d.iii)
    c.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message TEXT NOT NULL,
        type TEXT DEFAULT 'info',
        is_read INTEGER DEFAULT 0,
        created_at TEXT
    )
    """)

    conn.commit()
    conn.close()

    # Seed exercise library and common foods if empty
    seed_initial_data()


def seed_initial_data():
    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM exercise_library")
    if c.fetchone()[0] == 0:
        exercises = [
            ("Barbell Bench Press", "strength", ["Chest", "Triceps", "Front Delts"], "Barbell / Bench"),
            ("Incline Dumbbell Press", "strength", ["Upper Chest", "Front Delts"], "Dumbbells / Incline Bench"),
            ("Pec Deck / Chest Fly", "strength", ["Chest"], "Pec Deck Machine"),
            ("Cable Crossover", "strength", ["Chest"], "Cable Machine"),
            ("Barbell Back Squat", "strength", ["Quads", "Glutes", "Hamstrings"], "Squat Rack / Barbell"),
            ("Leg Press", "strength", ["Quads", "Glutes"], "45 Degree Leg Press Machine"),
            ("Leg Extension", "strength", ["Quads"], "Leg Extension Machine"),
            ("Hamstring Leg Curl", "strength", ["Hamstrings"], "Lying / Seated Leg Curl Machine"),
            ("Barbell Deadlift", "strength", ["Back", "Hamstrings", "Glutes", "Traps"], "Barbell"),
            ("Lat Pulldown", "strength", ["Lats", "Biceps", "Upper Back"], "Lat Pulldown Machine"),
            ("Seated Cable Row", "strength", ["Lats", "Rhomboids", "Biceps"], "Cable Row Machine"),
            ("Overhead Shoulder Press", "strength", ["Shoulders", "Triceps"], "Barbell / Dumbbells"),
            ("Lateral Raise", "strength", ["Side Delts"], "Dumbbells / Cable"),
            ("Barbell Bicep Curl", "strength", ["Biceps"], "Barbell / EZ Bar"),
            ("Tricep Rope Pushdown", "strength", ["Triceps"], "Cable Machine"),
            ("Plank / Hanging Leg Raise", "strength", ["Core", "Abs"], "Bodyweight / Pull-up Bar"),
            ("Treadmill Running", "cardio", ["Cardio", "Legs"], "Treadmill"),
            ("Stationary Bike", "cardio", ["Cardio", "Quads"], "Exercise Bike"),
            ("Rowing Machine", "cardio", ["Cardio", "Back", "Legs"], "Rowing Machine"),
            ("Elliptical Trainer", "cardio", ["Cardio", "Full Body"], "Elliptical Machine"),
            ("Stair Climber", "cardio", ["Cardio", "Glutes", "Calves"], "StairMaster Machine"),
        ]
        for name, cat, muscles, equip in exercises:
            c.execute(
                "INSERT OR IGNORE INTO exercise_library (name, category, target_muscles_json, equipment_type) VALUES (?, ?, ?, ?)",
                (name, cat, json.dumps(muscles), equip)
            )

    c.execute("SELECT COUNT(*) FROM food_cache WHERE is_staple = 1")
    if c.fetchone()[0] == 0:
        staples = [
            ("Chicken Breast (Skinless, Cooked)", "Generic", 165.0, 31.0, 0.0, 3.6, 100, 1),
            ("Eggs (Whole, Raw/Cooked)", "Generic", 143.0, 12.6, 0.7, 9.5, 100, 1),
            ("Egg Whites", "Generic", 52.0, 10.9, 0.7, 0.2, 100, 1),
            ("Ground Beef (90/10 Cooked)", "Generic", 217.0, 26.1, 0.0, 11.8, 100, 1),
            ("Salmon (Cooked)", "Generic", 206.0, 22.1, 0.0, 12.3, 100, 1),
            ("Tuna (Canned in Water)", "Generic", 116.0, 25.5, 0.0, 0.8, 100, 1),
            ("Whey Protein Powder", "Generic", 380.0, 78.0, 6.0, 4.0, 30, 1),
            ("Greek Yogurt (Nonfat, Plain)", "Generic", 59.0, 10.2, 3.6, 0.4, 100, 1),
            ("White Rice (Cooked)", "Generic", 130.0, 2.7, 28.2, 0.3, 100, 1),
            ("Brown Rice (Cooked)", "Generic", 112.0, 2.6, 23.5, 0.9, 100, 1),
            ("Oats (Rolled, Raw)", "Generic", 389.0, 16.9, 66.3, 6.9, 100, 1),
            ("Sweet Potato (Cooked)", "Generic", 90.0, 2.0, 20.7, 0.1, 100, 1),
            ("Broccoli (Cooked)", "Generic", 35.0, 2.4, 7.2, 0.4, 100, 1),
            ("Spinach (Raw)", "Generic", 23.0, 2.9, 3.6, 0.4, 100, 1),
            ("Olive Oil", "Generic", 884.0, 0.0, 0.0, 100.0, 15, 1),
            ("Avocado", "Generic", 160.0, 2.0, 8.5, 14.7, 100, 1),
            ("Peanut Butter", "Generic", 588.0, 25.0, 20.0, 50.0, 32, 1),
            ("Banana", "Generic", 89.0, 1.1, 22.8, 0.3, 100, 1),
            ("Apple", "Generic", 52.0, 0.3, 13.8, 0.2, 100, 1),
            ("Almonds", "Generic", 579.0, 21.2, 21.6, 49.9, 28, 1),
            ("Tofu (Firm)", "Generic", 144.0, 17.3, 2.8, 8.7, 100, 1),
            ("Cottage Cheese (Low Fat)", "Generic", 84.0, 11.1, 3.4, 2.3, 100, 1),
        ]
        for name, brand, cal, p, c_carb, f, s_size, staple in staples:
            c.execute(
                """INSERT INTO food_cache 
                (name, brand, calories_per_100g, protein_per_100g, carbs_per_100g, fat_per_100g, serving_size_g, is_staple)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (name, brand, cal, p, c_carb, f, s_size, staple)
            )

    conn.commit()
    conn.close()

