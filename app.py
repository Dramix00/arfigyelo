import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import os

# --- KONFIGURÁCIÓ ---
st.set_page_config(page_title="Magyar Piacfigyelő", layout="wide")

# Adatfájl neve
DATA_FILE = "price_history.csv"

# --- ADATKEZELÉS ---
def load_data():
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
        df['datum'] = pd.to_datetime(df['datum'])
        return df
    return pd.DataFrame(columns=['datum', 'termek', 'ar', 'forras', 'link'])

def save_data(df):
    df.to_csv(DATA_FILE, index=False)

# --- KERESŐ MOTOROK ---

def search_jofogas(keyword):
    try:
        url = f"https://www.jofogas.hu/magyarorszag?q={keyword.replace(' ', '+')}"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        items = soup.find_all('div', class_='list-item')
        prices = []
        for item in items:
            price_text = item.find('span', class_='price-value')
            if price_text:
                # Szám kinyerése a "25 000 Ft" szövegből
                price = int(''.join(filter(str.isdigit, price_text.text)))
                prices.append(price)
        return min(prices) if prices else None
    except:
        return None

def search_ebay(keyword):
    try:
        # Európai eBay (Németország) a nemzetközi árakhoz (EUR -> HUF váltással kb.)
        url = f"https://www.ebay.de/sch/i.html?_nkw={keyword.replace(' ', '+')}"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        price_tags = soup.find_all('span', class_='s-item__price')
        prices = []
        for p in price_tags:
            # Tisztítás (egyszerűsített: EUR-t HUF-nak tekinti a példa kedvéért, 400-zal szorozva)
            num = ''.join(filter(str.isdigit, p.text.split(',')[0]))
            if num:
                prices.append(int(num) * 400) 
        return min(prices) if prices else None
    except:
        return None

# --- UI ---
st.title("📈 Magyar & Nemzetközi Piacfigyelő")

# Inicializálás
if 'history' not in st.session_state:
    st.session_state.history = load_data()

# Oldalsáv: Termékek kezelése
with st.sidebar:
    st.header("Beállítások")
    new_item = st.text_input("Figyelni kívánt termék neve:")
    if st.button("Termék hozzáadása"):
        if new_item and new_item not in st.session_state.history['termek'].unique():
            st.success(f"Hozzáadva: {new_item}")
        else:
            st.warning("Ez a termék már létezik vagy üres.")

    st.divider()
    if st.button("Minden adat törlése", type="secondary"):
        if os.path.exists(DATA_FILE):
            os.remove(DATA_FILE)
        st.session_state.history = pd.DataFrame(columns=['datum', 'termek', 'ar', 'forras', 'link'])
        st.rerun()

# FŐPANEL: Frissítés gomb
col1, col2 = st.columns([1, 4])
with col1:
    if st.button("🔍 ÁRAK FRISSÍTÉSE", type="primary"):
        termekek = st.session_state.history['termek'].unique().tolist()
        if not termekek and new_item: termekek = [new_item]
        
        with st.spinner("Keresés a piacokon..."):
            new_records = []
            for t in termekek:
                # Jófogás keresés
                ar_jo = search_jofogas(t)
                if ar_jo:
                    new_records.append({'datum': datetime.now(), 'termek': t, 'ar': ar_jo, 'forras': 'Jófogás', 'link': ''})
                
                # eBay keresés (nemzetközi)
                ar_ebay = search_ebay(t)
                if ar_ebay:
                    new_records.append({'datum': datetime.now(), 'termek': t, 'ar': ar_ebay, 'forras': 'eBay (Int)', 'link': ''})
                
                time.sleep(1) # Ne tiltsanak le
            
            if new_records:
                new_df = pd.DataFrame(new_records)
                st.session_state.history = pd.concat([st.session_state.history, new_df], ignore_index=True)
                save_data(st.session_state.history)
                st.balloons()

# VIZUALIZÁCIÓ
if not st.session_state.history.empty:
    st.subheader("📊 Árfolyam grafikonok")
    
    # Termék választó a grafikonhoz
    valasztott_termek = st.selectbox("Válassz terméket a részletekhez:", st.session_state.history['termek'].unique())
    
    plot_df = st.session_state.history[st.session_state.history['termek'] == valasztott_termek]
    
    if not plot_df.empty:
        fig = px.line(plot_df, x='datum', y='ar', color='forras', 
                      title=f"{valasztott_termek} árváltozása",
                      markers=True, labels={'ar': 'Ár (HUF)', 'datum': 'Dátum'})
        st.plotly_chart(fig, use_container_width=True)
    
    st.subheader("📋 Legutóbbi adatok")
    st.dataframe(st.session_state.history.sort_values(by='datum', ascending=False), use_container_width=True)
else:
    st.info("Még nincsenek adatok. Adj meg egy terméket az oldalsávon és kattints az Árak frissítése gombra!")

# EXTRA FUNKCIÓ (5. pont): Értesítés imitáció
if not st.session_state.history.empty:
    utolso_ar = st.session_state.history.iloc[-1]['ar']
    termek_neve = st.session_state.history.iloc[-1]['termek']
    st.toast(f"Figyelés aktív: {termek_neve} legutóbbi ára {utolso_ar} Ft", icon='🔔')
