"""Verificare UI optionala: Chrome cu --remote-debugging-port=9223.

Necesita websocket-client (doar pentru verificare, nu pentru aplicatie).
"""
import base64
import json
import time
import urllib.request
from pathlib import Path

import websocket


tabs = json.load(urllib.request.urlopen("http://localhost:9223/json"))
tab = next(tab for tab in tabs if tab["type"] == "page")
connection = websocket.create_connection(tab["webSocketDebuggerUrl"], suppress_origin=True, timeout=20)
sequence = 0


def command(method, params=None):
    global sequence
    sequence += 1
    connection.send(json.dumps({"id": sequence, "method": method, "params": params or {}}))
    while True:
        result = json.loads(connection.recv())
        if result.get("id") == sequence:
            if "error" in result:
                raise RuntimeError(result["error"])
            return result.get("result", {})


def evaluate(expression):
    result = command("Runtime.evaluate", {"expression": expression, "awaitPromise": True, "returnByValue": True})
    if "exceptionDetails" in result:
        raise RuntimeError(result["exceptionDetails"])
    return result["result"].get("value")


def wait_for(expression):
    for _ in range(60):
        if evaluate(expression):
            return
        time.sleep(0.1)
    raise AssertionError(f"Timeout: {expression}")


try:
    command("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 1100, "deviceScaleFactor": 1, "mobile": False})
    command("Page.navigate", {"url": "http://localhost:8080"})
    wait_for("document.querySelectorAll('.product-card').length === 8")
    evaluate("document.querySelector('[data-category=Audio]').click()")
    assert evaluate("document.querySelectorAll('.product-card').length") == 3
    evaluate("document.querySelector('[data-category=Toate]').click(); document.querySelector('#search').value='Arc'; document.querySelector('#search').dispatchEvent(new Event('input'))")
    assert evaluate("document.querySelectorAll('.product-card').length") == 1
    evaluate("document.querySelector('#search').value=''; document.querySelector('#search').dispatchEvent(new Event('input'))")
    evaluate("document.querySelector('.product-grid [data-product]').click()")
    wait_for("!!document.querySelector('.detail-price')")
    assert evaluate("!document.querySelector('#reload-product') && !document.querySelector('#lab-toggle') && !document.querySelector('#about')")
    assert evaluate("!document.querySelector('#product-detail').textContent.includes('API')")
    evaluate("document.querySelector('#dialog-close').click()")
    # Force lazy images to load before capturing the full page.
    evaluate("Promise.all([...document.images].map(i => {i.loading='eager'; return i.decode().catch(() => null)}))")
    assert evaluate("[...document.images].every(i => i.complete && i.naturalWidth > 0)")
    metrics = command("Page.getLayoutMetrics")
    height = metrics["cssContentSize"]["height"]
    screenshot = command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True,
                          "clip": {"x": 0, "y": 0, "width": 1440, "height": height, "scale": 1}})
    Path("preview-desktop.png").write_bytes(base64.b64decode(screenshot["data"]))
    command("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True})
    assert evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Overflow mobil"
    screenshot = command("Page.captureScreenshot", {"format": "png"})
    Path("preview-mobile.png").write_bytes(base64.b64decode(screenshot["data"]))
    evaluate("document.querySelector('.product-grid [data-product]').click()")
    wait_for("!!document.querySelector('.detail-price')")
    assert evaluate("document.querySelector('#product-dialog').getBoundingClientRect().width <= window.innerWidth")
    evaluate("document.querySelector('#dialog-close').click(); document.querySelector('.project-link').click()")
    wait_for("!!document.querySelector('#test-product') && !document.querySelector('#test-product').disabled")
    assert evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Overflow panou mobil"
    evaluate("document.querySelector('#clear-cache').click()")
    wait_for("!document.querySelector('#clear-cache').disabled && document.querySelector('#lab-log').textContent.includes('Cache golit')")
    evaluate("document.querySelector('#request-product').click()")
    wait_for("document.querySelector('#lab-source').textContent === 'MISS' && !document.querySelector('#request-product').disabled")
    evaluate("document.querySelector('#request-product').click()")
    wait_for("document.querySelector('#lab-source').textContent === 'HIT' && !document.querySelector('#request-product').disabled")
    evaluate("document.querySelector('#cache-enabled').checked=false; document.querySelector('#request-product').click()")
    wait_for("document.querySelector('#lab-source').textContent === 'BYPASS' && !document.querySelector('#request-product').disabled")
    assert evaluate("document.querySelectorAll('#request-history tbody tr').length") == 3
    wait_for("!!document.querySelector('#benchmark-form') && !document.querySelector('#benchmark-fields').disabled")
    evaluate("document.querySelector('[name=requests]').value=200; document.querySelector('[name=concurrency]').value=5; document.querySelector('[name=products]').value=8; document.querySelector('#start-benchmark').click()")
    wait_for("!document.querySelector('#benchmark-fields').disabled && document.querySelectorAll('#result-content tbody tr').length===4")
    assert evaluate("document.querySelectorAll('.chart').length") == 4
    assert evaluate("!document.querySelector('#exports').hidden")
    assert evaluate("document.querySelector('#benchmark-error').textContent") == ''
    assert evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Overflow dashboard mobil"
    evaluate("document.querySelector('#refresh-history').click()")
    wait_for("document.querySelectorAll('#result-content tbody tr').length===4")
    job_id = evaluate("document.querySelector('#experiment-select').value")
    evaluate("window.qaOriginalURL=URL.createObjectURL;window.qaOriginalClick=HTMLAnchorElement.prototype.click;URL.createObjectURL=blob=>{window.qaBlob=blob;return 'blob:qa'};HTMLAnchorElement.prototype.click=function(){};document.querySelector('#export-json').click()")
    assert evaluate("window.qaBlob.text().then(text=>JSON.parse(text).id)") == job_id
    evaluate("document.querySelector('#export-csv').click()")
    assert evaluate("window.qaBlob.text().then(text=>text.split('\\r\\n').length)") == 5
    evaluate("URL.createObjectURL=window.qaOriginalURL;HTMLAnchorElement.prototype.click=window.qaOriginalClick")
    command("Page.reload")
    wait_for("document.querySelectorAll('#result-content tbody tr').length===4")
    assert evaluate("document.querySelector('#experiment-select').value") == job_id
    command("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 1100, "deviceScaleFactor": 1, "mobile": False})
    screenshot = command("Page.captureScreenshot", {"format": "png"})
    Path("preview-project.png").write_bytes(base64.b64decode(screenshot["data"]))
    print("OK: catalog, mobil, MISS/HIT/BYPASS, 4 configuratii, grafice, continut export JSON/CSV, istoric dupa reincarcare.")
finally:
    try:
        connection.send(json.dumps({"id": sequence + 1, "method": "Browser.close"}))
    finally:
        connection.close()
