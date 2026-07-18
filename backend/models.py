from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime, timedelta


class User(Base):
    """Stores user account information"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_verified = Column(String, default="no")           # "yes" / "no"
    verification_token = Column(String, nullable=True)

    profile = relationship("UserProfile", back_populates="owner", uselist=False)
    meals = relationship("MealLog", back_populates="owner")


class UserProfile(Base):
    """Stores user health profile collected during onboarding"""
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    name = Column(String, nullable=True)
    age = Column(Integer, nullable=True)
    height_cm = Column(Float, nullable=True)
    weight_kg = Column(Float, nullable=True)
    gender = Column(String, nullable=True)
    activity_level = Column(String, nullable=True)
    goal = Column(String, nullable=True)
    daily_calorie_target = Column(Float, nullable=True)

    owner = relationship("User", back_populates="profile")


class MealLog(Base):
    """Stores each meal a user logs"""
    __tablename__ = "meal_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    meal_type = Column(String)
    food_name = Column(String)
    calories = Column(Float)
    protein = Column(Float)
    carbs = Column(Float)
    fats = Column(Float)
    is_healthy = Column(String, nullable=True)
    alternative = Column(String, nullable=True)
    logged_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(hours=5, minutes=30))

    owner = relationship("User", back_populates="meals")