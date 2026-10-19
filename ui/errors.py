"""Ukrainian public error mapping; raw diagnostics stay in collapsed details."""
from playwright.sync_api import TimeoutError as BrowserTimeout
from ui.inference import ModelUnavailable,FeatureIncomplete,FeatureSchemaMismatch


def public_error(exc):
    from crawler.url_policy import UnsafeURL
    if isinstance(exc, UnsafeURL): return "Адресу заблоковано: дозволені лише публічні HTTP(S) вебресурси."
    if "browser busy" in str(exc).lower(): return "Браузер зайнятий іншим аналізом. Спробуйте трохи пізніше."
    if "ssrf" in str(exc).lower(): return "Аналіз зупинено: сторінка звернулася до забороненої мережевої адреси."
    if any(word in str(exc).lower() for word in ("byte_limit", "response_size_limit", "connection_limit")):
        return "Аналіз зупинено: перевищено ліміт мережевих ресурсів."
    if isinstance(exc,FeatureIncomplete): return "Не вдалося сформувати повний набір із 137 характеристик."
    if isinstance(exc,FeatureSchemaMismatch): return "Структура характеристик не відповідає схемі навченої моделі."
    if isinstance(exc,ModelUnavailable): return "Не вдалося завантажити або застосувати зафіксовану модель. Перевірте встановлення системи."
    text=str(exc).lower()
    if isinstance(exc,BrowserTimeout) or "timeout" in text: return "Не вдалося завантажити вебресурс у межах установленого часу."
    if "name_not_resolved" in text or "dns" in text: return "Не вдалося визначити адресу вебресурсу. Перевірте URL та мережеве підключення."
    if "cert" in text or "ssl" in text or "tls" in text: return "Не вдалося перевірити захищене з’єднання вебресурсу (TLS)."
    if "connection_refused" in text or "http status" in text or "unavailable" in text: return "Вебресурс недоступний для аналізу."
    if isinstance(exc,ValueError): return "Введіть повну HTTP або HTTPS адресу без облікових даних, наприклад https://example.com."
    return "Не вдалося виконати браузерний аналіз. Перевірте з’єднання та встановлення Chromium."
