"""Presentation-only styles for the final Streamlit interface."""
import streamlit as st


def apply_style():
    st.markdown('''<style>
    .stApp {background:#f5f7fb;color:#172b45;color-scheme:light;}
    [data-testid="stHeader"] {background:#f5f7fb;}
    .block-container {max-width:1200px;padding-top:2.5rem;padding-bottom:3rem;}
    h1 {font-size:clamp(1.8rem,4vw,2.8rem)!important;letter-spacing:-.035em;line-height:1.15!important;}
    h2,h3 {color:#172b45;letter-spacing:-.02em;}
    p,label,[data-testid="stCaptionContainer"] {color:#42546b;}
    [data-testid="stVerticalBlockBorderWrapper"]>div {background:#fff;border-color:#dce3ed!important;border-radius:16px!important;}
    .hero-tag {color:#245bbb;font-size:.78rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;margin-bottom:.6rem;}
    .hero-meta {display:flex;flex-wrap:wrap;gap:.5rem;margin:1rem 0 1.5rem;}
    .hero-meta span {background:#e9effa;border:1px solid #d6e0f2;border-radius:30px;padding:.35rem .8rem;color:#284c81;font-size:.85rem;}
    .result-card {min-height:175px;border:1px solid #dce3ed;border-radius:16px;background:white;padding:1.5rem;margin:.5rem 0 1rem;}
    .result-card.risk {border-top:4px solid #b83f37;}
    .result-card.safe {border-top:4px solid #237554;}
    .card-label {font-size:.85rem;color:#506279;margin-bottom:.7rem;}
    .probability {font-size:3.1rem;font-weight:750;letter-spacing:-.05em;color:#172b45;line-height:1.15;}
    .classification {font-size:1.5rem;font-weight:700;line-height:1.35;color:#172b45;}
    .card-note {font-size:.85rem;color:#506279;margin-top:.65rem;}
    .state-title {font-size:1.05rem;font-weight:700;color:#245bbb;margin-bottom:1rem;}
    .state-row {display:flex;justify-content:space-between;gap:1rem;padding:.55rem 0;border-bottom:1px solid #edf0f5;font-size:.9rem;}
    .state-row:last-child {border:0;}
    .state-row b {color:#172b45;font-variant-numeric:tabular-nums;}
    [data-testid="stMetric"] {background:white;border:1px solid #dce3ed;border-radius:14px;padding:1rem;}
    [data-testid="stMetricValue"] {font-size:1.7rem;}
    [data-testid="stTextInput"] input {background:#fff;color:#172b45;border-radius:10px;}
    .stButton button,.stFormSubmitButton button {border-radius:10px;min-height:2.75rem;}
    [data-testid="stFormSubmitButton"] button p, button[kind="primary"] p {color:white!important;}
    [data-testid="stCaptionContainer"] p {color:#506279!important;}
    .stFormSubmitButton button * {color:#fff!important;}
    button[kind="primary"] {background:#245bbb;color:white;border:0;}
    [data-baseweb="tab-list"] {gap:1rem;flex-wrap:wrap;}
    [data-baseweb="tab"] {white-space:normal;color:#42546b;}
    [data-testid="stExpander"] {background:white;border-radius:12px;border-color:#dce3ed;}
    @media(max-width:700px) {
      .block-container {padding:1.25rem 1rem;}
      [data-testid="stHorizontalBlock"] {flex-wrap:wrap;}
      [data-testid="stHorizontalBlock"]>[data-testid="stColumn"] {width:100%!important;flex:1 1 100%!important;min-width:0!important;}
      .result-card {min-height:0;padding:1.2rem;}
      .probability {font-size:2.6rem;}
      [role="radiogroup"] {flex-wrap:wrap;gap:.6rem;}
    }
    </style>''', unsafe_allow_html=True)



