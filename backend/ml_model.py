from transformers import pipeline
from PIL import Image
import io
import json

print("Loading food classification model...")

# This downloads the model once (~100MB) and caches it
# nateraw/food is trained specifically on Food-101 dataset
classifier = pipeline(
    "image-classification",
    model="nateraw/food",
    top_k=3
)

print("Model loaded!")

# Nutrition data per 100g for common foods
# This acts as our nutrition lookup after prediction
NUTRITION_DB = {
    "pizza": {"calories": 266, "protein": 11, "carbs": 33, "fats": 10},
    "hamburger": {"calories": 295, "protein": 17, "carbs": 24, "fats": 14},
    "burger": {"calories": 295, "protein": 17, "carbs": 24, "fats": 14},
    "sushi": {"calories": 150, "protein": 6, "carbs": 28, "fats": 1},
    "pasta": {"calories": 220, "protein": 8, "carbs": 43, "fats": 1},
    "salad": {"calories": 20, "protein": 1, "carbs": 4, "fats": 0},
    "fried_rice": {"calories": 163, "protein": 3, "carbs": 28, "fats": 4},
    "ice_cream": {"calories": 207, "protein": 4, "carbs": 24, "fats": 11},
    "chocolate_cake": {"calories": 371, "protein": 5, "carbs": 50, "fats": 18},
    "omelette": {"calories": 154, "protein": 11, "carbs": 1, "fats": 12},
    "sandwich": {"calories": 250, "protein": 11, "carbs": 33, "fats": 9},
    "steak": {"calories": 271, "protein": 26, "carbs": 0, "fats": 18},
    "soup": {"calories": 50, "protein": 3, "carbs": 7, "fats": 1},
    "noodles": {"calories": 138, "protein": 5, "carbs": 25, "fats": 2},
    "waffles": {"calories": 291, "protein": 8, "carbs": 37, "fats": 13},
    "pancakes": {"calories": 227, "protein": 6, "carbs": 36, "fats": 7},
    "french_fries": {"calories": 312, "protein": 3, "carbs": 41, "fats": 15},
    "hot_dog": {"calories": 290, "protein": 11, "carbs": 24, "fats": 17},
    "tacos": {"calories": 226, "protein": 9, "carbs": 20, "fats": 12},
    "samosa": {"calories": 308, "protein": 6, "carbs": 32, "fats": 18},
    "chicken_wings": {"calories": 290, "protein": 27, "carbs": 0, "fats": 19},
    "grilled_salmon": {"calories": 206, "protein": 22, "carbs": 0, "fats": 12},
    "donuts": {"calories": 452, "protein": 5, "carbs": 51, "fats": 25},
    "cheesecake": {"calories": 321, "protein": 6, "carbs": 26, "fats": 22},
    "apple_pie": {"calories": 237, "protein": 2, "carbs": 34, "fats": 11},
    "bibimbap": {"calories": 490, "protein": 22, "carbs": 66, "fats": 12},
    "ramen": {"calories": 436, "protein": 20, "carbs": 54, "fats": 14},
    "spring_rolls": {"calories": 165, "protein": 4, "carbs": 22, "fats": 7},
    "dumplings": {"calories": 210, "protein": 9, "carbs": 28, "fats": 7},
    "fried_rice": {"calories": 163, "protein": 3, "carbs": 28, "fats": 4},
    "eggs_benedict": {"calories": 290, "protein": 14, "carbs": 24, "fats": 15},
    "french_toast": {"calories": 229, "protein": 8, "carbs": 26, "fats": 11},
    "miso_soup": {"calories": 40, "protein": 3, "carbs": 5, "fats": 1},
    "pho": {"calories": 215, "protein": 15, "carbs": 30, "fats": 4},
    "pad_thai": {"calories": 357, "protein": 14, "carbs": 48, "fats": 12},
    "tiramisu": {"calories": 240, "protein": 4, "carbs": 27, "fats": 13},
    "creme_brulee": {"calories": 280, "protein": 4, "carbs": 26, "fats": 18},
    "baklava": {"calories": 428, "protein": 6, "carbs": 49, "fats": 24},
    "gyoza": {"calories": 210, "protein": 9, "carbs": 28, "fats": 7},
    "default": {"calories": 200, "protein": 8, "carbs": 25, "fats": 8}
}


def get_nutrition(food_label: str):
    """
    Look up nutrition data for a predicted food label.
    Returns default values if food not in database.
    """
    # Clean the label — remove underscores, lowercase
    clean = food_label.lower().replace("-", "_")

    # Direct match
    if clean in NUTRITION_DB:
        return NUTRITION_DB[clean]

    # Partial match — check if any key is in the label
    for key in NUTRITION_DB:
        if key in clean or clean in key:
            return NUTRITION_DB[key]

    # Return default if nothing found
    return NUTRITION_DB["default"]


def predict_food(image_bytes: bytes):
    """
    Takes image bytes, returns top prediction with
    food name, confidence, and nutrition data per 100g
    """
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    predictions = classifier(image)

    results = []
    for pred in predictions:
        label = pred["label"]
        confidence = round(pred["score"] * 100, 1)
        nutrition = get_nutrition(label)

        results.append({
            "food": label.replace("_", " ").title(),
            "confidence": confidence,
            "calories": nutrition["calories"],
            "protein": nutrition["protein"],
            "carbs": nutrition["carbs"],
            "fats": nutrition["fats"]
        })

    return results