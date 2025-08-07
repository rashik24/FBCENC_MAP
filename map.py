import streamlit as st
import pandas as pd
import pydeck as pdk
import geopandas as gpd
from shapely.geometry import Point
from datetime import datetime, time
from opencage.geocoder import OpenCageGeocode
from dateutil import parser
import os

# ─── CONFIG ──────────────────────────────────────────────────────────────

# Set your Mapbox token as environment variable
os.environ["MAPBOX_API_KEY"] = "pk.eyJ1IjoicnNpZGRpcTIiLCJhIjoiY21jbjcwNWtkMHV5bzJpb2pnM3QxaDFtMyJ9.6T6i_QFuKQatpGaCFUvCKg"

HOURS_CSV = "fbcenc_hourly.csv"
ODM_CSV = "ODM FBCENC 2.csv"
TRACTS_SHP = "cb_2023_37_tract_500k.shp"

OPENCAGE_API_KEY = "f53bdda785074d5499b7a4d29d5acd1f"
geocoder = OpenCageGeocode(OPENCAGE_API_KEY)

# ─── STREAMLIT APP ───────────────────────────────────────────────────────

st.set_page_config(page_title="Open Food Pantries", layout="wide")
st.title("Open Food Pantries Finder")

use_zip = st.checkbox("Use ZIP code instead of full address")

# ZIP-BASED LOGIC
if use_zip:
    input_zip = st.text_input("Enter your ZIP code (e.g., 27606):")

    if input_zip:
        odm_df = pd.read_csv(ODM_CSV)
        odm_df.columns = odm_df.columns.str.strip().str.lower()
        odm_df["zip"] = odm_df["zip"].astype(str).str.zfill(5)

        agencies_nearby = odm_df[odm_df["zip"] == input_zip]

        if agencies_nearby.empty:
            st.warning("No agencies found for the entered ZIP code.")
            st.stop()
        else:
            st.success(f"Found {len(agencies_nearby)} agencies in ZIP {input_zip}")

        # Continue to apply filters to `agencies_nearby` below (skip GEOID/travel time filtering)

# ADDRESS-BASED LOGIC
else:
    user_address = st.text_input("Enter your address (e.g., 123 Main St, Raleigh, NC):")

    if user_address:
        try:
            results = geocoder.geocode(user_address)
            if results:
                user_lat = results[0]["geometry"]["lat"]
                user_lon = results[0]["geometry"]["lng"]
                st.success(f"Geocoded location: {user_lat:.5f}, {user_lon:.5f}")
            else:
                st.error("Could not geocode your address.")
                st.stop()
        except Exception as e:
            st.error(f"Geocoding error: {e}")
            st.stop()

        odm_df = pd.read_csv(ODM_CSV)
        odm_df.columns = odm_df.columns.str.strip().str.lower()
        odm_df["geoid"] = odm_df["geoid"].astype(int)

        tracts_gdf = gpd.read_file(TRACTS_SHP).to_crs(epsg=4326)
        if tracts_gdf["GEOID"].dtype == object:
            tracts_gdf["GEOID"] = tracts_gdf["GEOID"].astype(int)

        user_point = Point(user_lon, user_lat)
        matched_tract = tracts_gdf[tracts_gdf.contains(user_point)]

        if not matched_tract.empty:
            user_geoid = matched_tract.iloc[0]["GEOID"]
            st.success(f"Matched your location to GEOID {user_geoid}")
        else:
            st.error("Could not match your location to a census tract.")
            st.stop()

        agencies_nearby = odm_df[
            (odm_df["geoid"] == user_geoid) &
            (odm_df["total_traveltime"] <= 20)
        ]

        if agencies_nearby.empty:
            st.warning("No agencies directly linked to your tract. Showing agencies within 60-minute travel time.")
            agencies_nearby = odm_df[odm_df["total_traveltime"] <= 60]



if user_address:
    try:
        results = geocoder.geocode(user_address)
        if results:
            user_lat = results[0]["geometry"]["lat"]
            user_lon = results[0]["geometry"]["lng"]
            st.success(f"Geocoded location: {user_lat:.5f}, {user_lon:.5f}")
        else:
            st.error("Could not geocode your address.")
            st.stop()
    except Exception as e:
        st.error(f"Geocoding error: {e}")
        st.stop()

    # ─── LOAD DATA ───────────────────────────────────────────────────────

    hourly_df = pd.read_csv(HOURS_CSV)
    hourly_df.columns = hourly_df.columns.str.strip().str.lower()
    hourly_df["day"] = hourly_df["day"].str.strip().str.title()

    odm_df = pd.read_csv(ODM_CSV)
    odm_df.columns = odm_df.columns.str.strip().str.lower()
    odm_df["geoid"] = odm_df["geoid"].astype(int)

    tracts_gdf = gpd.read_file(TRACTS_SHP)
    tracts_gdf = tracts_gdf.to_crs(epsg=4326)

    if tracts_gdf["GEOID"].dtype == object:
        tracts_gdf["GEOID"] = tracts_gdf["GEOID"].astype(int)

    # ─── FIND USER GEOID ────────────────────────────────────────────────

    user_point = Point(user_lon, user_lat)
    matched_tract = tracts_gdf[tracts_gdf.contains(user_point)]

    if not matched_tract.empty:
        user_geoid = matched_tract.iloc[0]["GEOID"]
        st.success(f"Matched your location to GEOID {user_geoid}")
    else:
        st.error("Could not match your location to a census tract.")
        st.stop()

    # ─── USER SELECTS TIME ─────────────────────────────────────────

    st.subheader("Select Time")

    use_now = st.checkbox("Use current time", value=True)

    if use_now:
        selected_datetime = datetime.now()
        st.info(f"Using current time: {selected_datetime.strftime('%A %Y-%m-%d %I:%M %p')}")
    else:
        future_date = st.date_input(
            "Select a future date:",
            datetime.today()
        )
        future_time = st.time_input(
            "Select a time:",
            value=time(12, 0)
        )
        selected_datetime = datetime.combine(future_date, future_time)
        st.info(f"Checking for: {selected_datetime.strftime('%A %Y-%m-%d %I:%M %p')}")

    selected_day = selected_datetime.strftime("%A")
    selected_week_num = (selected_datetime.day - 1) // 7 + 1
    selected_time = selected_datetime.time()

    #st.write(f"Selected Day: {selected_day}")
    #st.write(f"Selected Week: {selected_week_num}")
    #st.write(f"Selected Time: {selected_time.strftime('%I:%M %p')}")

    # ─── FIND AGENCIES REACHABLE FROM GEOID ─────────────────────────────

    agencies_from_user_geoid = odm_df[
        (odm_df["geoid"] == user_geoid) &
        (odm_df["total_traveltime"] <= 20)
    ]

    if agencies_from_user_geoid.empty:
        st.warning("No agencies linked to your tract. Searching all nearby agencies instead.")
        agencies_from_user_geoid = odm_df[odm_df["total_traveltime"] <= 60]

    accessible_agencies = agencies_from_user_geoid["agency_name"].unique()

    #st.write(f"Agencies reachable from your location: {len(accessible_agencies)}")

    # ─── TIME WINDOW CHECK ──────────────────────────────────────────────

    def safe_parse_time(time_str):
        try:
            return parser.parse(time_str).time()
        except:
            return None

    def is_within_window(selected_time, window_str):
        try:
            window_str = window_str.replace("-", "–")
            start_str, end_str = window_str.split("–")
            start_time = safe_parse_time(start_str.strip())
            end_time = safe_parse_time(end_str.strip())

            if start_time is None or end_time is None:
                return False

            if start_time <= end_time:
                return start_time <= selected_time <= end_time
            else:
                return selected_time >= start_time or selected_time <= end_time
        except:
            return False

    # ─── FILTER OPEN AGENCIES ──────────────────────────────────────────

    results_final = pd.DataFrame()

    if len(accessible_agencies) > 0:
        filtered_df = hourly_df[
            (hourly_df["agency"].isin(accessible_agencies)) &
            (hourly_df["day"] == selected_day) &
            (hourly_df["week"] == selected_week_num) &
            (hourly_df["window"].notna())
        ].copy()

        filtered_df["window"] = filtered_df["window"].astype(str).str.replace("-", "–")

        results_df = filtered_df[
            filtered_df["window"].apply(lambda w: is_within_window(selected_time, w))
        ].copy()

        if not results_df.empty:
            results_df = results_df.merge(
                agencies_from_user_geoid,
                left_on="agency",
                right_on="agency_name",
                how="left"
            )
            results_df = results_df.rename(columns={
                "total_traveltime": "travel_minutes",
                "total_miles": "distance_miles"
            })

            # Unify coordinates
            results_df["latitude"] = results_df["latitude_y"].fillna(results_df["latitude_x"])
            results_df["longitude"] = results_df["longitude_y"].fillna(results_df["longitude_x"])

            display_columns = [
                "agency", "city", "address", "window",
                "travel_minutes", "distance_miles", "latitude", "longitude"
            ]

            results_final = results_df[display_columns].drop_duplicates()
            results_final = results_final.sort_values("travel_minutes")

            st.success("Agencies open at your selected time:")
            results_final["travel_minutes"] = results_final["travel_minutes"].round(2)
            results_final["distance_miles"] = results_final["distance_miles"].round(2)

            st.dataframe(results_final[['agency', 'address','travel_minutes','distance_miles']])

            # ─── PYDECK MAP ─────────────────────────────────────────────

            # --- user location ---
            user_location_df = pd.DataFrame({
                "name": ["Your Location"],
                "latitude": [user_lat],
                "longitude": [user_lon],
                "color_r": [0],
                "color_g": [0],
                "color_b": [255],
                "tooltip": ["Your Location"]
            })

            # --- agency locations ---
            agency_map_df = results_final[[
                "agency", "latitude", "longitude", "travel_minutes", "distance_miles"
            ]].dropna().copy()

            agency_map_df["color_r"] = 255
            agency_map_df["color_g"] = 0
            agency_map_df["color_b"] = 0

            agency_map_df["tooltip"] = (
                "Agency: " + agency_map_df["agency"] +
                "<br>Travel Time (min): " + agency_map_df["travel_minutes"].astype(str) +
                "<br>Distance (miles): " + agency_map_df["distance_miles"].round(2).astype(str)
            )

            agency_map_df = agency_map_df.rename(columns={"agency": "name"})

            combined_df = pd.concat([user_location_df, agency_map_df], ignore_index=True)

            layer = pdk.Layer(
                "ScatterplotLayer",
                combined_df,
                get_position='[longitude, latitude]',
                get_color='[color_r, color_g, color_b]',
                get_radius=250,
                pickable=True,
            )

            tooltip = {
                "html": "{tooltip}",
                "style": {"color": "white"}
            }

            view_state = pdk.ViewState(
                longitude=user_lon,
                latitude=user_lat,
                zoom=10,
                pitch=0
            )

            deck = pdk.Deck(
                map_style='mapbox://styles/mapbox/light-v9',
                initial_view_state=view_state,
                layers=[layer],
                tooltip=tooltip
            )

            st.pydeck_chart(deck)

        else:
            st.warning("No agencies are open at your selected time.")
    else:
        st.warning("No agencies accessible from your GEOID.")
