# -*- coding: utf-8 -*-
"""Heptabase → Blogger 草稿發布器（純標準庫）。py app.py → http://localhost:8822"""
import json, os, sys, time, threading, subprocess, urllib.parse, urllib.request, urllib.error, webbrowser
import html as H
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

PORT = 8822
BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE, "config.json")
CLI = os.path.join(os.path.expanduser("~"), ".heptabase", "bin", "heptabase.cmd")
SCOPE = "https://www.googleapis.com/auth/blogger"
REDIRECT = f"http://localhost:{PORT}/oauth2callback"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ---------- config ----------

def load_cfg():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        return {}

def save_cfg(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

# ---------- Heptabase CLI ----------

def run_cli(*args):
    p = subprocess.run([CLI, *args], capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode("utf-8", "replace") or "heptabase CLI 失敗（桌面 App 有開嗎？）")
    return json.loads(p.stdout.decode("utf-8", "replace"))

_title_cache = {}
def card_title(cid):
    if cid not in _title_cache:
        try:
            _title_cache[cid] = run_cli("card", "properties", cid).get("title") or "(無標題卡片)"
        except Exception:
            _title_cache[cid] = "(卡片)"
    return _title_cache[cid]

# ---------- ProseMirror → Blogger-safe HTML（全 inline style） ----------

TEXT_COLORS = {"red": "#e03e3e", "orange": "#d9730d", "yellow": "#b8860b", "green": "#0f7b6c",
               "blue": "#0b6e99", "purple": "#6940a5", "pink": "#ad1a72", "brown": "#64473a",
               "gray": "#787774", "grey": "#787774"}
BG_COLORS = {"red": "#ffd6d6", "orange": "#ffe0c2", "yellow": "#ffec99", "green": "#d3f0e0",
             "blue": "#d3e5ef", "purple": "#e4d9f5", "pink": "#f8d8e7", "brown": "#e9dcd3",
             "gray": "#e8e8e8", "grey": "#e8e8e8"}
CODE_STYLE = "background:#f2f2f2;padding:1px 5px;border-radius:3px;font-family:Consolas,monospace;font-size:0.9em"

def esc(s):
    return H.escape(s or "", quote=False)

def render_text(node):
    t = esc(node.get("text", ""))
    for m in node.get("marks") or []:
        mt, a = m.get("type"), m.get("attrs") or {}
        if mt == "strong":
            t = f"<b>{t}</b>"
        elif mt == "em":
            t = f"<i>{t}</i>"
        elif mt == "underline":
            t = f"<u>{t}</u>"
        elif mt in ("strike", "strikethrough", "del"):
            t = f"<s>{t}</s>"
        elif mt == "code":
            t = f'<code style="{CODE_STYLE}">{t}</code>'
        elif mt == "link":
            href = H.escape(a.get("href", "#"), quote=True)
            t = f'<a href="{href}" target="_blank">{t}</a>'
        elif mt == "highlight":
            t = f'<mark style="background:#ffec99;padding:0 2px">{t}</mark>'
        elif mt == "color":
            c = str(a.get("color") or "").lower()
            if "background" in str(a.get("type") or "") or "highlight" in str(a.get("type") or ""):
                t = f'<span style="background:{BG_COLORS.get(c, c)};padding:0 2px">{t}</span>'
            else:
                t = f'<span style="color:{TEXT_COLORS.get(c, c)}">{t}</span>'
    return t

def math_src(node):
    if (node.get("attrs") or {}).get("latex"):
        return node["attrs"]["latex"]
    return "".join(c.get("text", "") for c in node.get("content") or [])

def image_placeholder(node):
    a = node.get("attrs") or {}
    label = a.get("alt") or a.get("title") or ""
    return ('<div style="border:1px dashed #bbb;border-radius:4px;padding:10px;color:#888;margin:12px 0">'
            f'🖼 圖片未匯入{("：" + esc(label)) if label else ""}（請在 Blogger 編輯器手動上傳）</div>')

def render_inline(nodes, state):
    out = []
    for n in nodes or []:
        t = n.get("type")
        if t == "text":
            out.append(render_text(n))
        elif t == "hard_break":
            out.append("<br>")
        elif t == "math_inline":
            state["math"] = True
            out.append("\\(" + esc(math_src(n)) + "\\)")
        elif t == "card":
            title = card_title((n.get("attrs") or {}).get("cardId", ""))
            out.append(f'<span style="border-bottom:1px dashed #999">{esc(title)}</span>')
        elif t == "image":
            out.append(image_placeholder(n))
        else:
            out.append(render_inline(n.get("content"), state))
    return "".join(out)

LIST_KINDS = {"numbered_list_item": "ol", "bullet_list_item": "ul", "todo_list_item": "ul"}

def render_list(kind, items, state):
    lis = []
    for it in items:
        kids = it.get("content") or []
        head, rest = "", kids
        if kids and kids[0].get("type") == "paragraph":
            head, rest = render_inline(kids[0].get("content"), state), kids[1:]
        if kind == "todo_list_item":
            head = ("☑ " if (it.get("attrs") or {}).get("checked") else "☐ ") + head
        lis.append(f'<li style="margin:3px 0">{head}{render_blocks(rest, state)}</li>')
    body = "".join(lis)
    if kind == "todo_list_item":
        return f'<ul style="margin:0 0 12px;padding-left:8px;list-style:none">{body}</ul>'
    return f'<{LIST_KINDS[kind]} style="margin:0 0 12px;padding-left:28px">{body}</{LIST_KINDS[kind]}>'

def render_table(node, state):
    rows = []
    for row in node.get("content") or []:
        cells = []
        for cell in row.get("content") or []:
            tag = "th" if cell.get("type") == "table_header" else "td"
            extra = "background:#f5f5f5;font-weight:bold;" if tag == "th" else ""
            cells.append(f'<{tag} style="border:1px solid #ccc;padding:5px 9px;{extra}text-align:left">'
                         f'{render_blocks(cell.get("content"), state)}</{tag}>')
        rows.append(f"<tr>{''.join(cells)}</tr>")
    return ('<div style="overflow-x:auto"><table style="border-collapse:collapse;margin:0 0 12px">'
            + "".join(rows) + "</table></div>")

def render_block(n, state):
    t = n.get("type")
    a = n.get("attrs") or {}
    if t == "paragraph":
        inner = render_inline(n.get("content"), state)
        return f'<p style="margin:0 0 12px">{inner}</p>' if inner else '<div style="height:0.6em"></div>'
    if t == "heading":
        lv = min(int(a.get("level", 1)) + 1, 6)  # 內文 H1 讓給文章標題，整體降一級
        return f'<h{lv}>{render_inline(n.get("content"), state)}</h{lv}>'
    if t == "blockquote":
        return ('<blockquote style="border-left:3px solid #ccc;margin:0 0 12px;padding:2px 0 2px 14px;color:#555">'
                f'{render_blocks(n.get("content"), state)}</blockquote>')
    if t in ("code_block", "codeBlock"):
        code = "".join(c.get("text", "") for c in n.get("content") or [])
        return ('<pre style="background:#f6f6f6;border:1px solid #e2e2e2;border-radius:4px;padding:10px;'
                'overflow-x:auto;font-family:Consolas,monospace;font-size:0.9em;margin:0 0 12px">'
                f"{esc(code)}</pre>")
    if t == "math_display":
        state["math"] = True
        return f'<div style="text-align:center;margin:12px 0">$${esc(math_src(n))}$$</div>'
    if t == "table":
        return render_table(n, state)
    if t == "horizontal_rule":
        return '<hr style="border:none;border-top:1px solid #ddd;margin:18px 0">'
    if t == "image":
        return image_placeholder(n)
    if t == "highlight_element":
        return ('<div style="background:#fff9db;border-left:3px solid #fab005;border-radius:3px;'
                f'padding:8px 12px;margin:0 0 12px">{render_blocks(n.get("content"), state)}</div>')
    if t == "card":
        title = card_title(a.get("cardId", ""))
        return f'<p style="margin:0 0 12px;border-bottom:1px dashed #999;display:inline-block">{esc(title)}</p>'
    if t == "embed":
        return (f'<div style="border:1px dashed #bbb;border-radius:4px;padding:10px;color:#888;margin:12px 0">'
                f'📎 嵌入內容（{esc(a.get("objectType", "object"))}）未匯入</div>')
    if t in LIST_KINDS:
        return render_list(t, [n], state)
    return render_blocks(n.get("content"), state)

def render_blocks(nodes, state):
    out, i, nodes = [], 0, nodes or []
    while i < len(nodes):
        t = nodes[i].get("type")
        if t in LIST_KINDS:
            items = []
            while i < len(nodes) and nodes[i].get("type") == t:
                items.append(nodes[i]); i += 1
            out.append(render_list(t, items, state))
        else:
            out.append(render_block(nodes[i], state)); i += 1
    return "".join(out)

MATHJAX = '<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js" async></script>'

def convert(card_id):
    note = run_cli("note", "read", card_id)
    doc = json.loads(note["content"])
    blocks = doc.get("content") or []
    title = note.get("title") or ""
    # 開頭 H1 若就是卡片標題，略過避免重複
    if blocks and blocks[0].get("type") == "heading" and (blocks[0].get("attrs") or {}).get("level") == 1:
        h1_text = "".join(c.get("text", "") for c in blocks[0].get("content") or [])
        if h1_text.strip() == title.strip():
            blocks = blocks[1:]
    state = {"math": False}
    body = render_blocks(blocks, state)
    html = f'<div style="line-height:1.8">{body}</div>'
    if state["math"]:
        html += MATHJAX
    return title, html

# ---------- Google OAuth / Blogger API ----------

_tok = {"v": None, "exp": 0}

def http_json(url, data=None, headers=None, form=False):
    headers = dict(headers or {})
    body = None
    if data is not None:
        if form:
            body = urllib.parse.urlencode(data).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"HTTP {e.code}: {detail[:600]}")

def access_token():
    if _tok["v"] and time.time() < _tok["exp"] - 60:
        return _tok["v"]
    cfg = load_cfg()
    r = http_json("https://oauth2.googleapis.com/token", form=True, data={
        "client_id": cfg["client_id"], "client_secret": cfg["client_secret"],
        "refresh_token": cfg["refresh_token"], "grant_type": "refresh_token"})
    _tok["v"], _tok["exp"] = r["access_token"], time.time() + r.get("expires_in", 3600)
    return _tok["v"]

def api(path, data=None):
    return http_json("https://www.googleapis.com/blogger/v3" + path, data=data,
                     headers={"Authorization": "Bearer " + access_token()})

# ---------- UI ----------

PAGE = """<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hepta → Blogger</title><style>
body{font-family:"Segoe UI","Microsoft JhengHei",sans-serif;margin:0;background:#f4f5f7;color:#222}
header{background:#1a73e8;color:#fff;padding:10px 20px;font-size:18px;font-weight:600}
header small{font-weight:400;opacity:.85;margin-left:10px}
main{max-width:1100px;margin:16px auto;padding:0 16px}
.card{background:#fff;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.12);padding:16px 20px;margin-bottom:16px}
input,button{font:inherit}
input[type=text],input[type=password]{width:100%;box-sizing:border-box;padding:8px;border:1px solid #ccc;border-radius:4px}
button{background:#1a73e8;color:#fff;border:none;border-radius:4px;padding:8px 18px;cursor:pointer}
button:disabled{background:#aaa}
button.ghost{background:#fff;color:#1a73e8;border:1px solid #1a73e8}
ol.steps li{margin:6px 0}
#results div{padding:7px 10px;border-radius:4px;cursor:pointer}
#results div:hover{background:#eef3fd}
#results div.sel{background:#dbe7fb}
.cols{display:flex;gap:16px;flex-wrap:wrap}
.cols>div{flex:1 1 320px}
iframe{width:100%;height:460px;border:1px solid #ddd;border-radius:4px;background:#fff}
.ok{color:#188038}.err{color:#c5221f;white-space:pre-wrap}
label{font-size:13px;color:#555;display:block;margin:10px 0 4px}
</style></head><body>
<header>Hepta → Blogger <small>Heptabase 卡片一鍵推成 Blogger 草稿</small></header>
<main>
<div class="card" id="setup" style="display:none">
  <h3>初始設定（只需一次）</h3>
  <ol class="steps">
    <li>開 <a href="https://console.cloud.google.com/projectcreate" target="_blank">Google Cloud Console</a> 建立專案（名稱隨意）。</li>
    <li>到 <a href="https://console.cloud.google.com/apis/library/blogger.googleapis.com" target="_blank">API Library — Blogger API v3</a> 按「啟用」。</li>
    <li>到「OAuth 同意畫面」：選 External、填 App 名稱、把自己的 Gmail 加入「測試使用者」。</li>
    <li>到「憑證」→ 建立憑證 → OAuth 用戶端 ID → 應用程式類型選「<b>電腦版應用程式</b>」→ 建立。</li>
    <li>把 Client ID 與 Client Secret 貼到下面（或直接貼下載的 JSON 全文）。</li>
  </ol>
  <label>Client ID（或整份 client_secret JSON）</label><input type="text" id="cid">
  <label>Client Secret</label><input type="password" id="csec">
  <p><button onclick="saveClient()">儲存並前往 Google 授權</button> <span id="setupMsg" class="err"></span></p>
</div>

<div class="card" id="blogpick" style="display:none">
  <h3>選擇要發布的 Blog</h3><div id="blogs"></div>
</div>

<div class="card" id="workbench" style="display:none">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <b>發布到：<span id="blogName"></span></b>
    <span><button class="ghost" onclick="show('blogpick');loadBlogs()">換 Blog</button></span>
  </div>
  <div class="cols" style="margin-top:12px">
    <div>
      <input type="text" id="q" placeholder="搜尋卡片標題／內容，Enter 搜尋" onkeydown="if(event.key==='Enter')search()">
      <div id="results" style="margin-top:8px;max-height:430px;overflow-y:auto"></div>
    </div>
    <div>
      <label>文章標題</label><input type="text" id="ptitle">
      <label>預覽（貼進 Blogger 後長這樣）</label>
      <iframe id="pv"></iframe>
      <p><button id="pub" onclick="publish()" disabled>推送草稿到 Blogger</button>
         <span id="pubMsg"></span></p>
    </div>
  </div>
</div>
</main>
<script>
let curId=null;
const $=id=>document.getElementById(id);
function show(id){for(const s of ['setup','blogpick','workbench'])$(s).style.display=s===id?'':'none';}
async function j(url,opts){const r=await fetch(url,opts);const d=await r.json();if(!r.ok)throw new Error(d.error||r.status);return d;}
async function init(){
  const s=await j('/api/state');
  if(!s.configured){show('setup');return;}
  if(!s.authed){show('setup');$('setupMsg').textContent='憑證已存，尚未授權。';
    $('cid').value='(已儲存)';$('csec').value='(已儲存)';
    document.querySelector('#setup button').textContent='前往 Google 授權';return;}
  if(!s.blog){show('blogpick');loadBlogs();return;}
  $('blogName').textContent=s.blog.name;show('workbench');search();
}
async function saveClient(){
  try{
    const cid=$('cid').value.trim(),csec=$('csec').value.trim();
    if(cid&&cid!=='(已儲存)')await j('/api/config',{method:'POST',body:JSON.stringify({client_id:cid,client_secret:csec})});
    location.href='/auth';
  }catch(e){$('setupMsg').textContent=e.message;}
}
async function loadBlogs(){
  $('blogs').innerHTML='載入中…';
  try{
    const d=await j('/api/blogs');
    $('blogs').innerHTML='';
    for(const b of d.items||[]){
      const el=document.createElement('p');
      el.innerHTML=`<button onclick='pickBlog(${JSON.stringify(JSON.stringify({id:b.id,name:b.name,url:b.url}))})'>${b.name}</button> <small>${b.url}</small>`;
      $('blogs').appendChild(el);
    }
    if(!(d.items||[]).length)$('blogs').textContent='這個 Google 帳號底下沒有 Blogger 網誌。';
  }catch(e){$('blogs').innerHTML='<span class="err">'+e.message+'</span>';}
}
async function pickBlog(s){await j('/api/blog',{method:'POST',body:s});init();}
async function search(){
  $('results').innerHTML='搜尋中…';
  try{
    const d=await j('/api/cards?q='+encodeURIComponent($('q').value));
    $('results').innerHTML='';
    for(const c of d.results){
      const el=document.createElement('div');
      el.textContent=c.title||'(無標題)';
      el.onclick=()=>{document.querySelectorAll('#results div').forEach(x=>x.classList.remove('sel'));el.classList.add('sel');preview(c.id);};
      $('results').appendChild(el);
    }
    if(!d.results.length)$('results').textContent='沒有結果。';
  }catch(e){$('results').innerHTML='<span class="err">'+e.message+'</span>';}
}
async function preview(id){
  curId=id;$('pub').disabled=true;$('pubMsg').textContent='';
  $('pv').src='/preview_frame?id='+id;
  try{const d=await j('/api/preview_meta?id='+id);$('ptitle').value=d.title;$('pub').disabled=false;}
  catch(e){$('pubMsg').innerHTML='<span class="err">'+e.message+'</span>';}
}
async function publish(){
  $('pub').disabled=true;$('pubMsg').textContent='推送中…';
  try{
    const d=await j('/api/publish',{method:'POST',body:JSON.stringify({id:curId,title:$('ptitle').value})});
    $('pubMsg').innerHTML=`<span class="ok">已建立草稿！</span> <a href="${d.editUrl}" target="_blank">在 Blogger 開啟編輯</a>`;
  }catch(e){$('pubMsg').innerHTML='<span class="err">'+e.message+'</span>';}
  $('pub').disabled=false;
}
init();
</script></body></html>"""

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n).decode("utf-8")) if n else {}

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        try:
            if u.path == "/":
                return self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
            if u.path == "/api/state":
                cfg = load_cfg()
                return self._send(200, {"configured": bool(cfg.get("client_id")),
                                        "authed": bool(cfg.get("refresh_token")),
                                        "blog": cfg.get("blog")})
            if u.path == "/auth":
                cfg = load_cfg()
                url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
                    "client_id": cfg.get("client_id", ""), "redirect_uri": REDIRECT,
                    "response_type": "code", "scope": SCOPE,
                    "access_type": "offline", "prompt": "consent"})
                self.send_response(302); self.send_header("Location", url); self.end_headers()
                return
            if u.path == "/oauth2callback":
                cfg = load_cfg()
                if "code" not in q:
                    return self._send(400, f"授權失敗：{q.get('error', '未取得 code')}".encode("utf-8"),
                                      "text/plain; charset=utf-8")
                r = http_json("https://oauth2.googleapis.com/token", form=True, data={
                    "code": q["code"], "client_id": cfg["client_id"], "client_secret": cfg["client_secret"],
                    "redirect_uri": REDIRECT, "grant_type": "authorization_code"})
                cfg["refresh_token"] = r["refresh_token"]
                save_cfg(cfg)
                self.send_response(302); self.send_header("Location", "/"); self.end_headers()
                return
            if u.path == "/api/blogs":
                return self._send(200, api("/users/self/blogs"))
            if u.path == "/api/cards":
                args = ["card", "list", "--card-types", "note", "--limit", "40"]
                if q.get("q"):
                    args += ["-q", q["q"]]
                return self._send(200, run_cli(*args))
            if u.path == "/api/preview_meta":
                title, _ = convert(q["id"])
                return self._send(200, {"title": title})
            if u.path == "/preview_frame":
                _, body = convert(q["id"])
                page = ('<!doctype html><html><head><meta charset="utf-8"></head>'
                        '<body style="font-family:Segoe UI,Microsoft JhengHei,sans-serif;'
                        f'max-width:720px;margin:12px auto;padding:0 14px">{body}</body></html>')
                return self._send(200, page.encode("utf-8"), "text/html; charset=utf-8")
            return self._send(404, {"error": "not found"})
        except Exception as e:
            return self._send(500, {"error": str(e)})

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        try:
            body = self._json_body()
            if u.path == "/api/config":
                cid, csec = body.get("client_id", ""), body.get("client_secret", "")
                if cid.strip().startswith("{"):  # 貼整份 client_secret JSON
                    j = json.loads(cid)
                    info = j.get("installed") or j.get("web") or {}
                    cid, csec = info.get("client_id", ""), info.get("client_secret", "")
                if not cid or not csec:
                    return self._send(400, {"error": "Client ID / Secret 不能是空的"})
                cfg = load_cfg()
                cfg["client_id"], cfg["client_secret"] = cid.strip(), csec.strip()
                save_cfg(cfg)
                return self._send(200, {"ok": True})
            if u.path == "/api/blog":
                cfg = load_cfg()
                cfg["blog"] = {"id": body["id"], "name": body["name"], "url": body.get("url", "")}
                save_cfg(cfg)
                return self._send(200, {"ok": True})
            if u.path == "/api/publish":
                cfg = load_cfg()
                title, html = convert(body["id"])
                post_title = body.get("title") or title or "(無標題)"
                blog_id = cfg["blog"]["id"]
                r = api(f"/blogs/{blog_id}/posts?isDraft=true",
                        data={"kind": "blogger#post", "title": post_title, "content": html})
                return self._send(200, {"postId": r.get("id"),
                                        "editUrl": f"https://www.blogger.com/blog/post/edit/{blog_id}/{r.get('id')}"})
            return self._send(404, {"error": "not found"})
        except Exception as e:
            return self._send(500, {"error": str(e)})

def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Hepta → Blogger 發布器：http://localhost:{PORT}")
    threading.Timer(0.8, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()
    srv.serve_forever()

if __name__ == "__main__":
    main()
