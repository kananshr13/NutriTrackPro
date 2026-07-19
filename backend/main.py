from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import Base, engine, get_db
import models
import auth
import os 
import re
import secrets
import requests as http_requests

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def send_verification_email(to_email: str, username: str, token: str):
    """
    Sends a real verification email via SendGrid's HTTP API.
    Render's free tier blocks outbound SMTP ports (25/465/587) entirely,
    so raw smtplib cannot work there — HTTPS API calls aren't blocked.

    Requires these env vars:
      SENDGRID_API_KEY   - from app.sendgrid.com > Settings > API Keys
      SENDGRID_FROM_EMAIL - the address you verified via Single Sender
                             Verification (Settings > Sender Authentication)
      BACKEND_URL        - your deployed backend URL

    If not configured, this silently no-ops and logs the verification
    link instead, so local dev / testing still works without email set up.
    """
    api_key = os.getenv("SENDGRID_API_KEY")
    from_email = os.getenv("SENDGRID_FROM_EMAIL")
    backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
    verify_link = f"{backend_url}/verify_email?token={token}"

    if not all([api_key, from_email]):
        print(f"[email] SendGrid not configured — skipping send. Verify link: {verify_link}")
        return

    body = (
        f"Hi {username},\n\n"
        f"Welcome to NutriTrackPro! Please verify your email address by clicking the link below:\n\n"
        f"{verify_link}\n\n"
        f"If you didn't create this account, you can ignore this email.\n"
    )

    res = http_requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": from_email, "name": "NutriTrackPro"},
            "subject": "Verify your NutriTrackPro account",
            "content": [{"type": "text/plain", "value": body}]
        },
        timeout=10
    )
    if res.status_code >= 300:
        print(f"[email] SendGrid send failed ({res.status_code}): {res.text}")
        raise Exception(f"SendGrid error {res.status_code}: {res.text}")

app = FastAPI(title="NutriTrackPro API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)


# SCHEMAS
class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    gender: Optional[str] = None
    activity_level: Optional[str] = None
    goal: Optional[str] = None

class MealCreate(BaseModel):
    meal_type: str
    food_name: str
    calories: float
    protein: float
    carbs: float
    fats: float


# CALORIE CALCULATOR using Mifflin-St Jeor BMR + TDEE
# Safe minimums per general nutrition guidance: never recommend under
# 1500 kcal/day for men or 1200 kcal/day for women, regardless of inputs.
SAFE_MIN_CALORIES = {"male": 1500, "female": 1200}

def calculate_calories(age, weight_kg, height_cm, activity_level, goal, gender='male'):
    if not all([age, weight_kg, height_cm]):
        return 2000

    # Reject unrealistic inputs rather than silently computing garbage
    if not (10 <= age <= 100) or not (30 <= weight_kg <= 300) or not (100 <= height_cm <= 250):
        return 2000

    # BMR formula differs by gender
    if gender == 'female':
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) - 161
    else:
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + 5

    # TDEE multipliers
    tdee_multipliers = {
        "frequently": 1.725,
        "sometimes":  1.55,
        "never":      1.2
    }
    multiplier = tdee_multipliers.get(activity_level, 1.55)
    tdee = bmr * multiplier

    # Adjust for goal — modest, evidence-informed adjustments only.
    # Never exceed a ~500 kcal deficit/surplus; the floor above is the
    # final safety net regardless of what's chosen here.
    goal_adjustments = {
        "maintain_weight": 0,
        "lose_weight": -500,
        "gain_weight": 350,
        "improve_health": -200,   # mild nudge, not a weight-loss deficit
    }
    tdee += goal_adjustments.get(goal, 0)

    floor = SAFE_MIN_CALORIES.get(gender, SAFE_MIN_CALORIES["male"])
    return round(max(tdee, floor))


# AUTH ROUTES
@app.get("/")
def home():
    return {"message": "NutriTrackPro API is running!"}

@app.post("/signup")
def signup(user: UserCreate, db: Session = Depends(get_db)):
    if not EMAIL_RE.match(user.email):
        raise HTTPException(status_code=400, detail="Please enter a valid email address")

    # Check if username already taken
    existing_username = db.query(models.User).filter(
        models.User.username == user.username
    ).first()
    if existing_username:
        raise HTTPException(status_code=400, detail="Username already taken")

    # Check if email already taken
    existing_email = db.query(models.User).filter(
        models.User.email == user.email
    ).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email already registered")

    token = secrets.token_urlsafe(32)
    new_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=auth.hash_password(user.password),
        is_verified="no",
        verification_token=token
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    try:
        send_verification_email(user.email, user.username, token)
    except Exception as e:
        backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        print(f"[email] Failed to send verification email: {e}")
        print(f"[email] Manual verify link for {user.email}: {backend_url}/verify_email?token={token}")

    return {
        "message": "Account created! Please check your email to verify your account before logging in.",
        "username": new_user.username
    }

@app.get("/verify_email")
def verify_email(token: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(
        models.User.verification_token == token
    ).first()
    if not user:
        return HTMLResponse("<h2>Invalid or expired verification link.</h2>", status_code=400)

    user.is_verified = "yes"
    user.verification_token = None
    db.commit()
    return HTMLResponse(
        "<h2>Email verified! You can close this tab and log in to NutriTrackPro.</h2>"
    )

@app.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(
        models.User.username == form_data.username
    ).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Wrong username or password")

    if user.is_verified != "yes":
        raise HTTPException(status_code=403, detail="Please verify your email before logging in. Check your inbox for the verification link.")

    token = auth.create_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}


# PROFILE ROUTES
@app.post("/profile")
def save_profile(
    data: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    profile = db.query(models.UserProfile).filter(
        models.UserProfile.user_id == current_user.id
    ).first()

    calorie_target = calculate_calories(
        data.age, data.weight_kg, data.height_cm,
        data.activity_level, data.goal, data.gender
    )

    if profile:
        profile.name = data.name
        profile.age = data.age
        profile.height_cm = data.height_cm
        profile.weight_kg = data.weight_kg
        profile.gender = data.gender
        profile.activity_level = data.activity_level
        profile.goal = data.goal
        profile.daily_calorie_target = calorie_target
    else:
        profile = models.UserProfile(
            user_id=current_user.id,
            name=data.name,
            age=data.age,
            height_cm=data.height_cm,
            weight_kg=data.weight_kg,
            gender=data.gender,
            activity_level=data.activity_level,
            goal=data.goal,
            daily_calorie_target=calorie_target
        )
        db.add(profile)

    db.commit()
    db.refresh(profile)
    return {"message": "Profile saved!", "daily_calorie_target": calorie_target}

@app.get("/profile")
def get_profile(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    profile = db.query(models.UserProfile).filter(
        models.UserProfile.user_id == current_user.id
    ).first()
    if not profile:
        return {"profile": None}
    return profile


# MEAL ROUTES
@app.post("/log_meal")
def log_meal(
    meal: MealCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    is_healthy = "yes" if meal.calories < 600 else "no"
    alternative = None
    if is_healthy == "no":
        alternative = "Consider a lighter option like grilled chicken with vegetables or a grain bowl."

    entry = models.MealLog(
        user_id=current_user.id,
        meal_type=meal.meal_type,
        food_name=meal.food_name,
        calories=meal.calories,
        protein=meal.protein,
        carbs=meal.carbs,
        fats=meal.fats,
        is_healthy=is_healthy,
        alternative=alternative
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {
        "message": "Meal logged!",
        "is_healthy": is_healthy,
        "alternative": alternative
    }

@app.get("/suggest")
def suggest_healthier_choices(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Looks at what the user has eaten today and, if the pattern looks
    heavy on low-nutrient/high-calorie food, asks an LLM for 2-3 short,
    practical swaps. Falls back to a plain rule-based tip if no
    GROQ_API_KEY is configured, so the app still works without it.
    """
    from datetime import datetime, timedelta

    now_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
    today_start = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)

    meals = db.query(models.MealLog).filter(
        models.MealLog.user_id == current_user.id,
        models.MealLog.logged_at >= today_start
    ).all()

    if not meals:
        return {"suggestion": "No meals logged yet today — once you log something, I can suggest swaps if needed."}

    total_calories = sum(m.calories for m in meals)
    junk_count = sum(1 for m in meals if m.is_healthy == "no")
    meal_list = "; ".join(f"{m.meal_type}: {m.food_name} ({m.calories} kcal)" for m in meals)

    # Only bother calling the LLM if there's actually something to flag
    if junk_count == 0:
        return {"suggestion": "Today's meals look reasonably balanced — nothing to flag right now. Keep it up!"}

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return {"suggestion": f"You've logged {junk_count} higher-calorie meal(s) today. Consider adding a lighter, protein-forward meal (e.g. grilled chicken with vegetables, or a lentil bowl) for your next one."}

    try:
        res = http_requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a supportive nutrition assistant inside a food-tracking app. "
                            "Given a user's logged meals for today, give 2-3 short, specific, "
                            "encouraging suggestions for healthier swaps or additions for their "
                            "next meal. Keep it under 60 words, no medical claims, no calorie "
                            "targets or restrictive language, just practical and kind."
                        )
                    },
                    {
                        "role": "user",
                        "content": f"Today's meals so far ({total_calories} kcal total): {meal_list}"
                    }
                ],
                "max_tokens": 150,
                "temperature": 0.6
            },
            timeout=10
        )
        data = res.json()
        suggestion = data["choices"][0]["message"]["content"].strip()
        return {"suggestion": suggestion}
    except Exception as e:
        return {"suggestion": f"You've logged {junk_count} higher-calorie meal(s) today. Consider a lighter, protein-forward option for your next meal.", "error": str(e)}


@app.get("/today_meals")
def today_meals(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    from datetime import datetime, timedelta, date

    # Use IST timezone offset to match how meals are stored
    now_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
    today_start = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)

    meals = db.query(models.MealLog).filter(
        models.MealLog.user_id == current_user.id,
        models.MealLog.logged_at >= today_start
    ).all()

    grouped = {"breakfast": [], "lunch": [], "snacks": [], "dinner": []}
    total_calories = 0

    for meal in meals:
        if meal.meal_type in grouped:
            grouped[meal.meal_type].append({
                "id": meal.id,
                "food_name": meal.food_name,
                "calories": meal.calories,
                "protein": meal.protein,
                "carbs": meal.carbs,
                "fats": meal.fats,
                "is_healthy": meal.is_healthy,
                "alternative": meal.alternative
            })
            total_calories += meal.calories

    return {"meals": grouped, "total_calories": total_calories}

@app.get("/weekly_summary")
def weekly_summary(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    from datetime import date, timedelta
    week_ago = date.today() - timedelta(days=7)

    meals = db.query(models.MealLog).filter(
        models.MealLog.user_id == current_user.id,
        models.MealLog.logged_at >= week_ago
    ).all()

    total = {"calories": 0, "protein": 0, "carbs": 0, "fats": 0}
    for meal in meals:
        total["calories"] += meal.calories
        total["protein"] += meal.protein
        total["carbs"] += meal.carbs
        total["fats"] += meal.fats

    return {"weekly_totals": total, "days": 7}

@app.post("/predict")
async def predict(
    file: UploadFile = File(...),
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Accepts a food image, runs ML classification,
    returns food name and nutrition data per 100g
    """
    from ml_model import predict_food

    image_bytes = await file.read()
    print("Filename:",file.filename)
    print("Content type:",file.content_type)
    predictions = predict_food(image_bytes)
    top = predictions[0]

    return {
        "top_prediction": top["food"],
        "confidence": top["confidence"],
        "calories": top["calories"],
        "protein": top["protein"],
        "carbs": top["carbs"],
        "fats": top["fats"],
        "alternatives": predictions[1:],
        "message": f"Detected: {top['food']} ({top['confidence']}% confidence)"
    }

@app.get("/nutrition_search")
def nutrition_search(
    query: str,
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Proxy route — frontend calls this, backend calls USDA with hidden API key
    """
    api_key = os.getenv("USDA_API_KEY")
    
    try:
        res = http_requests.get(
            f"https://api.nal.usda.gov/fdc/v1/foods/search",
            params={
                "query": query,
                "pageSize": 1,
                "api_key": api_key
            }
        )
        data = res.json()
        
        if data.get("foods") and len(data["foods"]) > 0:
            food = data["foods"][0]
            nutrients = food["foodNutrients"]

            def get(name):
                n = next((n for n in nutrients if name in n.get("nutrientName", "")), None)
                return round(n["value"]) if n else 0

            return {
                "found": True,
                "name": food["description"],
                "calories": get("Energy"),
                "protein": get("Protein"),
                "carbs": get("Carbohydrate"),
                "fats": get("Total lipid")
            }
        return {"found": False}
    except Exception as e:
        return {"found": False, "error": str(e)}

@app.delete("/delete_meal/{meal_id}")
def delete_meal(
    meal_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """Delete a specific meal log entry"""
    meal = db.query(models.MealLog).filter(
        models.MealLog.id == meal_id,
        models.MealLog.user_id == current_user.id
    ).first()

    if not meal:
        raise HTTPException(status_code=404, detail="Meal not found")

    db.delete(meal)
    db.commit()
    return {"message": "Meal deleted!"}

@app.get("/config")
def get_config(
    current_user: models.User = Depends(auth.get_current_user)
):
    return {
        "hf_token": os.getenv("HF_TOKEN", "")
    }
@app.get("/list_models")
def list_models():
    from google import genai
    import os
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    models = client.models.list()
    return {"models": [m.name for m in models]}