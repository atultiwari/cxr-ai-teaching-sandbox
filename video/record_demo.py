"""Record the v1a sandbox demo with Playwright (1920x1080) and write caption timings.

Usage: python app.py &   then   python video/record_demo.py <out-dir>
Writes <out-dir>/raw.webm and <out-dir>/marks.json (event times in seconds from video start).
A visible fake cursor is injected because Playwright videos do not show the OS pointer.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

URL = "http://127.0.0.1:7860/"
VIEW = {"width": 1920, "height": 1080}
CURSOR_JS = """
window.addEventListener('DOMContentLoaded', () => {
  const c = document.createElement('div');
  c.id = '__cursor';
  Object.assign(c.style, {position: 'fixed', left: '0', top: '0', width: '26px', height: '26px', zIndex: 99999,
    pointerEvents: 'none', borderRadius: '50%', background: 'rgba(255,255,255,0.9)', border: '3px solid #0B2545',
    boxShadow: '0 2px 8px rgba(0,0,0,.45)', transform: 'translate(-50%,-50%)', transition: 'width .12s, height .12s'});
  document.body.appendChild(c);
  document.addEventListener('mousemove', e => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; });
  document.addEventListener('mousedown', () => { c.style.width = '18px'; c.style.height = '18px'; });
  document.addEventListener('mouseup', () => { c.style.width = '26px'; c.style.height = '26px'; });
});
"""


class Recorder:
    def __init__(self, page: Page, t0: float):
        self.page, self.t0, self.marks, self.pos = page, t0, {}, (960, 540)

    def mark(self, name: str) -> None:
        self.marks[name] = round(time.monotonic() - self.t0, 2)

    def move_to(self, selector: str, dx: float = 0.5, dy: float = 0.5, steps: int = 45) -> None:
        box = self.page.locator(selector).first.bounding_box()
        target = (box["x"] + box["width"] * dx, box["y"] + box["height"] * dy)
        self.page.mouse.move(*target, steps=steps)
        self.pos = target

    def click(self, selector: str, **kw) -> None:
        self.move_to(selector, **kw)
        self.page.wait_for_timeout(250)
        self.page.mouse.down(); self.page.wait_for_timeout(90); self.page.mouse.up()

    def run_and_wait(self, selector: str) -> None:
        with self.page.expect_response(lambda r: "/api/analyse" in r.url and r.ok):
            self.click(selector)
        self.page.wait_for_function("document.getElementById('busy').hidden")
        self.page.wait_for_timeout(200)

    def pause(self, seconds: float) -> None:
        self.page.wait_for_timeout(int(seconds * 1000))


def script(r: Recorder) -> None:
    p = r.page
    r.mark("start"); r.pause(2.5)
    r.run_and_wait(".sample[data-id='pneumothorax_left_pa']"); r.mark("ptx_loaded")
    r.move_to("#findings li:nth-child(1)", dx=0.3, steps=40); r.pause(1.0)
    r.move_to("#findings li:nth-child(4)", dx=0.3, steps=30); r.pause(2.2)
    r.click("#heat"); r.mark("heat_on"); r.pause(2.8)
    r.move_to("#camlabel", steps=35); r.pause(0.4)
    with p.expect_response(lambda x: "/api/analyse" in x.url and x.ok):
        p.select_option("#camlabel", "Pneumothorax")
    p.wait_for_function("document.getElementById('busy').hidden"); r.mark("ptx_cam")
    r.move_to("#stage", dx=0.5, dy=0.2, steps=40); r.pause(3.0)
    with p.expect_response(lambda x: "/api/analyse" in x.url and x.ok):
        p.select_option("#camlabel", "")  # back to "top finding" before the next film
    p.wait_for_function("document.getElementById('busy').hidden")
    r.run_and_wait(".sample[data-id='ett_right_mainstem_ap']"); r.mark("ett_loaded")
    r.pause(1.8)
    r.move_to("#missing", dx=0.9, dy=0.25, steps=45); p.evaluate("document.getElementById('missing').classList.add('flash')")
    r.mark("no_tube"); r.pause(3.2)
    r.move_to("#stage", dx=0.42, dy=0.5, steps=45); r.mark("ett_cam"); r.pause(3.2)
    r.click("#whybtn"); r.mark("why"); r.pause(5.5)
    r.mark("end")


def main(out_dir: str) -> None:
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport=VIEW, record_video_dir=str(out), record_video_size=VIEW,
                                  color_scheme="light", device_scale_factor=1, bypass_csp=True)
        ctx.add_init_script(CURSOR_JS)
        page = ctx.new_page()
        t0 = time.monotonic()
        page.goto(URL)
        page.wait_for_selector(".sample")
        page.mouse.move(960, 540)
        page.wait_for_timeout(600)
        rec = Recorder(page, t0)
        script(rec)
        video_path = page.video.path()
        ctx.close(); browser.close()
    Path(video_path).rename(out / "raw.webm")
    (out / "marks.json").write_text(json.dumps(rec.marks, indent=1))
    print(json.dumps(rec.marks))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "recordings/v1a")
