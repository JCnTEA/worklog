#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把站上所有更新紀錄整理成一頁（不含版本號）。

來源：
  1. pages_site/vi/index.html 內嵌的 LOG_MAIN / LOG_DEV（最早到 11/17 的完整歷史）
  2. report/updates.json 的 items（11/17 之後的更新紀錄）

輸出：pages_site/hist/index.html（單檔、可離線開）
"""
import json, os, re, html, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VI = os.path.join(ROOT, "pages_site", "vi", "index.html")
UPD = os.path.join(ROOT, "report", "updates.json")
OUT = os.path.join(ROOT, "pages_site", "hist", "index.html")

DEC = json.JSONDecoder()
YEAR = "2026"

VER_PREFIX = re.compile(r"(?:Vi\.\d+|Vn\.\d+|vn[\d.]+|V\d+[\.\d]*)\s*[　]*")
VER_ANY = re.compile(r"[（(]\s*(?:v|V|Vi\.|Vn\.|vn)[\d.]+\s*(?:[–\-~]\s*(?:v|V)?[\d.]+)?\s*[）)]"
                     r"|(?:Vi\.\d+|Vn\.\d+|vn[\d.]+|V\d+\.\d+[–\-]V[\d.]+|\bv\d+[\.\d]*)")


def strip_tags(t):
    t = re.sub(r"<br\s*/?>", "\n", t)
    t = re.sub(r"<[^>]+>", "", t)
    return html.unescape(t)


def norm_date(d):
    d = (d or "").strip()
    m = re.match(r"(\d{1,2})/(\d{1,2})", d)
    if m:
        return "%s-%02d-%02d" % (YEAR, int(m.group(1)), int(m.group(2)))
    m = re.match(r"(20\d\d)-(\d{2})-(\d{2})", d)
    if m:
        return m.group(0)
    return None


def clean(text):
    text = strip_tags(text)
    text = VER_PREFIX.sub("", text)
    text = VER_ANY.sub("", text)
    text = re.sub(r"[　]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" 　・、，,；;")
    return text


def load_logs():
    s = open(VI, encoding="utf-8").read()
    rows = []
    for name in ("LOG_MAIN", "LOG_DEV"):
        m = re.search(r"var\s+%s\s*=\s*" % name, s)
        if not m:
            continue
        arr, _ = DEC.raw_decode(s[m.end():])
        for it in arr:
            date = norm_date(it.get("date"))
            raw = strip_tags(it.get("text") or "")
            # 一個字串裡常合併多筆（每個版本一句），先拆開
            parts = re.split(r"(?=(?:Vi\.|Vn\.|vn|V\d+\.)[\d.]*\s*[　])", raw)
            for p in parts:
                c = clean(p)
                if len(c) < 6:
                    continue
                rows.append({"date": date, "cat": "功能", "text": c, "src": "changelog"})
    return rows


def load_updates():
    d = json.load(open(UPD, encoding="utf-8"))
    items = d.get("items", []) if isinstance(d, dict) else d
    rows = []
    for it in items:
        date = norm_date(it.get("date"))
        title = clean(it.get("title") or "")
        detail = clean(it.get("detail") or "")
        text = title + ("：" + detail if detail else "")
        rows.append({"date": date, "cat": it.get("cat") or "其他",
                     "text": text.strip("："), "state": it.get("state") or "", "src": "updates"})
    return rows


def dedupe(rows):
    seen, out = set(), []
    for r in rows:
        key = re.sub(r"[^\w\u4e00-\u9fff]", "", r["text"])[:80]
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def build():
    rows = load_logs() + load_updates()
    rows = dedupe(rows)
    rows.sort(key=lambda r: (r["date"] or "0000-00-00"), reverse=True)
    cats = sorted({r["cat"] for r in rows})
    data = {"rows": rows, "cats": cats,
            "total": len(rows),
            "first": min(r["date"] for r in rows if r["date"]),
            "last": max(r["date"] for r in rows if r["date"])}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False)))
    return data


TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#F3EEE3">
<title>更新總覽・勤務記錄系統</title>
<link rel="preconnect" href="https://miaoda.feishu.cn">
<link href="https://miaoda.feishu.cn/fonts/css2?family=Noto+Sans+TC:wght@400;500;700;900&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{
  --paper:#F3EEE3;--card:#FFFDF8;--line:#DDD3BF;--ink:#1C1A16;--dim:#6F675A;
  --green:#1E6B57;--rust:#B4643B;--slate:#3D5A80;--plum:#6B5AA8;--olive:#7A6A2F;
}
*{box-sizing:border-box}
html,body{margin:0}
body{
  background:
    radial-gradient(120% 60% at 50% -10%,#FBF7EE,#F3EEE3 62%) fixed,
    repeating-linear-gradient(180deg,rgba(28,26,22,.045) 0 1px,transparent 1px 30px);
  color:var(--ink);
  font-family:"Noto Sans TC",-apple-system,"PingFang TC","Microsoft JhengHei",sans-serif;
  -webkit-font-smoothing:antialiased;
}
.wrap{max-width:720px;margin:0 auto;padding:18px 16px 48px}
.toprow{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:18px}
.back{color:var(--dim);text-decoration:none;font-size:12.5px;letter-spacing:.04em}
.live{font:500 11.5px/1.4 "IBM Plex Mono",monospace;color:var(--dim);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.live.on{color:var(--green)}
.live.on::before{content:"";display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--green);margin-right:6px;vertical-align:1px}

.brand{display:flex;align-items:center;gap:13px}
.logo{width:58px;height:58px;flex:0 0 auto}
.wm-cn{font:900 26px/1.1 "Noto Sans TC",sans-serif;letter-spacing:.14em}
.wm-sub{margin-top:6px;font:500 10.5px/1 "IBM Plex Mono",monospace;letter-spacing:.24em;color:var(--dim);text-transform:uppercase}
.sub{margin:14px 0 0;font-size:13px;line-height:1.75;color:var(--dim)}
.rule{height:1px;background:linear-gradient(90deg,var(--line),transparent);margin:20px 0 6px}

.sec{margin-top:22px}
.sec>h2{display:flex;align-items:center;gap:9px;margin:0 0 12px;font:700 13px/1.4 "IBM Plex Mono",monospace;letter-spacing:.16em;color:var(--ink);text-transform:uppercase}
.sec>h2::before{content:"";width:3px;height:15px;background:var(--green);border-radius:2px}

.kpi{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.kpi>div{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 12px 11px;
box-shadow:0 1px 0 rgba(28,26,22,.04)}
.kpi b{display:block;font:600 20px/1.1 "IBM Plex Mono",monospace;letter-spacing:-.01em}
.kpi span{display:block;margin-top:5px;font-size:11px;color:var(--dim);letter-spacing:.05em}
.kpi .k-date b{font-size:13px;letter-spacing:0}

.tools{display:flex;gap:8px;flex-wrap:wrap}
.chip{appearance:none;border:1px solid var(--line);background:var(--card);color:var(--dim);border-radius:999px;
padding:6px 13px;font:500 12.5px/1 "Noto Sans TC",sans-serif;cursor:pointer}
.chip.on{background:var(--green);border-color:var(--green);color:#FCFAF4;font-weight:700}
.chip .n{font:500 10.5px/1 "IBM Plex Mono",monospace;opacity:.62;margin-left:5px}
.qwrap{position:relative;margin-top:10px}
.q{width:100%;background:var(--card);border:1px solid var(--line);border-radius:10px;color:var(--ink);
padding:11px 13px;font-size:13.5px;outline:none}
.q:focus{border-color:var(--green);box-shadow:0 0 0 3px rgba(30,107,87,.1)}
.q::placeholder{color:#A9A193}

.day{margin-top:18px}
.day-h{display:flex;align-items:baseline;gap:9px;margin-bottom:9px;padding-bottom:6px;border-bottom:1px dashed var(--line)}
.day-d{font:600 13px/1 "IBM Plex Mono",monospace;letter-spacing:.04em}
.day-n{font-size:11px;color:var(--dim)}
.item{position:relative;background:var(--card);border:1px solid var(--line);border-radius:11px;
padding:11px 13px 12px 15px;margin-bottom:8px;font-size:13.5px;line-height:1.75;word-break:break-word}
.item::before{content:"";position:absolute;left:0;top:12px;bottom:12px;width:3px;border-radius:2px;background:var(--rust);opacity:.85}
.tag{display:inline-block;font:600 10.5px/1.5 "IBM Plex Mono",monospace;letter-spacing:.04em;
border-radius:5px;padding:1px 6px 2px;margin-right:7px;vertical-align:1px;
background:#EFEAD9;color:#5B5343}
.tag[data-c="修正"]{background:#F6E2D8;color:#9C4E28}
.tag[data-c="優化"]{background:#E3EBF0;color:#33566E}
.tag[data-c="功能"]{background:#DFEFE7;color:#1B6350}
.tag[data-c="新增"]{background:#E8E3F6;color:#554390}
.tag[data-c="自檢"]{background:#F1EBD6;color:#6C5B24}
.tag[data-c="資料"]{background:#EAE7DF;color:#4A4335}
.tag[data-c="移除"]{background:#F3DCDC;color:#8E3B3B}
.chip[data-c="移除"]{border-color:#D9B4B4}
.empty{color:var(--dim);text-align:center;padding:38px 0;font-size:13.5px}
.foot{margin-top:30px;padding-top:14px;border-top:1px solid var(--line);color:var(--dim);font-size:11.5px;line-height:1.8}
@media (max-width:360px){.kpi{grid-template-columns:1fr 1fr}.kpi .k-date{grid-column:1/-1}}
</style>
</head>
<body>
<div class="wrap">
  <div class="toprow"><a class="back" href="../">← 勤務系統</a><div class="live" id="liveBar">連線中…</div></div>

  <div class="brand">
    <svg class="logo" viewBox="0 0 64 64" role="img" aria-label="勤務日誌">
      <defs>
        <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="#28564A"/><stop offset="1" stop-color="#163E34"/>
        </linearGradient>
      </defs>
      <rect x="1.5" y="1.5" width="61" height="61" rx="15" fill="url(#bg)"/>
      <rect x="5.5" y="5.5" width="53" height="53" rx="11.5" fill="none" stroke="#E9DCC2" stroke-opacity=".45" stroke-width="1.6"/>
      <rect x="20" y="10" width="18" height="6" rx="3" fill="#E9DCC2" fill-opacity=".92"/>
      <rect x="15" y="15" width="28" height="34" rx="4" fill="#FBF7EE"/>
      <g stroke="#1B4137" stroke-width="2.6" stroke-linecap="round">
        <path d="M21 24h13"/><path d="M21 31h13"/><path d="M21 38h8"/>
      </g>
      <g fill="#B4643B">
        <path d="M44 30a9 9 0 1 0 0 18 9 9 0 0 0 0-18z" fill="#B4643B" fill-opacity=".14"/>
      </g>
      <circle cx="44" cy="39" r="8.4" fill="#FFFDF8" stroke="#B4643B" stroke-width="2"/>
      <path d="M44 34.4V39l3.2 2" stroke="#8E4A25" stroke-width="1.9" stroke-linecap="round"/>
    </svg>
    <div>
      <div class="wm-cn">勤務日誌</div>
      <div class="wm-sub">Worklog · Changelog</div>
    </div>
  </div>
  <p class="sub">從最初到現在，所有改動集中在這一頁。只列內容，不標版本。</p>

  <div class="sec">
    <h2>目前狀態</h2>
    <div class="kpi">
      <div><b id="kTotal">0</b><span>累計更新</span></div>
      <div class="k-date"><b id="kFirst">—</b><span>最早紀錄</span></div>
      <div class="k-date"><b id="kLast">—</b><span>最近更新</span></div>
    </div>
  </div>

  <div class="sec">
    <h2>異動紀錄</h2>
    <div class="tools" id="chips"></div>
    <div class="qwrap"><input class="q" id="q" placeholder="搜尋關鍵字，例如 廁所、GPS、捷運、蝦皮" autocomplete="off"></div>
    <div id="list"></div>
  </div>

  <div class="foot">資料來源：站台更新紀錄（含各版本頁內歷史）。同一天的多筆改動依原文順序陳列；已移除或已被取代的功能仍保留紀錄。本頁每 60 秒自動同步更新資料庫。</div>
</div>
<script>
const DATA = __DATA__;
const BASE = DATA.rows.filter(r => r.src !== 'updates');
let cat = '全部', kw = '';
/* 移除類：分類標成「移除」，或內容提到移除／拿掉／下架等 */
const RM_RE = /移除|拿掉|拔掉|撤掉|下架|關掉|不再提供/;
function isRm(r){ return r.cat === '移除' || ((r.cat === '修正' || r.cat === '優化') && RM_RE.test(r.text || '')); }

function kpi(){
  document.getElementById('kTotal').textContent = DATA.total;
  document.getElementById('kFirst').textContent = DATA.first || '—';
  document.getElementById('kLast').textContent = DATA.last || '—';
}
function chips(){
  const box = document.getElementById('chips');
  const counts = {};
  DATA.rows.forEach(r => counts[r.cat] = (counts[r.cat]||0) + 1);
  const rmN = DATA.rows.filter(isRm).length;
  const all = ['全部', '移除'].concat(DATA.cats.filter(c => c !== '移除'));
  box.innerHTML = all.map(c => {
    const n = c === '全部' ? DATA.rows.length : (c === '移除' ? rmN : (counts[c]||0));
    return '<button class="chip'+(c===cat?' on':'')+'" data-c="'+c+'">'+c+'<span class="n">'+n+'</span></button>';
  }).join('');
  box.querySelectorAll('.chip').forEach(b => b.onclick = () => { cat = b.dataset.c; chips(); render(); });
}
function render(){
  const rows = DATA.rows.filter(r =>
    (cat==='全部' || (cat==='移除' ? isRm(r) : r.cat===cat)) &&
    (!kw || r.text.toLowerCase().includes(kw.toLowerCase())));
  if(!rows.length){ document.getElementById('list').innerHTML = '<div class="empty">沒有符合的紀錄</div>'; return; }
  let out = '', day = '', n = 0;
  const closeDay = () => { if(day) out = out.replace('__N__', n) + '</div>'; };
  for(const r of rows){
    if(r.date !== day){
      if(day) out += '</div>';
      out += '<div class="day"><div class="day-h"><span class="day-d">'+(r.date||'未標日期')+'</span><span class="day-n">__N__ 筆</span></div>';
      day = r.date; n = 0;
    }
    n++;
    const rmTag = (isRm(r) && r.cat !== '移除') ? '<span class="tag" data-c="移除">移除</span>' : '';
    out += '<div class="item"><span class="tag" data-c="'+r.cat+'">'+r.cat+'</span>'+rmTag+r.text+'</div>';
  }
  if(day) out += '</div>';
  // 把 __N__ 換成實際筆數（逐日）
  const parts = out.split('<div class="day">');
  let fixed = parts[0];
  for(let i=1;i<parts.length;i++){
    const seg = parts[i];
    const cnt = (seg.match(/class="item"/g)||[]).length;
    fixed += '<div class="day">' + seg.replace('__N__', cnt);
  }
  document.getElementById('list').innerHTML = fixed;
}
function mergeLive(items){
  const rows = BASE.slice();
  const seen = new Set(rows.map(r => (r.text||'').replace(/[^\w\u4e00-\u9fff]/g,'').slice(0,80)));
  for(const it of items){
    const d = String(it.date||'').slice(0,10);
    const t = String(it.title||'').replace(/\s+/g,' ').trim();
    const det = String(it.detail||'').replace(/\s+/g,' ').trim();
    const text = (t + (det ? '：' + det : '')).trim();
    const key = text.replace(/[^\w\u4e00-\u9fff]/g,'').slice(0,80);
    if(!key || seen.has(key)) continue;
    seen.add(key);
    rows.push({date:d, cat:it.cat||'其他', text:text});
  }
  rows.sort((a,b)=> String(b.date).localeCompare(String(a.date)));
  DATA.rows = rows; DATA.total = rows.length;
  DATA.first = rows.length ? rows[rows.length-1].date : DATA.first;
  DATA.last = rows.length ? rows[0].date : DATA.last;
  DATA.cats = Array.from(new Set(rows.map(r=>r.cat))).sort();
  kpi(); chips(); render();
}
function loadLive(){
  const bar = document.getElementById('liveBar');
  fetch('../assets/updates.json?ts=' + Date.now(), {cache:'no-store'})
    .then(r => r.ok ? r.json() : Promise.reject(r.status))
    .then(d => {
      const items = (d && d.items) ? d.items : (Array.isArray(d) ? d : []);
      mergeLive(items);
      bar.className = 'live on';
      bar.textContent = '即時同步・' + new Date().toLocaleTimeString('zh-Hant',{hour12:false}) + '・' + DATA.total + ' 筆';
    })
    .catch(() => { bar.className = 'live'; bar.textContent = '離線快照'; });
}
document.getElementById('q').oninput = e => { kw = e.target.value.trim(); render(); };
kpi(); chips(); render(); loadLive(); setInterval(loadLive, 60000);
</script>
</body>
</html>
"""

if __name__ == "__main__":
    d = build()
    print(json.dumps({"total": d["total"], "cats": d["cats"], "first": d["first"], "last": d["last"]}, ensure_ascii=False))
