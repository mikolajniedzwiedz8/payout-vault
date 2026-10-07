import calendar
from datetime import datetime
import os
from zoneinfo import ZoneInfo
import feedparser
import google.generativeai as genai
import numpy as np
import pandas as pd
from PIL import Image
import plotly.graph_objects as go
import requests
import streamlit as st
import streamlit.components.v1 as components

# --- KONFIGURACJA STRONY ---
st.set_page_config(
    page_title="PAYOUT VAULT // COMMAND BRIDGE",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- BEZPIECZNE POBIERANIE KLUCZA API ---
try:
  GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
except Exception:
  GEMINI_API_KEY = "TUTAJ_WKLEJ_LOKALNY_KLUCZ_JEŚLI_TESTUJESZ_OFFLINE"


def get_clean_gemini_key():
  key = str(globals().get("GEMINI_API_KEY", "")).strip()
  if "TUTAJ_" in key or not key:
    key = ""
  return key


def get_gemini_model():
  klucz = get_clean_gemini_key()
  if not klucz or len(klucz) < 15:
    return None, "Brak klucza API w sekretach Streamlit"

  genai.configure(api_key=klucz)
  wybrany_model = "gemini-2.0-flash"
  try:
    dostepne = [
        m.name
        for m in genai.list_models()
        if "generateContent" in m.supported_generation_methods
    ]
    for pref in [
        "gemini-3.5-flash-lite",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash-latest",
        "flash",
    ]:
      trafiony = next((m for m in dostepne if pref in m.lower()), None)
      if trafiony:
        wybrany_model = trafiony
        break
    if not trafiony and dostepne:
      wybrany_model = dostepne[0]
  except Exception:
    pass

  return genai.GenerativeModel(wybrany_model), str(wybrany_model).replace(
      "models/", ""
  )


# --- BAZA DANYCH I KATALOG ZDJĘĆ ---
JOURNAL_FILE = "trades.csv"
IMAGES_DIR = "journal_images"
if not os.path.exists(IMAGES_DIR):
  os.makedirs(IMAGES_DIR)

if not os.path.exists(JOURNAL_FILE):
  df_init = pd.DataFrame(columns=[
      "id",
      "data",
      "instrument",
      "kierunek",
      "model",
      "wynik_r",
      "status",
      "jakosc",
      "notatki",
      "zdjecie",
  ])
  df_init.to_csv(JOURNAL_FILE, index=False)

# --- STYLE CSS ---
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700;800&display=swap');
    [data-testid="stHeader"], section.main, .block-container { background: transparent !important; }
    html, body, [class*="css"], .stApp {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        color: #d1d5eb;
    }
    .stApp, [data-testid="stAppViewContainer"] {
        background-color: #070712 !important;
        background-image: linear-gradient(180deg, #06060f 0%, #090918 100%) !important;
    }
    section[data-testid="stSidebar"] {
        background: #04050a !important;
        border-right: 1px solid rgba(255, 255, 255, 0.06) !important;
        padding-top: 14px;
    }
    .brand-header {
        display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 800; color: #ffffff;
        padding: 0 4px 16px 4px; border-bottom: 1px solid rgba(255, 255, 255, 0.06); margin-bottom: 16px;
    }
    .brand-sparkle { color: #818cf8; font-size: 15px; }
    .stSidebar [data-testid="stButton"] { margin-bottom: -8px !important; }
    .stSidebar [data-testid="stButton"] > button {
        width: 100% !important; text-align: left !important; justify-content: flex-start !important;
        border-radius: 8px !important; padding: 10px 14px !important; font-size: 13px !important; font-weight: 600 !important;
    }
    .stSidebar [data-testid="stButton"] > button[kind="secondary"] {
        background: rgba(255, 255, 255, 0.02) !important; border: 1px solid rgba(255, 255, 255, 0.07) !important; color: #94a3b8 !important;
    }
    .stSidebar [data-testid="stButton"] > button[kind="primary"] {
        background: linear-gradient(90deg, rgba(168, 85, 247, 0.22) 0%, rgba(20, 14, 38, 0.95) 100%) !important;
        border: 1px solid rgba(192, 132, 252, 0.7) !important; border-left: 5px solid #c084fc !important; color: #ffffff !important;
    }
    .tape-headline { font-size: 10px; font-weight: 800; letter-spacing: 0.12em; color: #64748b; text-transform: uppercase; margin-bottom: 8px; }
    .tape-container {
        display: flex; justify-content: space-between; background: rgba(10, 12, 22, 0.75);
        border-top: 1px solid rgba(255, 255, 255, 0.06); border-bottom: 1px solid rgba(255, 255, 255, 0.06);
        padding: 12px 6px; margin-bottom: 24px; overflow-x: auto;
    }
    .tape-col { display: flex; flex-direction: column; align-items: flex-start; padding: 0 14px; min-width: 95px; border-right: 1px solid rgba(255, 255, 255, 0.04); }
    .tape-symbol { font-size: 9px; font-weight: 700; color: #64748b; text-transform: uppercase; }
    .tape-price { font-size: 15px; font-weight: 700; color: #ffffff; font-family: 'JetBrains Mono', monospace !important; margin: 2px 0 1px 0; }
    .tape-delta-up { font-size: 11px; font-weight: 600; color: #10b981; font-family: 'JetBrains Mono', monospace !important; }
    .tape-delta-down { font-size: 11px; font-weight: 600; color: #ef4444; font-family: 'JetBrains Mono', monospace !important; }
    .hero-report-card {
        background: rgba(9, 11, 20, 0.9); border: 1px solid rgba(255, 255, 255, 0.06);
        border-top: 2px solid #38bdf8; border-left: 2px solid #38bdf8; border-radius: 8px; padding: 22px; margin-bottom: 22px;
    }
    .gf-card {
        background: rgba(11, 14, 25, 0.9); border: 1px solid rgba(255, 255, 255, 0.07);
        border-radius: 8px; padding: 18px; margin-bottom: 14px;
    }
    </style>
""",
    unsafe_allow_html=True,
)


# --- POBIERANIE CEN RYNKOWYCH ---
def get_market_data(symbol):
  try:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
    }
    response = requests.get(url, headers=headers, timeout=4)
    data = response.json()
    meta = data["chart"]["result"][0]["meta"]
    price = meta["regularMarketPrice"]
    prev_close = meta["chartPreviousClose"]
    change_pct = ((price - prev_close) / prev_close) * 100
    return price, change_pct
  except Exception:
    return 0.0, 0.0


eur_p, eur_c = get_market_data("EURUSD=X")
gbp_p, gbp_c = get_market_data("GBPUSD=X")
gold_p, gold_c = get_market_data("GC=F")
nq_p, nq_c = get_market_data("NQ=F")
oil_p, oil_c = get_market_data("CL=F")
dxy_p, dxy_c = get_market_data("DX-Y.NYB")
sp_p, sp_c = get_market_data("ES=F")
btc_p, btc_c = get_market_data("BTC-USD")
vix_p, vix_c = get_market_data("^VIX")
yield_p, yield_c = get_market_data("^TNX")


def render_delta(val):
  if val > 0:
    return f'<span class="tape-delta-up">+{val:.2f}% ▲</span>'
  elif val < 0:
    return f'<span class="tape-delta-down">{val:.2f}% ▼</span>'
  else:
    return '<span class="tape-symbol" style="color:#94a3b8;">0.00%</span>'


st.markdown(
    f"""
<div class="tape-headline">THE TAPE // LIVE ASSETS</div>
<div class="tape-container">
    <div class="tape-col"><span class="tape-symbol">EURUSD</span><span class="tape-price">{eur_p:.4f}</span>{render_delta(eur_c)}</div>
    <div class="tape-col"><span class="tape-symbol">GBPUSD</span><span class="tape-price">{gbp_p:.4f}</span>{render_delta(gbp_c)}</div>
    <div class="tape-col"><span class="tape-symbol">XAUUSD</span><span class="tape-price">{gold_p:.2f}</span>{render_delta(gold_c)}</div>
    <div class="tape-col"><span class="tape-symbol">NASDAQ</span><span class="tape-price">{nq_p:.2f}</span>{render_delta(nq_c)}</div>
    <div class="tape-col"><span class="tape-symbol">OIL</span><span class="tape-price">{oil_p:.2f}</span>{render_delta(oil_c)}</div>
    <div class="tape-col"><span class="tape-symbol">DXY</span><span class="tape-price">{dxy_p:.2f}</span>{render_delta(dxy_c)}</div>
    <div class="tape-col"><span class="tape-symbol">S&P 500</span><span class="tape-price">{sp_p:.2f}</span>{render_delta(sp_c)}</div>
    <div class="tape-col"><span class="tape-symbol">BTC</span><span class="tape-price">{btc_p:,.0f}</span>{render_delta(btc_c)}</div>
    <div class="tape-col"><span class="tape-symbol">VIX</span><span class="tape-price">{vix_p:.2f}</span>{render_delta(vix_c)}</div>
    <div class="tape-col"><span class="tape-symbol">10Y</span><span class="tape-price">{yield_p:.2f}%</span>{render_delta(yield_c)}</div>
</div>
""",
    unsafe_allow_html=True,
)

# --- FUNKCJE POMOCNICZE DANYCH ---
def get_forex_calendar():
  try:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    r = requests.get(
        "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
        headers=headers,
        timeout=5,
    )
    return r.json() if r.status_code == 200 else []
  except Exception:
    return []


def get_google_finance_news(query):
  try:
    encoded_query = requests.utils.quote(f"{query} when:2d")
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    r = requests.get(url, headers=headers, timeout=6)
    feed = feedparser.parse(r.content)

    news_items = []
    for entry in feed.entries[:3]:
      full_title = entry.get("title", "")
      source = "Google Finance"
      title = full_title
      if " - " in full_title:
        parts = full_title.rsplit(" - ", 1)
        title = parts[0]
        source = parts[1]
      news_items.append({
          "title": title,
          "source": source,
          "link": entry.get("link", "#"),
          "published": entry.get("published", "")[:16],
      })
    return news_items
  except Exception:
    return []


def get_rss_with_images(url):
  try:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    r = requests.get(url, headers=headers, timeout=6)
    feed = feedparser.parse(r.content)
    items = []
    for entry in feed.entries[:8]:
      img_url = None
      if "media_thumbnail" in entry and len(entry.media_thumbnail) > 0:
        img_url = entry.media_thumbnail[0].get("url")
      elif "media_content" in entry and len(entry.media_content) > 0:
        img_url = entry.media_content[0].get("url")
      elif "enclosures" in entry and len(entry.enclosures) > 0:
        for enc in entry.enclosures:
          if "image" in enc.get("type", ""):
            img_url = enc.get("href")
            break
      if not img_url:
        img_url = (
            "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=300&q=80"
        )
      items.append({
          "title": entry.get("title", ""),
          "link": entry.get("link", "#"),
          "published": entry.get("published", "")[:22],
          "image": img_url,
      })
    return items
  except Exception:
    return []


# --- PANEL BOCZNY ---
if "current_tab" not in st.session_state:
  st.session_state["current_tab"] = (
      "Taktyczny terminal na żywo i interfejs HUD mapy"
  )

with st.sidebar:
  st.markdown(
      """
    <div class="brand-header">
        <span class="brand-sparkle">✦</span> SKARBIEC WYPŁAT <span style="color:#64748b; font-weight:600;">SILNIK</span>
    </div>
    """,
      unsafe_allow_html=True,
  )

  menu_opcje = [
      "Taktyczny terminal na żywo i interfejs HUD mapy",
      "Poranny raport i skanowanie dzienne",
      "🌐 Fundamental Pulse i strumień Google Finance",
      "👁️ Inspektor wykresów wizji AI",
      "Dziennik handlowy",
      "Krzywa kapitału (Netto R)",
      "Kursy na dziś",
      "Kalendarz Forex Factory",
      "Wiadomości na żywo i CNBC",
  ]

  for opcja in menu_opcje:
    is_active = st.session_state["current_tab"] == opcja
    btn_type = "primary" if is_active else "secondary"
    if st.button(
        opcja, key=f"nav_{opcja}", type=btn_type, use_container_width=True
    ):
      st.session_state["current_tab"] = opcja
      st.rerun()

  menu = st.session_state["current_tab"]

  st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)
  st.caption("🛡️ MENEDŻER RYZYKA")
  kapital = st.number_input("Kapitał konta ($)", value=10000, step=1000)
  ryzyko_proc = st.selectbox("Ryzyko na transakcję (%)", [0.25, 0.50, 1.00], index=1)
  sl_pips = st.number_input("Stop Loss (pips)", value=8.0, step=0.5)

  kwota_ryzyka = kapital * (ryzyko_proc / 100)
  lot_size = kwota_ryzyka / (sl_pips * 10) if sl_pips > 0 else 0
  prowizja_usd = lot_size * 6.0
  prowizja_r = prowizja_usd / kwota_ryzyka if kwota_ryzyka > 0 else 0

# ==============================================================================
# MODUŁ 1: TERMINAL & CHART
# ==============================================================================
if menu == "Taktyczny terminal na żywo i interfejs HUD mapy":
  st.title("🖥️ Taktyczny terminal na żywo i interfejs HUD mapy")
  st.caption(
      "Monitoring sesji rynkowych w czasie rzeczywistym, algorytmiczne Golden"
      " Minutes oraz wykres TradingView"
  )

  now_lon = datetime.now(ZoneInfo("Europe/London"))
  now_ny = datetime.now(ZoneInfo("America/New_York"))
  now_utc = datetime.now(ZoneInfo("UTC"))

  lon_open = 8 <= now_lon.hour < 16
  ny_open = (now_ny.hour == 9 and now_ny.minute >= 30) or (
      9 < now_ny.hour < 16
  )
  asia_open = 0 <= now_lon.hour < 7

  min_lon_815 = (8 * 60 + 15) - (now_lon.hour * 60 + now_lon.minute)
  min_ny_930 = (9 * 60 + 30) - (now_ny.hour * 60 + now_ny.minute)

  if min_lon_815 > 0:
    ldn_alert = f"Za {min_lon_815} min (Oczekiwanie na sweep Azji)"
    ldn_color = "#f59e0b"
  elif -60 <= min_lon_815 <= 0:
    ldn_alert = f"AKTYWNE OKNO (-{abs(min_lon_815)}m)! Poluj na Type 1"
    ldn_color = "#10b981"
  else:
    ldn_alert = "Sesja w toku / Poza oknem Type 1"
    ldn_color = "#64748b"

  if min_ny_930 > 0:
    ny_alert = f"Za {min_ny_930} min (Oczekiwanie na Cash Open)"
    ny_color = "#38bdf8"
  elif -60 <= min_ny_930 <= 0:
    ny_alert = f"AKTYWNY OPEN (-{abs(min_ny_930)}m)! Zwiększona płynność"
    ny_color = "#10b981"
  else:
    ny_alert = "Po oficjalnym otwarciu kasowym"
    ny_color = "#64748b"

  zc1, zc2, zc3, zc4 = st.columns(4)
  with zc1:
    st.markdown(
        f"""
        <div class="terminal-clock-card">
            <div class="clock-city">LONDYN (UK)</div>
            <div class="clock-time">{now_lon.strftime('%H:%M:%S')}</div>
            <span class="clock-status {'status-open' if lon_open else 'status-closed'}">
                {'SESJA AKTYWNA' if lon_open else 'ZAMKNIĘTA'}
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

  with zc2:
    st.markdown(
        f"""
        <div class="terminal-clock-card">
            <div class="clock-city">NOWY JORK (EST)</div>
            <div class="clock-time">{now_ny.strftime('%H:%M:%S')}</div>
            <span class="clock-status {'status-open' if ny_open else ('status-pre' if now_ny.hour >= 7 else 'status-closed')}">
                {'CASH OPEN' if ny_open else ('PRE-MARKET' if now_ny.hour >= 7 else 'ZAMKNIĘTA')}
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

  with zc3:
    st.markdown(
        f"""
        <div class="terminal-clock-card">
            <div class="clock-city">AZJA (TOKYO / UTC)</div>
            <div class="clock-time">{now_utc.strftime('%H:%M:%S')} UTC</div>
            <span class="clock-status {'status-open' if asia_open else 'status-closed'}">
                {'RANGE BUDOWANY' if asia_open else 'ZAMKNIĘTA'}
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

  with zc4:
    st.markdown(
        f"""
        <div class="terminal-clock-card" style="border-color: rgba(56, 189, 248, 0.4);">
            <div class="clock-city" style="color:#38bdf8;">GOLDEN MINUTES</div>
            <div style="font-size:12px; margin-top:6px; color:#ffffff; font-family:'JetBrains Mono';"><b>08:15 UK:</b> <span style="color:{ldn_color}">{ldn_alert}</span></div>
            <div style="font-size:12px; margin-top:2px; color:#ffffff; font-family:'JetBrains Mono';"><b>09:30 NY:</b> <span style="color:{ny_color}">{ny_alert}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

  st.markdown("---")

  tv_c1, tv_c2 = st.columns([1, 4])
  with tv_c1:
    wybrany_inst = st.selectbox(
        "Aktywo TradingView",
        [
            "FX:EURUSD",
            "FX:GBPUSD",
            "OANDA:XAUUSD",
            "NASDAQ:NDX",
            "BITSTAMP:BTCUSD",
        ],
        index=0,
    )
    wybrany_tf = st.selectbox(
        "Interwał początkowy", ["1", "5", "15", "60", "D"], index=2
    )

  with tv_c2:
    tv_widget_html = f"""
        <div class="tradingview-widget-container" style="height:620px; width:100%; border:1px solid rgba(255,255,255,0.08); border-radius:8px; overflow:hidden;">
          <div id="tradingview_embed" style="height:100%; width:100%;"></div>
          <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
          <script type="text/javascript">
          new TradingView.widget({{
            "autosize": true,
            "symbol": "{wybrany_inst}",
            "interval": "{wybrany_tf}",
            "timezone": "Europe/London",
            "theme": "dark",
            "style": "1",
            "locale": "pl",
            "toolbar_bg": "#05060b",
            "enable_publishing": false,
            "hide_side_toolbar": false,
            "allow_symbol_change": true,
            "save_image": true,
            "container_id": "tradingview_embed"
          }});
          </script>
        </div>
        """
    components.html(tv_widget_html, height=630)

# ==============================================================================
# MODUŁ 2: MORNING REPORT
# ==============================================================================
elif menu == "Poranny raport i skanowanie dzienne":
  st.markdown(
      """<div class="hero-report-card">
<span style="color:#38bdf8; font-size:11px; font-weight:800; letter-spacing:1px; text-transform:uppercase;">● AI INSTITUTIONAL RECON SCAN</span>
<h1 style="color:#ffffff; margin: 4px 0 10px 0; font-size:26px;">Morning Report & Directional Call</h1>
<p style="color:#94a3b8; font-size:14px; margin:0;">
Precyzyjna dekonstrukcja struktury rynkowej C.E.T., absorpcji w strefach <b>D1 Supply / Demand</b> oraz wyczerpania pędu przez silnik <b>Gemini AI</b>.
</p>
</div>""",
      unsafe_allow_html=True,
  )

  r1_c1, r1_c2, r1_c3 = st.columns(3)
  with r1_c1:
    instrument = st.selectbox(
        "Instrument", ["EURUSD", "GBPUSD", "XAUUSD (Złoto)", "NQ100"]
    )
  with r1_c2:
    d1_candle = st.selectbox("Świeca D1 (Wczoraj)", [
        "Engulfing Up (Silny impuls wzrostowy)",
        "Engulfing Down (Silny impuls spadkowy)",
        "Indecision (Doji / Konsolidacja)",
        "Rejection Up (Odrzucenie góry - knot)",
        "Rejection Down (Odrzucenie dołu - knot)",
    ])
  with r1_c3:
    d1_zone = st.selectbox("Lokalizacja w strefie D1 (HTF)", [
        "Otwarta przestrzeń (Brak kluczowej strefy D1)",
        "Wewnątrz D1 DEMAND / Bullish OB / FVG (Strefa Kupna)",
        "Wewnątrz D1 SUPPLY / Bearish OB / FVG (Strefa Sprzedaży)",
        "Świeży Sweep / Odrzucenie D1 Demand (Paliwo na odbicie w górę)",
        "Świeży Sweep / Odrzucenie D1 Supply (Paliwo na zrzut w dół)",
    ])

  r2_c1, r2_c2 = st.columns(2)
  with r2_c1:
    pdl_pdh = st.selectbox(
        "Sweep PDH / PDL?",
        ["Brak sweepu", "Sweep PDL (Paliwo na Long)", "Sweep PDH (Paliwo na Short)"],
    )
  with r2_c2:
    phase = st.selectbox("Faza Rynku 30M (MTF)", [
        "Faza 1A (Pro MTF / Początek impulsu)",
        "Faza 1B (Pro MTF / CHoCH)",
        "Faza 1C (Pro MTF / BOS + CHoCH - Setup A+)",
        "Faza 1D (Pro MTF / Wybity High/Low - Rozciągnięcie)",
        "Faza 2A (Counter MTF / Wczesny Pullback)",
        "Faza 2B (Counter MTF / Głęboka Korekta)",
        "Faza 2C (Counter MTF / Pełne Odwrócenie Struktury)",
    ])

  if st.button(
      "⚡ URUCHOM PEŁNY RAPORT SESYJNY (INSTITUTIONAL SCAN)", type="primary"
  ):
    ai_model, model_name = get_gemini_model()
    if ai_model:
      with st.spinner(
          f"Gemini ({model_name}) analizuje strefy D1, absorpcję wolumenu i"
          " generuje briefing..."
      ):
        try:
          prompt_baza = f"""
                    Jesteś Głównym Analitykiem C.E.T. Framework (Capital Efficiency Trading). Przygotuj instytucjonalny briefing przedsesyjny.
                    DANE SESJI:
                    - Aktywo: {instrument}
                    - Kontekst D1: {d1_candle}
                    - Strefa HTF D1: {d1_zone}
                    - Płynność zewnętrzna: {pdl_pdh}
                    - Faza struktury 30M: {phase}

                    ZASADY C.E.T.:
                    1. Pułapka pędu: Spadek w D1 Demand oznacza akumulację i szansę na V-bounce (zakaz sprzedaży w dołek D1 Demand). Wzrost w D1 Supply oznacza absorpcję podaży (zakaz kupowania w szczyt).
                    2. Wymóg zamknięcia korpusem (Body Close) po sweepie płynności sesyjnej.

                    Sformatuj w 4 sekcjach Markdown:
                    ### 1. 🏛 MECHANIKA D1 HTF & ABSORPCJA
                    ### 2. 🧭 FAZA 30M ORDER FLOW & BIAS
                    ### 3. 🎯 TAKTYKA EGZEKUCYJNA (LONDON / NY PLAYBOOK)
                    ### 4. ⚖️ WERDYKT KIERUNKOWY (BUY / SELL / STAND DOWN)
                    """
          res_g = ai_model.generate_content(prompt_baza)
          st.session_state["gemini_report"] = res_g.text
          st.session_state["gemini_model_name"] = model_name
          st.session_state["gemini_instrument"] = instrument
        except Exception as e:
          st.error(f"Błąd silnika Gemini: {e}")
    else:
      st.error("Brak skonfigurowanego klucza API w sekretach Streamlit Cloud.")

  if st.session_state.get("gemini_report"):
    st.markdown("---")
    st.markdown(
        f"""<div class="hero-report-card">
        <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
            <span style="color:#38bdf8; font-weight:800; font-size:13px;">DIRECTIONAL REPORT | {st.session_state.get('gemini_instrument', '')}</span>
            <span style="color:#64748b; font-family:'JetBrains Mono'; font-size:11px;">ENGINE: {st.session_state.get('gemini_model_name', 'Gemini Flash')}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(st.session_state["gemini_report"])
    st.markdown("</div>", unsafe_allow_html=True)

# ==============================================================================
# MODUŁ 3: FUNDAMENTAL PULSE & GOOGLE FINANCE STREAM (DYNAMICZNY)
# ==============================================================================
elif menu == "🌐 Fundamental Pulse i strumień Google Finance":
  st.markdown(
      """<div class="hero-report-card">
<span style="color:#38bdf8; font-size:11px; font-weight:800; letter-spacing:1px; text-transform:uppercase;">● REAL-TIME GOOGLE FINANCE INTELLIGENCE</span>
<h1 style="color:#ffffff; margin: 4px 0 8px 0; font-size:26px;">Fundamental Pulse & Google Finance Stream</h1>
<p style="color:#94a3b8; font-size:13px; margin:0;">
Agregacja depesz wprost ze strumieni <b>Google Finance</b> (Reuters, Bloomberg, FT) dedykowana dla <b>EURUSD</b>, <b>XAUUSD</b> oraz <b>GBPUSD</b>.
</p>
</div>""",
      unsafe_allow_html=True,
  )

  with st.spinner("Pobieranie strumieni depesz z Google Finance..."):
    gf_eur = get_google_finance_news(
        'EURUSD OR "EUR/USD" OR "European Central Bank"'
    )
    gf_gold = get_google_finance_news('XAUUSD OR "gold price" OR "gold market"')
    gf_gbp = get_google_finance_news('GBPUSD OR "GBP/USD" OR "Bank of England"')

  st.markdown(
      """<div style="background: linear-gradient(180deg, rgba(14, 18, 34, 0.9) 0%, rgba(8, 10, 20, 0.95) 100%); border: 1px solid rgba(255, 255, 255, 0.08); border-left: 4px solid #38bdf8; border-radius: 8px; padding: 18px; margin-bottom: 20px;">
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
<span style="color:#38bdf8; font-size:11px; font-weight:800; letter-spacing:0.08em; text-transform:uppercase;">DOMINUJĄCY MOTYW SESJI (GLOBAL DRIVER)</span>
<span style="color:#94a3b8; font-size:11px; font-family:'JetBrains Mono';">DXY: 101.40 | US10Y: 4.18%</span>
</div>
<div style="font-size:15px; font-weight:700; color:#ffffff; line-height:1.4;">
Oczekiwanie na nowe katalizatory inflacyjne w USA oraz popyt na aktywa Safe-Haven.
</div>
<div style="color:#94a3b8; font-size:12px; margin-top:6px; line-height:1.5;">
Inwestorzy instytucjonalni wstrzymują się z agresywnym skupem dolara (DXY). Rentowności obligacji USA stabilizują się, co sprzyja wycenie surowców oraz metali szlachetnych.
</div>
</div>""",
      unsafe_allow_html=True,
  )


  def get_market_badge(chg):
    if chg > 0.05:
      return (
          "▲ BULLISH / POPYT",
          "rgba(16, 185, 129, 0.18)",
          "#34d399",
          "rgba(52, 211, 153, 0.6)",
      )
    elif chg < -0.05:
      return (
          "▼ BEARISH / SPRZEDAŻ",
          "rgba(239, 68, 68, 0.18)",
          "#f87171",
          "rgba(248, 113, 113, 0.6)",
      )
    else:
      return (
          "◆ RANGE / WYCZEKIWANIE",
          "rgba(245, 158, 11, 0.18)",
          "#fbbf24",
          "rgba(251, 191, 36, 0.6)",
      )


  eur_txt, eur_bg_b, eur_col_b, eur_border_b = get_market_badge(eur_c)
  gold_txt, gold_bg_b, gold_col_b, gold_border_b = get_market_badge(gold_c)
  gbp_txt, gbp_bg_b, gbp_col_b, gbp_border_b = get_market_badge(gbp_c)

  col_eur, col_xau, col_gbp = st.columns(3)

  # --- KARTA EURUSD ---
  with col_eur:
    eur_news_html = (
        "".join([
            f"<div style='margin-bottom:8px; padding-bottom:6px;"
            " border-bottom:1px solid rgba(255,255,255,0.04);'><a"
            f" href='{item['link']}' target='_blank'"
            " style='color:#f1f5f9; text-decoration:none; font-size:12px;"
            f" font-weight:600; line-height:1.3; display:block;'>{item['title']}</a><span"
            " style='font-size:10px; color:#38bdf8;"
            f" font-weight:700;'>{item['source']}</span> • <span"
            f" style='font-size:10px; color:#64748b;'>{item['published']}</span></div>"
            for item in gf_eur
        ])
        if gf_eur
        else (
            "<div style='color:#64748b; font-size:11px;'>Brak świeżych"
            " depesz.</div>"
        )
    )

    st.markdown(
        f"""<div class="gf-card" style="border-top: 3px solid #38bdf8; display:flex; flex-direction:column; justify-content:space-between; min-height:480px;">
<div>
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
<span style="font-size:16px; font-weight:800; color:#ffffff; letter-spacing:0.02em;">EURUSD</span>
<span style="background:{eur_bg_b}; color:{eur_col_b}; border:1px solid {eur_border_b}; padding:5px 12px; border-radius:20px; font-size:11px; font-weight:800; font-family:'JetBrains Mono';">{eur_txt}</span>
</div>
<div style="font-size:24px; font-weight:800; color:#ffffff; font-family:'JetBrains Mono'; margin:6px 0 2px 0;">{eur_p:.4f}</div>
<div style="font-size:11px; color:{"#10b981" if eur_c >= 0 else "#ef4444"}; font-family:'JetBrains Mono'; margin-bottom:14px; font-weight:700;">{eur_c:+.2f}% dzisiaj</div>
<div style="font-size:10px; color:#64748b; font-weight:800; letter-spacing:0.06em; text-transform:uppercase; margin-bottom:8px;">DEPESZE GOOGLE FINANCE:</div>
{eur_news_html}
</div>
<div style="background: linear-gradient(180deg, rgba(56, 189, 248, 0.14) 0%, rgba(10, 16, 30, 0.95) 100%); border: 1px solid rgba(56, 189, 248, 0.45); border-left: 5px solid #38bdf8; border-radius: 8px; padding: 14px 16px; margin-top: 16px;">
<div style="color:#38bdf8; font-size:12px; font-weight:800; text-transform:uppercase; margin-bottom:6px;">⚡ C.E.T. PLAYBOOK</div>
<div style="color:#ffffff; font-size:13px; font-weight:700; line-height:1.4;">Reakcja ceny na aktualne przepływy zleceń (Order Flow) i strefy D1.</div>
</div>
</div>""",
        unsafe_allow_html=True,
    )

  # --- KARTA XAUUSD ---
  with col_xau:
    gold_news_html = (
        "".join([
            f"<div style='margin-bottom:8px; padding-bottom:6px;"
            " border-bottom:1px solid rgba(255,255,255,0.04);'><a"
            f" href='{item['link']}' target='_blank'"
            " style='color:#f1f5f9; text-decoration:none; font-size:12px;"
            f" font-weight:600; line-height:1.3; display:block;'>{item['title']}</a><span"
            " style='font-size:10px; color:#fbbf24;"
            f" font-weight:700;'>{item['source']}</span> • <span"
            f" style='font-size:10px; color:#64748b;'>{item['published']}</span></div>"
            for item in gf_gold
        ])
        if gf_gold
        else (
            "<div style='color:#64748b; font-size:11px;'>Brak świeżych"
            " depesz.</div>"
        )
    )

    st.markdown(
        f"""<div class="gf-card" style="border-top: 3px solid #fbbf24; display:flex; flex-direction:column; justify-content:space-between; min-height:480px;">
<div>
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
<span style="font-size:16px; font-weight:800; color:#ffffff; letter-spacing:0.02em;">XAUUSD (ZŁOTO)</span>
<span style="background:{gold_bg_b}; color:{gold_col_b}; border:1px solid {gold_border_b}; padding:5px 12px; border-radius:20px; font-size:11px; font-weight:800; font-family:'JetBrains Mono';">{gold_txt}</span>
</div>
<div style="font-size:24px; font-weight:800; color:#ffffff; font-family:'JetBrains Mono'; margin:6px 0 2px 0;">{gold_p:.2f}</div>
<div style="font-size:11px; color:{"#10b981" if gold_c >= 0 else "#ef4444"}; font-family:'JetBrains Mono'; margin-bottom:14px; font-weight:700;">{gold_c:+.2f}% dzisiaj</div>
<div style="font-size:10px; color:#64748b; font-weight:800; letter-spacing:0.06em; text-transform:uppercase; margin-bottom:8px;">DEPESZE GOOGLE FINANCE:</div>
{gold_news_html}
</div>
<div style="background: linear-gradient(180deg, rgba(245, 158, 11, 0.14) 0%, rgba(26, 18, 10, 0.95) 100%); border: 1px solid rgba(245, 158, 11, 0.45); border-left: 5px solid #fbbf24; border-radius: 8px; padding: 14px 16px; margin-top: 16px;">
<div style="color:#fbbf24; font-size:12px; font-weight:800; text-transform:uppercase; margin-bottom:6px;">⚡ C.E.T. PLAYBOOK</div>
<div style="color:#ffffff; font-size:13px; font-weight:700; line-height:1.4;">Monitorowanie płynności instytucjonalnej oraz poziomów stop loss.</div>
</div>
</div>""",
        unsafe_allow_html=True,
    )

  # --- KARTA GBPUSD ---
  with col_gbp:
    gbp_news_html = (
        "".join([
            f"<div style='margin-bottom:8px; padding-bottom:6px;"
            " border-bottom:1px solid rgba(255,255,255,0.04);'><a"
            f" href='{item['link']}' target='_blank'"
            " style='color:#f1f5f9; text-decoration:none; font-size:12px;"
            f" font-weight:600; line-height:1.3; display:block;'>{item['title']}</a><span"
            " style='font-size:10px; color:#a855f7;"
            f" font-weight:700;'>{item['source']}</span> • <span"
            f" style='font-size:10px; color:#64748b;'>{item['published']}</span></div>"
            for item in gf_gbp
        ])
        if gf_gbp
        else (
            "<div style='color:#64748b; font-size:11px;'>Brak świeżych"
            " depesz.</div>"
        )
    )

    st.markdown(
        f"""<div class="gf-card" style="border-top: 3px solid #a855f7; display:flex; flex-direction:column; justify-content:space-between; min-height:480px;">
<div>
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
<span style="font-size:16px; font-weight:800; color:#ffffff; letter-spacing:0.02em;">GBPUSD</span>
<span style="background:{gbp_bg_b}; color:{gbp_col_b}; border:1px solid {gbp_border_b}; padding:5px 12px; border-radius:20px; font-size:11px; font-weight:800; font-family:'JetBrains Mono';">{gbp_txt}</span>
</div>
<div style="font-size:24px; font-weight:800; color:#ffffff; font-family:'JetBrains Mono'; margin:6px 0 2px 0;">{gbp_p:.4f}</div>
<div style="font-size:11px; color:{"#10b981" if gbp_c >= 0 else "#ef4444"}; font-family:'JetBrains Mono'; margin-bottom:14px; font-weight:700;">{gbp_c:+.2f}% dzisiaj</div>
<div style="font-size:10px; color:#64748b; font-weight:800; letter-spacing:0.06em; text-transform:uppercase; margin-bottom:8px;">DEPESZE GOOGLE FINANCE:</div>
{gbp_news_html}
</div>
<div style="background: linear-gradient(180deg, rgba(168, 85, 247, 0.14) 0%, rgba(20, 12, 30, 0.95) 100%); border: 1px solid rgba(168, 85, 247, 0.45); border-left: 5px solid #a855f7; border-radius: 8px; padding: 14px 16px; margin-top: 16px;">
<div style="color:#c084fc; font-size:12px; font-weight:800; text-transform:uppercase; margin-bottom:6px;">⚡ C.E.T. PLAYBOOK</div>
<div style="color:#ffffff; font-size:13px; font-weight:700; line-height:1.4;">Zarządzanie pozycją w oparciu o aktualne zmienne makro.</div>
</div>
</div>""",
        unsafe_allow_html=True,
    )

  st.markdown("---")
  st.subheader("⚡ Głęboki Audyt AI (Gemini)")
  if st.button(
      "URUCHOM ANALIZĘ DEPESZ GOOGLE FINANCE PRZEZ AI", type="primary"
  ):
    ai_model, model_name = get_gemini_model()
    if ai_model:
      with st.spinner(f"Gemini ({model_name}) analizuje depesze z Google Finance..."):
        try:
          eur_text = "\n".join(
              [f"- {i['title']} ({i['source']})" for i in gf_eur]
          )
          gold_text = "\n".join(
              [f"- {i['title']} ({i['source']})" for i in gf_gold]
          )
          gbp_text = "\n".join(
              [f"- {i['title']} ({i['source']})" for i in gf_gbp]
          )

          prompt_gf = f"""
                    Oceń wpływ tych depesz rynkowych z Google Finance na sesję:
                    EURUSD: {eur_text}
                    ZŁOTO: {gold_text}
                    GBPUSD: {gbp_text}
                    Przygotuj werdykt: sentyment, siła dolara DXY oraz pułapki na detalistów dla każdego z 3 aktywów.
                    """
          res_gf = ai_model.generate_content(prompt_gf)
          st.session_state["macro_digest"] = res_gf.text
          st.session_state["macro_model_name"] = model_name
        except Exception as e:
          st.error(f"Błąd silnika Gemini: {e}")
    else:
      st.error("Brak klucza API w sekretach Streamlit Cloud.")

  if st.session_state.get("macro_digest"):
    st.markdown(
        f"""<div style="background: rgba(9, 11, 20, 0.95); border: 1px solid rgba(255, 255, 255, 0.08); border-top: 2px solid #38bdf8; border-radius: 8px; padding: 22px; margin-top: 18px;">
        <span style="font-size:11px; font-weight:800; color:#38bdf8; text-transform:uppercase;">AI MACRO PULSE SUMMARY</span>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(st.session_state["macro_digest"])
    st.markdown("</div>", unsafe_allow_html=True)

# ==============================================================================
# MODUŁ 4: INSPEKTOR WIZJI AI
# ==============================================================================
elif menu == "👁️ Inspektor wykresów wizji AI":
  st.markdown(
      """<div class="hero-report-card">
<span style="color:#38bdf8; font-size:11px; font-weight:800; letter-spacing:1px; text-transform:uppercase;">● MULTIMODAL COMPUTER VISION ENGINE</span>
<h1 style="color:#ffffff; margin: 4px 0 8px 0; font-size:26px;">AI Vision Chart Inspector</h1>
<p style="color:#94a3b8; font-size:13px; margin:0;">Wgraj zrzut ekranu wykresu giełdowego do bezpośredniej weryfikacji przez AI.</p>
</div>""",
      unsafe_allow_html=True,
  )

  v_c1, v_c2 = st.columns([1, 1])
  with v_c1:
    uploaded_chart = st.file_uploader(
        "Załącz zrzut ekranu wykresu",
        type=["png", "jpg", "jpeg", "webp"],
        key="vision_uploader",
    )
    v_asset = st.selectbox(
        "Analizowany Instrument",
        ["EURUSD", "GBPUSD", "XAUUSD (Złoto)", "NQ100", "Inny"],
    )
    v_intent = st.selectbox(
        "Planowany Kierunek", ["LONG 🟢", "SHORT 🔴", "Ocena neutralna"]
    )
    v_context = st.text_input("Dodatkowy kontekst sesji (opcjonalnie)")

  with v_c2:
    if uploaded_chart is not None:
      pil_img = Image.open(uploaded_chart)
      st.image(pil_img, caption="Wgrany wykres", use_container_width=True)

  if uploaded_chart is not None:
    if st.button("⚡ PRZESKANUJ STRUKTURĘ WYKRESU (VISION SCAN)", type="primary"):
      ai_model, model_name = get_gemini_model()
      if ai_model:
        with st.spinner(
            f"AI Vision ({model_name}) analizuje geometrię świec i płynność..."
        ):
          try:
            prompt_v = (
                f"Przeanalizuj zrzut wykresu dla {v_asset} pod kątem wejścia w"
                f" {v_intent}. Zwróć uwagę na zamknięcie korpusem po sweepie,"
                " pułapki D1 HTF i poziomy inwalidacji."
            )
            res_v = ai_model.generate_content([prompt_v, pil_img])
            st.session_state["vision_report"] = res_v.text
            st.session_state["vision_model_name"] = model_name
          except Exception as e:
            st.error(f"Błąd analizy: {e}")
      else:
        st.error("Brak klucza API w sekretach Streamlit Cloud.")

  if st.session_state.get("vision_report"):
    st.markdown("---")
    st.markdown(
        f"""<div class="hero-report-card">
        <h3 style="color:#38bdf8; margin:0 0 10px 0;">VISION AUDIT VERDICT</h3>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(st.session_state["vision_report"])
    st.markdown("</div>", unsafe_allow_html=True)

# ==============================================================================
# MODUŁ 5: DZIENNIK HANDLOWY (Z NOTATKAMI, SCREENAMI I EDYCJĄ)
# ==============================================================================
elif menu == "Dziennik handlowy":
  st.title("📖 Tactical Trading Journal & Multi-Chart Vault")
  st.caption(
      "Ewidencja pozycji C.E.T., podgląd notatek, galeria screenów oraz"
      " edycja/korekta błędów"
  )

  tab1, tab2 = st.tabs([
      "➕ Dodaj nową pozycję",
      "📜 Historia, Notatki & Edycja (Vault)",
  ])

  with tab1:
    with st.form("new_trade_form", clear_on_submit=True):
      tc1, tc2, tc3 = st.columns(3)
      with tc1:
        t_date = st.date_input("Data transakcji", datetime.now())
        t_inst = st.selectbox(
            "Instrument", ["EURUSD", "GBPUSD", "XAUUSD", "NQ100"]
        )
        t_side = st.selectbox("Kierunek", ["LONG 🟢", "SHORT 🔴"])
      with tc2:
        t_model = st.selectbox(
            "Model Wejścia",
            [
                "LDN Type 1 (Sweep Azji)",
                "LDN Type 3 (Continuation)",
                "NY Continuation",
                "NY Reversal",
                "NY Inversion",
            ],
        )
        t_quality = st.selectbox(
            "Klasa Setupu",
            [
                "A+ Quality (Wszystkie konfluencje)",
                "B Quality (Częściowe)",
                "C Quality",
            ],
        )
      with tc3:
        t_status = st.selectbox(
            "Wynik", ["WIN", "LOSS", "BE (Break Even)", "TRAIL STOP"]
        )
        t_rr = st.number_input(
            "Wynik transakcji w R",
            value=1.5,
            step=0.1,
            min_value=-50.0,
            max_value=100.0,
        )

      uploaded_imgs = st.file_uploader(
          "Załącz zrzuty ekranu wykresu",
          type=["png", "jpg", "jpeg", "webp"],
          accept_multiple_files=True,
      )
      t_notes = st.text_area("Notatki z egzekucji")

      save_btn = st.form_submit_button("ZAPISZ TRANSAKCJĘ DO BAZY")
      if save_btn:
        saved_paths = []
        trade_id = int(datetime.now().timestamp())
        if uploaded_imgs:
          for idx, img in enumerate(uploaded_imgs):
            ext = img.name.split(".")[-1]
            img_path = os.path.join(IMAGES_DIR, f"trade_{trade_id}_{idx}.{ext}")
            with open(img_path, "wb") as f:
              f.write(img.getbuffer())
            saved_paths.append(img_path)

        img_string = ";".join(saved_paths)
        r_final = (
            -abs(t_rr)
            if t_status == "LOSS"
            else (0.0 if t_status == "BE (Break Even)" else abs(t_rr))
        )

        new_row = {
            "id": trade_id,
            "data": str(t_date),
            "instrument": t_inst,
            "kierunek": t_side,
            "model": t_model,
            "wynik_r": r_final,
            "status": t_status,
            "jakosc": t_quality,
            "notatki": t_notes,
            "zdjecie": img_string,
        }
        df_curr = pd.read_csv(JOURNAL_FILE)
        df_upd = pd.concat(
            [df_curr, pd.DataFrame([new_row])], ignore_index=True
        )
        df_upd.to_csv(JOURNAL_FILE, index=False)
        st.success("Transakcja zapisana pomyślnie!")
        st.rerun()

  with tab2:
    st.subheader("📜 Twoje Transakcje, Notatki i Zrzuty Ekranu")
    df_trades = pd.read_csv(JOURNAL_FILE)

    if df_trades.empty:
      st.info("Brak zapisanych pozycji w bazie.")
    else:
      pola = [
          c
          for c in [
              "data",
              "instrument",
              "kierunek",
              "model",
              "status",
              "wynik_r",
              "jakosc",
          ]
          if c in df_trades.columns
      ]
      st.dataframe(df_trades[pola], use_container_width=True)
      st.markdown("---")
      st.write("### 🔍 Szczegóły transakcji, notatki i miniatury screenów:")

      for idx, row in df_trades.iloc[::-1].iterrows():
        trade_id = row["id"]
        with st.expander(
            f"{row['data']} | {row['instrument']} {row['kierunek']} — Wynik:"
            f" {row['wynik_r']} R ({row['status']})"
        ):
          c_d1, c_d2 = st.columns([1, 2])
          with c_d1:
            st.write(f"**Model:** {row['model']}")
            st.write(f"**Klasa jakości:** {row['jakosc']}")
            st.write(f"**Notatki:** {row['notatki']}")

          with c_d2:
            raw_imgs = (
                str(row["zdjecie"]) if pd.notna(row["zdjecie"]) else ""
            )
            img_list = [
                p.strip()
                for p in raw_imgs.split(";")
                if p.strip() and os.path.exists(p.strip())
            ]
            if img_list:
              st.write("**Zrzuty ekranu:**")
              grid_cols = st.columns(min(len(img_list), 3))
              for i, p in enumerate(img_list):
                with grid_cols[i % 3]:
                  st.image(p, caption=f"Screen #{i+1}", use_container_width=True)
            else:
              st.caption("Brak załączonych zrzutów ekranu dla tej pozycji.")

          with st.form(key=f"edit_form_{trade_id}"):
            st.markdown(f"**✏️ Korekta / Edycja wpisu (ID: {trade_id})**")
            e_status = st.selectbox(
                "Zmień wynik",
                ["WIN", "LOSS", "BE (Break Even)", "TRAIL STOP"],
                index=(
                    ["WIN", "LOSS", "BE (Break Even)", "TRAIL STOP"].index(
                        row["status"]
                    )
                    if row["status"]
                    in ["WIN", "LOSS", "BE (Break Even)", "TRAIL STOP"]
                    else 0
                ),
                key=f"status_{trade_id}",
            )
            e_rr = st.number_input(
                "Zmień wynik w R",
                value=float(row["wynik_r"]),
                step=0.1,
                key=f"rr_{trade_id}",
            )
            e_notes = st.text_area(
                "Edytuj notatki",
                value=str(row["notatki"]),
                key=f"notes_{trade_id}",
            )
            new_img = st.file_uploader(
                "Dołącz dodatkowy zrzut ekranu",
                type=["png", "jpg", "jpeg", "webp"],
                key=f"img_{trade_id}",
            )

            col_upd, col_del = st.columns(2)
            with col_upd:
              update_btn = st.form_submit_button("ZAPISZ ZMIANY W WPISIE")
            with col_del:
              delete_btn = st.form_submit_button(
                  "USUŃ TEN WPIS", type="secondary"
              )

            if update_btn:
              stare_z = (
                  str(row["zdjecie"])
                  if pd.notna(row["zdjecie"]) and row["zdjecie"] != "nan"
                  else ""
              )
              lista_z = [p.strip() for p in stare_z.split(";") if p.strip()]
              if new_img is not None:
                ext = new_img.name.split(".")[-1]
                p_nowa = os.path.join(
                    IMAGES_DIR, f"trade_{trade_id}_add_{int(time.time())}.{ext}"
                )
                with open(p_nowa, "wb") as f:
                  f.write(new_img.getbuffer())
                lista_z.append(p_nowa)

              df_trades.loc[df_trades["id"] == trade_id, "status"] = e_status
              df_trades.loc[df_trades["id"] == trade_id, "wynik_r"] = e_rr
              df_trades.loc[df_trades["id"] == trade_id, "notatki"] = e_notes
              df_trades.loc[df_trades["id"] == trade_id, "zdjecie"] = ";".join(
                  lista_z
              )
              df_trades.to_csv(JOURNAL_FILE, index=False)
              st.success("Zaktualizowano pomyślnie!")
              st.rerun()

            if delete_btn:
              df_trades = df_trades[df_trades["id"] != trade_id]
              df_trades.to_csv(JOURNAL_FILE, index=False)
              st.warning("Usunięto transakcję.")
              st.rerun()

# ==============================================================================
# POZOSTAŁE MODUŁY
# ==============================================================================
elif menu == "Krzywa kapitału (Netto R)":
  st.title("Krzywa kapitału (Netto R)")
elif menu == "Kursy na dziś":
  st.title("Kursy na dziś")
elif menu == "Kalendarz Forex Factory":
  st.title("Kalendarz Forex Factory")
elif menu == "Wiadomości na żywo i CNBC":
  st.title("Wiadomości na żywo i CNBC")
