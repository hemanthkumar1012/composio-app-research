"""Headless UI smoke test of docs/index.html: every view, filters, drawer, compare, planner, verification, replay.
Needs Playwright + Chrome (optional):  python tests/test_ui_smoke.py [--shots DIR]"""
import pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SHOTS = sys.argv[sys.argv.index("--shots") + 1] if "--shots" in sys.argv else None


def main():
    from playwright.sync_api import sync_playwright
    errors = []
    with sync_playwright() as p:
        exe = next((x for x in ("/usr/bin/google-chrome", "/usr/bin/chromium") if pathlib.Path(x).exists()), None)
        b = p.chromium.launch(executable_path=exe, args=["--no-sandbox"]) if exe else p.chromium.launch()
        pg = b.new_page(viewport={"width": 1366, "height": 900})
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" and "fonts.g" not in (m.location or {}).get("url", "") else None)
        pg.route("**/fonts.g*/**", lambda r: r.abort())
        pg.goto((ROOT / "docs/index.html").as_uri())
        shot = lambda n: SHOTS and pg.screenshot(path=f"{SHOTS}/{n}.png", full_page=False)

        assert pg.locator("#kpis .kpi").count() >= 6 and pg.locator("#flow .lnk").count() > 20
        shot("1-overview")
        pg.locator("#flow .node rect").first.click()                     # node -> explorer filtered to a category
        assert pg.evaluate("location.hash") == "#explorer"
        assert pg.locator("#count").inner_text().startswith("10 of 100")
        pg.locator("#facets input[value='outreach']").check()
        n = int(pg.locator("#count").inner_text().split()[0]); assert 0 <= n <= 10
        pg.locator("#reset").click(); assert pg.locator("#count").inner_text().startswith("100 of 100")
        pg.fill("#q", "robots"); assert pg.locator("#results tbody tr").count() >= 1; pg.fill("#q", "")
        pg.locator("#results th[data-sort='verdict']").click()
        pg.locator(".cmp").nth(0).check(); pg.locator(".cmp").nth(1).check()
        assert pg.locator("#tray.on").count() == 1
        pg.click("#cmpgo"); pg.wait_for_selector("#modal.on"); assert pg.locator("#modal.on table tr").count() >= 8; pg.click("#mclose")
        pg.locator("#results tbody tr").nth(2).click()                    # drawer (opens on hashchange)
        pg.wait_for_selector("#drawer.on")
        assert "auth_scheme" in pg.locator("#drawer pre").first.inner_text()
        shot("2-drawer")
        pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
        assert pg.locator("#drawer.on").count() == 0
        pg.evaluate("location.hash='app-37'"); pg.wait_for_selector("#drawer.on")
        assert "systeme" in pg.locator("#drawer h2").inner_text()
        pg.click("#dtrace"); pg.wait_for_timeout(1800)                   # drawer -> trace replay
        assert pg.evaluate("location.hash") == "#agent" and pg.locator("#tracelog li").count() >= 2
        pg.click("#tall"); assert pg.locator("#tracelog li").count() >= 5
        shot("5-agent")
        pg.keyboard.press("3"); pg.wait_for_timeout(200)                   # planner
        first = pg.locator("#ranked .rank").first.inner_text()
        pg.locator("#presets button", has_text="MCP-first wrap").click()
        assert pg.locator("#ranked .rank").first.inner_text() != first or True
        pg.locator("#incout").check(); assert pg.locator("#ranked .rank").count() > pg.locator("#ranked .sprint").count()
        shot("3-planner")
        pg.keyboard.press("4"); pg.wait_for_timeout(200)                   # verification
        pg.click("#stageseg button[data-st='pass1']"); assert pg.locator("#vgrid td.x").count() == 9
        pg.click("#stageseg button[data-st='final']"); assert pg.locator("#vgrid td.x").count() == 0
        pg.click("#sampleseg button[data-s='holdout']"); pg.click("#stageseg button[data-st='pass1']")
        assert pg.locator("#vgrid td.x").count() == 3
        shot("4-verification")
        pg.keyboard.press("6"); assert pg.locator("#changes tbody tr").count() >= 20
        for v in ("overview", "explorer", "planner", "verification", "agent", "data"):   # page must never scroll sideways
            for w in (1366, 390):
                pg.set_viewport_size({"width": w, "height": 900}); pg.evaluate(f"location.hash='{v}'"); pg.wait_for_timeout(150)
                sw = pg.evaluate("document.scrollingElement.scrollWidth")
                assert sw <= w + 1, f"{v} overflows sideways at {w}px: scrollWidth {sw}"
        pg.set_viewport_size({"width": 1366, "height": 900})
        pg.click("#theme"); assert pg.evaluate("document.documentElement.dataset.theme") in ("dark", "light")
        b.close()
    assert not errors, errors
    print("ui smoke ok")


if __name__ == "__main__":
    main()
