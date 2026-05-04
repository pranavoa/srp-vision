"""Theme CSS — light + dark, plus shared rules.

Apply via ``inject_theme(dark=...)`` from ``app.py``.
"""

from __future__ import annotations

import streamlit as st


CSS_BASE = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

@font-face {
    font-family: 'Ubuntu Sans Mono';
    src: url('app/static/fonts/UbuntuSansMono-VariableFont_wght.ttf') format('truetype');
    font-weight: 100 900;
    font-style: normal;
    font-display: swap;
}
@font-face {
    font-family: 'Ubuntu Sans Mono';
    src: url('app/static/fonts/UbuntuSansMono-Italic-VariableFont_wght.ttf') format('truetype');
    font-weight: 100 900;
    font-style: italic;
    font-display: swap;
}

/* ── Reset + base ───────────────────────────────────── */
html, body, .stApp, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    font-feature-settings: 'cv11', 'ss01', 'ss03';
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    text-rendering: optimizeLegibility;
}
h1, h2, h3, h4, h5, h6 {
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    letter-spacing: -0.02em;
    line-height: 1.18;
}
code, pre, .stCode, [data-testid="stCodeBlock"], .mono {
    font-family: 'Ubuntu Sans Mono', ui-monospace, monospace !important;
    font-size: 12.5px !important;
    letter-spacing: -0.005em;
}

.block-container {
    padding-top: 1.6rem !important;
    padding-bottom: 3rem !important;
    max-width: 100% !important;
}

#MainMenu, footer { visibility: hidden; }

/* Sidebar expand control — keep visible across versions */
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapseButton"],
button[kind="header"] {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    z-index: 9999 !important;
}
[data-testid="stHeader"] {
    visibility: visible !important;
    background: transparent !important;
}

/* ── App header band ────────────────────────────────── */
.app-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 22px 28px;
    border-radius: 16px;
    margin-bottom: 24px;
    position: relative;
    overflow: hidden;
    transition: all 240ms cubic-bezier(0.16, 1, 0.3, 1);
}
.app-header .brand {
    display: flex;
    align-items: center;
    gap: 14px;
}
.app-header .brand-icon {
    width: 30px;
    height: 30px;
    flex-shrink: 0;
    opacity: 0.95;
    color: currentColor;
}
.app-header .app-title {
    font-size: 22px;
    font-weight: 700;
    letter-spacing: -0.025em;
    margin-bottom: 5px;
    line-height: 1.1;
}
.app-header .app-sub {
    font-family: 'Ubuntu Sans Mono', monospace;
    font-size: 12.5px;
    letter-spacing: -0.005em;
}
.app-header .app-meta {
    font-family: 'Ubuntu Sans Mono', monospace;
    font-size: 10.5px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    opacity: 0.65;
}

/* ── KPI metric cards ───────────────────────────────── */
[data-testid="stMetric"] {
    border-radius: 12px;
    padding: 14px 18px;
    transition: all 220ms cubic-bezier(0.16, 1, 0.3, 1);
}
[data-testid="stMetric"]:hover { transform: translateY(-1px); }
[data-testid="stMetricLabel"] {
    font-size: 11px !important;
    font-weight: 500 !important;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}
[data-testid="stMetricValue"] {
    font-family: 'Ubuntu Sans Mono', monospace !important;
    font-size: 24px !important;
    font-weight: 600 !important;
    letter-spacing: -0.02em;
    line-height: 1.15;
}

/* ── Sidebar ─────────────────────────────────────────── */
[data-testid="stSidebar"] > div { padding-top: 1.5rem; }
[data-testid="stSidebar"] h2 {
    font-size: 11px !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-top: 1.4rem !important;
    margin-bottom: 0.5rem !important;
}

/* ── Buttons ─────────────────────────────────────────── */
.stButton > button {
    border-radius: 9px !important;
    font-weight: 500 !important;
    letter-spacing: -0.005em;
    transition: all 180ms cubic-bezier(0.16, 1, 0.3, 1);
}
.stButton > button[kind="primary"] { font-weight: 600 !important; }

/* ── Inputs ──────────────────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-baseweb="select"] > div,
[data-baseweb="input"] > div {
    border-radius: 9px !important;
    transition: border-color 180ms cubic-bezier(0.16, 1, 0.3, 1),
                box-shadow 180ms cubic-bezier(0.16, 1, 0.3, 1);
}

/* ── Dataframe ───────────────────────────────────────── */
[data-testid="stDataFrame"] {
    font-family: 'Inter', sans-serif !important;
    border-radius: 12px !important;
    overflow: hidden !important;
    font-size: 13px;
}
[data-testid="stDataFrame"] thead tr th {
    font-size: 10.5px !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}
[data-testid="stDataFrame"] tbody tr {
    transition: background 160ms cubic-bezier(0.16, 1, 0.3, 1);
}

/* ── Tabs ────────────────────────────────────────────── */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    gap: 4px;
    padding: 4px;
    border-radius: 10px;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 500;
    letter-spacing: -0.005em;
    transition: all 180ms cubic-bezier(0.16, 1, 0.3, 1);
}

/* ── Segmented control ───────────────────────────────── */
[data-testid="stSegmentedControl"] {
    padding: 3px;
    border-radius: 10px;
}
[data-testid="stSegmentedControl"] label {
    font-size: 13px;
    font-weight: 500;
    letter-spacing: -0.005em;
    border-radius: 7px !important;
    transition: all 160ms cubic-bezier(0.16, 1, 0.3, 1);
}

/* ── Expanders ───────────────────────────────────────── */
[data-testid="stExpander"] {
    border-radius: 10px !important;
    overflow: hidden;
    margin-bottom: 6px !important;
    transition: border-color 180ms cubic-bezier(0.16, 1, 0.3, 1);
}
[data-testid="stExpander"] summary {
    font-size: 13px !important;
    font-weight: 500 !important;
    letter-spacing: -0.005em;
    padding: 11px 14px !important;
}

/* ── Sliders ─────────────────────────────────────────── */
[data-testid="stSlider"] [role="slider"] {
    transition: box-shadow 200ms cubic-bezier(0.16, 1, 0.3, 1);
}

/* ── Captions ────────────────────────────────────────── */
.stCaption, [data-testid="stCaptionContainer"] {
    font-size: 12px !important;
    letter-spacing: -0.005em;
}

/* ── Empty state ─────────────────────────────────────── */
.empty-card {
    border-radius: 16px;
    padding: 64px 32px;
    text-align: center;
    margin-top: 48px;
    position: relative;
    overflow: hidden;
}
.empty-card .empty-icon {
    font-family: 'Ubuntu Sans Mono', monospace;
    font-size: 40px;
    font-weight: 200;
    letter-spacing: -0.04em;
    margin-bottom: 18px;
    opacity: 0.55;
    line-height: 1;
}
.empty-card .empty-title {
    font-size: 17px;
    font-weight: 600;
    margin-bottom: 8px;
    letter-spacing: -0.01em;
}
.empty-card .empty-body {
    font-size: 13.5px;
    max-width: 480px;
    margin: 0 auto;
    line-height: 1.6;
}

/* ── Toasts ──────────────────────────────────────────── */
[data-testid="stToast"] {
    border-radius: 10px !important;
    font-size: 13px !important;
    backdrop-filter: blur(20px);
}
"""

# ── Light theme — Notion-inspired (warm off-white, soft contrast, monochrome accent)
LIGHT_THEME = """
.stApp { background: #F7F7F5 !important; color: #1F1E1B; }
h1, h2, h3, h4 { color: #1F1E1B !important; }

.app-header {
    background: #FFFFFF;
    border: 1px solid #E8E8E4;
}
.app-header::after {
    content: "";
    position: absolute;
    left: 0; right: 0; bottom: 0; height: 2px;
    background: linear-gradient(90deg, transparent, #0A66E8 50%, transparent);
    opacity: 0.18;
}
.app-header .app-title { color: #1F1E1B; }
.app-header .app-sub { color: #6F6E69; }
.app-header .app-meta { color: #9B9A93; }

[data-testid="stMetric"] {
    background: #FFFFFF;
    border: 1px solid #E8E8E4;
    box-shadow: 0 1px 0 rgba(15,15,15,0.02);
}
[data-testid="stMetric"]:hover { border-color: #DCDCD7; }
[data-testid="stMetricLabel"] { color: #6F6E69 !important; }
[data-testid="stMetricValue"] { color: #1F1E1B !important; }

[data-testid="stSidebar"] {
    background: #FFFFFF !important;
    border-right: 1px solid #E8E8E4;
}
[data-testid="stSidebar"] h2 { color: #6F6E69 !important; }
[data-testid="stSidebar"] hr { border-color: #EFEFEC; margin: 0.6rem 0; }

.stButton > button[kind="primary"] {
    background: #1F1E1B;
    color: #FFFFFF;
    border: 1px solid #1F1E1B;
}
.stButton > button[kind="primary"]:hover {
    background: #000000;
    border-color: #000000;
    transform: translateY(-1px);
    box-shadow: 0 2px 10px rgba(0,0,0,0.12);
}
.stButton > button:not([kind="primary"]) {
    background: #FFFFFF;
    color: #1F1E1B;
    border: 1px solid #E8E8E4;
}
.stButton > button:not([kind="primary"]):hover {
    background: #FAFAFA;
    border-color: #D5D5D0;
}

[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-baseweb="select"] > div {
    background: #FFFFFF !important;
    color: #1F1E1B !important;
    border: 1px solid #E8E8E4 !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stNumberInput"] input:focus,
[data-baseweb="select"] > div:focus-within {
    border-color: #0A66E8 !important;
    box-shadow: 0 0 0 3px rgba(10,102,232,0.10) !important;
}
[data-baseweb="select"] svg { fill: #6F6E69 !important; }

[data-testid="stDataFrame"] {
    background: #FFFFFF;
    border: 1px solid #E8E8E4;
}
[data-testid="stDataFrame"] thead tr th {
    background: #FAFAFA !important;
    color: #6F6E69 !important;
    border-bottom: 1px solid #E8E8E4 !important;
}
[data-testid="stDataFrame"] tbody tr td {
    color: #1F1E1B !important;
    border-bottom: 1px solid #F0F0EC !important;
}
[data-testid="stDataFrame"] tbody tr:hover td { background: #FAFAFA !important; }

[data-testid="stTabs"] [data-baseweb="tab-list"] {
    background: #F1F1ED;
    border: 1px solid #E8E8E4;
}
[data-testid="stTabs"] [data-baseweb="tab"] { color: #6F6E69; }
[data-testid="stTabs"] [data-baseweb="tab"]:hover {
    background: #E8E8E4;
    color: #1F1E1B;
}
[data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] {
    background: #FFFFFF !important;
    color: #1F1E1B !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

[data-testid="stSegmentedControl"] {
    background: #F1F1ED;
    border: 1px solid #E8E8E4;
}
[data-testid="stSegmentedControl"] label[aria-checked="true"] {
    background: #FFFFFF !important;
    color: #1F1E1B !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

[data-testid="stExpander"] {
    background: #FFFFFF;
    border: 1px solid #E8E8E4 !important;
}
[data-testid="stExpander"] summary { color: #1F1E1B !important; }
[data-testid="stExpander"] summary:hover { background: #FAFAFA; }

[data-testid="stSlider"] [role="slider"] {
    background: #1F1E1B !important;
    border-color: #1F1E1B !important;
}
[data-testid="stSlider"] [role="slider"]:focus {
    box-shadow: 0 0 0 4px rgba(10,102,232,0.16) !important;
}

.stCaption, [data-testid="stCaptionContainer"] { color: #6F6E69 !important; }

.empty-card {
    background: #FFFFFF;
    border: 1px solid #E8E8E4;
    color: #6F6E69;
}
.empty-card .empty-title { color: #1F1E1B; }
.empty-card .empty-icon { color: #9B9A93; }

[data-testid="stSidebarCollapsedControl"] button {
    background: #FFFFFF !important;
    color: #1F1E1B !important;
    border: 1px solid #E8E8E4 !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04) !important;
}
[data-testid="stSidebarCollapsedControl"] button:hover {
    background: #FAFAFA !important;
    border-color: #D5D5D0 !important;
}
[data-testid="stSidebarCollapsedControl"] svg { color: #1F1E1B !important; fill: #1F1E1B !important; }

[data-testid="stToast"] {
    background: #FFFFFF !important;
    border: 1px solid #E8E8E4 !important;
    color: #1F1E1B !important;
}
"""

# ── Dark theme — Apple-inspired (rich black, glass surfaces, system blue glow)
DARK_THEME = """
.stApp {
    background:
      radial-gradient(ellipse 70% 45% at 18% 0%, rgba(10,132,255,0.09), transparent 60%),
      radial-gradient(ellipse 55% 40% at 82% 100%, rgba(94,92,230,0.07), transparent 60%),
      #0A0A0B !important;
    color: #F5F5F7;
}
h1, h2, h3, h4 { color: #F5F5F7 !important; }

.app-header {
    background: linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.02) 100%);
    border: 1px solid rgba(255,255,255,0.07);
    backdrop-filter: blur(24px);
    -webkit-backdrop-filter: blur(24px);
    box-shadow:
      0 8px 32px -8px rgba(10,132,255,0.18),
      inset 0 1px 0 rgba(255,255,255,0.05);
}
.app-header::before {
    content: "";
    position: absolute;
    inset: 0;
    border-radius: 16px;
    padding: 1px;
    background: linear-gradient(135deg, rgba(10,132,255,0.5), rgba(94,92,230,0.25), transparent 70%);
    -webkit-mask:
      linear-gradient(#fff 0 0) content-box,
      linear-gradient(#fff 0 0);
    -webkit-mask-composite: xor;
    mask-composite: exclude;
    pointer-events: none;
    opacity: 0.55;
}
.app-header .app-title { color: #F5F5F7; }
.app-header .app-sub { color: #A1A1A6; }
.app-header .app-meta { color: #6E6E73; }

[data-testid="stMetric"] {
    background: linear-gradient(180deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.02) 100%);
    border: 1px solid rgba(255,255,255,0.06);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
}
[data-testid="stMetric"]:hover {
    border-color: rgba(10,132,255,0.28);
    background: linear-gradient(180deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.03) 100%);
}
[data-testid="stMetricLabel"] { color: #A1A1A6 !important; }
[data-testid="stMetricValue"] {
    color: #F5F5F7 !important;
    text-shadow: 0 0 24px rgba(10,132,255,0.14);
}

[data-testid="stSidebar"] {
    background: rgba(15,15,17,0.92) !important;
    backdrop-filter: blur(40px);
    -webkit-backdrop-filter: blur(40px);
    border-right: 1px solid rgba(255,255,255,0.06);
}
[data-testid="stSidebar"] h2 { color: #A1A1A6 !important; }
[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.06); margin: 0.6rem 0; }
[data-testid="stSidebar"] label, [data-testid="stSidebar"] p { color: #D2D2D7; }

.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #0A84FF 0%, #5E5CE6 100%);
    color: #FFFFFF;
    border: 1px solid rgba(255,255,255,0.12);
    box-shadow:
      0 4px 14px rgba(10,132,255,0.36),
      inset 0 1px 0 rgba(255,255,255,0.18);
}
.stButton > button[kind="primary"]:hover {
    transform: translateY(-1px);
    box-shadow:
      0 6px 22px rgba(10,132,255,0.5),
      inset 0 1px 0 rgba(255,255,255,0.22);
}
.stButton > button:not([kind="primary"]) {
    background: rgba(255,255,255,0.05);
    color: #F5F5F7;
    border: 1px solid rgba(255,255,255,0.08);
}
.stButton > button:not([kind="primary"]):hover {
    background: rgba(255,255,255,0.08);
    border-color: rgba(10,132,255,0.4);
}

[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-baseweb="select"] > div,
[data-baseweb="input"] > div {
    background: rgba(255,255,255,0.04) !important;
    color: #F5F5F7 !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stNumberInput"] input:focus,
[data-baseweb="select"] > div:focus-within {
    border-color: rgba(10,132,255,0.55) !important;
    box-shadow: 0 0 0 3px rgba(10,132,255,0.16) !important;
}
[data-baseweb="select"] svg { fill: #A1A1A6 !important; }

[data-testid="stDataFrame"] {
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.06);
    backdrop-filter: blur(10px);
}
[data-testid="stDataFrame"] thead tr th {
    background: rgba(255,255,255,0.04) !important;
    color: #A1A1A6 !important;
    border-bottom: 1px solid rgba(255,255,255,0.07) !important;
}
[data-testid="stDataFrame"] tbody tr td {
    color: #F5F5F7 !important;
    background: transparent !important;
    border-bottom: 1px solid rgba(255,255,255,0.04) !important;
}
[data-testid="stDataFrame"] tbody tr:hover td {
    background: rgba(10,132,255,0.06) !important;
}

[data-testid="stTabs"] [data-baseweb="tab-list"] {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
}
[data-testid="stTabs"] [data-baseweb="tab"] { color: #A1A1A6; }
[data-testid="stTabs"] [data-baseweb="tab"]:hover {
    background: rgba(255,255,255,0.05);
    color: #F5F5F7;
}
[data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] {
    background: rgba(10,132,255,0.18);
    color: #F5F5F7;
    box-shadow: inset 0 0 0 1px rgba(10,132,255,0.32);
}

[data-testid="stSegmentedControl"] {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
}
[data-testid="stSegmentedControl"] label { color: #A1A1A6; }
[data-testid="stSegmentedControl"] label[aria-checked="true"] {
    background: rgba(10,132,255,0.20) !important;
    color: #F5F5F7 !important;
    box-shadow: inset 0 0 0 1px rgba(10,132,255,0.36);
}

[data-testid="stExpander"] {
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.06) !important;
}
[data-testid="stExpander"] summary { color: #D2D2D7 !important; }
[data-testid="stExpander"] summary:hover { background: rgba(255,255,255,0.04); }

[data-testid="stSlider"] [role="slider"] {
    background: linear-gradient(135deg, #0A84FF, #5E5CE6) !important;
    border-color: rgba(255,255,255,0.14) !important;
    box-shadow: 0 0 12px rgba(10,132,255,0.28);
}
[data-testid="stSlider"] [role="slider"]:focus {
    box-shadow: 0 0 0 4px rgba(10,132,255,0.20), 0 0 16px rgba(10,132,255,0.4) !important;
}

.stCaption, [data-testid="stCaptionContainer"] { color: #A1A1A6 !important; }

.empty-card {
    background: linear-gradient(180deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.02) 100%);
    border: 1px solid rgba(255,255,255,0.08);
    color: #A1A1A6;
    backdrop-filter: blur(20px);
}
.empty-card::before {
    content: "";
    position: absolute;
    top: -50%; left: -50%;
    width: 200%; height: 200%;
    background: radial-gradient(circle, rgba(10,132,255,0.06) 0%, transparent 50%);
    pointer-events: none;
}
.empty-card .empty-title { color: #F5F5F7; }
.empty-card .empty-icon { color: #5E5CE6; }

[data-testid="stSidebarCollapsedControl"] button {
    background: rgba(255,255,255,0.06) !important;
    color: #F5F5F7 !important;
    border: 1px solid rgba(255,255,255,0.10) !important;
    backdrop-filter: blur(10px);
}
[data-testid="stSidebarCollapsedControl"] button:hover {
    background: rgba(255,255,255,0.10) !important;
    border-color: rgba(10,132,255,0.5) !important;
}
[data-testid="stSidebarCollapsedControl"] svg { color: #F5F5F7 !important; fill: #F5F5F7 !important; }

[data-testid="stToast"] {
    background: rgba(20,20,22,0.95) !important;
    border: 1px solid rgba(255,255,255,0.10) !important;
    color: #F5F5F7 !important;
    backdrop-filter: blur(20px);
}
"""



def inject_theme(dark: bool) -> None:
    """Inject the active theme's CSS into the current Streamlit page."""
    st.markdown(
        "<style>" + CSS_BASE + (DARK_THEME if dark else LIGHT_THEME) + "</style>",
        unsafe_allow_html=True,
    )
