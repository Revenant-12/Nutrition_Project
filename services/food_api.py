"""Food Database service: Open Food Facts API + Local Cached Staples."""
import sqlite3
import httpx
from typing import List, Dict, Any, Optional
from data.db import get_connection

OPEN_FOOD_FACTS_SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl"
OPEN_FOOD_FACTS_BARCODE_URL = "https://world.openfoodfacts.org/api/v0/product/{barcode}.json"


async def search_foods(query: str, limit: int = 25) -> List[Dict[str, Any]]:
    """
    Searches local cached & staple foods first, then attempts Open Food Facts API.
    """
    results: List[Dict[str, Any]] = []
    q = query.strip()
    if not q:
        return results

    # 1. Search local SQLite database
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """SELECT id, name, brand, calories_per_100g, protein_per_100g, carbs_per_100g, fat_per_100g, serving_size_g, barcode
        FROM food_cache
        WHERE name LIKE ? OR brand LIKE ?
        ORDER BY is_staple DESC, name ASC
        LIMIT ?""",
        (f"%{q}%", f"%{q}%", limit),
    )
    for row in c.fetchall():
        results.append({
            "source": "local",
            "name": row["name"],
            "brand": row["brand"] or "Generic",
            "calories_per_100g": row["calories_per_100g"],
            "protein_per_100g": row["protein_per_100g"],
            "carbs_per_100g": row["carbs_per_100g"],
            "fat_per_100g": row["fat_per_100g"],
            "serving_size_g": row["serving_size_g"],
            "barcode": row["barcode"],
        })
    conn.close()

    # If we got enough local results, return them
    if len(results) >= limit:
        return results[:limit]

    # 2. Query Open Food Facts API (if online)
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(
                OPEN_FOOD_FACTS_SEARCH_URL,
                params={
                    "search_terms": q,
                    "search_simple": 1,
                    "action": "process",
                    "json": 1,
                    "page_size": limit - len(results),
                    "fields": "product_name,brands,nutriments,code",
                },
                headers={"User-Agent": "AntigravityNutritionApp - Python - Version 1.0"}
            )
            if resp.status_code == 200:
                data = resp.json()
                products = data.get("products", [])
                conn = get_connection()
                c = conn.cursor()
                for prod in products:
                    name = prod.get("product_name")
                    if not name:
                        continue
                    brand = prod.get("brands", "Generic")
                    nutr = prod.get("nutriments", {})
                    # Per 100g nutrients
                    kcal = float(nutr.get("energy-kcal_100g", nutr.get("energy-kcal", 0)) or 0)
                    protein = float(nutr.get("proteins_100g", nutr.get("proteins", 0)) or 0)
                    carbs = float(nutr.get("carbohydrates_100g", nutr.get("carbohydrates", 0)) or 0)
                    fat = float(nutr.get("fat_100g", nutr.get("fat", 0)) or 0)
                    code = prod.get("code")

                    item = {
                        "source": "openfoodfacts",
                        "name": name,
                        "brand": brand,
                        "calories_per_100g": round(kcal, 1),
                        "protein_per_100g": round(protein, 1),
                        "carbs_per_100g": round(carbs, 1),
                        "fat_per_100g": round(fat, 1),
                        "serving_size_g": 100.0,
                        "barcode": code,
                    }
                    results.append(item)

                    # Cache into local database for fast subsequent lookups
                    try:
                        c.execute(
                            """INSERT OR IGNORE INTO food_cache 
                            (name, brand, calories_per_100g, protein_per_100g, carbs_per_100g, fat_per_100g, serving_size_g, barcode, is_staple)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                            (name, brand, kcal, protein, carbs, fat, 100.0, code)
                        )
                    except Exception:
                        pass
                conn.commit()
                conn.close()
    except Exception:
        # Fallback gracefully to local results if offline or network timed out
        pass

    return results


async def lookup_barcode(barcode: str) -> Optional[Dict[str, Any]]:
    """Look up a product by barcode in cache or Open Food Facts."""
    clean_code = barcode.strip()
    if not clean_code:
        return None

    # Check local
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """SELECT name, brand, calories_per_100g, protein_per_100g, carbs_per_100g, fat_per_100g, serving_size_g, barcode
        FROM food_cache WHERE barcode = ?""",
        (clean_code,),
    )
    row = c.fetchone()
    conn.close()
    if row:
        return {
            "name": row["name"],
            "brand": row["brand"],
            "calories_per_100g": row["calories_per_100g"],
            "protein_per_100g": row["protein_per_100g"],
            "carbs_per_100g": row["carbs_per_100g"],
            "fat_per_100g": row["fat_per_100g"],
            "serving_size_g": row["serving_size_g"],
            "barcode": row["barcode"],
        }

    # Query Open Food Facts
    try:
        url = OPEN_FOOD_FACTS_BARCODE_URL.format(barcode=clean_code)
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(url, headers={"User-Agent": "AntigravityNutritionApp/1.0"})
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == 1:
                    prod = data.get("product", {})
                    name = prod.get("product_name", "Unknown Product")
                    brand = prod.get("brands", "Generic")
                    nutr = prod.get("nutriments", {})
                    kcal = float(nutr.get("energy-kcal_100g", 0) or 0)
                    protein = float(nutr.get("proteins_100g", 0) or 0)
                    carbs = float(nutr.get("carbohydrates_100g", 0) or 0)
                    fat = float(nutr.get("fat_100g", 0) or 0)

                    item = {
                        "name": name,
                        "brand": brand,
                        "calories_per_100g": round(kcal, 1),
                        "protein_per_100g": round(protein, 1),
                        "carbs_per_100g": round(carbs, 1),
                        "fat_per_100g": round(fat, 1),
                        "serving_size_g": 100.0,
                        "barcode": clean_code,
                    }
                    # Save to cache
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute(
                        """INSERT OR REPLACE INTO food_cache 
                        (name, brand, calories_per_100g, protein_per_100g, carbs_per_100g, fat_per_100g, serving_size_g, barcode, is_staple)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                        (name, brand, kcal, protein, carbs, fat, 100.0, clean_code)
                    )
                    conn.commit()
                    conn.close()
                    return item
    except Exception:
        pass

    return None

