import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import requests

st.set_page_config(page_title="Magyar Árfigyelő", layout="wide")

st.title("🔍 Magyar Termékfigyelő & Ár-grafikon")

# --- INTERFÉSZ ---
with st.sidebar:
    st.header("Új termék hozzáadása")
    item_name = st.text_input("Termék neve (pl. Nike Air Max)")
    target_price = st.number_input("Célár (HUF)", value=10000)
    add_button = st.button("Hozzáadás a figyelőhöz")

# --- ADATOK BETÖLTÉSE (Példa adatok a szemléltetéshez) ---
# A valóságban itt a Google Sheets-hez kapcsolódunk
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame({
        'Dátum': pd.to_datetime(['2023-11-01', '2023-11-05', '2023-11-10', '2023-11-15']),
        'Ár': [15000, 14200, 15500, 13800],
        'Termék': ['Nike Air Max', 'Nike Air Max', 'Nike Air Max', 'Nike Air Max']
    })

# --- GRAFIKON MEGJELENÍTÉSE ---
st.subheader(f"Árfolyam alakulása: {item_name if item_name else 'Válassz terméket'}")
fig = px.line(st.session_state.data, x='Dátum', y='Ár', markers=True, title="Árváltozások")
st.plotly_chart(fig, use_container_width=True)

# --- KERESÉS FUNKCIÓ (Egyszerűsített) ---
if st.button("Friss árak lekérése most"):
    with st.spinner('Keresés a magyar piacokon... (Jófogás, Vinted)'):
        # Itt hívnánk meg a ScraperAPI-t
        # Példa találat:
        new_price = 13500 
        st.success(f"Talált legolcsóbb ár: {new_price} Ft")
        
        # Adat hozzáadása a táblázathoz
        new_row = {'Dátum': datetime.now(), 'Ár': new_price, 'Termék': item_name}
        st.session_state.data = pd.concat([st.session_state.data, pd.DataFrame([new_row])], ignore_index=True)
        st.rerun()

# --- LISTA ---
st.subheader("Jelenleg figyelt termékek")
st.dataframe(st.session_state.data.sort_values(by='Dátum', ascending=False))
