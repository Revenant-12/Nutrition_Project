"""Smart Recipe Recommendation & Safe Food Scoring Engine.
Implements Pseudocode Section 4.2.
"""
import json
import sqlite3
from typing import List, Dict, Any, Optional
from data.db import get_connection

SAFETY_RANKS_ORDER = {
    "always_safe": 3,
    "safe": 2,
    "mostly_safe": 1,
}


def get_safe_food_map() -> Dict[str, str]:
    """Returns a dict mapping lowercase ingredient name to its safety ranking."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT name, ranking FROM safe_foods")
    safe_map = {row["name"].lower().strip(): row["ranking"] for row in c.fetchall()}
    conn.close()
    return safe_map


def get_frequently_used_ingredients(limit: int = 15) -> List[str]:
    """
    Finds frequently used ingredients in logged meals and existing recipes.
    """
    conn = get_connection()
    c = conn.cursor()
    # Check recipe ingredients
    c.execute("SELECT ingredients_json FROM recipes")
    freq: Dict[str, int] = {}
    for row in c.fetchall():
        try:
            ings = json.loads(row["ingredients_json"])
            for ing in ings:
                name = ing.get("name", "").lower().strip()
                if name:
                    freq[name] = freq.get(name, 0) + 1
        except Exception:
            pass

    # Check logged meal names as staples
    c.execute("SELECT name FROM meals_logged ORDER BY id DESC LIMIT 50")
    for row in c.fetchall():
        name = row["name"].lower().strip()
        if name:
            freq[name] = freq.get(name, 0) + 1

    conn.close()
    sorted_ings = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    return [name for name, _ in sorted_ings[:limit]]


def recommend_recipes(
    meal_type: Optional[str] = None,  # 'breakfast', 'meal', 'snack', 'dessert' or None
    use_safe_foods: bool = False,
    safe_rank_required: str = "mostly_safe",  # 'always_safe', 'safe', 'mostly_safe'
    filter_mode: str = "soft",  # 'hard' or 'soft'
    specific_ingredients: Optional[List[str]] = None,
    prefer_familiar: bool = False,
    prioritize: str = "calories",  # 'calories' or 'macros'
    target_calories_remaining: float = 600.0,
    target_protein_remaining: float = 30.0,
    target_carbs_remaining: float = 50.0,
    target_fat_remaining: float = 20.0,
) -> List[Dict[str, Any]]:
    """
    Recommends and ranks recipes according to criteria in Pseudocode Section 4.2.
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, meal_type, batch_weight_g, total_calories, total_protein_g, total_carbs_g, total_fat_g, ingredients_json, notes FROM recipes")
    rows = c.fetchall()
    conn.close()

    if not rows:
        return []

    safe_map = get_safe_food_map() if use_safe_foods else {}
    min_rank_val = SAFETY_RANKS_ORDER.get(safe_rank_required, 1)
    frequent_ings = set(get_frequently_used_ingredients()) if prefer_familiar else set()

    clean_specific = [s.lower().strip() for s in (specific_ingredients or []) if s.strip()]

    candidates = []
    for r in rows:
        recipe_dict = {
            "id": r["id"],
            "name": r["name"],
            "meal_type": r["meal_type"],
            "batch_weight_g": r["batch_weight_g"],
            "calories": r["total_calories"],
            "protein_g": r["total_protein_g"],
            "carbs_g": r["total_carbs_g"],
            "fat_g": r["total_fat_g"],
            "notes": r["notes"],
        }
        try:
            ings = json.loads(r["ingredients_json"])
        except Exception:
            ings = []
        recipe_dict["ingredients"] = ings
        ing_names = [i.get("name", "").lower().strip() for i in ings]

        # Meal type filter
        if meal_type and meal_type.lower() != "any":
            if recipe_dict["meal_type"].lower() != meal_type.lower():
                continue

        # Specific ingredients filter
        if clean_specific:
            matches_specific = any(spec in " ".join(ing_names) for spec in clean_specific)
            if not matches_specific:
                continue

        # Safe food evaluation
        safe_score = 0
        all_safe = True
        has_unsafe = False
        for iname in ing_names:
            rank = safe_map.get(iname)
            if rank:
                r_val = SAFETY_RANKS_ORDER.get(rank, 0)
                if r_val >= min_rank_val:
                    safe_score += r_val
                else:
                    all_safe = False
                    has_unsafe = True
            else:
                # Ingredient not in safe food list
                all_safe = False
                has_unsafe = True

        if use_safe_foods and filter_mode == "hard":
            # Hard filter: Exclude any recipe containing an ingredient outside selected rank or not in list
            if has_unsafe:
                continue

        recipe_dict["safe_score"] = safe_score
        recipe_dict["all_safe"] = all_safe

        # Familiarity score
        familiarity_score = 0
        if prefer_familiar and frequent_ings:
            familiarity_score = sum(1 for iname in ing_names if iname in frequent_ings)
        recipe_dict["familiarity_score"] = familiarity_score

        # Nutrition fit score
        cal_diff = abs(recipe_dict["calories"] - target_calories_remaining)
        p_diff = abs(recipe_dict["protein_g"] - target_protein_remaining)
        c_diff = abs(recipe_dict["carbs_g"] - target_carbs_remaining)
        f_diff = abs(recipe_dict["fat_g"] - target_fat_remaining)

        if prioritize == "macros":
            # Prioritize matching protein and carbs/fat
            nutr_penalty = (p_diff * 4.0) + (c_diff * 2.0) + (f_diff * 3.0) + (cal_diff * 0.2)
        else:
            # Prioritize matching calorie target
            nutr_penalty = cal_diff + (p_diff * 1.5)

        # Composite score (lower is better)
        # We reward safe score (-20 per safe match) and familiarity (-15 per familiar ingredient)
        composite_score = nutr_penalty - (safe_score * 20.0) - (familiarity_score * 15.0)
        recipe_dict["score"] = composite_score
        candidates.append(recipe_dict)

    # Sort candidates by score
    candidates.sort(key=lambda x: x["score"])

    # Pseudocode Section 4.2.1.3:
    # Soft filter: if fewer than 3 matches exist, allow recipes containing neutral ingredients.
    return candidates

