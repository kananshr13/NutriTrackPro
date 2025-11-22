import numpy as np
import pandas as pd
import os
from PIL import Image
from tensorflow.keras.models import load_model 

# --- Configuration & Path Fixing ---
IMG_SIZE = (224, 224)

# FIX: Use os.path to calculate absolute paths relative to the project root
# This prevents the 'No such file or directory' errors.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
MODEL_PATH = os.path.join(PROJECT_ROOT, 'models', 'food_classifier_cnn.h5')
CLASSES_FILE = os.path.join(PROJECT_ROOT, 'data', 'ABBREV.csv')
# --- End Path Fixing ---


# Cache the model and class names for fast access
food_model = None
FOOD_CLASSES = ["Error: Model Not Loaded"]

try:
    # 1. Load the class names 
    df_classes = pd.read_csv(CLASSES_FILE)
    df_classes.columns = df_classes.columns.str.strip() # Ensure column names are clean
    FOOD_CLASSES = df_classes['Food_Name'].tolist()
    
    # 2. Load the trained model
    food_model = load_model(MODEL_PATH)
    print(f"CV Model and {len(FOOD_CLASSES)} classes loaded successfully from {MODEL_PATH}.")

except FileNotFoundError as e:
    print(f"WARNING: Required file not found: {e}. Ensure all files exist.")
except Exception as e:
    # This catches errors like the model file not existing yet or KeyError
    print(f"WARNING: Could not load CV model. Run cv_model_trainer.py first. Error: {e}")


def preprocess_image(image_file):
    """Opens, resizes, and normalizes the uploaded image for the CNN."""
    try:
        img = Image.open(image_file).convert('RGB')
        img = img.resize(IMG_SIZE)
        img_array = np.array(img).astype('float32')
        img_array /= 255.0
        img_array = np.expand_dims(img_array, axis=0)
        return img_array
    except Exception as e:
        print(f"Image preprocessing failed: {e}")
        return None

def predict_food_from_image(image_file):
    """
    Runs the image through the CNN, returns the predicted food item, and a mock portion size.
    """
    if food_model is None:
        return "Model Unavailable", 100.0, 0.0 

    input_tensor = preprocess_image(image_file)
    if input_tensor is None:
        return "Preprocessing Failed", 0.0, 0.0

    predictions = food_model.predict(input_tensor)
    
    predicted_index = np.argmax(predictions[0])
    predicted_food = FOOD_CLASSES[predicted_index]
    confidence = predictions[0][predicted_index] * 100

    # MOCK Portion Size Estimation 
    mock_portion_g = round(np.random.uniform(120, 350), 1) 
    
    return predicted_food, mock_portion_g, confidence