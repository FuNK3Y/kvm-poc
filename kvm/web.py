# Minimal HTTP server on asyncio streams: identical on CPython and MicroPython.

import asyncio
import json

from .core import PCS

PAGE = """<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>KVM</title>
<style>
:root{color-scheme:light dark;--a:#2563eb;--b:#16a34a}
body{margin:0;min-height:100vh;display:flex;flex-direction:column;align-items:center;
justify-content:center;gap:1.5rem;font-family:system-ui,sans-serif;background:Canvas;color:CanvasText}
#now{font-size:1.1rem;opacity:.75}
button{font:600 1.6rem system-ui;padding:1.4rem 2.6rem;border:0;border-radius:1rem;color:#fff;
background:var(--a);cursor:pointer;min-width:16rem}
button[data-pc=B]{background:var(--b)}button:disabled{opacity:.6}
.row{display:flex;gap:.75rem}.row button{font-size:1rem;padding:.7rem 1.2rem;min-width:0}
#err{color:#dc2626;max-width:90vw;white-space:pre-wrap}
</style></head><body>
<div id="now">Active: <b id="name">%NAME%</b></div>
<form method="post" action="/toggle"><button id="toggle" data-pc="%PC%">Switch to %OTHER%</button></form>
<div class="row">
<form method="post" action="/select/A"><button data-pc="A">%NAME_A%</button></form>
<form method="post" action="/select/B"><button data-pc="B">%NAME_B%</button></form>
</div>
<div id="err">%ERR%</div>
<script>
const $=id=>document.getElementById(id);
function show(s){const other=s.active=="A"?"B":"A";$("name").textContent=s.name;
 $("toggle").dataset.pc=s.active;$("toggle").textContent="Switch to "+s.names[other];
 $("err").textContent=s.errors.join("\\n");}
document.querySelectorAll("form").forEach(f=>f.addEventListener("submit",async e=>{
 e.preventDefault();const b=f.querySelector("button");b.disabled=true;
 try{show(await (await fetch("/api"+f.getAttribute("action"),{method:"POST"})).json())}
 catch(x){$("err").textContent=String(x)}finally{b.disabled=false}}));
setInterval(async()=>{try{show(await (await fetch("/api/status")).json())}catch(x){}},3000);
</script></body></html>
"""


def _escape(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(kvm):
    s = kvm.status()
    other = PCS[1 - kvm.active]
    return (PAGE.replace("%NAME%", _escape(s["name"]))
            .replace("%PC%", s["active"])
            .replace("%OTHER%", _escape(s["names"][other]))
            .replace("%NAME_A%", _escape(s["names"]["A"]))
            .replace("%NAME_B%", _escape(s["names"]["B"]))
            .replace("%ERR%", _escape("\n".join(s["errors"]))))


async def _respond(writer, status, ctype, body, extra=""):
    if isinstance(body, str):
        body = body.encode()
    head = ("HTTP/1.0 %s\r\nContent-Type: %s\r\nContent-Length: %d\r\n"
            "Cache-Control: no-store\r\nConnection: close\r\n%s\r\n"
            % (status, ctype, len(body), extra))
    writer.write(head.encode())
    writer.write(body)
    await writer.drain()


def route(kvm, method, path):
    """Return (status, content_type, body, extra_headers)."""
    api = path.startswith("/api/")
    action = path[4:] if api else path

    if method == "POST" and action == "/toggle":
        kvm.toggle()
    elif method == "POST" and action in ("/select/A", "/select/B"):
        kvm.select(PCS.index(action[-1]))
    elif not (method == "GET" and action in ("/", "/status")):
        return "404 Not Found", "text/plain", "not found", ""

    if api:
        return "200 OK", "application/json", json.dumps(kvm.status()), ""
    if method == "POST":  # no-JS form fallback: redirect back to the page
        return "303 See Other", "text/plain", "", "Location: /\r\n"
    return "200 OK", "text/html; charset=utf-8", render(kvm), ""


def make_handler(kvm):
    async def handle(reader, writer):
        try:
            line = await reader.readline()
            parts = line.decode().split(" ")
            if len(parts) < 2:
                return
            method, path = parts[0], parts[1].split("?")[0]
            while True:  # drain headers; bodies are never needed
                h = await reader.readline()
                if not h or h in (b"\r\n", b"\n"):
                    break
            await _respond(writer, *route(kvm, method, path))
        except Exception as e:
            print("HTTP error:", e)
        finally:
            writer.close()
            await writer.wait_closed()

    return handle


async def serve(kvm, host="0.0.0.0", port=80):
    await asyncio.start_server(make_handler(kvm), host, port)
    print("KVM web UI on http://%s:%d/" % (host, port))
    while True:
        await asyncio.sleep(3600)
