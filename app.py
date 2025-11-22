import streamlit as st
import pandas as pd
import sqlite3
import datetime
from core_logic.cv_predictor import predict_food_from_image 
import os

# --- Configuration & Initialization ---
DB_NAME = 'database/nutrient_log.db'

@st.cache_resource
def get_db_connection():
    """Returns a connection to the SQLite database."""
    # FIX: Calculate absolute path for DB_NAME as well, for consistency
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
    # The DB name is relative to the project root, regardless of where app.py is executed
    absolute_db_path = os.path.join(PROJECT_ROOT, DB_NAME)
    
    conn = sqlite3.connect(absolute_db_path)
    return conn

# --- Data Fetching and Calculations ---

def fetch_user_data(user_id):
    """Fetches user profile and goals."""
    conn = get_db_connection()
    df = pd.read_sql_query(f"SELECT * FROM users WHERE user_id = '{user_id}'", conn)
    return df.iloc[0] if not df.empty else None

def get_nutrients_by_food(food_name):
    """Fetches nutrient data for 100g of a specific food."""
    conn = get_db_connection()
    # Note: Food_Name must be stripped/cleaned when loaded into the DB table as well, which is handled in database_setup.py 
    df = pd.read_sql_query(f"SELECT * FROM nutrient_data WHERE Food_Name = '{food_name}'", conn)
    return df.iloc[0] if not df.empty else None

def log_food_entry(user_id, food_name, quantity_g):
    """Calculates nutrients and logs the entry to the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    nutrient_100g = get_nutrients_by_food(food_name)
    if nutrient_100g is None:
        st.error(f"Nutrient data for '{food_name}' not found. Please ensure the food name exactly matches an entry in your database.")
        return False
        
    scale_factor = quantity_g / 100.0
    
    try:
        # These columns must match ABBREV.csv headers exactly
        calories = int(nutrient_100g['Energy_(kcal)'] * scale_factor)
        protein = nutrient_100g['Protein_(g)'] * scale_factor
        iron = nutrient_100g['Iron_(mg)'] * scale_factor
    except KeyError as e:
        st.error(f"Missing column in ABBREV.csv: {e}. Check CSV column names.")
        return False

    cursor.execute("""
        INSERT INTO food_log (user_id, log_date, food_name, quantity_g, calories_consumed, protein_g, iron_mg)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, datetime.date.today().isoformat(), food_name, quantity_g, calories, protein, iron))
    conn.commit()
    return True

# --- Main Application Logic ---

def display_main_dashboard(user_data, user_id):
    """Displays the main dashboard with today's intake summary."""
    st.title("🧠 AI Nutrient Analyzer")
    st.markdown(f"**Welcome, {user_data['name']}!** (User ID: `{user_id}`)")
    
    today_date = datetime.date.today().isoformat()
    conn = get_db_connection()
    
    summary_query = f"""
    SELECT SUM(calories_consumed) as total_calories,
           SUM(protein_g) as total_protein,
           SUM(iron_mg) as total_iron
    FROM food_log
    WHERE user_id = '{user_id}' AND log_date = '{today_date}';
    """
    summary_df = pd.read_sql_query(summary_query, conn)
    
    total_calories = summary_df['total_calories'].iloc[0] if not summary_df['total_calories'].isnull().all() else 0
    total_protein = summary_df['total_protein'].iloc[0] if not summary_df['total_protein'].isnull().all() else 0.0
    total_iron = summary_df['total_iron'].iloc[0] if not summary_df['total_iron'].isnull().all() else 0.0

    st.header("Daily Progress (Today)")
    
    col_c, col_p, col_i = st.columns(3)

    cal_goal = user_data['daily_calorie_goal']
    cal_progress = min(total_calories / cal_goal, 1.0) if cal_goal > 0 else 0
    col_c.metric(label="Calories (kcal)", value=f"{total_calories}/{cal_goal}", delta=f"{int(cal_progress * 100)}% of goal")
    col_c.progress(cal_progress)

    protein_goal = user_data['target_protein_g']
    protein_progress = min(total_protein / protein_goal, 1.0) if protein_goal > 0 else 0
    col_p.metric(label="Protein (g)", value=f"{total_protein:.1f}/{protein_goal:.1f}", delta=f"{int(protein_progress * 100)}% of goal")
    col_p.progress(protein_progress)

    iron_goal = user_data['target_iron_mg']
    iron_progress = min(total_iron / iron_goal, 1.0) if iron_goal > 0 else 0
    col_i.metric(label="Iron (mg)", value=f"{total_iron:.1f}/{iron_goal:.1f}", delta=f"{int(iron_progress * 100)}% of goal")
    col_i.progress(iron_progress)
    
    st.divider()
    
    st.subheader(f"Today's Log ({today_date})")
    log_query = f"""
    SELECT log_date, food_name, quantity_g, calories_consumed, protein_g, iron_mg
    FROM food_log
    WHERE user_id = '{user_id}' AND log_date = '{today_date}'
    ORDER BY log_id DESC;
    """
    log_df = pd.read_sql_query(log_query, conn)
    st.dataframe(log_df, use_container_width=True)

# --- Main App Execution ---

USER_ID = "user_123"

def main():
    """The main Streamlit application function."""
    st.set_page_config(page_title="AI Nutrient Analyzer", layout="wide")
    
    # Check if DB file exists (using os.path logic from above)
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
    absolute_db_path = os.path.join(PROJECT_ROOT, DB_NAME)
    
    if not os.path.exists(absolute_db_path):
        st.warning("Database file not found. Please run `python database_setup.py` first.")
        return

    user_data = fetch_user_data(USER_ID)
    if user_data is None:
        st.error("User data not found. Check `database_setup.py`.")
        return

    tab_dashboard, tab_image, tab_chat, tab_predictions = st.tabs([
        "📊 Dashboard", "📸 Image Analyzer (CV)", "💬 NLP Chatbot", "🔮 Deficiency Prediction (RNN)"
    ])

    with tab_dashboard:
        display_main_dashboard(user_data, USER_ID)

    with tab_image:
        st.header("Computer Vision Food Logging")
        st.markdown("Upload a picture of your food. Our CNN will classify the food and estimate the portion size.")

        uploaded_file = st.file_uploader("Choose an image...", type=["jpg", "jpeg", "png"])

        if uploaded_file is not None:
            st.image(uploaded_file, caption='Uploaded Food Image', use_column_width=True)
            
            with st.spinner('Analyzing image with local CNN...'):
                predicted_food, portion_g, confidence = predict_food_from_image(uploaded_file)
                
            st.success("Analysis Complete!")
            
            col_res, col_log = st.columns([2, 1])

            with col_res:
                st.subheader("Classification Result")
                st.info(f"**Predicted Food:** {predicted_food}")
                st.write(f"Confidence: **{confidence:.2f}%**")
                
                st.subheader("Portion Estimation (Advanced CV Mock)")
                st.write(f"Estimated Portion: **{portion_g:.1f} grams**")
                st.caption("*(Note: Portion size is mocked/simplified.)*")

            with col_log:
                st.subheader("Confirm & Log")
                
                final_food = st.text_input("Food Name to Log:", value=predicted_food)
                final_quantity = st.number_input("Quantity (grams):", value=portion_g, min_value=1.0, step=10.0)
                
                if st.button("Log Meal to Database", use_container_width=True, type="primary"):
                    if final_food == "Model Unavailable":
                        st.error("Cannot log. The AI model is not trained or was not loaded. Run `core_logic/cv_model_trainer.py` first.")
                    elif log_food_entry(USER_ID, final_food, final_quantity):
                        st.success(f"Successfully logged {final_quantity:.1f}g of {final_food}!")
                        st.rerun()
                    else:
                        st.error("Failed to log entry. Food not in nutrient database or database error.")

    with tab_chat:
        st.header("NLP Nutrition Chatbot")
        st.warning("Feature development needed: Create `nlp_model.py` and fine-tune a small BERT/GPT model locally.")
        
    with tab_predictions:
        st.header("Deficiency Prediction (RNN) & Recommendations")
        st.warning("Feature development needed: Create `rnn_trainer.py` and train a Time Series model on historical log data.")


if __name__ == '__main__':
    main()