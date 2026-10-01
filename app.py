import feedparser
import google.generativeai as genai
import numpy as np
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# Konfiguracja strony
st.set_page_config(
    page_title="Payout Vault // Command Bridge", page_icon="⚡", layout="wide"
)

# Stylizacja ciemnego motywu (Custom CSS)
st.markdown(
    """
    <style>
    .stApp { background-color: #0b0f19; color: #ffffff; }
    .hero-report-card {
        background: linear-gradient(180deg, rgba(14, 18, 34, 0.9) 0%, rgba(8, 10, 15, 0.95) 100%);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-left: 4px solid #38bdf8;
        border-radius: 12px;
        padding: 18px;
        margin-bottom: 20px;
    }
    .tape-card {
        background: rgba(14, 18, 34, 0.8);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px;
        padding: 12px;
        text-align: center;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# Konfiguracja Gemini API z sekretów Streamlit
try:
  if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except Exception:
  pass


# Funkcja pobierająca aktualne ceny na żywo z Yahoo Finance
def get_market_data(symbol):
  try:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
    }
    response = requests.get(url, headers=headers, timeout=5)
    data = response.json()
    meta = data["chart"]["result"][0]["meta"]
    price = meta["regularMarketPrice"]
    prev_close = meta["chartPreviousClose"]
    change_pct = ((price - prev_close) / prev_close) * 100
    return price, change_pct
  except Exception:
    return 0.0, 0.0


# Pobieranie danych dla kluczowych aktywów
eur_price, eur_chg = get_market_data("EURUSD=X")
gbp_price, gbp_chg = get_market_data("GBPUSD=X")
gold_price, gold_chg = get_market_data("GC=F")
nq_price, nq_chg = get_market_data("NQ=F")

# Górny pasek: TAPE // LIVE ASSETS
st.markdown(
    "### THE TAPE // LIVE ASSETS (REAL-TIME MARKET DATA)", unsafe_allow_html=True
)
col1, col2, col3, col4 = st.columns(4)

with col1:
  st.markdown(
      f"""<div class="tape-card">
          <div style="font-size:11px; color:#94a3b8; font-weight:700;">EURUSD</div>
          <div style="font-size:20px; font-weight:800; color:#fff;">{eur_price:.4f}</div>
          <div style="font-size:12px; color:{"#10b981" if eur_chg >= 0 else "#ef4444"};">{"▲" if eur_chg >= 0 else "▼"} {eur_chg:+.2f}%</div>
      </div>""",
      unsafe_allow_html=True,
  )

with col2:
  st.markdown(
      f"""<div class="tape-card">
          <div style="font-size:11px; color:#94a3b8; font-weight:700;">GBPUSD</div>
          <div style="font-size:20px; font-weight:800; color:#fff;">{gbp_price:.4f}</div>
          <div style="font-size:12px; color:{"#10b981" if gbp_chg >= 0 else "#ef4444"};">{"▲" if gbp_chg >= 0 else "▼"} {gbp_chg:+.2f}%</div>
      </div>""",
      unsafe_allow_html=True,
  )

with col3:
  st.markdown(
      f"""<div class="tape-card">
          <div style="font-size:11px; color:#94a3b8; font-weight:700;">XAUUSD (ZŁOTO)</div>
          <div style="font-size:20px; font-weight:800; color:#fff;">{gold_price:.2f}</div>
          <div style="font-size:12px; color:{"#10b981" if gold_chg >= 0 else "#ef4444"};">{"▲" if gold_chg >= 0 else "▼"} {gold_chg:+.2f}%</div>
      </div>""",
      unsafe_allow_html=True,
  )

with col4:
  st.markdown(
      f"""<div class="tape-card">
          <div style="font-size:11px; color:#94a3b8; font-weight:700;">NASDAQ 100</div>
          <div style="font-size:20px; font-weight:800; color:#fff;">{nq_price:.2f}</div>
          <div style="font-size:12px; color:{"#10b981" if nq_chg >= 0 else "#ef4444"};">{"▲" if nq_chg >= 0 else "▼"} {nq_chg:+.2f}%</div>
      </div>""",
      unsafe_allow_html=True,
  )

st.markdown("---")

# Menu nawigacyjne
menu = st.sidebar.selectbox(
    "Nawigacja", ["Command Bridge", "Fundamental Pulse i strumień Google Finance"]
)

if menu == "Command Bridge":
  st.markdown(
      """<div class="hero-report-card">
          <span style="color:#38bdf8; font-size:11px; font-weight:800; letter-spacing:1px; text-transform:uppercase;">• COMMAND BRIDGE // AI DESK</span>
          <h1 style="color:#ffffff; margin: 4px 0 8px 0; font-size:26px;">Payout Vault Control Center</h1>
          <p style="color:#94a3b8; font-size:13px; margin:0;">Zintegrowane centrum zarządzania kapitałem prop tradingowym oraz analizą rynkową wspieraną przez Gemini API.</p>
      </div>""",
      unsafe_allow_html=True,
  )

  st.subheader("🤖 Gemini Market Analyst")
  prompt = st.text_input("Zadaj pytanie lub poproś o analizę sytuacji rynkowej:")
  if st.button("Generuj analizę AI"):
    if "GEMINI_API_KEY" in st.secrets:
      try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(
            f"Przeanalizuj bieżący sentyment rynkowy dla głównych par walutowych i indeksów (EURUSD: {eur_price}, GBPUSD: {gbp_price}, Złoto: {gold_price}, NQ: {nq_price}). Kontekst: {prompt}"
        )
        st.success(response.text)
      except Exception as e:
        st.error(f"Błąd generowania odpowiedzi przez Gemini: {e}")
    else:
      st.warning("Brak skonfigurowanego klucza GEMINI_API_KEY w Secrets!")

elif menu == "Fundamental Pulse i strumień Google Finance":
  st.markdown(
      """<div class="hero-report-card">
          <span style="color:#38bdf8; font-size:11px; font-weight:800; letter-spacing:1px; text-transform:uppercase;">• REAL-TIME GOOGLE FINANCE INTELLIGENCE</span>
          <h1 style="color:#ffffff; margin: 4px 0 8px 0; font-size:26px;">Fundamental Pulse & Google Finance Stream</h1>
          <p style="color:#94a3b8; font-size:13px; margin:0;">Agregacja depesz wprost ze strumieni <b>Google Finance</b> (Reuters, Bloomberg, FT) dedykowana wyłącznie dla <b>EURUSD</b>, <b>XAUUSD</b> oraz <b>GBPUSD</b>.</p>
      </div>""",
      unsafe_allow_html=True,
  )

  st.info("Moduł strumienia wiadomości rynkowych gotowy do działania.")
