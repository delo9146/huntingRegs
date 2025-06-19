import datetime
import os
import streamlit as st
from configManager import ConfigManager
from query_helper import run_query_return, extract_legality_from_text

from huntingAreas.ConfigManager import ConfigManager as HuntingConfigManager
from huntingAreas.imageAnalysis import ImageAnalysisManager
from huntingAreas.waypointDrawer import WaypointDrawer

cfg = ConfigManager()

input_dir = cfg.input_dir
if os.path.exists(input_dir):
    available_states = [
        d for d in os.listdir(input_dir)
        if os.path.isdir(os.path.join(input_dir, d))
    ]
else:
    available_states = ["MT", "CO"]
available_species = cfg.valid_species

species_to_units = {
    sp: cfg.units_for("Montana", sp)
    for sp in cfg.valid_species
    if cfg.units_for("Montana", sp)
}

def show_regulations_ui():
    st.button(
        "⬅️ Back to Home",
        on_click=lambda: st.session_state.pop("page", None)
    )

    st.title("Hunting Regulations AI Demo")
    st.write("Select a state and species to see a summary. Then ask specific questions.")

    state = st.selectbox("Select state", available_states)
    species = st.selectbox("Select species", available_species)

    st.session_state.setdefault("auto_summary", "")
    st.session_state.setdefault("auto_summary_annotations", [])
    st.session_state.setdefault("chat_history", [])
    st.session_state.setdefault("prompt", "")

    # Generate Summary
    if st.button("Generate Summary"):
        with st.spinner(f"Summarizing {state} – {species}…"):
            summary_prompt = cfg.summary_prompt_for(state).format(
                state=state,
                species=species
            )
            res = run_query_return(state, species, inject_chunks=True)
            st.session_state.auto_summary = res["text"]
            st.session_state.auto_summary_annotations = res.get("annotations", [])

    # Display Summary if present
    if st.session_state.auto_summary:
        st.subheader(f"Summary for {state} – {species}")
        st.markdown(st.session_state.auto_summary, unsafe_allow_html=True)

    st.divider()
    st.markdown("**Ask a specific question:**")

    # Q&A
    user_q = st.text_area(
        "Your question",
        key="prompt",
        value=st.session_state.prompt,
        placeholder="Type your regulation question here…"
    )
    if st.button("Ask"):
        with st.spinner("Getting answer…"):
            ans = run_query_return(state, species, user_q)
            st.session_state.chat_history.append((user_q, ans))

    if st.button("Clear Conversation"):
        st.session_state.chat_history = []

    if st.session_state.chat_history:
        st.markdown("## Conversation History")
        for i, (q, a) in enumerate(st.session_state.chat_history, 1):
            st.markdown(f"**Q{i}:** {q}")
            st.markdown(a["text"], unsafe_allow_html=True)
            st.divider()


def show_unit_demo_ui():
    st.button(
        "⬅️ Back to Home",
        on_click=lambda: st.session_state.pop("page", None)
    )

    st.title("📍 Species / Unit Demo")
    st.write("Select a state, species, and unit to see all regulations for that combination, and whether the species can be hunted today.")

    state = st.selectbox("Select state", [":--Select--","Montana"])

    species = None
    if state != "-- Select --":
        species_options = ["-- Select --"] + list(species_to_units.keys())
        species = st.selectbox("Select species", species_options)
    else:
        st.selectbox("Select species", ["-- Select state first --"])

    unit = None
    if species and species != "-- Select --":
        unit_options = ["-- Select --"] + species_to_units.get(species, [])
        unit = st.selectbox("Select HD/Unit", unit_options)
    else:
        st.selectbox("Select HD/Unit", ["-- Select species first --"])

    # Auto-check legality once all 3 are selected
    if (
        state and species and unit
        and state != "-- Select --"
        and species != "-- Select --"
        and unit != "-- Select --"
    ):
        today_str = datetime.date.today().strftime("%B %d, %Y")
        legality_prompt = f"Can a hunter legally hunt {species} in {state}, unit {unit}, on {today_str}? Respond YES or NO, then explain."

        with st.spinner(f"Checking if {species} is huntable today in unit {unit}…"):
            res = run_query_return(state, species, legality_prompt)
            legality = extract_legality_from_text(res["text"])
            print("Legality output:", res["text"])
            if legality is True:
                st.success(f"✅ Yes – {species.capitalize()} **can** currently be hunted in unit {unit}.")
            elif legality is False:
                st.error(f"❌ No – {species.capitalize()} **cannot** be hunted today in unit {unit}.")
            else:
                st.warning("⚠️ Couldn't determine legality with confidence. Please review the regulations manually.")

            st.caption(res["text"])

    if st.button(f"Show regs for {species.capitalize()} in HD {unit}"):
        today_str = datetime.date.today().strftime("%B %d, %Y")
        prompt = cfg.unit_prompt.format(
            state=state,
            species=species.capitalize(),
            unit=unit,
            today_str=today_str
        )
        with st.spinner(f"Querying regs for {species.capitalize()} in HD {unit}…"):
            res = run_query_return(state, species, prompt)
        st.markdown(res["text"], unsafe_allow_html=True)



def show_hunting_areas_ui():
    st.button(
        "⬅️ Back to Home",
        key="ha_back_home",
        on_click=lambda: st.session_state.pop("page", None),
    )
    st.title("🗺️ Hunting Areas")

    species = st.selectbox(
        "Species",
        ["elk", "black_bear", "mule_deer"],
        index=0,
        key="ha_species",
    )
    state = st.selectbox(
        "State",
        ["MT", "CO", "WY"],
        index=0,
        key="ha_state",
    )
    month = st.selectbox(
        "Month",
        [
            "September", "October", "November",
            "December", "January", "February"
        ],
        index=0,
        key="ha_month",
    )

    base = os.path.dirname(__file__)
    input_dir = os.path.join(base, "huntingAreas", "data", "input")
    image_files = sorted(
        f for f in os.listdir(input_dir)
        if f.lower().endswith((".png", ".jpg", ".jpeg"))
    )
    selected = st.selectbox(
        "Select a map image",
        ["--"] + image_files,
        key="ha_image_select",
    )
    if selected == "--":
        return

    image_path = os.path.join(input_dir, selected)
    st.subheader("Original Map")
    st.image(image_path, use_container_width=True)

    if st.button("Analyze Map", key="ha_run_analyze"):
        with st.spinner("Running analysis…"):
            cfg_h = HuntingConfigManager()
            base_prompt     = cfg_h.load_species_prompt(species)
            legend_info     = cfg_h.get_map_legend_description()
            full_state_name = cfg_h.get_full_state_name(state)
            schema_prompt   = cfg_h.get_response_schema()
            top_left, bottom_right = cfg_h.get_map_coordinates(image_path)
            gps_context = (
                f"The top-left corner of the image corresponds to latitude {top_left[0]:.6f}, "
                f"longitude {top_left[1]:.6f}; and the bottom-right corner corresponds to "
                f"latitude {bottom_right[0]:.6f}, longitude {bottom_right[1]:.6f}.\n\n"
            )
            full_prompt = (
                f"You are analyzing a hunting map for the state of {full_state_name} during the month of {month}.\n\n"
                f"{gps_context}"
                f"{base_prompt.strip()}\n\n"
                f"{legend_info.strip()}\n\n"
                f"{schema_prompt.strip()}"
            )

            analyzer = ImageAnalysisManager()
            reasoning = analyzer.analyze_image(image_path, full_prompt)
            out_path, parsed = WaypointDrawer.draw_waypoints(image_path, reasoning)

        st.subheader("Annotated Map")
        st.image(out_path, use_container_width=True)

        st.subheader("Model Reasoning")
        st.code(reasoning)


