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

# --- IDE MÁSOLD BE AZ API KULCSODAT ---
# Az ingyenes csomag 5000 kérést ad havonta, ami bőven elég neked!
SCRAPER_API_KEY = "41d4ff55c2f7e677f5e091e8b156e08e" 

DATA_FILE = "price_history.csv"
ITEMS_FILE = "monitored_items.txt"

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

@st.cache_data(ttl=3600)
def get_eur_huf():
    try:
        response = requests.get("https://open.er-api.com/v6/latest/EUR", timeout=5)
        return response.json()['rates']['HUF']
    except:
        return 400.0

# --- KERESŐ MOTOROK (SCRAPER API-VAL) ---

def call_scraper_api(url):
    # Ez a rész felel azért, hogy ne tiltsanak le
    proxy_url = f"http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url={url}&country_code=eu"
    try:
        response = requests.get(proxy_url, timeout=30)
        if response.status_code == 200:
            return response.content
    except Exception as e:
        print(f"Hiba a lekérés során: {e}")
    return None

def search_jofogas(keyword):
    url = f"https://www.jofogas.hu/magyarorszag?q={keyword.replace(' ', '+')}"
    content = call_scraper_api(url)
    if not content: return None, "Hálózati hiba"
    
    soup = BeautifulSoup(content, 'html.parser')
    item = soup.select_one(".list-item") or soup.select_one(".item")
    if item:
        try:
            link = item.find('a', href=True)['href']
            price_tag = item.select_one(".price-value")
            price = int(''.join(filter(str.isdigit, price_tag.text)))
            return price, link
        except: pass
    return None, "Nincs találat"

def search_ebay(keyword, eur_rate):
    url = f"https://www.ebay.de/sch/i.html?_nkw={keyword.replace(' ', '+')}&_sop=15"
    content = call_scraper_api(url)
    if not content: return None, "Hálózati hiba"
    
    soup = BeautifulSoup(content, 'html.parser')
    items = soup.select(".s-item__info")
    for item in items[1:]:
        try:
            price_tag = item.select_one(".s-item__price")
            link_tag = item.select_one(".s-item__link")
            if price_tag and link_tag:
                price_text = price_tag.text.split('bis')[0].replace('EUR', '')
                price_num = ''.join(c for c in price_text if c.isdigit() or c in ',.')
                price_num = price_num.replace(',', '.')
                return int(float(price_num) * eur_rate), link_tag['href']
        except: continue
    return None, "Nincs találat"

# --- UI ---
st.title("📈 Profi Piacfigyelő (ScraperAPI védelemmel)")

eur_huf = get_eur_huf()
st.sidebar.info(f"Árfolyam: 1 EUR = {eur_huf:.2f} HUF")

if 'monitored_items' not in st.session_state:
    st.session_state.monitored_items = load_monitored_items()
if 'history' not in st.session_state:
    st.session_state.history = load_price_history()

# OLDALSÁV
with st.sidebar:
    st.header("Beállítások")
    new_item = st.text_input("Új termék neve:")
    if st.button("Hozzáadás"):
        if new_item:
            save_monitored_item(new_item)
            st.session_state.monitored_items = load_monitored_items()
            st.rerun()

    if st.button("Minden törlése"):
        if os.path.exists(ITEMS_FILE): os.remove(ITEMS_FILE)
        if os.path.exists(DATA_FILE): os.remove(DATA_FILE)
        st.session_state.monitored_items = []
        st.session_state.history = pd.DataFrame(columns=['datum', 'termek', 'ar', 'forras', 'link'])
        st.rerun()

# FŐPANEL
if not st.session_state.monitored_items:
    st.info("Adj hozzá egy terméket a kezdéshez!")
else:
    if st.button("🚀 ÁRAK FRISSÍTÉSE", type="primary"):
        if SCRAPER_API_KEY == "IDE_MASOLD_AZ_API_KULCSODAT":
            st.error("Hiba: Elfelejtetted beállítani az API kulcsot!")
        else:
            new_records = []
            status = st.empty()
            progress = st.progress(0)
            
            for idx, t in enumerate(st.session_state.monitored_items):
                status.text(f"Keresés: {t}...")
                
                # Jófogás
                ar, link = search_jofogas(t)
                if ar: new_records.append({'datum': datetime.now(), 'termek': t, 'ar': ar, 'forras': 'Jófogás', 'link': link})
                
                # eBay
                ar_eb, link_eb = search_ebay(t, eur_huf)
                if ar_eb: new_records.append({'datum': datetime.now(), 'termek': t, 'ar': ar_eb, 'forras': 'eBay (EUR)', 'link': link_eb})
                
                progress.progress((idx + 1) / len(st.session_state.monitored_items))
                time.sleep(1)
            
            if new_records:
                new_df = pd.DataFrame(new_records)
                st.session_state.history = pd.concat([st.session_state.history, new_df], ignore_index=True)
                st.session_state.history.to_csv(DATA_FILE, index=False)
                st.success("Adatok mentve!")
                st.rerun()
            else:
                st.error("Sajnos most sem sikerült adatot kinyerni. Ellenőrizd az API kulcsodat!")

# VIZUALIZÁCIÓ
if not st.session_state.history.empty:
    tab1, tab2 = st.tabs(["📈 Grafikon", "📋 Adatlap"])
    with tab1:
        target = st.selectbox("Válassz terméket:", st.session_state.monitored_items)
        plot_df = st.session_state.history[st.session_state.history['termek'] == target]
        if not plot_df.empty:
            fig = px.line(plot_df, x='datum', y='ar', color='forras', markers=True)
            st.plotly_chart(fig, use_container_width=True)
    with tab2:
        st.dataframe(st.session_state.history.sort_values(by='datum', ascending=False),
                     column_config={"link": st.column_config.LinkColumn("Megnyitás")},
                     use_container_width=True)
