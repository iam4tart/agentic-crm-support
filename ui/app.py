import streamlit as st
import requests
import json

st.set_page_config(layout="wide")

st.markdown("""
    <style>
    .stApp {
        background-color: #0e1117;
        color: #fafafa;
    }
    </style>
""", unsafe_allow_html=True)

col1, col2 = st.columns([1, 2])

with col1:
    st.header("Query")
    user_query = st.text_area("Enter your support query:", height=150)
    submit = st.button("Submit")

with col2:
    st.header("Agent Execution Trace")
    if submit and user_query:
        with st.spinner("Processing..."):
            try:
                response = requests.post("http://api:8000/query", json={"query": user_query})
                data = response.json()
                
                with st.expander("🧠 Reasoning", expanded=True):
                    st.write(data.get("reasoning_steps", []))
                
                with st.expander("📚 Retrieved Docs"):
                    st.write(data.get("retrieved_docs", []))
                    
                with st.expander("🔌 Tool Calls"):
                    st.json(data.get("tool_outputs", []))
                    
                with st.expander("✅ Final Answer", expanded=True):
                    st.write(data.get("final_answer", ""))
                    
                with st.expander("📊 Evaluation Score"):
                    st.metric(label="Score", value=f"{data.get('evaluation_score', 0.0):.2f}")
                    
            except Exception as e:
                st.error(f"Error: {str(e)}")
