"""Offline browser smoke probe, supervised by cloud_readiness."""
import json
from playwright.sync_api import sync_playwright


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, chromium_sandbox=True,
            ignore_default_args=["--disable-popup-blocking", "--safebrowsing-disable-auto-update",
                                 "--disable-component-update"])
        try:
            context = browser.new_context(ignore_https_errors=False, service_workers="block",
                                          accept_downloads=False, permissions=[])
            try:
                page = context.new_page()
                page.set_content("<html><body>offline readiness probe</body></html>")
                assert page.locator("body").inner_text() == "offline readiness probe"
                print(json.dumps({"version": browser.version, "sandbox": True,
                                  "context": True, "offline_probe": True}))
            finally:
                context.close()
        finally:
            browser.close()


if __name__ == "__main__":
    main()
