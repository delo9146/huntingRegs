import datetime
import os
import streamlit as st
from configManager import ConfigManager
from query_helper import run_query_return, extract_legality_from_text, run_prompt_simple

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
        legality_prompt = f"Can a hunter legally hunt {species} in {state}, unit {unit}, on {today_str}? Respond YES or NO, then explain. It doesn't matter if only one weapon type is valid, if one is valid then hunting is open for that weapon and your response should be yes. If no hunting is available for any weapons, the answer should be no. If a unit shows that there are restricted areas closed to hunting, that does not mean the unit is. If the date sent falls within an open season, the answer should be yes. Regardless of the answer, provide season dates for the given unit."

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

def show_dopecalc_ui():
    # NOTE: assumes at top of file you already have:
    # from configManager import ConfigManager
    # from query_helper import run_prompt_simple
    import streamlit as st

    # Back button + title
    st.button("⬅️ Back to Home", on_click=lambda: st.session_state.pop("page", None))
    st.title("🎯 Ballistics / DOPE Calculator")
    st.caption(
        "Caliber is required. Rifle and scope are optional. "
        "If you include them, the assistant can add suggestions and scope-specific guidance."
    )

    cfg = ConfigManager()

    # --- Load lists from TOML ---
    try:
        caliber_options = cfg.load_calibers()
    except Exception:
        caliber_options = ["6.5 PRC"]  # graceful fallback
    try:
        scope_brands_map = cfg.load_scopes()  # { "Vortex": [...models], "Leupold": [...], ... }
    except Exception:
        scope_brands_map = {}

    # Prepare brand options with a true "None" option
    brand_options = ["— None —"] + sorted(scope_brands_map.keys())

    # Layout: two columns
    col_left, col_right = st.columns(2)

    # --- Left column: Caliber (required) + optional Rifle/Scope + Bullet & Zero (required) ---
    with col_left:
        st.subheader("Caliber & Equipment")
        # Caliber dropdown (required)
        default_idx = caliber_options.index("6.5 PRC") if "6.5 PRC" in caliber_options else 0
        caliber = st.selectbox(
            "Caliber / Cartridge (required)",
            options=caliber_options,
            index=default_idx,
            key="dope_caliber",
        )

        # Optional rifle model (free text)
        rifle_model = st.text_input(
            "Rifle model (optional) — e.g., 'Savage 110 Brush Hunter'",
            value="",
            placeholder="Optional: make/model for context (won't override your inputs)",
            key="dope_rifle_model",
        )
        rifle_model = rifle_model.strip() or None

        # Optional scope brand/model (truly optional via '— None —')
        scope_brand_choice = st.selectbox(
            "Scope brand (optional)",
            options=brand_options,
            index=0,
            key="dope_scope_brand",
        )
        if scope_brand_choice == "— None —":
            scope_brand = None
            scope_model = None
        else:
            scope_brand = scope_brand_choice
            model_options = ["— Select —"] + scope_brands_map.get(scope_brand, [])
            scope_model_choice = st.selectbox(
                "Scope model (optional)",
                options=model_options,
                index=0,
                key="dope_scope_model",
            )
            scope_model = None if scope_model_choice == "— Select —" else scope_model_choice

        st.subheader("Bullet & Zero (required)")
        bullet_weight = st.number_input(
            "Bullet Weight (grains)", min_value=80, max_value=250, value=143, step=1, key="dope_bullet_weight"
        )
        muzzle_velocity = st.number_input(
            "Muzzle Velocity (fps)", min_value=1000, max_value=4000, value=2960, step=10, key="dope_muzzle_velocity"
        )
        zero_range = st.number_input(
            "Zero Range (yards)", min_value=25, max_value=500, value=200, step=25, key="dope_zero_range"
        )

        # Advanced optional fields: environment, sight height, wind, and scope details
        st.subheader("Advanced (optional)")
        with st.expander("Environment, sight height, wind, and scope details (optional)"):
            use_advanced = st.checkbox("Include advanced values in the calculation", value=False, key="dope_use_advanced")
            if use_advanced:
                sight_height = st.number_input(
                    "Sight Height over Bore (inches)", min_value=0.5, max_value=3.0, value=1.5, step=0.1, key="dope_sight_height"
                )
                temp_f = st.number_input(
                    "Temperature (°F)", min_value=-40, max_value=130, value=50, step=1, key="dope_temp_f"
                )
                altitude_ft = st.number_input(
                    "Altitude (ft)", min_value=0, max_value=15000, value=5000, step=100, key="dope_altitude_ft"
                )
                wind_mph = st.number_input(
                    "Crosswind Speed (mph)", min_value=0, max_value=40, value=10, step=1, key="dope_wind_mph"
                )
                wind_value = st.selectbox(
                    "Crosswind Value", options=["Full value 90°", "Half value 45°", "Quarter value 22.5°"],
                    index=0, key="dope_wind_value"
                )

                # Optional scope-specific inputs for better UX (clicks / dial vs hold)
                st.markdown("**Scope details (optional)**")
                click_value = st.number_input(
                    "Click value (e.g., 0.25 for 0.25 MOA per click or 0.1 for 0.1 MIL per click). Leave 0 to skip.",
                    min_value=0.0, max_value=5.0, value=0.0, step=0.05, key="dope_click_value"
                )
                dial_or_hold = st.selectbox(
                    "Preferred application method (optional)",
                    options=["No preference", "Dial (turn turrets)", "Hold (use reticle)"],
                    index=0,
                    key="dope_dial_or_hold"
                )
            else:
                sight_height = None
                temp_f = None
                altitude_ft = None
                wind_mph = None
                wind_value = None
                click_value = 0.0
                dial_or_hold = "No preference"

    # --- Right column: Units, Table Settings, Generate ---
    with col_right:
        st.subheader("Output Units")
        units = st.radio("Choose units for elevation/wind holds", options=["MOA", "MIL"], index=0, horizontal=True, key="dope_units")

        st.subheader("Table Settings")
        min_range = st.number_input("Min Range (yd)", min_value=50, max_value=500, value=100, step=25, key="dope_min_range")
        max_range = st.number_input("Max Range (yd)", min_value=200, max_value=1500, value=800, step=50, key="dope_max_range")
        step_yd = st.number_input("Step (yd)", min_value=25, max_value=100, value=100, step=25, key="dope_step_yd")

        generate = st.button("Generate DOPE Sheet", type="primary", key="dope_generate_btn")

    # --- Validation ---
    if generate:
        errors = []
        if not caliber or not str(caliber).strip():
            errors.append("Please select a caliber/cartridge.")
        if muzzle_velocity < 1200:
            errors.append("Muzzle velocity should be at least ~1200 fps.")
        if not (50 <= zero_range <= 300):
            errors.append("Zero range should be between 50 and 300 yards.")
        if min_range >= max_range:
            errors.append("Min range must be less than max range.")
        if step_yd <= 0:
            errors.append("Step must be greater than zero.")
        if (max_range - min_range) % step_yd != 0:
            st.info("Note: (Max - Min) isn’t a multiple of Step; the last row may not align perfectly.")

        if errors:
            st.error("Please fix these issues before continuing:\n- " + "\n- ".join(errors))
            return

        # --- Build dynamic prompt (omit wind unless provided) ---
        parts = [
            f"Caliber/Cartridge: {caliber}",
            f"Bullet weight: {bullet_weight} gr",
            f"Muzzle velocity: {muzzle_velocity} fps",
            f"Zero range: {zero_range} yd",
            f"Output units: {units}",
            f"Table ranges: {min_range}-{max_range} yd in {step_yd} yd steps",
        ]

        # Optional rifle/scope metadata
        if rifle_model:
            parts.insert(0, f"Rifle model: {rifle_model} (optional context)")
        if scope_brand and scope_model:
            parts.insert(1, f"Scope: {scope_brand} {scope_model} (optional context)")

        # Optional/advanced context
        if sight_height is not None:
            parts.append(f"Sight height over bore: {sight_height} in")
        if temp_f is not None:
            parts.append(f"Temperature: {temp_f} °F")
        if altitude_ft is not None:
            parts.append(f"Altitude: {altitude_ft} ft")

        include_wind = wind_mph is not None
        if include_wind:
            parts.append(f"Crosswind: {wind_mph} mph ({wind_value})")

        include_clicks = (click_value and click_value > 0.0)

        # Build instructions, conditionally adding wind-related lines
        instructions = [
            "You are a careful ballistics assistant. Using ONLY the explicit inputs below, produce a DOPE (ballistics) table.",
            "Do NOT assume any wind conditions unless a crosswind value was explicitly provided above. "
            "If no wind is provided, omit any wind column entirely.",
            "If a rifle model is present, you MAY suggest typical factory muzzle velocity or common bullet weights/BCs, "
            "but list any such inferred values explicitly in the Field Notes and mark them as 'inferred/assumed'. "
            "Do NOT fabricate precise BC values — if unavailable, say 'unknown'.",
            "If a scope model is present, you MAY suggest whether the scope's typical click value or reticle type would make dialing or holding preferable; "
            "do not alter ballistic numbers based on scope model alone.",
            f"Use {units} for elevation (and wind, if present).",
            "Table rows: one row per range starting at the min range up to the max range inclusive using the provided step.",
        ]

        # Columns instruction (wind column only if wind is provided)
        columns_line = f"Columns (required): Range (yd) | Elevation ({units}) | Notes."
        if include_wind:
            columns_line = (
                f"Columns (required): Range (yd) | Elevation ({units}) | Wind hold ({wind_mph} mph) | Notes."
            )
        instructions.append(columns_line)

        # Clicks column only if click_value provided
        if include_clicks:
            instructions.append(
                f"If click value is provided ({click_value}), include an additional column 'Clicks to dial' adjacent to Elevation, "
                "rounding to the nearest whole click."
            )

        instructions.extend([
            "Elevation holds should be positive 'UP' values (e.g., 3.5 MOA meaning hold up).",
            "Keep the output strictly formatted: first a single markdown table only (no leading prose), "
            "then a short 'Field Notes' section (3–5 bullets) that lists any inferred assumptions and warnings "
            "(e.g., 'chronograph your load for field accuracy')."
        ])

        prompt = (
            "Inputs:\n" + "\n".join(f"- {p}" for p in parts) + "\n\n" +
            "Important instructions:\n" + "\n".join(f"- {line}" for line in instructions) + "\n"
        )

        # --- Call the LLM (Responses) ---
        with st.spinner("Generating DOPE sheet…"):
            try:
                res = run_prompt_simple(prompt)
            except Exception as e:
                st.error(f"Error calling LLM: {e}")
                return

        output_md = (res.get("text") or "").strip()
        if not output_md:
            st.warning("Model returned no output. Try adjusting inputs.")
            return

        # --- Render the model output ---
        st.markdown("### DOPE Table")
        st.markdown(output_md, unsafe_allow_html=True)

        # Show the inputs used for transparency
        with st.expander("Inputs used for generation"):
            st.write({
                "caliber": caliber,
                "rifle_model": rifle_model,
                "scope_brand": scope_brand,
                "scope_model": scope_model,
                "bullet_weight_gr": bullet_weight,
                "muzzle_velocity_fps": muzzle_velocity,
                "zero_range_yd": zero_range,
                "units": units,
                "range_min_yd": min_range,
                "range_max_yd": max_range,
                "step_yd": step_yd,
                "sight_height_in": sight_height,
                "temp_f": temp_f,
                "altitude_ft": altitude_ft,
                "wind_mph": wind_mph,
                "wind_value": wind_value,
                "click_value": click_value,
                "dial_or_hold": dial_or_hold,
            })








