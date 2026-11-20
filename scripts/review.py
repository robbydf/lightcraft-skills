"""Build a local HTML review page for a batch of LightCraft edits.

Usage:
  python -I review.py OUT.html DIR [DIR ...] [--title "Review"]

Each DIR holds the worker's renders (ID-before.jpg, ID-after.jpg, crops) and a review.jsonl with one
JSON object per photo:
  {"id": 501, "file": "IMG_0501", "title": "Night portrait",
   "changes": ["Night look", "SAM 3 mask, face +23 %", "AI Denoise 65 %"],
   "crops": [["501-dn.png", "Denoise 0 / 50 / 65 / 75 %"], ["501-edge.png", "Mask edge at 100 %"]],
   "decide": {"q": "Use the Night look for blue hour?", "options": ["Approve", "Change", "Revert this photo"]},
   "group": "New looks"}
"decide" and "group" are optional. Photos with "decide" go to the top, grouped by "group"
(default "Needs your decision"); the rest get Fine / Change buttons.

The page is self-contained (no network), responsive, and refers to images by relative path, so keep
OUT.html where it can reach the DIRs (it is usually written next to them). A DIR on another drive is
linked by an absolute file:// URL, so that page only works on this computer. The viewer picks answers and
presses "Copy my decisions", then pastes the text into the chat.
"""
import argparse
import html
import json
import os
import pathlib
import sys

PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--bg:#f6f5f2;--card:#fff;--ink:#1d1d1f;--mute:#6b6b70;--line:#e2e0db;--accent:#b4540a;--chip:#f0ede6}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#151517;--card:#1f1f22;--ink:#ececee;--mute:#9a9aa2;--line:#33333a;--accent:#f0a35e;--chip:#2a2a2f}}
:root[data-theme="dark"]{--bg:#151517;--card:#1f1f22;--ink:#ececee;--mute:#9a9aa2;--line:#33333a;--accent:#f0a35e;--chip:#2a2a2f}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,Segoe UI,sans-serif}
main{margin:0 auto;padding:24px clamp(16px,2vw,40px) 120px}
h1{font-size:24px;margin:0 0 4px}h2{font-size:18px;margin:36px 0 4px}.sub{color:var(--mute);margin:0 0 16px;max-width:1100px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin:14px 0}
.head{display:flex;flex-wrap:wrap;gap:8px;align-items:baseline}.head b{font-size:16px}
.tag{background:var(--chip);border-radius:99px;padding:1px 9px;font-size:12px;color:var(--mute)}.tag.need{background:var(--accent);color:#fff}
.body{display:grid;grid-template-columns:1fr;gap:4px}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:10px 0;align-items:start}
figure{margin:0}img{width:100%;height:auto;display:block;border-radius:6px;cursor:zoom-in}
.pair img{max-height:calc(100vh - 140px);object-fit:contain}
figcaption{font-size:12px;color:var(--mute);margin-top:2px}
.crop{display:flex;flex-wrap:wrap;gap:10px;margin:8px 0}.crop figure{flex:1 1 320px;max-width:900px}
ul{margin:6px 0 0;padding-left:20px}li{margin:2px 0}
.q{margin-top:10px;padding:10px;border-left:3px solid var(--accent);background:var(--chip);border-radius:4px}
.dec{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px;align-items:center}
.dec label{border:1px solid var(--line);border-radius:6px;padding:4px 10px;cursor:pointer;font-size:14px}
.dec input[type=radio]{margin-right:5px}
.dec input[type=text]{flex:1 1 260px;min-width:0;padding:6px 8px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--ink)}
.missing{padding:40px;text-align:center;color:var(--mute);border:1px dashed var(--line);border-radius:6px}
#bar{position:fixed;left:0;right:0;bottom:0;background:var(--card);border-top:1px solid var(--line);padding:10px 16px;display:flex;gap:10px;align-items:center;justify-content:center;flex-wrap:wrap}
button{background:var(--accent);color:#fff;border:0;border-radius:6px;padding:8px 16px;font-size:15px;cursor:pointer}
#out{display:none;width:min(1100px,100%);height:140px;font:13px monospace;background:var(--bg);color:var(--ink);border:1px solid var(--line);border-radius:6px}
#zoom{position:fixed;inset:0;background:rgba(0,0,0,.92);display:none;overflow:auto;z-index:9}#zoom img{width:auto;max-width:none;cursor:zoom-out;margin:auto}
@media (max-width:640px){.pair{grid-template-columns:1fr}}
</style></head><body><main>
<h1>__TITLE__</h1>
<p class="sub">__COUNT__ photos. Click any image for full size; click again to close. Pick an answer per photo,
add a note if you like, then press <b>Copy my decisions</b> and paste the text into the chat.</p>
<div id="cards"></div></main>
<div id="bar"><button id="copy">Copy my decisions</button><span id="msg" class="tag"></span><textarea id="out" readonly></textarea></div>
<div id="zoom"><img id="zimg" alt=""></div>
<script id="data" type="application/json">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById('data').textContent);
const H=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const img=(src,alt,cap)=>`<figure>${src?`<img loading="lazy" src="${H(src)}" alt="${H(alt)}" onerror="this.outerHTML='<div class=missing>missing: ${H(src)}</div>'">`:'<div class="missing">no render</div>'}<figcaption>${H(cap)}</figcaption></figure>`;
let out='',last=null;
for(const p of D){
 if(p.section!==last){out+=`<h2>${H(p.section)}</h2>`;last=p.section}
 const radios=(opts)=>opts.map(o=>`<label><input type="radio" name="d${p.key}" value="${H(o)}">${H(o)}</label>`).join('');
 out+=`<div class="card" data-id="${H(p.id)}" data-f="${H(p.file)}"><div class="head"><b>${H(p.file)}</b><span>${H(p.title||'')}</span>${p.decide?'<span class="tag need">decide</span>':''}<span class="tag">id ${H(p.id)}</span></div>
 <div class="body"><div class="pair">${img(p.before,p.file+' before','Before')}${img(p.after,p.file+' after','After')}</div>
 <div><ul>${(p.changes||[]).map(c=>`<li>${H(c)}</li>`).join('')}</ul></div></div>
 ${(p.crops&&p.crops.length)?`<div class="crop">${p.crops.map(c=>img(c[0],c[1],c[1])).join('')}</div>`:''}
 ${p.decide?`<div class="q"><b>${H(p.decide.q)}</b><div class="dec">${radios(p.decide.options||['Approve','Change','Revert this photo'])}<input type="text" placeholder="Note (optional)"></div></div>`
   :`<div class="dec">${radios(['Fine','Change'])}<input type="text" placeholder="Note (optional)"></div>`}</div>`;
}
document.getElementById('cards').innerHTML=out;
const z=document.getElementById('zoom'),zi=document.getElementById('zimg');
document.addEventListener('click',e=>{if(e.target.tagName==='IMG'&&e.target!==zi){zi.src=e.target.src;z.style.display='block'}else if(z.contains(e.target)){z.style.display='none'}});
document.getElementById('copy').onclick=async()=>{
 const lines=[];document.querySelectorAll('.card').forEach(c=>{const r=c.querySelector('input[type=radio]:checked');const n=c.querySelector('input[type=text]').value.trim();if(r||n)lines.push(`${c.dataset.f} (${c.dataset.id}): ${r?r.value:'-'}${n?' | '+n:''}`)});
 const txt=lines.length?document.title+' decisions:\n'+lines.join('\n'):document.title+': no decisions entered';
 const o=document.getElementById('out');o.value=txt;o.style.display='block';o.select();
 let ok=false;try{await navigator.clipboard.writeText(txt);ok=true}catch(e){try{ok=document.execCommand('copy')}catch(_){}}
 document.getElementById('msg').textContent=ok?`Copied ${lines.length} decisions: paste them into the chat`:'Copy the text below and paste it into the chat';
};
</script></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--title", default="Edit review")
    a = ap.parse_args()
    outdir = os.path.dirname(os.path.abspath(a.out))
    items, problems = [], []
    for d in a.dirs:
        path = os.path.join(d, "review.jsonl")
        if not os.path.exists(path):
            problems.append(f"no review.jsonl in {d}")
            continue
        with open(path, encoding="utf-8-sig") as f:
            for n, line in enumerate(f, 1):
                if not line.strip():
                    continue
                try:
                    p = json.loads(line)
                except ValueError as e:
                    problems.append(f"{path}:{n}: {e}")
                    continue
                if "id" not in p:
                    problems.append(f"{path}:{n}: missing id")
                    continue

                def rel(name):
                    full = os.path.join(d, name)
                    if not os.path.exists(full):
                        problems.append(f"missing file {full}")
                    try:
                        return os.path.relpath(full, outdir).replace("\\", "/")
                    except ValueError:  # another drive on Windows: no relative path exists
                        return pathlib.Path(os.path.abspath(full)).as_uri()

                pid = p["id"]
                b, af = f"{pid}-before.jpg", f"{pid}-after.jpg"
                items.append({
                    "id": pid, "key": f"{len(items)}", "file": p.get("file", str(pid)),
                    "title": p.get("title", ""), "changes": p.get("changes", []),
                    "before": rel(b) if os.path.exists(os.path.join(d, b)) else None,
                    "after": rel(af) if os.path.exists(os.path.join(d, af)) else None,
                    "crops": [[rel(c[0]), c[1] if len(c) > 1 else c[0]] for c in p.get("crops", [])],
                    "decide": p.get("decide"),
                    "section": (p.get("group") or "Needs your decision") if p.get("decide") else "Check that you like them",
                })
    # decision items first (keeping their groups together), then the rest; input order otherwise
    order = []
    for it in items:
        if it["decide"] and it["section"] not in order:
            order.append(it["section"])
    order.append("Check that you like them")
    items.sort(key=lambda it: order.index(it["section"]))
    data = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
    page = (PAGE.replace("__TITLE__", html.escape(a.title)).replace("__COUNT__", str(len(items)))
            .replace("__DATA__", data))
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(page)
    for p in problems:
        print("WARNING", p)
    print(f"wrote {a.out}: {len(items)} photos, {sum(1 for i in items if i['decide'])} to decide")
    sys.exit(0)


if __name__ == "__main__":
    main()
