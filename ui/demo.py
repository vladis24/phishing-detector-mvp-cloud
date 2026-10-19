"""Controlled demonstrations using the same restricted collector/extractor/model."""
from pathlib import Path
from ui.demo_server import serve_fixture
from ui.analysis import _analyze_trusted_url
from ui.inference import ROOT,infer

EXAMPLES={
    "A — Статична інформаційна сторінка":("tests/pages","01_static_simple.html","Локальна інформаційна структура; очікуваний зміст не визначає результат моделі."),
    "B — Login-подібна сторінка":("robustness/originals","O01_STATIC_LOGIN.html","Контрольована форма email/password із dummy action."),
    "C — Динамічне створення форми":("robustness/variants","O01_STATIC_LOGIN_M04_1500.html","Форма створюється JavaScript після S0 із затримкою 1500 мс."),
}


def analyze_demo(name,root=ROOT):
    root=Path(root)
    directory,filename,_=EXAMPLES[name]
    with serve_fixture(root/directory/filename) as url:
        analysis=_analyze_trusted_url(url,source="Контрольований локальний приклад: "+name)
        return analysis,infer(analysis.result,root)
