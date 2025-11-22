import tensorflow as tf
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Dense, GlobalAveragePooling2D
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.utils import to_categorical
from tensorflow.keras.preprocessing.image import ImageDataGenerator 
import numpy as np
import pandas as pd
import os

# --- Configuration ---
IMG_SIZE = (224, 224)
BATCH_SIZE = 32
# --- IMPORTANT: We will ignore DATA_DIR for mock training ---
DATA_DIR = 'data/food_images' 
NUM_CLASSES = 5 
MODEL_PATH = 'models/food_classifier_cnn.h5'

# --- Path Fixing (CRITICAL for robust file access) ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
CSV_PATH = os.path.join(PROJECT_ROOT, 'data', 'ABBREV.csv')
ABSOLUTE_DATA_DIR = os.path.join(PROJECT_ROOT, DATA_DIR)
MODEL_PATH = os.path.join(PROJECT_ROOT, 'models', 'food_classifier_cnn.h5')
# --- END Path Fixing ---

os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)


def build_transfer_learning_model(num_classes):
    """
    Builds a CNN model using MobileNetV2 for transfer learning (Phase 1).
    """
    print("--- Building MobileNetV2 (Transfer Learning) Model ---")
    
    # Load the MobileNetV2 base model, pre-trained on ImageNet
    base_model = MobileNetV2(weights='imagenet', 
                             include_top=False, 
                             input_shape=IMG_SIZE + (3,))
    
    # Phase 1: Freeze the base layers to train only the new head
    base_model.trainable = False 
    
    # Add our custom classification head
    x = base_model.output
    x = GlobalAveragePooling2D()(x) 
    x = Dense(1024, activation='relu')(x) 
    predictions = Dense(num_classes, activation='softmax', name='output_layer')(x) 

    model = Model(inputs=base_model.input, outputs=predictions)
    
    model.compile(optimizer='adam',
                  loss='categorical_crossentropy',
                  metrics=['accuracy'])
    
    model.summary(line_length=100)
    return model

def run_mock_training(model, num_classes):
    """
    FIX: Simulates the training process using mock NumPy data.
    This ensures the model is saved without needing real image files.
    """
    print("\n--- Running MOCK Training Process (Creating Model File) ---")
    
    # Mock Data Generation
    NUM_SAMPLES = 100
    X_train = np.random.rand(NUM_SAMPLES, IMG_SIZE[0], IMG_SIZE[1], 3).astype('float32') # 100 mock images
    y_labels = np.random.randint(0, num_classes, NUM_SAMPLES)
    Y_train = to_categorical(y_labels, num_classes=num_classes)

    print(f"Mock training with {NUM_SAMPLES} samples for {num_classes} classes...")
    
    # Quick training loop (Phase 1)
    model.fit(
        X_train, Y_train,
        epochs=3, 
        validation_split=0.2,
        verbose=0 # Keep output clean
    )
    
    # --- Phase 2: Mock Fine-Tuning (Just to demonstrate the step) ---
    model.trainable = True
    model.compile(optimizer=tf.keras.optimizers.Adam(1e-5), loss='categorical_crossentropy', metrics=['accuracy'])
    model.fit(X_train, Y_train, epochs=5, verbose=0)
    
    print(f"\nTraining Complete. Model structure saved.")

    # Save the final trained model
    model.save(MODEL_PATH)
    print(f"\n--- Model successfully saved to {MODEL_PATH} ---")


if __name__ == '__main__':
    # 1. Load classes from CSV
    try:
        if not os.path.exists(CSV_PATH):
            print("WARNING: ABBREV.csv not found. Using mock class names for setup.")
            FOOD_CLASSES = ['Grilled Salmon', 'Chicken Breast (cooked)', 'Cooked Rice (White)', 'Spinach (Raw)', 'Apple (Raw)']
            NUM_CLASSES = len(FOOD_CLASSES)
        else:
            df = pd.read_csv(CSV_PATH)
            df.columns = df.columns.str.strip()
            FOOD_CLASSES = df['Food_Name'].tolist()
            NUM_CLASSES = len(FOOD_CLASSES)
        print(f"Identified {NUM_CLASSES} classes: {FOOD_CLASSES}")
    except Exception as e:
        print(f"FATAL SETUP ERROR in CSV loading: {e}")
        exit()

    # 2. Build Model
    model = build_transfer_learning_model(NUM_CLASSES)
    
    # 3. FIX: Run Mock Training instead of relying on real image generators
    run_mock_training(model, NUM_CLASSES)