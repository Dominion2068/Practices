import streamlit as st

def map_component(map_html):
    st.markdown(
        f"""
        <iframe srcdoc="{map_html}" width="100%" height="600px"></iframe>
        """,
        unsafe_allow_html=True,
    )
