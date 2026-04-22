import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import os

# --- KONFIGURÁCIÓ ---
st.set_page_config(page_title="Okos Piacfigyelő", layout="wide")

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
        try:
            df = pd.read_csv(DATA_FILE)
            df['datum'] = pd.to_datetime(df['datum'])
            return df
        except:
            return pd.DataFrame(columns=['datum', 'termek', 'ar', 'forras', 'link'])
    return pd.DataFrame(columns=['datum', 'termek', 'ar', 'forras', 'link'])

@st.cache_data(ttl=3600)
def get_eur_huf():
    try:
        response = requests.get("https://open.er-api.com/v6/latest/EUR", timeout=5)
        return response.json()['rates']['HUF']
    except:
        return 400.0

# --- KERESŐ MOTOROK (JAVÍTOTT) ---

def get_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Accept-Language": "hu-HU,hu;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.google.com/"
    }

def search_jofogas(keyword):
    try:
        url = f"https://www.jofogas.hu/magyarorszag?q={keyword.replace(' ', '+')}"
        response = requests.get(url, headers=get_headers(), timeout=15)
        
        if response.status_code != 200:
            return None, f"Hiba: {response.status_code}"
            
        soup = BeautifulSoup(response.content, 'html.parser')
        # Megpróbáljuk több szelektorral is
        item = soup.select_one(".list-item") or soup.select_one(".item")
        
        if item:
            link = item.find('a', href=True)['href']
            price_tag = item.select_one(".price-value")
            if price_tag:
                price = int(''.join(filter(str.isdigit, price_tag.text)))
                return price, link
        return None, "Nem található termék"
    except Exception as e:
        return None, str(e)

def search_ebay(keyword, eur_rate):
    try:
        url = f"https://www.ebay.de/sch/i.html?_nkw={keyword.replace(' ', '+')}&_sop=15"
        response = requests.get(url, headers=get_headers(), timeout=15)
        
        if response.status_code != 200:
            return None, "Blokkolva"

        soup = BeautifulSoup(response.content, 'html.parser')
        items = soup.select(".s-item__info")
        
        for item in items[1:]: # Az első elem gyakran hibás az eBay-en
            price_tag = item.select_one(".s-item__price")
            link_tag = item.select_one(".s-item__link")
            
            if price_tag and link_tag:
                price_text = price_tag.text.split('bis')[0] # Ha ársáv van
                price_num = ''.join(c for c in price_text if c.isdigit() or c in ',.')
                price_num = price_num.replace(',', '.')
                
                if price_num:
                    price_eur = float(price_num)
                    return int(price_eur * eur_rate), link_tag['href']
        return None, "Nincs találat"
    except:
        return None, "Hiba"

# --- UI ---
st.title("🔍 Profi Piacfigyelő")

eur_huf = get_eur_huf()
st.sidebar.info(f"Árfolyam: 1 EUR = {eur_huf:.2f} HUF")

# Adatok betöltése
if 'monitored_items' not in st.session_state:
    st.session_state.monitored_items = load_monitored_items()
if 'history' not in st.session_state:
    st.session_state.history = load_price_history()

# OLDALSÁV
with st.sidebar:
    st.header("Beállítások")
    new_item = st.text_input("Új termék:", placeholder="Pl. iPhone 13")
    if st.button("Hozzáadás"):
        if new_item and new_item not in st.session_state.monitored_items:
            save_monitored_item(new_item)
            st.session_state.monitored_items = load_monitored_items()
            st.rerun()

    st.write("---")
    st.write("Figyelt listád:")
    for m in st.session_state.monitored_items:
        st.caption(f"• {m}")
    
    if st.button("Összes törlése"):
        if os.path.exists(ITEMS_FILE): os.remove(ITEMS_FILE)
        if os.path.exists(DATA_FILE): os.remove(DATA_FILE)
        st.session_state.monitored_items = []
        st.session_state.history = pd.DataFrame(columns=['datum', 'termek', 'ar', 'forras', 'link'])
        st.rerun()

# FŐPANEL
if not st.session_state.monitored_items:
    st.info("Adj hozzá egy terméket a bal oldalon a kezdéshez!")
else:
    if st.button("🚀 ÁRAK FRISSÍTÉSE", type="primary"):
        new_records = []
        status_box = st.empty()
        progress_bar = st.progress(0)
        
        for idx, t in enumerate(st.session_state.monitored_items):
            status_box.text(f"Keresés: {t}...")
            
            # Jófogás lekérés
            ar_jo, info_jo = search_jofogas(t)
            if ar_jo:
                new_records.append({'datum': datetime.now(), 'termek': t, 'ar': ar_jo, 'forras': 'Jófogás', 'link': info_jo})
            else:
                st.warning(f"Jófogás ({t}): {info_jo}")
            
            # eBay lekérés
            ar_eb, info_eb = search_ebay(t, eur_huf)
            if ar_eb:
                new_records.append({'datum': datetime.now(), 'termek': t, 'ar': ar_eb, 'forras': 'eBay (EUR)', 'link': info_eb})
            else:
                st.warning(f"eBay ({t}): {info_eb}")
            
            progress_bar.progress((idx + 1) / len(st.session_state.monitored_items))
            time.sleep(2) # Kicsit több szünet a tiltás elkerülésére
            
        if new_records:
            new_df = pd.DataFrame(new_records)
            st.session_state.history = pd.concat([st.session_state.history, new_df], ignore_index=True)
            st.session_state.history.to_csv(DATA_FILE, index=False)
            st.success(f"Sikeresen frissítve {len(new_records)} új adatpont!")
            status_box.empty()
            st.rerun()
        else:
            st.error("Egyetlen oldalon sem sikerült árat találni. Lehet, hogy a robotvédelmet nem sikerült megkerülni.")

# MEGJELENÍTÉS
if not st.session_state.history.empty:
    tab1, tab2 = st.tabs(["📈 Grafikon", "📋 Adatok és Linkek"])
    
    with tab1:
        target = st.selectbox("Termék kiválasztása:", st.session_state.monitored_items)
        plot_df = st.session_state.history[st.session_state.history['termek'] == target]
        if not plot_df.empty:
            fig = px.line(plot_df, x='datum', y='ar', color='forras', markers=True, title=f"{target} árfolyam")
            st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        st.dataframe(
            st.session_state.history.sort_values(by='datum', ascending=False),
            column_config={
                "link": st.column_config.LinkColumn("Hirdetés"),
                "ar": st.column_config.NumberColumn("Ár", format="%d Ft")
            },
            use_container_width=True
        )
