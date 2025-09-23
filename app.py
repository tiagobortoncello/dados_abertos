import streamlit as st
import pandas as pd
import requests
import google.generativeai as genai
import altair as alt

st.set_page_config(layout="wide")

# Corrected API Key configuration
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except Exception as e:
    st.error(f"Error configuring the Gemini API: {e}")
    st.info("Please add your API key to the app's secrets in Streamlit Cloud.")

# Test API URL (Open Library API)
url = "https://openlibrary.org/search.json?q=python"

@st.cache_data(ttl=3600)
def load_api_data():
    """Fetches data from the Test API and returns a DataFrame."""
    try:
        st.info("Fetching data from the Open Library API...")
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        # The data key in this API is 'docs'
        df = pd.DataFrame(data.get('docs', []))

        if not df.empty:
            # List of desired columns. The code will handle missing columns.
            desired_columns = ['title', 'first_publish_year', 'author_name', 'subject']

            # Filter for columns that actually exist in the DataFrame
            existing_columns = [col for col in desired_columns if col in df.columns]

            # Reorganize the DataFrame with only the existing columns
            df = df[existing_columns]

        return df
    except requests.exceptions.RequestException as e:
        st.error(f"Error loading data from the API: {e}. Check the link.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error processing API data: {e}.")
        return pd.DataFrame()

# Load API data
df_data = load_api_data()

st.title("Data Assistant (Test Mode)")
st.subheader("Ask questions about the listed books")

# The assistant is only shown if data and the Gemini key are loaded
if not df_data.empty and genai.api_key:
    user_query = st.text_input("Your question:", placeholder="Ex: What's the most common publication year?")

    if user_query:
        st.info("Fetching response and generating output...")

        data_string = df_data.to_string(index=False)

        prompt = f"""
        You are a data assistant about books.
        Analyze the provided data and answer the user's question.

        If the question is about counts or years, include a Python code block with a chart to supplement the information.

        Book data:
        {data_string}

        Chart instructions:
        - Use the `altair` library. The DataFrame is named `df_data`.
        - Use the format: ```python ... ```
        - Example:
          ```python
          chart = alt.Chart(df_data).mark_bar().encode(
              x=alt.X('first_publish_year:O', title='Publication Year'),
              y=alt.Y('count():Q', title='Count')
          ).properties(
              title='Books by Publication Year'
          )
          st.altair_chart(chart, use_container_width=True)
          ```

        User question: {user_query}
        """

        try:
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content(prompt)
            response_text = response.text.strip()

            if "```python" in response_text:
                parts = response_text.split("```python")
                text_part = parts[0].strip()
                code_part = parts[1].split("```")[0].strip()

                if text_part:
                    st.markdown(text_part)

                st.code(code_part, language='python')
                exec(code_part)
            else:
                st.markdown(response_text)

        except Exception as e:
            st.error(f"An error occurred: {e}")
            st.caption("Verify your API key is correct or your question is clear.")

else:
    st.warning("Data not loaded. Cannot use the assistant.")
