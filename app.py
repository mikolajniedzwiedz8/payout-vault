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

# --- PANEL BOCZNY ---
if "current_tab" not in st.session_state:
  st.session_state["current_tab"] = "Dziennik handlowy"

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
# MODUŁY APLIKACJI
# ==============================================================================
if menu == "Taktyczny terminal na żywo i interfejs HUD mapy":
  st.title("🖥️ Taktyczny terminal na żywo i interfejs HUD mapy")
  st.info(
      "Moduł terminala aktywny. Wybierz zakładkę w menu bocznym, aby przejść do"
      " edycji dziennika."
  )

elif menu == "Poranny raport i skanowanie dzienne":
  st.title("Morning Report & Directional Call")

elif menu == "🌐 Fundamental Pulse i strumień Google Finance":
  st.title("Fundamental Pulse & Google Finance Stream")

elif menu == "👁️ Inspektor wykresów wizji AI":
  st.title("AI Vision Chart Inspector")

# ==============================================================================
# MODUŁ: DZIENNIK HANDLOWY Z EDYCJĄ I DODAWANIEM SCREENÓW
# ==============================================================================
elif menu == "Dziennik handlowy":
  st.title("📖 Tactical Trading Journal & Multi-Chart Vault")
  st.caption(
      "Ewidencja pozycji C.E.T., dodawanie nowych, edycja błędów oraz zarządzanie"
      " zrzutami ekranu"
  )

  tab1, tab2, tab3 = st.tabs([
      "➕ Dodaj nową pozycję",
      "📜 Historia Transakcji & Przegląd",
      "✏️ Edycja / Usuwanie i Screeny",
  ])

  # --- ZAKŁADKA 1: DODAWANIE ---
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

  # --- ZAKŁADKA 2: HISTORIA ---
  with tab2:
    df_trades = pd.read_csv(JOURNAL_FILE)
    if df_trades.empty:
      st.info("Brak zapisanych pozycji w bazie.")
    else:
      st.dataframe(df_trades, use_container_width=True)

  # --- ZAKŁADKA 3: EDYCJA, KOREKTA I DODAWANIE SCREENÓW ---
  with tab3:
    st.subheader("✏️ Edytuj lub usuń wpis w dzienniku")
    df_trades = pd.read_csv(JOURNAL_FILE)

    if df_trades.empty:
      st.info("Brak pozycji do edycji.")
    else:
      # Tworzymy czytelną listę transakcji do wyboru
      df_trades["label"] = (
          df_trades["id"].astype(str)
          + " | "
          + df_trades["data"].astype(str)
          + " | "
          + df_trades["instrument"].astype(str)
          + " "
          + df_trades["kierunek"].astype(str)
          + " (Wynik: "
          + df_trades["wynik_r"].astype(str)
          + "R)"
      )
      wybrana_etykieta = st.selectbox(
          "Wybierz transakcję do korekty:", df_trades["label"].tolist()
      )

      if wybrana_etykieta:
        wybrany_id = int(wybrana_etykieta.split(" | ")[0])
        wiersz = df_trades[df_trades["id"] == wybrany_id].iloc[0]

        with st.form("edit_trade_form"):
          st.write(f"Edytujesz transakcję ID: {wybrany_id}")
          e_inst = st.text_input("Instrument", value=str(wiersz["instrument"]))
          e_side = st.selectbox(
              "Kierunek",
              ["LONG 🟢", "SHORT 🔴"],
              index=(
                  0
                  if "LONG" in str(wiersz["kierunek"])
                  else (1 if "SHORT" in str(wiersz["kierunek"]) else 0)
              ),
          )
          e_status = st.selectbox(
              "Wynik",
              ["WIN", "LOSS", "BE (Break Even)", "TRAIL STOP"],
              index=["WIN", "LOSS", "BE (Break Even)", "TRAIL STOP"].index(
                  wiersz["status"]
                  if wiersz["status"]
                  in ["WIN", "LOSS", "BE (Break Even)", "TRAIL STOP"]
                  else "WIN"
              ),
          )
          e_rr = st.number_input(
              "Wynik w R", value=float(wiersz["wynik_r"]), step=0.1
          )
          e_notes = st.text_area("Notatki", value=str(wiersz["notatki"]))

          new_extra_imgs = st.file_uploader(
              "Dołącz dodatkowe zrzuty ekranu",
              type=["png", "jpg", "jpeg", "webp"],
              accept_multiple_files=True,
          )

          col_save, col_del = st.columns(2)
          with col_save:
            update_btn = st.form_submit_button("ZAPISZ ZMIANY")
          with col_del:
            delete_btn = st.form_submit_button(
                "USUŃ TĘ TRANSAKCJĘ", type="secondary"
            )

          if update_btn:
            # Pobieramy stare ścieżki zdjęć
            stare_zdjecia = (
                str(wiersz["zdjecie"])
                if pd.notna(wiersz["zdjecie"]) and wiersz["zdjecie"] != "nan"
                else ""
            )
            nowe_sciezki = [
                p.strip() for p in stare_zdjecia.split(";") if p.strip()
            ]

            # Dodajemy nowe pliki, jeśli zostały wgrane
            if new_extra_imgs:
              for idx, img in enumerate(new_extra_imgs):
                ext = img.name.split(".")[-1]
                img_path = os.path.join(
                    IMAGES_DIR, f"trade_{wybrany_id}_add_{idx}.{ext}"
                )
                with open(img_path, "wb") as f:
                  f.write(img.getbuffer())
                nowe_sciezki.append(img_path)

            df_trades.loc[df_trades["id"] == wybrany_id, "instrument"] = e_inst
            df_trades.loc[df_trades["id"] == wybrany_id, "kierunek"] = e_side
            df_trades.loc[df_trades["id"] == wybrany_id, "status"] = e_status
            df_trades.loc[df_trades["id"] == wybrany_id, "wynik_r"] = e_rr
            df_trades.loc[df_trades["id"] == wybrany_id, "notatki"] = e_notes
            df_trades.loc[df_trades["id"] == wybrany_id, "zdjecie"] = ";".join(
                nowe_sciezki
            )

            # Usuwamy pomocniczą kolumnę 'label' przed zapisem do pliku CSV
            if "label" in df_trades.columns:
              df_trades = df_trades.drop(columns=["label"])

            df_trades.to_csv(JOURNAL_FILE, index=False)
            st.success("Transakcja została pomyślnie zaktualizowana!")
            st.rerun()

          if delete_btn:
            df_trades = df_trades[df_trades["id"] != wybrany_id]
            if "label" in df_trades.columns:
              df_trades = df_trades.drop(columns=["label"])
            df_trades.to_csv(JOURNAL_FILE, index=False)
            st.warning("Transakcja została trwale usunięta z bazy.")
            st.rerun()

elif menu == "Krzywa kapitału (Netto R)":
  st.title("Krzywa kapitału (Netto R)")
elif menu == "Kursy na dziś":
  st.title("Kursy na dziś")
elif menu == "Kalendarz Forex Factory":
  st.title("Kalendarz Forex Factory")
elif menu == "Wiadomości na żywo i CNBC":
  st.title("Wiadomości na żywo i CNBC")
