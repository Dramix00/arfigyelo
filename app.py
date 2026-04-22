import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import os

# --- KONFIGURÁCIÓ ---
st.set_page_config(page_title="Profi Piacfigyelő", layout="wide")

DATA_FILE = "price_history.csv"
ITEMS_FILE = "monitored_items.txt"

# --- ADATKEZELÉS ---
def load_monitored_items():
    if os.path.exists(ITEMS_FILE):
        with open(ITEMS_FILE, "r", encoding="utf-8") as f:
            return [line.strip() for line in f.readlines() if line.strip()]
    return []

def save_monitored_item(item):
    items = load_monitored_items()
    if item not in items:
        with open(ITEMS_FILE, "a", encoding="utf-8") as f:
            f.write(item + "\n")

def load_price_history():
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
        df['datum'] = pd.to_datetime(df['datum'])
        return df
    return pd.DataFrame(columns=['datum', 'termek', 'ar', 'forras', 'link'])

# --- VALUTAVÁLTÓ (Élő árfolyam) ---
@st.cache_data(ttl=3600) # Óránként frissíti csak az árfolyamot
def get_eur_huf():
    try:
        # Ingyenes, regisztráció nélküli API
        response = requests.get("https://open.er-api.com/v6/latest/EUR")
        data = response.json()
        return data['rates']['HUF']
    except:
        return 400.0  # Tartalék, ha az API nem elérhető

# --- KERESŐ MOTOROK ---
def search_jofogas(keyword):
    try:
        url = f"https://www.jofogas.hu/magyarorszag?q={keyword.replace(' ', '+')}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        item = soup.find('div', class_='list-item')
        if item:
            link = item.find('a', class_='item-title')['href']
            price_text = item.find('span', class_='price-value').text
            price = int(''.join(filter(str.isdigit, price_text)))
            return price, link
    except:
        pass
    return None, None

def search_ebay(keyword, eur_rate):
    try:
        # eBay Németország (Európai piac)
        url = f"https://www.ebay.de/sch/i.html?_nkw={keyword.replace(' ', '+')}&_sop=15" # _sop=15 a legolcsóbb
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Az első valid termék keresése
        items = soup.find_all('div', class_='s-item__info')
        for item in items[1:]: # Az első elem sokszor reklám
            price_tag = item.find('span', class_='s-item__price')
            link_tag = item.find('a', class_='s-item__link')
            if price_tag and link_tag:
                # EUR tisztítása (pl. "12,99 EUR")
                price_raw = price_tag.text.replace('EUR', '').replace(' ', '').replace('.', '').replace(',', '.')
                # Csak az első számot vesszük ki, ha ár-tartomány van (pl. 10 - 20 EUR)
                price_eur = float(''.join(c for c in price_raw.split('bis')[0] if c.isdigit() or c == '.'))
                return int(price_eur * eur_rate), link_tag['href']
    except:
        pass
    return None, None

# --- UI ---
st.title("🔍 Okos Piacfigyelő & Ár-összehasonlító")

eur_huf = get_eur_huf()
st.info(f"Aktuális árfolyam: **1 EUR = {eur_huf:.2f} HUF**")

# Inicializálás
if 'items' not in st.session_state:
    st.session_state.monitored_items = load_monitored_items()
if 'history' not in st.session_state:
    st.session_state.history = load_price_history()

# OLDALSÁV
with st.sidebar:
    st.header("Figyelt termékek")
    new_item = st.text_input("Új termék neve:", placeholder="Pl. RTX 3060ti")
    if st.button("Hozzáadás"):
        if new_item and new_item not in st.session_state.monitored_items:
            save_monitored_item(new_item)
            st.session_state.monitored_items = load_monitored_items()
            st.rerun()

    st.write("---")
    for m_item in st.session_state.monitored_items:
        st.write(f"📌 {m_item}")
    
    if st.button("Lista ürítése", type="secondary"):
        if os.path.exists(ITEMS_FILE): os.remove(ITEMS_FILE)
        st.session_state.monitored_items = []
        st.rerun()

# FŐPANEL
if not st.session_state.monitored_items:
    st.warning("Még nem adtál hozzá terméket az oldalsávon!")
else:
    if st.button("🚀 ÖSSZES TERMÉK FRISSÍTÉSE", type="primary"):
        new_records = []
        progress_bar = st.progress(0)
        
        for idx, t in enumerate(st.session_state.monitored_items):
            # Jófogás
            ar_jo, link_jo = search_jofogas(t)
            if ar_jo:
                new_records.append({'datum': datetime.now(), 'termek': t, 'ar': ar_jo, 'forras': 'Jófogás', 'link': link_jo})
            
            # eBay
            ar_eb, link_eb = search_ebay(t, eur_huf)
            if ar_eb:
                new_records.append({'datum': datetime.now(), 'termek': t, 'ar': ar_eb, 'forras': 'eBay (EUR)', 'link': link_eb})
            
            progress_bar.progress((idx + 1) / len(st.session_state.monitored_items))
            time.sleep(1) # Etikus scraping
            
        if new_records:
            new_df = pd.DataFrame(new_records)
            st.session_state.history = pd.concat([st.session_state.history, new_df], ignore_index=True)
            st.session_state.history.to_csv(DATA_FILE, index=False)
            st.success("Adatok frissítve!")
            st.rerun()

# ADATOK MEGJELENÍTÉSE
if not st.session_state.history.empty:
    # Grafikon választó
    target = st.selectbox("Melyik termék grafikonját nézzük?", st.session_state.monitored_items)
    plot_df = st.session_state.history[st.session_state.history['termek'] == target]
    
    if not plot_df.empty:
        fig = px.line(plot_df, x='datum', y='ar', color='forras', markers=True,
                      title=f"{target} árváltozása (HUF)")
        st.plotly_chart(fig, use_container_width=True)

    # Táblázat linkekkel
    st.subheader("Aktuális találatok és linkek")
    
    # Formázzuk a táblázatot, hogy a linkek kattinthatóak legyenek
    display_df = st.session_state.history.sort_values(by='datum', ascending=False).copy()
    
    # Streamlit oszlop konfiguráció a linkekhez
    st.dataframe(
        display_df,
        column_config={
            "link": st.column_config.LinkColumn("Hirdetés megnyitása"),
            "ar": st.column_config.NumberColumn("Ár (HUF)", format="%d Ft"),
            "datum": st.column_config.DatetimeColumn("Dátum")
        },
        use_container_width=True,
        hide_index=True
    )
