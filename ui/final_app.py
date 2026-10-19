"""Final Ukrainian Streamlit research/demo system with frozen primary inference."""
from concurrent.futures import ThreadPoolExecutor
import logging
import streamlit as st
from ui.analysis import analyze_url
from ui.inference import infer
from ui.demo import EXAMPLES,analyze_demo
from ui.errors import public_error
from ui.final_views import cards,about
from ui.final_style import apply_style
from cloud_config import available_modes


@st.cache_resource
def startup():
    from cloud_readiness import check_readiness
    report = check_readiness(browser=True)
    if not report["ready"]:
        raise StartupFailure(report)
    return report


class StartupFailure(RuntimeError):
    def __init__(self, report):
        super().__init__("Cloud readiness check failed")
        self.report = report


def main():
    st.set_page_config(page_title="Виявлення фішингових вебресурсів",layout="wide",page_icon="🔎")
    apply_style()
    try:
        readiness = startup()
    except StartupFailure as exc:
        readiness = exc.report
    if not readiness["ready"]:
        st.error("Система не готова до аналізу. Перевірте модель, артефакти та Chromium.")
        with st.expander("Діагностика запуску"):
            st.json(readiness)
        st.stop()
    st.markdown('<div class="hero-tag">Дослідницька система · Аналіз вебресурсів</div>',unsafe_allow_html=True)
    st.title("Виявлення фішингових вебресурсів")
    st.caption("Метод аналізу структурної трансформації вебсторінки")
    st.markdown('<div class="hero-meta"><span>Random Forest</span><span>137 характеристик</span><span>S₀ → S₁ → ΔS</span></div>',unsafe_allow_html=True)
    st.caption("Аналіз виконується у контрольованому браузерному середовищі без введення облікових даних та активної взаємодії з формами.")
    mode=st.radio("Режим системи",available_modes(),horizontal=True)
    if mode=="Результати дослідження":
        from ui.final_views import research
        research();about();return
    if mode=="Дослідницький режим":
        from ui.research_app import main as legacy
        legacy();return
    if mode=="Демонстраційний режим":
        st.info("Demo Mode · Локальні контрольовані сторінки. Показується фактичний прогноз моделі, без наперед заданого класу.")
    with st.form("final_analysis_form",border=False):
        if mode=="Аналіз URL":
            input_col,button_col=st.columns([5,1],vertical_alignment="bottom")
            with input_col:
                url=st.text_input("Адреса вебресурсу",placeholder="https://example.com");example=None
        else:
            example=st.selectbox("Контрольований локальний приклад",list(EXAMPLES))
            st.caption(EXAMPLES[example][2]);url=""
            st.info("Контрольований локальний приклад. Це не реальний live phishing-вебсайт; показується фактичний прогноз моделі.")
        if mode=="Аналіз URL":
            with button_col:
                submitted=st.form_submit_button("Аналізувати",type="primary",width="stretch")
        else:
            submitted=st.form_submit_button("Аналізувати",type="primary")
    if submitted:
        st.session_state.pop("final_result",None)
        try:
            with st.status("Браузерний збір S0/S1 та формування характеристик…",expanded=False) as status:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    if example: analysis,prediction=executor.submit(analyze_demo,example).result()
                    else:
                        analysis=executor.submit(analyze_url,url).result();prediction=infer(analysis.result)
                st.session_state["final_result"]=(analysis,prediction,mode)
                status.update(label="Аналіз завершено",state="complete",expanded=False)
        except Exception as exc:
            logging.getLogger(__name__).exception("Final analysis failed")
            st.error(public_error(exc))
            with st.expander("Технічні подробиці помилки"): st.code(f"{type(exc).__name__}: {exc}")
    result=st.session_state.get("final_result")
    if result and result[2]==mode: cards(result[0],result[1])
    about()


if __name__=="__main__": main()
