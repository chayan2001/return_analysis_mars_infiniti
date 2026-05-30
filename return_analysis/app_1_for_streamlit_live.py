import streamlit as st
import pandas as pd
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential
import os  

# ==========================================
# 0. PAGE CONFIGURATION
# ==========================================
st.set_page_config(page_title="SKU Return Analyzer", page_icon="📊", layout="wide")
st.title("🛒 E-Commerce SKU Return Analyzer")

# ==========================================
# 1. SECURE API SETUP (No Hardcoded Keys!)
# ==========================================
try:
    # Ekhon API key file er bhitor theke nibe, tai GitHub e leak hobe na
    YOUR_API_KEY = st.secrets["GEMINI_API_KEY"]
except Exception:
    st.error("⚠️ API Key not found! Please set GEMINI_API_KEY in .streamlit/secrets.toml")
    st.stop()

genai.configure(api_key=YOUR_API_KEY)
MODEL_NAME = 'gemini-2.5-flash' 
model = genai.GenerativeModel(MODEL_NAME)

@retry(
    stop=stop_after_attempt(3), 
    wait=wait_exponential(multiplier=1, min=2, max=6), 
    reraise=True
)
def call_gemini_api(prompt_text):
    response = model.generate_content(prompt_text)
    return response.text

# ==========================================
# 2. DATA LOADING (Path Fixed & Memory Optimized)
# ==========================================
@st.cache_resource
def load_data():
    try:
        # App-ti je folder-e ache tar ashol thikana ber kora
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        earn_more_path = os.path.join(current_dir, "earn_more.xlsx")
        fk_mars_path = os.path.join(current_dir, "fk_mars_return.xlsx")

        # Shudhu dorkari column gulo RAM e nibe
        sales_needed_cols = ['SKU ID', 'Style Code', 'Group Code', 'Gross Units', 'Return Units', 'GMV']
        
        sales_df = pd.read_excel(
            earn_more_path, 
            usecols=lambda c: c in sales_needed_cols
        )
        sales_df = sales_df.rename(columns={'SKU ID': 'SKU'})

        returns_df = pd.read_excel(
            fk_mars_path, 
            usecols=lambda c: c in ['SKU', 'Comments']
        )
        
        # Merge ebong null comments remove
        df = pd.merge(returns_df, sales_df, on='SKU', how='left')
        df_with_comments = df.dropna(subset=['Comments'])
        
        return sales_df, df_with_comments
    except Exception as e:
        st.error(f"❌ Excel File Load Error: {e}")
        return None, None

sales_df, df_with_comments = load_data()

# ==========================================
# 3. INTERACTIVE UI (Dropdowns)
# ==========================================
if df_with_comments is not None:
    st.markdown("### 🔍 Select Product to Analyze")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        group_options = ["-- Select --"] + df_with_comments['Group Code'].dropna().unique().tolist()
        selected_group = st.selectbox("Group Code:", group_options)

    with col2:
        if selected_group != "-- Select --":
            style_options = ["-- Select --"] + df_with_comments[df_with_comments['Group Code'] == selected_group]['Style Code'].dropna().unique().tolist()
        else:
            style_options = ["-- Select --"]
        selected_style = st.selectbox("Style Code:", style_options)

    with col3:
        if selected_style != "-- Select --":
            sku_options = ["-- Select --"] + df_with_comments[
                (df_with_comments['Group Code'] == selected_group) & 
                (df_with_comments['Style Code'] == selected_style)
            ]['SKU'].dropna().unique().tolist()
        else:
            sku_options = ["-- Select --"]
        selected_sku = st.selectbox("SKU:", sku_options)

    # ==========================================
    # 4. METRICS & ANALYSIS ACTION
    # ==========================================
    st.markdown("---")
    
    if st.button("⚡ Get Metrics & Solution", type="primary", use_container_width=True):
        if selected_sku == "-- Select --":
            st.warning("⚠️ Please select a valid SKU from the dropdowns first!")
        else:
            with st.spinner("⏳ Analyzing Data & Consulting Gemini..."):
                
                # Metrics Calculation
                sku_sales_data = sales_df[sales_df['SKU'] == selected_sku]
                if not sku_sales_data.empty:
                    gross_units = int(sku_sales_data['Gross Units'].sum())
                    return_units = int(sku_sales_data['Return Units'].sum())
                    total_gmv = float(sku_sales_data['GMV'].sum())
                    return_percentage = round((return_units / gross_units) * 100, 2) if gross_units > 0 else 0
                else:
                    gross_units, return_units, total_gmv, return_percentage = 0, 0, 0.0, 0
                
                # Display 4 Metrics
                st.markdown("### 📊 Key Metrics")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric(label="Gross Units", value=f"{gross_units}")
                m2.metric(label="Gross Sale (₹)", value=f"₹{total_gmv:,.2f}")
                m3.metric(label="Return Units", value=f"{return_units}", delta_color="inverse")
                m4.metric(label="Return Rate", value=f"{return_percentage}%", delta_color="inverse")
                
                # Extract Comments & Get Solution
                target_data = df_with_comments[df_with_comments['SKU'] == selected_sku]
                comments_list = target_data['Comments'].tolist()
                
                st.markdown("### 💡 AI Actionable Solution")
                
                if not comments_list:
                    st.info("⚠️ No customer return text comments found for this SKU.")
                else:
                    comments_text = "\n".join([f"- {c}" for c in comments_list])
                    prompt = f"""
                    Analyze these customer return feedbacks for clothing SKU '{selected_sku}'.
                    Identify the majority single problem and provide exactly ONE short, actionable, single-line solution.
                    Do not include headers, bullet points, intro text, or blank lines. Output ONLY the raw solution text in one sentence.

                    User Comments:
                    {comments_text}
                    """
                    
                    try:
                        raw_response = call_gemini_api(prompt)
                        clean_solution = raw_response.strip().replace("\n", " ")
                        st.success(f"**Solution:** {clean_solution}")
                            
                    except Exception as e:
                        st.error(f"❌ API Request Failed: {e}")