"""Gemini Vision API service for Gym Machine Recognition & Nutrition Label Scanning."""
import os
import json
import base64
import httpx
from typing import Dict, Any, Optional

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"


def get_api_key(override_key: Optional[str] = None) -> Optional[str]:
    if override_key and override_key.strip():
        return override_key.strip()
    return os.environ.get("GEMINI_API_KEY")


async def identify_gym_machine(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Sends an image of gym equipment to Gemini Vision to identify the machine,
    targeted muscles, exercise names, and setup tips.
    """
    key = get_api_key(api_key)
    if not key:
        return {
            "success": False,
            "error": "No Gemini API key configured. Please enter your Google Gemini API key in Settings.",
        }

    b64_image = base64.b64encode(image_bytes).decode("utf-8")

    prompt = (
        "Identify the gym machine or exercise equipment in this image. "
        "Return ONLY a clean JSON object (no markdown code fences) with these fields: "
        "machine_name (string), "
        "exercise_name (string), "
        "primary_muscles (array of strings, e.g. ['Quads', 'Glutes']), "
        "secondary_muscles (array of strings), "
        "equipment_type (string, e.g. 'Cable', 'Plate Loaded', 'Pin Selector', 'Free Weight', 'Cardio'), "
        "suggested_sets (number, e.g. 3), "
        "suggested_reps (number, e.g. 10), "
        "instructions (concise 2-sentence guide on how to perform the movement safely)."
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": b64_image,
                        }
                    },
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }

    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.post(
                f"{GEMINI_API_URL}?key={key}",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code != 200:
                return {
                    "success": False,
                    "error": f"Gemini API returned status {resp.status_code}: {resp.text}",
                }

            result_json = resp.json()
            candidates = result_json.get("candidates", [])
            if not candidates:
                return {"success": False, "error": "No recognition result from Gemini Vision."}

            text_output = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            parsed = json.loads(text_output)
            return {"success": True, "data": parsed}
    except Exception as e:
        return {"success": False, "error": f"Failed to identify machine: {str(e)}"}


async def scan_nutrition_label(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Sends an image of a nutrition label to Gemini Vision to extract
    calories, macros, serving sizes, and product details.
    """
    key = get_api_key(api_key)
    if not key:
        return {
            "success": False,
            "error": "No Gemini API key configured. Please enter your Google Gemini API key in Settings.",
        }

    b64_image = base64.b64encode(image_bytes).decode("utf-8")

    prompt = (
        "Extract the nutrition facts from this food packaging or label image. "
        "Return ONLY a clean JSON object (no markdown code fences) with these fields: "
        "product_name (string, or 'Unknown Food' if not visible), "
        "serving_size_g (number in grams, e.g. 100), "
        "calories (number per serving), "
        "protein_g (number in grams), "
        "carbs_g (number in grams), "
        "fat_g (number in grams), "
        "fiber_g (number in grams or null), "
        "sugar_g (number in grams or null), "
        "sodium_mg (number in mg or null)."
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": b64_image,
                        }
                    },
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }

    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.post(
                f"{GEMINI_API_URL}?key={key}",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code != 200:
                return {
                    "success": False,
                    "error": f"Gemini API returned status {resp.status_code}: {resp.text}",
                }

            result_json = resp.json()
            candidates = result_json.get("candidates", [])
            if not candidates:
                return {"success": False, "error": "No text extracted from label."}

            text_output = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            parsed = json.loads(text_output)
            return {"success": True, "data": parsed}
    except Exception as e:
        return {"success": False, "error": f"Failed to extract nutrition label: {str(e)}"}

