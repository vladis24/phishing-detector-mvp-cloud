"""Ukrainian final presentation; no new research computations."""
import json
from html import escape
from pathlib import Path
import pandas as pd
import streamlit as st
from ui.inference import ROOT
from ui.tables import model_table

DISCLAIMER="Наведені характеристики показують параметри, які використовує модель. Вони не є окремими правилами визначення фішингу та не встановлюють причинно-наслідкового зв'язку."


def cards(analysis,prediction):
    r=analysis.result
    st.caption(analysis.source)
    if r["url"]!=r["final_url"]: st.caption("Кінцева адреса після навігації: "+r["final_url"])
    tone="risk" if prediction.predicted_label else "safe"
    left,right=st.columns([1,1.3])
    with left:
        st.markdown(f'<div class="result-card {tone}"><div class="card-label">Ймовірність фішингового класу</div><div class="probability">{prediction.probability*100:.1f} %</div><div class="card-note">Поріг класифікації · 0,50</div></div>',unsafe_allow_html=True)
    with right:
        st.markdown(f'<div class="result-card {tone}"><div class="card-label">Результат класифікації</div><div class="classification">{escape(prediction.title)}</div><div class="card-note">Попередньо навчена модель · F02_RF_A08</div></div>',unsafe_allow_html=True)
    st.write(prediction.description)
    st.subheader("Структура вебсторінки")
    groups=[("Початковий стан S0","early_dom",[("dom_nodes","DOM-вузли"),("forms","Форми"),("password_inputs","Парольні поля"),("iframes","Iframes"),("external_resources","Зовнішні ресурси")]),
        ("Кінцевий стан S1","rendered",[("dom_nodes","DOM-вузли"),("forms","Форми"),("password_inputs","Парольні поля"),("iframes","Iframes"),("external_resources","Зовнішні ресурси")]),
        ("Структурна трансформація","delta",[("delta_dom_nodes","Δ DOM-вузли"),("delta_forms","Δ форми"),("delta_password_inputs","Δ парольні поля"),("delta_iframes","Δ iframes")]),
        ("Створені елементи","derived",[("created_forms","Форми"),("created_password_inputs","Парольні поля"),("created_iframes","Iframes"),("created_scripts","Скрипти")]),
        ("Динамічна поведінка","temporal",[("dom_change_events","Зміни DOM"),("last_significant_dom_change_ms","Остання зміна, мс"),("late_form_creation","Пізня форма"),("late_password_creation","Пізнє парольне поле"),("late_iframe_creation","Пізній iframe")]),
        ("Мережа","network",[("network_requests","Запити"),("external_request_ratio","Частка зовнішніх запитів"),("unique_external_hosts","Зовнішні хости"),("requests_after_domcontentloaded","Запити після DCL")])]
    for col,(title,section,fields) in zip(st.columns(3),groups[:3]):
        with col.container(border=True):
            heading={"early_dom":"S₀ · Початковий стан","rendered":"S₁ · Кінцевий стан","delta":"ΔS · Структурні зміни"}[section]
            rows="".join(f'<div class="state-row"><span>{escape(label)}</span><b>{r[section][key]:+g}</b></div>' if section=="delta" else f'<div class="state-row"><span>{escape(label)}</span><b>{r[section][key]:g}</b></div>' for key,label in fields)
            st.markdown(f'<div class="state-title">{heading}</div>'+rows,unsafe_allow_html=True)
    st.subheader("Динаміка та мережа")
    for col,(label,value) in zip(st.columns(4),[
        ("Мережеві запити",f"{r['network']['network_requests']:g}"),
        ("Зміни DOM",f"{r['temporal']['dom_change_events']:g}"),
        ("Остання зміна, мс",f"{r['temporal']['last_significant_dom_change_ms']:g}"),
        ("Час аналізу, с",f"{analysis.duration:.2f}")]):
        col.metric(label,value)
    st.subheader("Деталі аналізу")
    technical,interpretation,experiments=st.tabs(["Характеристики та збір","Інтерпретація моделі","Дослідницькі результати"])
    with experiments:
        research()
    with interpretation:
        with st.expander("Чому система отримала такий результат?"):
            st.write("За зафіксованим post-hoc аналізом Phase 7 найсильніші групи — початковий та сформований стани; часові характеристики мають менший додатний середній внесок за дослідженими метриками.")
            st.caption("Це загальна інформація про frozen-модель, а не індивідуальна атрибуція поточного прогнозу.")
            try:
                importance=pd.read_csv(ROOT/"output/model_interpretability/group_permutation_importance.csv")
                st.dataframe(importance[["group_name","feature_count","f1_drop_mean","average_precision_drop_mean","roc_auc_drop_mean"]],hide_index=True,width="stretch")
                st.caption("Збережена групова permutation importance Phase 7: середнє падіння метрики після перестановки групи. Внесок залежить від метрики.")
            except (OSError,ValueError,KeyError):
                st.warning("Таблиця загальної інтерпретації моделі недоступна.")
            st.write(DISCLAIMER)
            st.write(f"Для цієї сторінки: {r['rendered']['forms']:g} форм у S1, Δ password inputs = {r['delta']['delta_password_inputs']:g}, DOM change events = {r['temporal']['dom_change_events']:g}.")
    with technical:
        for title,section in (("Початковий стан S0","early_dom"),("Кінцевий стан S1","rendered"),("Структурна трансформація ΔS","delta"),
                             ("Похідні характеристики","derived"),("Мережеві характеристики","network"),("Часові характеристики","temporal")):
            with st.expander(title):
                values={k:v for k,v in r[section].items() if isinstance(v,(int,float))}
                st.dataframe(pd.DataFrame([{"Характеристика":k,"Значення":float(v)} for k,v in values.items()]),hide_index=True,width="stretch")
        with st.expander("Повний вектор 137 характеристик"):
            st.dataframe(model_table(r),hide_index=True,width="stretch")
        with st.expander("Технічні метадані збору"):
            st.write("Політика: restricted-v1 · TLS verification · passive observation")
            st.write(f"HTTP {r['status_code']} · час {analysis.duration:.2f} с")
            st.json(analysis.snapshot.operational)


def about():
    with st.expander("Про модель"):
        st.write("**Random Forest · F02_RF_A08 · A08_FULL_137**")
        st.write("137 характеристик: 33 S0, 33 S1, 33 delta, 25 derived, 8 network, 5 temporal. Поріг — 0,5.")
        st.caption("Під час аналізу використовується попередньо навчена модель. Її параметри залишаються незмінними, а система виконує лише прогнозування.")


def research(root=ROOT):
    root=Path(root)
    st.subheader("Результати дослідження")
    st.caption("Зафіксовані результати; запуск застосунку не повторює експерименти.")
    try:
        with st.expander("Held-out test",expanded=True):
            metrics=pd.read_csv(root/"output/final_test_evaluation/final_test_metrics.csv")
            st.dataframe(metrics[["configuration_id","accuracy","precision","recall","f1","average_precision","roc_auc"]],hide_index=True,width="stretch")
            st.caption("Primary — F02_RF_A08; descriptive best F1 не змінює основну конфігурацію.")
        with st.expander("Ablation: 15 підмножин"):
            data=pd.read_csv(root/"output/feature_ablation/ablation_results.csv")
            st.dataframe(data[["ablation_id","model_name","feature_count","f1","average_precision","roc_auc"]],hide_index=True,width="stretch")
            st.caption("Transformation-блоки дають metric-dependent результати; повний набір не є найкращим за всіма критеріями.")
        with st.expander("Пізніше зібраний PhishTank cohort"):
            t=json.loads((root/"output/temporal_evaluation/temporal_metrics.json").read_text())
            st.dataframe([{"N":t["N"],"TP":t["TP"],"FN":t["FN"],"Recall":t["recall"],"FNR":t["false_negative_rate"],
                           "CI lower":t["recall_ci95_lower"],"CI upper":t["recall_ci95_upper"]}],hide_index=True,width="stretch")
            st.caption("Phishing-only cohort; двокласові метрики непридатні. PhishTank-derived provenance не є незалежним джерелом валідації.")
        with st.expander("Контрольований експеримент зі структурними модифікаціями",expanded=True):
            summary=pd.read_csv(root/"output/phase11_structural_robustness/phase11_model_summary.csv")
            st.dataframe(summary[["model_id","n","flip_count","consistency_rate","mean_absolute_probability_delta"]],hide_index=True,width="stretch")
            primary=summary.loc[summary["model_id"]=="F02_RF_A08"].iloc[0]
            consistency=f"{100*primary['consistency_rate']:.2f}".replace(".",",")
            st.info(f"F02_RF_A08: {int(primary['n'])} варіантів · {int(primary['flip_count'])} змін класу · {consistency}% узгодженості прогнозів. Consistency is not accuracy.")
            st.caption("Контрольовані local login fixtures; не незалежний benchmark реального phishing detection.")
            image=root/"output/phase11_structural_robustness/figures/primary_probability_shift.png"
            if image.exists(): st.image(str(image),caption="Зафіксовані paired probability shifts основної моделі")
    except (OSError,ValueError,KeyError): st.error("Не вдалося прочитати зафіксовані результати дослідження. Перевірте комплектність встановлення.")
