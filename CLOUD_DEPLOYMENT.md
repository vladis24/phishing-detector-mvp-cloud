# Phase 12: Streamlit Community Cloud

Ця папка є cloud-копією. Модель, datasets і результати Phase 7/10/11 не перебудовуються.
Публічний UI за замовчуванням має тільки **Live URL Analysis** і **Demo Mode**.
HTML Upload, Controlled Validation, дослідницький режим і сторінка результатів
приховані. Їхній локальний код збережено; public entrypoint не імпортує research routines.

## Локальний запуск (Python 3.13)

Windows PowerShell, із поточної папки:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
$env:PUBLIC_CLOUD_MODE = "true"
.\.venv\Scripts\python.exe cloud_readiness.py
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Linux, у віртуальному середовищі Python 3.13:

```bash
python -m pip install -r requirements.txt
python -m playwright install --with-deps chromium
PUBLIC_CLOUD_MODE=true python cloud_readiness.py
PUBLIC_CLOUD_MODE=true python -m streamlit run app.py
```

`--with-deps` призначений для підготовки локального/CI Linux host, де є дозволи apt.
Community Cloud встановлює apt-залежності з `packages.txt`, а браузер — startup CLI
`python -m playwright install chromium`. Повторний CLI запуск використовує вже
встановлену відповідну ревізію. Завантаження має дедлайн 180 секунд.

У повній локальній копії `$env:PUBLIC_CLOUD_MODE = "false"` повертає research UI.
Не встановлюйте false на публічному host: локальні research routines збережені
для дослідника й не мають усіх нових cloud-обмежень. Deployment allowlist не включає
research-only модулі, тому одного перемикання прапорця у скороченому Git-наборі
недостатньо для відновлення повного дослідницького середовища.

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `PUBLIC_CLOUD_MODE` | `true` | Тільки `true`/`false`; інше значення є помилкою |
| `INSTALL_CHROMIUM` | `true` на Linux, `false` на Windows | Дозволити startup встановити pinned Playwright Chromium |
| `PLAYWRIGHT_BROWSERS_PATH` | Playwright default | Необов'язковий шлях до browser cache; однаковий для install і runtime |

Cloud не потребує секретів. Streamlit Secrets не слід вважати автоматичним
способом встановлення OS environment variables для цих прапорців: без жодного
налаштування застосунок уже має безпечний public default.

## Python dependencies

`requirements.txt` закріплює задані версії: Streamlit 1.63.0, Playwright 1.62.0,
BeautifulSoup 4.15.0, lxml 6.1.3, pandas 3.0.5, scikit-learn 1.9.1, NumPy 2.5.3,
SciPy 1.18.1, joblib 1.6.0, threadpoolctl 3.6.0, tldextract 5.3.2.
Додано прямий runtime dependency `filelock==3.32.6` для міжпроцесного browser lock.
Torch не потрібен і не входить у cloud requirements. Не оновлюйте sklearn/NumPy
навмання: joblib-модель перевірена з цим середовищем.

Windows перевіряється на Python 3.13.14. Метадані PyPI для всіх pinned пакетів
містять Linux x86_64 wheel-кандидати для Python 3.13 або універсальні wheels.
Це не замінює фактичне встановлення всіх транзитивних залежностей на Linux.

## Deployment file set

`.gitignore` працює як allowlist: сторонні файли не додаються в новий Git repository.
Файли, які вже були tracked в іншому repository, `.gitignore` не вилучає з індексу.
У цій папці repository під час підготовки не створювався.

Runtime code:

- `app.py`, `collect_one.py`, `cloud_config.py`, `cloud_readiness.py`;
- Python modules `crawler/`, `extractor/`;
- `dataset/__init__.py`, `dataset/schema.py`, `dataset/domains.py`;
- `ui/__init__.py`, `final_app.py`, `final_style.py`, `final_views.py`, `analysis.py`,
  `inference.py`, `demo.py`, `demo_server.py`, `errors.py`, `tables.py`;
- `requirements.txt`, `packages.txt`, `deployment_manifest.json`;
- deployment docs і три cloud test modules.

Незмінні артефакти (усі listed hashes перевіряються startup):

```text
output/final_test_evaluation/models/F02_RF_A08.joblib
output/final_test_evaluation/primary_model_result.json
output/final_test_evaluation/final_test_metrics.csv
output/feature_ablation/feature_subsets.json
output/feature_ablation/ablation_results.csv
output/model_interpretability/group_permutation_importance.csv
output/temporal_evaluation/temporal_metrics.json
output/phase11_structural_robustness/phase11_summary.json
output/phase11_structural_robustness/phase11_model_summary.csv
output/phase11_structural_robustness/figures/primary_probability_shift.png
tests/pages/01_static_simple.html
robustness/originals/O01_STATIC_LOGIN.html
robustness/variants/O01_STATIC_LOGIN_M04_1500.html
```

Таблиці результатів залишені для комплектності UI/локального перегляду; публічне
меню наразі містить два режими. Phase 7 interpretation table використовується в cards.
Інші models, datasets, manifests, reports, raw sources, experimental CSV, кеші,
venv, node_modules, локальні документи та сторонні скрипти ігноруються.
Локальні оригінали не видаляються.

## Integrity and startup

Модель SHA-256:

```text
8ba5c2743b5f0af05b438bb629ac88dc3daba4914fe20b9bed11bd7630e5e4a0
```

До завантаження joblib перевіряється hardcoded digest, а також frozen provenance.
Перевіряються exact RandomForestClassifier, fitted state, класи, hyperparameters,
137 ознак, frozen feature order і threshold 0.5. Порядок незмінний:
**S0 → S1 → delta → network → derived → temporal**.

`deployment_manifest.json` — новий файл із hashes лише потрібних frozen assets.
Він не переписує provenance Phase 7/10/11. Startup перевіряє imports, manifest,
модель/schema і offline browser worker. При помилці аналіз UI заблокований.
Inference повторно перевіряє model/schema hashes навіть при кешованій моделі.

```bash
python cloud_readiness.py
python cloud_readiness.py --skip-browser
```

Другий варіант позначає browser як PENDING і повертає nonzero exit status:
це не повна готовність. Тільки успішний startup кешується в Streamlit resource cache;
після тимчасової помилки можна повторити запуск/rerun. Після зміни встановлених
пакетів або браузера перезапустіть app/очистіть resource cache.

## SSRF and resource policy

Публічний URL і кожен перехоплений запит проходять HTTP(S)/credentials/DNS policy;
URL довший за 8192 символи відхиляється.
Початкова синтаксична/IP перевірка не робить DNS; DNS виконується всередині
supervised worker і входить у його загальний 35-секундний дедлайн.
Відхиляються непублічні A/AAAA, mixed public/private DNS answers, альтернативні
OS-supported IPv4 форми та mapped private IPv6. DNS resolution fail закриває доступ.

Chromium використовує тимчасовий HTTP/CONNECT proxy. Proxy ще раз перевіряє всі
DNS answers та з'єднується з numeric sockaddr, без повторного DNS між check/connect.
HTTPS залишається end-to-end із перевіркою TLS у браузері. Redirects, subresources,
frames і workers проходять proxy; main-target CDP додатково перевіряє запити.
Вимкнено implicit loopback proxy bypass, QUIC і non-proxied WebRTC UDP.
Загального localhost exception немає.

Demo запускається тільки з hardcoded EXAMPLES. Окремий сервер віддає один fixture;
trusted policy дозволяє лише точний `http://127.0.0.1:<ephemeral-port>` цього запуску.
Введений користувачем URL не може встановити trusted origin.

Обмеження:

- один restricted browser worker для shared deployment через semaphore + OS file lock;
- зайнятий browser відхиляє новий аналіз, не створюючи необмеженої черги;
- navigation timeout 20 s, worker lifetime 35 s;
- 2000 requests, 20 main navigations, 5 popup attempts;
- 5 млн DOM characters; downloads заборонені;
- proxy: 16 одночасних connections, 10 MiB на connection/tunnel, 50 MiB на session
  (обидва напрямки, encrypted wire bytes), socket idle timeout 10 s;
- request body до 1 MiB; невідоме chunked upload framing відхиляється;
- `Content-Length` response понад 10 MiB відхиляється при перехопленні;
- finally cleanup contexts/browser/server, supervisor kill tree/group при hard timeout.

Порушення proxy policy/byte budget блокує inference замість прогнозу на обрізаній
сторінці. Після побудови характеристик public mode не зберігає великі DOM snapshots
у session state; результати extractor і operational metadata залишаються.

Ці ліміти можуть відхиляти важкі сторінки; вони не змінюють формули 137 ознак.
Proxy/CDP не замінюють OS-level egress firewall і container isolation у разі browser
exploit. Перед публічним запуском перевірте proxy routing, IPv6, WebRTC та sandbox
на цільовому host; для сильнішої ізоляції використовуйте окремий collector service.
Модельна ймовірність не є гарантією безпечності сторінки.

## Community Cloud deployment steps (не виконані під час підготовки)

1. Переглянути `.gitignore` і майбутній tracked file list; включити тільки allowlist.
2. Після окремого рішення користувача створити GitHub repository і завантажити files.
3. У Streamlit Community Cloud вибрати repository, branch та `app.py`.
4. У Advanced settings явно вибрати **Python 3.13**, а не default 3.12.
5. Залишити public mode default. `packages.txt` встановлює Debian libraries;
   startup встановлює відповідну Playwright browser revision без `--no-sandbox`.
6. Переглянути startup diagnostics/logs і запустити readiness на Linux host/CI.
7. Перевірити три demo, live URL на дозволеному public site, SSRF redirects/subresources,
   паралельні сесії, timeout cleanup, restart/browser cache та usage memory.
8. Якщо sandbox або Linux dependencies не працюють, зупинити public launch.
   Не вимикати sandbox автоматично й не змінювати frozen model/dependencies навмання.

**Target-host compatibility PENDING:** офіційна документація Community Cloud
згадує Debian/bullseye packages, тоді як актуальні Playwright system requirements
перелічують Debian 12/13. Фактичний образ, apt package names (зокрема libasound2),
browser ABI і sandbox треба перевірити на host. Цей Windows результат не є Linux PASS.

Документація Community Cloud заявляє підтримку released Python versions, що
отримують security updates, із вибором у Advanced settings; Python 3.13 відповідає
цій політиці. Наявність вибору та повне встановлення у конкретному account ще PENDING.

Sources:

- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies
- https://playwright.dev/python/docs/intro
- https://playwright.dev/python/docs/browsers

## Tests without training

Full local copy:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -p cloud_test_policy -p no:cacheprovider -q --basetemp=.cloud-tests
```

Legacy tests that invoke estimator fitting are SKIPPED by a session-wide no-training
plugin, including module-scoped fitting fixtures. Public/research UI tests explicitly
select their mode. New cloud tests can run from the deployment file set:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests/test_cloud_security.py tests/test_cloud_runtime.py tests/test_cloud_browser.py
```

Training scripts and test-only generated temporary outputs never enter deployment.
