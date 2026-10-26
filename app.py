import json, os, re, random, time, urllib.parse
from datetime import datetime
from html import escape as esc
import pandas as pd
import streamlit as st
from core import generate, transcribe, to_markdown

st.set_page_config(page_title="Minutes", page_icon="✦", layout="wide")


def get_key() -> str:
    """Find the key in Streamlit secrets, the environment, or a .streamlit folder next to app.py."""
    try:
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    try:
        import tomllib
        here = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(here, ".streamlit", "secrets.toml"), "rb") as f:
            return tomllib.load(f).get("GEMINI_API_KEY", "")
    except Exception:
        return ""


API_KEY = get_key()


def wave_html(n=28, cls=""):
    """Animated equalizer bars. Each bar gets its own height and delay."""
    rnd = random.Random(7)
    bars = "".join(f"<i style='--h:{rnd.randint(8, 30)}px;--d:{round(rnd.uniform(0, 1.2), 2)}s'></i>" for _ in range(n))
    return f"<div class='wave {cls}'>{bars}</div>"


def _up_icon_uri():
    """A simple upload arrow in gold, used in the audio drop box."""
    svg = ("<svg xmlns='http://www.w3.org/2000/svg' width='44' height='44' viewBox='0 0 24 24' fill='none' stroke='#E0B43A' "
           "stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'><path d='M12 16V4'/><path d='M7 9l5-5 5 5'/>"
           "<path d='M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3'/></svg>")
    return "data:image/svg+xml," + urllib.parse.quote(svg)


UP_URI = _up_icon_uri()


CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@500;600;700&family=DM+Sans:wght@400;500;700&display=swap');
:root { --bg:#100F0D; --card:#181612; --raise:#201D17; --line:#2E2A1F; --gold:#E0B43A; --gold2:#F0D58A; --txt:#F2EDE0; --mute:#9C947E; }

/* Base type: set on the root only. Forcing a font on every span/div breaks Streamlit's icon font. */
.stApp { background:var(--bg); color:var(--txt); font-family:'DM Sans',sans-serif; line-height:1.6; }
.stApp h1, .stApp h2, .stApp h3, .stApp h4 { font-family:'Outfit',sans-serif !important; color:var(--txt) !important; font-weight:600 !important; letter-spacing:-0.02em; }
.stApp p, .stApp li, .stApp label { color:var(--txt); }
.stApp [data-testid="stCaptionContainer"], .stApp [data-testid="stCaptionContainer"] p { color:var(--mute) !important; }
.stApp [data-testid="stIconMaterial"], .stApp span[class*="material-symbols"] { font-family:'Material Symbols Rounded' !important; }

[data-testid="stHeaderActionElements"], #MainMenu, footer { display:none; }
/* hide the Deploy button; the running indicator in the same toolbar stays */
.stAppDeployButton, [data-testid="stAppDeployButton"], [data-testid="stDeployButton"], .stDeployButton { display:none !important; }
header[data-testid="stHeader"] { background:transparent; }
.block-container { padding:1.2rem 2.5rem 4rem; max-width:1200px; }
.stApp [data-testid="stVerticalBlock"] { gap:1.25rem !important; }

/* sidebar */
section[data-testid="stSidebar"] { background:#0D0C0A; border-right:1px solid var(--line); }
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap:.8rem !important; }
.brand { font-family:'Outfit'; font-weight:700; font-size:1.4rem; display:flex; gap:.6rem; align-items:center; margin:.4rem 0 1.4rem; }
.brand b { display:inline-block; width:28px; height:28px; border-radius:8px; background:var(--gold); color:#000; text-align:center; line-height:28px; font-size:.95rem; }
.side-h { color:var(--mute); font-size:.85rem; margin:1.4rem 0 0; padding-bottom:1rem; font-weight:500; }

/* hero */
.hero { padding:.4rem 0 0; }
.hero h1 { font-size:2.85rem !important; line-height:1.1; margin:.9rem 0 .8rem; }
.hero h1 { color:var(--txt) !important; }
.hero h1 .gold { color:var(--gold); }
.hero p { color:var(--mute); font-size:1.02rem; max-width:34rem; margin:0; }
.pv { background:var(--card); border:1px solid var(--line); border-radius:16px; padding:1.1rem 1.2rem 1rem; box-shadow:8px 8px 0 rgba(224,180,58,.16); }
.pv-top { display:flex; justify-content:space-between; align-items:center; margin-bottom:.8rem; }
.pv-top b { font-family:'Outfit'; font-weight:600; font-size:1.05rem; }
.rec { color:var(--gold2); font-size:.8rem; display:flex; align-items:center; gap:.45rem; }
.rec::before { content:''; width:8px; height:8px; border-radius:50%; background:var(--gold); animation:pulse 1.4s ease-in-out infinite; }
.pv .wave { height:30px; margin-bottom:.9rem; }
.pv-row { display:flex; gap:.7rem; align-items:center; padding:.55rem .75rem; margin-bottom:.5rem; background:var(--raise); border:1px solid var(--line); border-radius:10px; font-size:.9rem; }
.pv-row i { flex:0 0 14px; height:14px; border-radius:50%; border:2px solid var(--gold); }
.pv-row span { flex:1; } .pv-row em { font-style:normal; color:var(--gold2); font-size:.82rem; }
.pv-foot { display:flex; justify-content:space-between; color:var(--mute); font-size:.82rem; margin-top:.7rem; }

/* section titles */
.sec-t { font-family:'Outfit'; font-weight:600; font-size:1.55rem; letter-spacing:-0.02em; margin:2.1rem 0 .3rem; }
.sec-s { color:var(--mute); margin:0 0 1.1rem; }
.sec-t.sm { font-size:1.15rem; margin:1.4rem 0 .8rem; }

/* cards */
.card, .kpi, .person, .step, .feat, .gc, [data-testid="stVerticalBlockBorderWrapper"] { background:var(--card); border:1px solid var(--line) !important; border-radius:16px; }
.card { padding:1.3rem 1.4rem; }
[data-testid="stVerticalBlockBorderWrapper"] { padding:1rem 1rem 1.4rem; }
.ch { display:flex; justify-content:space-between; align-items:center; margin-bottom:.9rem; font-family:'Outfit'; font-weight:600; font-size:1.05rem; }
.ch em { font-style:normal; font-family:'DM Sans'; font-size:.8rem; color:var(--mute); }
.chk { display:flex; gap:.7rem; margin-bottom:.8rem; font-size:.95rem; }
.chk i { flex:0 0 20px; height:20px; border-radius:50%; background:var(--gold); color:#14110A; font-style:normal; font-size:.75rem; font-weight:700; text-align:center; line-height:20px; margin-top:.15rem; }

/* how it works + features */
.steps, .feats { display:grid; grid-template-columns:repeat(3, 1fr); gap:1.1rem; }
.step { padding:1.3rem 1.4rem; }
.step .n { width:42px; height:42px; border-radius:50%; border:2px solid var(--gold); display:grid; place-items:center; font-family:'Outfit'; font-weight:600; color:var(--gold); font-size:1.1rem; margin-bottom:1rem; }
.step b, .feat b { display:block; font-size:1.05rem; margin-bottom:.3rem; }
.step span, .feat span { color:var(--mute); font-size:.95rem; }
.feat { padding:1.3rem 1.4rem; }
.feat .ic { width:46px; height:46px; border-radius:12px; background:var(--raise); border:1px solid var(--line); display:grid; place-items:center; margin-bottom:1rem; }
.feat svg { width:24px; height:24px; stroke:var(--gold); fill:none; stroke-width:1.7; stroke-linecap:round; stroke-linejoin:round; }

/* results */
.ptitle { font-family:'Outfit'; font-size:2.4rem; font-weight:600; letter-spacing:-0.02em; line-height:1.15; margin:.3rem 0 .2rem; }
.people { display:grid; grid-template-columns:repeat(auto-fit, minmax(250px, 1fr)); gap:1.1rem; }
.person { padding:1.1rem 1.2rem; }
.ph { display:flex; gap:.75rem; align-items:center; margin-bottom:.8rem; }
.ph b { display:block; line-height:1.2; } .ph small { color:var(--mute); }
.pt { display:flex; justify-content:space-between; gap:.8rem; padding:.55rem .7rem; margin-bottom:.5rem; background:var(--raise); border:1px solid var(--line); border-radius:10px; font-size:.92rem; }
.pt em { font-style:normal; color:var(--gold2); white-space:nowrap; font-size:.84rem; }
.pt.dn span { text-decoration:line-through; color:var(--mute); }
.pn { color:var(--mute); font-size:.92rem; }
.grid4 { display:grid; grid-template-columns:repeat(4, 1fr); gap:1.1rem; margin:1.6rem 0 1.8rem; }
.kpi { padding:1.1rem 1.3rem; }
.kpi small { color:var(--mute); font-size:.85rem; display:block; margin-bottom:.35rem; }
.kpi b { font-family:'Outfit'; font-size:2.1rem; font-weight:600; line-height:1; }
.chip { display:inline-block; border:1px solid var(--line); background:var(--raise); border-radius:99px; padding:.12rem .8rem; margin:.5rem .4rem 0 0; font-size:.88rem; }
.msg { display:flex; gap:.85rem; margin-bottom:1rem; }
.av { flex:0 0 36px; height:36px; border-radius:50%; background:var(--gold); color:#000; font-weight:700; text-align:center; line-height:36px; }
.msg b { display:block; font-size:.92rem; margin-bottom:.05rem; } .msg span { color:#D9D2BE; }
.scroll { max-height:330px; overflow:auto; padding-right:.5rem; }
.item { background:var(--raise); border:1px solid var(--line); border-radius:10px; padding:.8rem 1rem; margin-bottom:.7rem; }
.item b { display:block; margin-bottom:.1rem; } .item span { color:var(--mute); font-size:.92rem; }
.bar { height:6px; background:#2A261C; border-radius:99px; overflow:hidden; margin:.3rem 0 .9rem; }
.bar i { display:block; height:100%; background:var(--gold); border-radius:99px; }
.row { display:flex; justify-content:space-between; font-size:.92rem; }

.wave { display:flex; align-items:center; gap:3px; height:34px; }
.wave i { display:block; width:4px; height:var(--h, 20px); border-radius:3px; background:var(--gold); transform-origin:center; animation:eq 1.3s ease-in-out infinite; animation-delay:var(--d, 0s); }
.wave.big { height:52px; justify-content:center; }
.wave.big i { width:5px; }
.prog { display:flex; align-items:center; gap:1.2rem; }
.ring { position:relative; width:96px; height:96px; flex:0 0 96px; border-radius:50%; display:grid; place-items:center; background:conic-gradient(var(--gold) calc(var(--p) * 1%), #2A261C 0); }
.ring::before { content:''; position:absolute; inset:10px; border-radius:50%; background:var(--card); }
.ring b { position:relative; font-family:'Outfit'; font-size:1.25rem; font-weight:600; }
.prog .big { font-family:'Outfit'; font-size:1.5rem; font-weight:600; line-height:1.1; }
.prog span { color:var(--mute); font-size:.9rem; }
.stack { display:flex; height:12px; border-radius:99px; overflow:hidden; gap:2px; margin:.2rem 0 1.1rem; }
.stack i { display:block; height:100%; }
.dot { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:.55rem; }
.row { margin-bottom:.45rem; }
.work { background:var(--card); border:1px solid var(--line); border-radius:16px; padding:1.8rem 1.6rem 1.6rem; text-align:center; margin:.8rem 0 1.4rem; }
.work .wt { font-family:'Outfit'; font-weight:600; font-size:1.2rem; margin:.9rem 0 .8rem; }
.sweep { height:4px; background:#2A261C; border-radius:99px; overflow:hidden; max-width:340px; margin:0 auto 1rem; }
.sweep::after { content:''; display:block; width:40%; height:100%; background:var(--gold); border-radius:99px; animation:slide 1.6s ease-in-out infinite; }
.wsteps { display:flex; justify-content:center; gap:1.6rem; flex-wrap:wrap; }
.ws { color:var(--mute); font-size:.92rem; opacity:.35; animation:lit 5.4s ease-in-out infinite; animation-delay:calc(var(--i) * 1.8s); }
.ws::before { content:''; display:inline-block; width:8px; height:8px; border-radius:50%; background:var(--gold); margin-right:.5rem; }
@keyframes eq { 0%, 100% { transform:scaleY(.3); } 50% { transform:scaleY(1); } }
@keyframes float { 0%, 100% { transform:translateY(0); } 50% { transform:translateY(-9px); } }
@keyframes pulse { 0%, 100% { opacity:1; transform:scale(1); } 50% { opacity:.35; transform:scale(.7); } }
@keyframes slide { 0% { transform:translateX(-110%); } 100% { transform:translateX(280%); } }
@keyframes lit { 0%, 8% { opacity:.35; } 20%, 45% { opacity:1; } 60%, 100% { opacity:.35; } }
[data-testid="stAlert"] { margin-bottom:.6rem; }
/* Streamlit pulls the element after a markdown block up by about 1rem; this padding cancels it */
.mk { padding-bottom:1rem; }
.stk { display:flex; flex-direction:column; gap:1.25rem; }
/* the Share box: wrap long lines instead of cutting them off */
[data-testid="stCode"] pre, [data-testid="stCode"] code { white-space:pre-wrap !important; word-break:break-word; }
@media (prefers-reduced-motion: reduce) { .wave i, .rec::before, .pill2::before, .sweep::after, .ws, .bar i, .stack i, .ring, [data-baseweb="tab-panel"] { animation:none !important; } .ws { opacity:1; } }
/* hero pill */
.pill2 { display:inline-flex; align-items:center; gap:.55rem; border:1px solid var(--line); background:var(--raise); border-radius:99px; padding:.28rem 1rem .28rem .8rem; font-size:.86rem; color:var(--gold2); }
.pill2::before { content:''; width:7px; height:7px; border-radius:50%; background:var(--gold); animation:pulse 1.8s ease-in-out infinite; }
/* at a glance */
.glance { display:grid; grid-template-columns:repeat(3, 1fr); gap:1.1rem; margin-bottom:.4rem; }
.gc { padding:1rem 1.2rem; }
.gc-h { display:flex; align-items:center; gap:.55rem; color:var(--mute); font-size:.88rem; margin-bottom:.5rem; }
.gc-h svg { width:20px; height:20px; stroke:var(--gold); fill:none; stroke-width:1.7; stroke-linecap:round; stroke-linejoin:round; }
.gc b { display:block; font-family:'Outfit'; font-size:2rem; font-weight:600; line-height:1.05; }
.gc span { color:var(--mute); font-size:.85rem; }
.gc .bar { margin:.55rem 0 .35rem; }
/* sidebar menu */
.nav-h { color:var(--mute); font-size:.8rem; margin:1.2rem 0 0; padding-bottom:1rem; font-weight:500; }
section[data-testid="stSidebar"] [class*="st-key-nav_"] button { justify-content:flex-start !important; background:transparent !important; border:1px solid transparent !important; color:var(--mute) !important; padding:.5rem .85rem; }
section[data-testid="stSidebar"] [class*="st-key-nav_"] button:hover { background:var(--raise) !important; color:var(--txt) !important; border-color:var(--line) !important; }
section[data-testid="stSidebar"] [class*="__active"] button { background:var(--raise) !important; color:var(--gold2) !important; border-color:#4A4126 !important; box-shadow:inset 3px 0 0 var(--gold); }
section[data-testid="stSidebar"] [class*="st-key-nav_"] button, section[data-testid="stSidebar"] [class*="st-key-nav_"] button * { text-align:left !important; justify-content:flex-start !important; }
section[data-testid="stSidebar"] [class*="st-key-nav_"] button > div { width:100%; }
section[data-testid="stSidebar"] [class*="st-key-nav_"] { margin-bottom:-.35rem; }
/* meeting cards */
.mt { font-family:'Outfit'; font-weight:600; font-size:1.1rem; line-height:1.25; }
.mw { color:var(--mute); font-size:.85rem; margin-bottom:.3rem; }
.mm { color:var(--mute); font-size:.9rem; margin:.8rem 0 .2rem; }
/* gentle hover and motion */
.card, .kpi, .person, .step, .feat, .gc, .pv { transition:transform .22s ease, border-color .22s ease; }
.kpi:hover, .person:hover, .step:hover, .feat:hover, .gc:hover { transform:translateY(-3px); border-color:#4A4126 !important; }
.stApp button:not([role="tab"]):not(:disabled):hover { transform:translateY(-1px); }
[data-baseweb="tab-panel"] { animation:tabin .35s ease; }
.bar i, .stack i { transform-origin:left center; animation:grow .9s cubic-bezier(.2,.7,.2,1) both; }
.ring { animation:pop .6s ease both; }
@keyframes tabin { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:none; } }
@keyframes grow { from { transform:scaleX(0); } to { transform:scaleX(1); } }
@keyframes pop { from { opacity:0; transform:scale(.85); } to { opacity:1; transform:none; } }
@media (max-width:900px) { .steps, .feats, .glance { grid-template-columns:1fr; } .grid4 { grid-template-columns:repeat(2, 1fr); } .hero h1 { font-size:2.5rem !important; } }

/* buttons: gold fill only for the main action, everything else outlined */
.stApp button { border-radius:10px !important; font-weight:600 !important; transition:border-color .15s, background .15s; }
.stApp button p, .stApp button span { color:inherit !important; }
.stApp [data-testid="stBaseButton-secondary"], .stApp [data-testid="stBaseButton-secondaryFormSubmit"] { background:transparent !important; color:var(--txt) !important; border:1px solid #4A4126 !important; }
.stApp [data-testid="stBaseButton-secondary"]:hover { border-color:var(--gold) !important; color:var(--gold2) !important; background:rgba(224,180,58,.06) !important; }
.stApp [data-testid="stBaseButton-primary"] { background:var(--gold) !important; color:#14110A !important; border:1px solid var(--gold) !important; }
.stApp [data-testid="stBaseButton-primary"]:hover { background:var(--gold2) !important; border-color:var(--gold2) !important; }

/* inputs, uploader, expanders */
.stApp textarea, .stApp input { background:#0D0C0A !important; color:var(--txt) !important; border:1px solid var(--line) !important; border-radius:10px !important; }
.stApp textarea:focus, .stApp input:focus { border-color:var(--gold) !important; box-shadow:none !important; }
[data-testid="stFileUploaderDropzone"] { background:#0D0C0A !important; border:1px dashed #4A4126 !important; border-radius:12px; }
/* the audio drop box: simple icon, subtle dashed border, one gold button */
.st-key-aud_up [data-testid="stFileUploaderDropzone"] { background:#0D0C0A !important; border:1px dashed #4A4126 !important; border-radius:16px !important; min-height:190px; padding:1.5rem 1.4rem !important; display:flex !important; flex-direction:column !important; align-items:center !important; justify-content:center !important; text-align:center; gap:.7rem; transition:border-color .2s, background .2s; }
.st-key-aud_up [data-testid="stFileUploaderDropzone"]::before { order:-2; content:url("__UP__"); width:44px; height:44px; }
.st-key-aud_up [data-testid="stFileUploaderDropzone"]::after { order:-1; content:"Drop your recording here"; font-family:'Outfit'; font-weight:600; font-size:1.15rem; color:var(--txt); }
.st-key-aud_up [data-testid="stFileUploaderDropzone"]:hover { border-color:var(--gold) !important; background:#12100C !important; }
.st-key-aud_up [data-testid="stFileUploaderDropzoneInstructions"] { flex-direction:column !important; align-items:center !important; text-align:center; }
.st-key-aud_up [data-testid="stFileUploaderDropzone"] button { background:var(--gold) !important; color:#14110A !important; border:1px solid var(--gold) !important; padding:.5rem 1.5rem; }
.st-key-aud_up [data-testid="stFileUploaderDropzone"] button:hover { background:var(--gold2) !important; border-color:var(--gold2) !important; }
[data-testid="stFileUploaderDropzone"] small, [data-testid="stFileUploaderDropzoneInstructions"] span { color:var(--mute) !important; }
[data-testid="stFileUploaderFile"] * { color:var(--txt) !important; }
[data-testid="stExpander"] details { background:var(--card) !important; border:1px solid var(--line) !important; border-radius:12px !important; }
[data-testid="stExpander"] summary p { color:var(--txt) !important; font-weight:600; }

/* tabs */
.stApp button[role="tab"] { background:transparent !important; border:none !important; color:var(--mute) !important; }
.stApp button[role="tab"][aria-selected="true"] { color:var(--txt) !important; }
[data-baseweb="tab-highlight"] { background:var(--gold) !important; }
[data-baseweb="tab-border"] { background:var(--line) !important; }
</style>
"""
st.markdown(CSS.replace("__UP__", UP_URI), unsafe_allow_html=True)

SAMPLE = """Priya: Let's lock the launch for November 15th. Everyone okay with that?
Arjun: Yes. I'll finish the landing page by Friday.
Priya: Great. Meera, can you send the press kit to the partners?
Meera: Sure, I'll do that after the budget is approved.
Priya: Decision made, we are using Streamlit for the demo. Budget review is still pending."""

ss = st.session_state
ss.setdefault("text", ""); ss.setdefault("hist", []); ss.setdefault("rid", 0); ss.setdefault("txt_id", None)
ss.setdefault("page", "Overview"); ss.setdefault("show_tr", True); ss.setdefault("show_spk", True)


def lines_of(text):
    return [(a.strip(), b.strip()) for a, b in re.findall(r"^([A-Za-z][\w .'-]{0,30}):\s*(.+)$", text, flags=re.M)]


def bubbles(pairs):
    return "".join(f"<div class='msg'><div class='av'>{esc(n[0].upper())}</div><div><b>{esc(n)}</b><span>{esc(t)}</span></div></div>" for n, t in pairs)


def card(title, inner, tag=""):
    return f"<div class='card'><div class='ch'><span>{title}</span><em>{tag}</em></div>{inner}</div>"


def md(html):
    """Render HTML inside .mk. Streamlit pulls the next element up by 1rem after a markdown block,
    and the .mk padding gives that 1rem back, so blocks keep their normal gap."""
    st.markdown(f"<div class='mk'>{html}</div>", unsafe_allow_html=True)


def people_html(attendees, tasks):
    """One card per person with the tasks they own and when each is due."""
    by = {}
    for t in tasks:
        if t.get("task"):
            by.setdefault((t.get("owner") or "").strip().lower(), []).append(t)
    names, known = list(attendees), {a.lower() for a in attendees}
    for t in tasks:
        o = (t.get("owner") or "").strip()
        if o and o.lower() not in known:
            names.append(o); known.add(o.lower())

    def block(name, ts):
        rows = ""
        for t in ts:
            cls = "pt dn" if t.get("done") else "pt"
            due = esc(str(t["due_date"])) if t.get("due_date") else "No date"
            rows += f"<div class='{cls}'><span>{esc(str(t['task']))}</span><em>{due}</em></div>"
        rows = rows or "<div class='pn'>No tasks assigned</div>"
        plural = "" if len(ts) == 1 else "s"
        return (f"<div class='person'><div class='ph'><div class='av'>{esc(name[:1].upper())}</div>"
                f"<div><b>{esc(name)}</b><small>{len(ts)} task{plural}</small></div></div>{rows}</div>")

    cards = [block(n, by.get(n.lower(), [])) for n in names if n]
    if by.get(""):
        cards.append(block("Unassigned", by[""]))
    return "<div class='sec-t sm'>Who’s doing what</div><div class='people'>" + "".join(cards) + "</div>"


def working(title, steps):
    """Animated card shown while the model is busy."""
    rows = "".join(f"<div class='ws' style='--i:{i}'>{esc(s)}</div>" for i, s in enumerate(steps))
    return f"<div class='work'>{wave_html(34, 'big')}<div class='wt'>{esc(title)}</div><div class='sweep'></div><div class='wsteps'>{rows}</div></div>"


def run_transcribe(data, mime):
    ph = st.empty()
    ph.markdown(working("Listening to your recording", ["Reading the audio", "Telling speakers apart", "Writing the transcript"]), unsafe_allow_html=True)
    err = None
    started = time.time()
    try:
        text = transcribe(data, mime, API_KEY)
    except Exception as e:
        err = e
    secs = time.time() - started
    ph.empty()
    if err:
        st.error(f"Transcription failed after {secs:.0f}s: {err}")
    else:
        ss["text"] = text
        st.success(f"Transcript ready in {secs:.1f}s. Check it in the Paste transcript tab, then create the minutes.")


def input_panel():
    t1, t2, t3 = st.tabs(["Upload recording", "Record live", "Paste transcript"])
    with t1:
        audio = st.file_uploader("Audio file (up to about 15 MB)", type=["mp3", "wav", "m4a", "aac", "ogg", "flac"], key="aud_up")
        if audio and st.button("Transcribe recording", key="tr_up"):
            run_transcribe(audio.getvalue(), audio.type)
    with t2:
        if hasattr(st, "audio_input"):
            rec = st.audio_input("Record the meeting")
            if rec and st.button("Transcribe recording", key="tr_rec"):
                run_transcribe(rec.getvalue(), "audio/wav")
        else:
            st.info("Live recording needs a newer Streamlit. Run: pip3 install -U streamlit")
    with t3:
        c1, c2 = st.columns(2)
        if c1.button("Try a sample meeting", key="sample"):
            ss["text"] = SAMPLE
        up = c2.file_uploader("Upload a .txt transcript", type="txt", label_visibility="collapsed")
        # load the file once per new upload, so later edits in the box are not overwritten
        if up and ss["txt_id"] != f"{up.name}-{up.size}":
            ss["txt_id"] = f"{up.name}-{up.size}"
            ss["text"] = up.getvalue().decode("utf-8", errors="ignore")
        st.text_area("Transcript", key="text", height=180)
    if st.button("Create minutes", type="primary", key="create"):
        if not ss["text"].strip():
            st.warning("Add a transcript or transcribe a recording first.")
        else:
            ph = st.empty()
            ph.markdown(working("Writing your minutes", ["Reading the transcript", "Finding decisions", "Matching tasks to owners"]), unsafe_allow_html=True)
            err = None
            try:
                mom = generate(ss["text"], API_KEY)
            except Exception as e:
                err = e
            ph.empty()
            if err:
                st.error(f"Could not create the minutes: {err}")
            else:
                ss["mom"] = mom; ss["rid"] += 1
                ss["hist"].insert(0, {"mom": mom, "text": ss["text"], "when": datetime.now().strftime("%d %b, %H:%M")})
                st.rerun()


# ---------- sidebar ----------
PAGES = [("Overview", ":material/dashboard:"), ("All meetings", ":material/groups:"),
         ("Tasks", ":material/task_alt:"), ("Settings", ":material/settings:")]


def plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


with st.sidebar:
    st.markdown("<div class='brand'><b>✦</b>Minutes</div>", unsafe_allow_html=True)
    if st.button("＋ New meeting", type="primary", width="stretch", key="new_meeting"):
        ss["text"] = ""; ss.pop("mom", None); ss["page"] = "Overview"; st.rerun()
    st.markdown("<div class='nav-h'>Menu</div>", unsafe_allow_html=True)
    for name, icon in PAGES:
        slug = name.lower().replace(" ", "_")
        # the active page gets "__active" in its key, which the CSS uses to highlight it
        if st.button(name, icon=icon, width="stretch", key=f"nav_{slug}" + ("__active" if ss["page"] == name else "")):
            ss["page"] = name; st.rerun()
    if not API_KEY:
        st.warning("No API key found. Add GEMINI_API_KEY to .streamlit/secrets.toml, then restart the app.")
    st.markdown("<div class='side-h'>Recent minutes</div>", unsafe_allow_html=True)
    if not ss["hist"]:
        st.caption("Your meetings will show up here.")
    for i, h in enumerate(ss["hist"][:5]):
        if st.button(h["mom"]["title"][:28], key=f"h{i}", width="stretch"):
            ss["mom"], ss["text"] = h["mom"], h["text"]; ss["rid"] += 1; ss["page"] = "Overview"; st.rerun()

m = ss.get("mom")
ICON_CAL = "<rect x='4' y='5' width='16' height='15' rx='2'/><path d='M4 10h16M9 3v4M15 3v4'/>"
ICON_TASK = "<rect x='4' y='4' width='16' height='16' rx='3'/><path d='M9 12l2 2 4-4'/>"
ICON_FLAG = "<path d='M6 21V4'/><path d='M6 5h11l-2 4 2 4H6'/>"


def glance_html(hist):
    """Meetings, tasks and decisions across everything created so far."""
    n_m = len(hist)
    tasks_all = [t for h in hist for t in h["mom"]["action_items"]]
    n_t = len(tasks_all)
    n_d = sum(len(h["mom"]["decisions"]) for h in hist)
    owned = round(100 * sum(1 for t in tasks_all if t.get("owner")) / n_t) if n_t else 0
    last = f"Last: {esc(hist[0]['mom']['title'][:26])}" if hist else "Create your first one below"
    own_txt = f"{owned}% have an owner" if n_t else "Tasks will show up here"
    dec_txt = f"Across {plural(n_m, 'meeting')}" if n_m else "Decisions will show up here"

    def gc(icon, label, big, extra, sub):
        return (f"<div class='gc'><div class='gc-h'><svg viewBox='0 0 24 24'>{icon}</svg>{label}</div>"
                f"<b>{big}</b>{extra}<span>{sub}</span></div>")

    return ("<div class='mk'><div class='glance'>"
            + gc(ICON_CAL, "Meetings", n_m, "", last)
            + gc(ICON_TASK, "Tasks", n_t, f"<div class='bar'><i style='width:{owned}%'></i></div>", own_txt)
            + gc(ICON_FLAG, "Decisions", n_d, "", dec_txt)
            + "</div></div>")


# ================= OTHER PAGES =================
def page_meetings():
    st.markdown("<div class='mk'><div class='ptitle'>All meetings</div>"
                "<div class='sec-s'>Every meeting you have created in this session.</div></div>", unsafe_allow_html=True)
    hist = ss["hist"]
    if not hist:
        md(card("No meetings yet", "<div class='pn'>Create your first minutes from a recording or a transcript.</div>"))
        if st.button("Start a meeting", type="primary", key="empty_start"):
            ss["page"] = "Overview"; st.rerun()
        return
    # one row of three cards at a time, so cards in a row line up and the gaps stay even
    for start in range(0, len(hist), 3):
        cols = st.columns(3, gap="medium")
        for j, h in enumerate(hist[start:start + 3]):
            i, mom = start + j, h["mom"]
            with cols[j]:
                with st.container(border=True):
                    chips = "".join(f"<span class='chip'>{esc(p)}</span>" for p in mom["attendees"][:4])
                    st.markdown(f"<div class='mk'><div class='mt'>{esc(mom['title'])}</div><div class='mw'>{esc(h.get('when', ''))}</div>{chips}"
                                f"<div class='mm'>{plural(len(mom['action_items']), 'task')}, {plural(len(mom['decisions']), 'decision')}</div></div>",
                                unsafe_allow_html=True)
                    if st.button("Open", key=f"open{i}", width="stretch"):
                        ss["mom"], ss["text"] = mom, h["text"]; ss["rid"] += 1; ss["page"] = "Overview"; st.rerun()


def page_tasks():
    st.markdown("<div class='mk'><div class='ptitle'>Tasks</div>"
                "<div class='sec-s'>Every action item from every meeting, in one list. Tick tasks off inside each meeting.</div></div>", unsafe_allow_html=True)
    rows = [{"Meeting": h["mom"]["title"], "Task": t["task"], "Owner": t.get("owner") or "Unassigned",
             "Due": t.get("due_date") or "No date", "Quote": t.get("evidence") or ""}
            for h in ss["hist"] for t in h["mom"]["action_items"]]
    if not rows:
        md(card("No tasks yet", "<div class='pn'>Tasks from your meetings will be collected here.</div>"))
        return
    df = pd.DataFrame(rows)
    f1, f2 = st.columns([2, 1], gap="large")
    pick = f1.multiselect("Owner", sorted(df["Owner"].unique()), placeholder="All owners")
    gaps = f2.toggle("Only tasks with no due date")
    view = df[df["Owner"].isin(pick)] if pick else df
    if gaps:
        view = view[view["Due"] == "No date"]
    n_no_owner = int((view["Owner"] == "Unassigned").sum()); n_no_due = int((view["Due"] == "No date").sum())
    st.markdown("<div class='mk'><div class='glance'>"
                f"<div class='gc'><div class='gc-h'><svg viewBox='0 0 24 24'>{ICON_TASK}</svg>Showing</div><b>{len(view)}</b><span>of {len(df)} tasks</span></div>"
                f"<div class='gc'><div class='gc-h'><svg viewBox='0 0 24 24'>{ICON_FLAG}</svg>No owner</div><b>{n_no_owner}</b><span>Nobody was named</span></div>"
                f"<div class='gc'><div class='gc-h'><svg viewBox='0 0 24 24'>{ICON_CAL}</svg>No due date</div><b>{n_no_due}</b><span>No deadline was mentioned</span></div>"
                "</div></div>", unsafe_allow_html=True)
    st.dataframe(view, width="stretch", hide_index=True)


def page_settings():
    st.markdown("<div class='mk'><div class='ptitle'>Settings</div>"
                "<div class='sec-s'>Preferences and your data.</div></div>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("#### Preferences")
        st.toggle("Show the transcript on results", key="show_tr")
        st.toggle("Show the “Who spoke” chart", key="show_spk")
    with st.container(border=True):
        st.markdown("#### Your data")
        st.caption(f"{plural(len(ss['hist']), 'meeting')} kept for this session. Closing the app clears them, so download anything you want to keep.")
        d1, d2 = st.columns(2, gap="large")
        d1.download_button("Download all meetings (.json)", json.dumps([h["mom"] for h in ss["hist"]], indent=2),
                           "all_meetings.json", width="stretch", disabled=not ss["hist"])
        if d2.button("Clear all meetings", width="stretch", key="clear_all", disabled=not ss["hist"]):
            ss["hist"] = []; ss.pop("mom", None); ss["text"] = ""; st.rerun()


page = ss["page"]
if page == "All meetings":
    page_meetings(); st.stop()
if page == "Tasks":
    page_tasks(); st.stop()
if page == "Settings":
    page_settings(); st.stop()

# ================= OVERVIEW: LANDING =================
if not m:
    hl, hr = st.columns([1.7, 1], gap="large")
    hl.markdown("<div class='mk'><div class='hero'><div class='pill2'>Recording</div>"
                "<h1>Turn messy conversations into <span class='gold'>clear action.</span></h1>"
                "<p>Upload a recording, record live, or paste a transcript. Get a clear summary, the decisions, "
                "and who owes what, with proof for every task.</p></div></div>", unsafe_allow_html=True)
    hr.markdown("<div class='mk'><div class='pv'><div class='pv-top'><b>Launch planning</b><span class='rec'>Recording · 24:18</span></div>" + wave_html(34)
                + "<div class='pv-row'><i></i><span><b>Arjun</b> finishes the landing page</span><em>Friday</em></div>"
                "<div class='pv-row'><i></i><span><b>Meera</b> sends the press kit</span><em>After budget</em></div>"
                "<div class='pv-row'><i></i><span><b>Priya</b> locks the launch date</span><em>Nov 15</em></div>"
                "<div class='pv-foot'><span>3 action items found</span><span>1 decision</span></div></div></div>", unsafe_allow_html=True)

    a, b = st.columns([1.7, 1], gap="large")
    with a:
        st.markdown(glance_html(ss["hist"]), unsafe_allow_html=True)
        with st.container(border=True):
            input_panel()
    chk = "".join(f"<div class='chk'><i>✓</i><span>{t}</span></div>" for t in [
        "A short summary of what was discussed",
        "Every decision, listed on its own",
        "Tasks with the owner and due date that were actually said",
        "A quote from the transcript as proof for each task",
        "Export as Markdown, CSV or JSON"])
    with b:
        md(card("What you get", chk))

    st.markdown("<div class='mk'><div class='sec-t'>How it works</div><div class='sec-s'>From a messy recording to a clean task list in three steps.</div>"
                "<div class='steps'>"
                "<div class='step'><div class='n'>1</div><b>Capture</b><span>Upload a recording, record the meeting live, or paste a transcript.</span></div>"
                "<div class='step'><div class='n'>2</div><b>Analyse</b><span>Minutes reads the conversation and picks out decisions, tasks, owners and open questions.</span></div>"
                "<div class='step'><div class='n'>3</div><b>Organise</b><span>Edit anything, tick off tasks as they get done, then share or export the minutes.</span></div>"
                "</div></div>", unsafe_allow_html=True)

    st.markdown("<div class='mk'><div class='sec-t'>Built for follow-through</div><div class='sec-s'>Everything you need to leave a meeting knowing who does what.</div>"
                "<div class='feats'>"
                "<div class='feat'><div class='ic'><svg viewBox='0 0 24 24'><circle cx='9' cy='8' r='3.2'/><path d='M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6'/><circle cx='17.5' cy='9' r='2.4'/><path d='M16 14.2c2.9.2 5 2.3 5 5.8'/></svg></div><b>Who’s doing what</b><span>Every person gets their own list of tasks and deadlines.</span></div>"
                "<div class='feat'><div class='ic'><svg viewBox='0 0 24 24'><path d='M12 3l7 3v5c0 4.5-3 8.2-7 10-4-1.8-7-5.5-7-10V6z'/><path d='M9 12l2 2 4-4'/></svg></div><b>Nothing invented</b><span>Owners and due dates are kept only when someone actually said them.</span></div>"
                "<div class='feat'><div class='ic'><svg viewBox='0 0 24 24'><path d='M5 8h5v5H7c0 2 1 3 3 3'/><path d='M14 8h5v5h-3c0 2 1 3 3 3'/></svg></div><b>Proof for every task</b><span>Each task carries a quote from the transcript so you can check it.</span></div>"
                "<div class='feat'><div class='ic'><svg viewBox='0 0 24 24'><path d='M6 21V4'/><path d='M6 5h11l-2 4 2 4H6'/></svg></div><b>Gaps flagged</b><span>See which tasks have no owner or no due date, and which questions are still open.</span></div>"
                "<div class='feat'><div class='ic'><svg viewBox='0 0 24 24'><path d='M4 20l1-4L16 5l3 3L8 19z'/><path d='M14 7l3 3'/></svg></div><b>Fully editable</b><span>Fix a name, change a date, or add a task before you share.</span></div>"
                "<div class='feat'><div class='ic'><svg viewBox='0 0 24 24'><path d='M21 3L10 14'/><path d='M21 3l-7 18-4-7-7-4z'/></svg></div><b>Ready to send</b><span>Copy a short message for chat, or download Markdown, CSV or JSON.</span></div>"
                "</div></div>", unsafe_allow_html=True)

    md("<div class='sec-t'>Good to know</div>")
    with st.expander("Does Minutes guess owners or dates?"):
        st.write("No. An owner or due date is kept only if that wording appears in the transcript. Otherwise it shows as missing, so you can fill it in.")
    with st.expander("Which recordings work?"):
        st.write("MP3, WAV, M4A, AAC, OGG and FLAC, up to about 15 MB. For a longer meeting, split the file or paste a transcript instead.")
    with st.expander("How should I label speakers in a transcript?"):
        st.write("Start each line with the speaker's name and a colon, like “Priya: Let's lock the date.” This lets Minutes show who spoke and how much.")
    with st.expander("What happens to my meeting?"):
        st.write("Recordings and transcripts are sent to Google's Gemini API to be processed. Minutes keeps your results only for the current session, so download anything you want to keep.")
    st.stop()

# ================= RESULTS =================
rid = ss["rid"]
md(f"<div class='ptitle'>{esc(m['title'])}</div>")
top = st.empty()
left, right = st.columns([1.7, 1], gap="large")

owner_opts = list(m["attendees"])
for t in m["action_items"]:
    if t.get("owner") and t["owner"] not in owner_opts:
        owner_opts.append(t["owner"])

with left:
    with st.container(border=True):
        st.markdown("#### Summary")
        summary = st.text_area("Summary", m["summary"], height=120, label_visibility="collapsed", key=f"sum{rid}")
        if m["topics"]:
            st.markdown("".join(f"<span class='chip'>{esc(t)}</span>" for t in m["topics"]), unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("#### Decisions")
        dec = st.data_editor(pd.DataFrame({"decision": m["decisions"]}), num_rows="dynamic", width="stretch", key=f"dec{rid}")
    with st.container(border=True):
        st.markdown("#### Action items")
        df = pd.DataFrame(m["action_items"], columns=["task", "owner", "due_date", "evidence"])
        df.insert(0, "done", False)
        owner_col = (st.column_config.SelectboxColumn("Owner", options=owner_opts) if owner_opts
                     else st.column_config.TextColumn("Owner"))
        act = st.data_editor(df, num_rows="dynamic", width="stretch", key=f"act{rid}", column_config={
            "done": st.column_config.CheckboxColumn("Done", width="small"),
            "task": st.column_config.TextColumn("Task", width="large"),
            "owner": owner_col,
            "due_date": st.column_config.TextColumn("Due"),
            "evidence": st.column_config.TextColumn("Quote from transcript"),
        })
    pairs = lines_of(ss["text"])
    if pairs and ss["show_tr"]:
        md(card("Transcript", f"<div class='scroll'>{bubbles(pairs)}</div>", f"{len(pairs)} lines"))

tasks = [{k: (None if (v is None or v == "" or (isinstance(v, float) and pd.isna(v))) else v) for k, v in r.items()} for r in act.to_dict("records")]
decisions = [d for d in dec["decision"].dropna() if d]
done = sum(1 for t in tasks if t.get("done"))
pct = round(100 * done / len(tasks)) if tasks else 0
no_owner = sum(1 for t in tasks if not t.get("owner")); no_due = sum(1 for t in tasks if not t.get("due_date"))
out = dict(m, summary=summary, decisions=decisions, action_items=tasks)

kp = "".join(f"<div class='kpi'><small>{l}</small><b>{v}</b></div>" for l, v in
             [("Decisions", len(decisions)), ("Action items", len(tasks)), ("People", len(m["attendees"])), ("Tasks done", f"{pct}%")])
top.markdown("<div class='mk'>" + people_html(m["attendees"], tasks) + f"<div class='grid4'>{kp}</div></div>", unsafe_allow_html=True)

words = {}
for n, t in pairs:
    words[n] = words.get(n, 0) + len(t.split())
total = sum(words.values()) or 1
shades = ["#E0B43A", "#F0D58A", "#B98F24", "#8F6E1B", "#6B5313"]
segs, legend = "", ""
for i, (n, w) in enumerate(sorted(words.items(), key=lambda x: -x[1])):
    p, c = round(100 * w / total), shades[i % len(shades)]
    segs += f"<i style='width:{p}%;background:{c}'></i>"
    legend += f"<div class='row'><span><b class='dot' style='background:{c}'></b>{esc(n)}</span><span>{p}%</span></div>"
share = f"<div class='stack'>{segs}</div>{legend}" if words else "<span style='color:#9C947E'>Speaker labels not found.</span>"
attn = (f"<div class='item'><b>{no_owner} without an owner</b><span>Nobody was named for these tasks.</span></div>"
        f"<div class='item'><b>{no_due} without a due date</b><span>No deadline was mentioned.</span></div>")
if m["open_questions"]:
    attn += "<div class='item'><b>Open questions</b>" + "".join(f"<span>• {esc(q)}</span><br>" for q in m["open_questions"]) + "</div>"

prog = (f"<div class='prog'><div class='ring' style='--p:{pct}'><b>{pct}%</b></div>"
        f"<div><div class='big'>{done} of {len(tasks)}</div><span>tasks done</span></div></div>")

with right:
    st.markdown("<div class='mk'><div class='stk'>" + card("Needs attention", attn) + card("Progress", prog)
                + (card("Who spoke", share, "by words") if ss["show_spk"] else "") + "</div></div>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("#### Share")
        msg = f"*{m['title']}*\n{summary}\n\nDecisions:\n" + "\n".join(f"• {d}" for d in decisions) + "\n\nTasks:\n" + "\n".join(
            f"• {t['task']}" + (f" ({t['owner']})" if t.get("owner") else "") + (f" - {t['due_date']}" if t.get("due_date") else "") for t in tasks if t.get("task"))
        st.code(msg, language=None)
    with st.container(border=True):
        st.markdown("#### Export")
        st.download_button("Minutes (.md)", to_markdown(out), "minutes.md", width="stretch")
        st.download_button("Tasks (.csv)", act.to_csv(index=False), "tasks.csv", width="stretch")
        st.download_button("Data (.json)", json.dumps(out, indent=2), "minutes.json", width="stretch")

st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)
with st.expander("Edit the transcript or start another meeting"):
    input_panel()