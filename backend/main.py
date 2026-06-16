from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import Base, engine, get_db
import models
import auth

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
def calculate_calories(age, weight_kg, height_cm, activity_level, goal, gender='male'):
    if not all([age, weight_kg, height_cm]):
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

    # Adjust for goal
    if goal == "improve_health":
        tdee -= 500

    return round(tdee)


# AUTH ROUTES
@app.get("/")
def home():
    return {"message": "NutriTrackPro API is running!"}

@app.post("/signup")
def signup(user: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(
        models.User.username == user.username
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken")

    new_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=auth.hash_password(user.password)
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "Account created!", "username": new_user.username}

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

@app.get("/today_meals")
def today_meals(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    from datetime import date
    today = date.today()

    meals = db.query(models.MealLog).filter(
        models.MealLog.user_id == current_user.id,
        models.MealLog.logged_at >= today
    ).all()

    grouped = {"breakfast": [], "lunch": [], "snacks": [], "dinner": []}
    total_calories = 0

    for meal in meals:
        if meal.meal_type in grouped:
            grouped[meal.meal_type].append({
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
    return {
        "message": "Image received!",
        "filename": file.filename,
        "note": "ML model will be connected here"
    }