from google import genai
import os
import PIL.Image
import io

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

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
    "samosa": {"calories": 308, "protein": 6, "carbs": 32, "fats": 18},
    "chicken_wings": {"calories": 290, "protein": 27, "carbs": 0, "fats": 19},
    "ramen": {"calories": 436, "protein": 20, "carbs": 54, "fats": 14},
    "spring_rolls": {"calories": 165, "protein": 4, "carbs": 22, "fats": 7},
    "dumplings": {"calories": 210, "protein": 9, "carbs": 28, "fats": 7},
    "eggs_benedict": {"calories": 290, "protein": 14, "carbs": 24, "fats": 15},
    "french_toast": {"calories": 229, "protein": 8, "carbs": 26, "fats": 11},
    "pad_thai": {"calories": 357, "protein": 14, "carbs": 48, "fats": 12},
    "tiramisu": {"calories": 240, "protein": 4, "carbs": 27, "fats": 13},
    "donuts": {"calories": 452, "protein": 5, "carbs": 51, "fats": 25},
    "cheesecake": {"calories": 321, "protein": 6, "carbs": 26, "fats": 22},
    "apple_pie": {"calories": 237, "protein": 2, "carbs": 34, "fats": 11},
    "bibimbap": {"calories": 490, "protein": 22, "carbs": 66, "fats": 12},
    "tacos": {"calories": 226, "protein": 9, "carbs": 20, "fats": 12},
    "dal": {"calories": 116, "protein": 9, "carbs": 20, "fats": 1},
    "rice": {"calories": 130, "protein": 3, "carbs": 28, "fats": 0},
    "roti": {"calories": 104, "protein": 3, "carbs": 18, "fats": 3},
    "curry": {"calories": 150, "protein": 8, "carbs": 12, "fats": 8},
    "biryani": {"calories": 290, "protein": 12, "carbs": 40, "fats": 9},
    "idli": {"calories": 58, "protein": 2, "carbs": 12, "fats": 0},
    "dosa": {"calories": 168, "protein": 4, "carbs": 30, "fats": 4},
    "paratha": {"calories": 260, "protein": 6, "carbs": 36, "fats": 10},
    "default": {"calories": 200, "protein": 8, "carbs": 25, "fats": 8}
}


def get_nutrition(food_label: str):
    clean = food_label.lower().replace("-", "_").replace(" ", "_")
    if clean in NUTRITION_DB:
        return NUTRITION_DB[clean]
    for key in NUTRITION_DB:
        if key in clean or clean in key:
            return NUTRITION_DB[key]
    return NUTRITION_DB["default"]


def predict_food(image_bytes: bytes):
    """Sends image to Gemini for food identification"""
    print("Sending image to Gemini for analysis...")

    try:
        image = PIL.Image.open(io.BytesIO(image_bytes))

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                "What food is in this image? Reply with ONLY the food name, nothing else. "
                "Use simple common names like 'pizza', 'burger', 'salad', 'rice', 'dal', "
                "'roti', 'biryani', 'pasta', 'dosa', 'idli', 'paratha' etc. "
                "If you cannot identify food, reply with 'unknown'.",
                image
            ]
        )

        food_name = response.text.strip().lower()
        print(f"Gemini identified: {food_name}")

        nutrition = get_nutrition(food_name)

        return [{
            "food": food_name.replace("_", " ").title(),
            "confidence": 95,
            "calories": nutrition["calories"],
            "protein": nutrition["protein"],
            "carbs": nutrition["carbs"],
            "fats": nutrition["fats"]
        }]

    except Exception as e:
        print(f"Gemini API error: {e}")
        return [{
            "food": "Unknown",
            "confidence": 0,
            "calories": 200,
            "protein": 8,
            "carbs": 25,
            "fats": 8
        }]