import streamlit as st
from appManager import show_regulations_ui, show_unit_demo_ui, show_hunting_areas_ui, show_dopecalc_ui

st.set_page_config(page_title="Hunting Regs AI Demo", layout="wide")

if "page" not in st.session_state:
    st.title("🔧 AI-Tool Directory")
    st.write("Select a demo to run:")

    st.button("🎯 Hunting Regulations", on_click=lambda: st.session_state.__setitem__("page", "regs"))
    st.button("📍 Species / Unit Demo", on_click=lambda: st.session_state.__setitem__("page", "demo"))
    st.button("🗺️ Hunting Areas (Completions API)", on_click=lambda: st.session_state.__setitem__("page", "areas"))
    st.button("🎯 Ballistics / DOPE Calculator", on_click=lambda: st.session_state.__setitem__("page", "dope"))


    if "page" not in st.session_state:
        st.stop()

if st.session_state.page == "regs":
    show_regulations_ui()
elif st.session_state.page == "demo":
    show_unit_demo_ui()
elif st.session_state.page == "areas":
    show_hunting_areas_ui()
elif st.session_state.page == "dope":
    show_dopecalc_ui()
