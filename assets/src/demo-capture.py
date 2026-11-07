"""Capture the README demo: job-agent filling a live Greenhouse form in your own Chrome.

Drives one tab through chrome-devtools-axi (CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1),
reads each field from the page, fills it, and saves a screenshot plus the field's
bounding rect after every action. It never presses Submit or Enter: the last
frame hovers the Submit button. demo-compose.py turns the frames into the GIF.

    python3 demo-capture.py values.json <out_dir>

values.json (kept out of the repo) holds the applicant's answers:
    {"first": "...", "last": "...", "email": "...", "phone": "...",
     "phone_shown": "(555) 555-0100", "city": "...", "school": "...",
     "github": "...", "resume": "/abs/path.pdf", "why": "...", "project": "..."}
Run it from a directory that contains the resume, so the browser MCP may upload it.
"""
import json, os, re, subprocess, sys, time

V = json.load(open(sys.argv[1]))
OUTDIR = os.path.abspath(sys.argv[2])
WORKSPACE = os.path.dirname(os.path.abspath(V["resume"]))
HIDE = '(()=>{const kill=()=>{document.querySelectorAll(\'.simplify-jobs-shadow-root,speedyapply-modal,bettercanvas-reminders,[id*=simplify i]:not(script),[class*=simplify i],.grecaptcha-badge,iframe[src^="chrome-extension://"]\').forEach(e=>{if(e.classList&&e.classList.contains(\'grecaptcha-badge\')){e.style.visibility=\'hidden\';return}e.remove()});document.querySelectorAll(\'body > *\').forEach(e=>{if(e.shadowRoot&&!e.id?.startsWith(\'app\')){const s=getComputedStyle(e);if(s.position===\'fixed\'||e.tagName.includes(\'-\'))e.remove()}});document.documentElement.style.marginRight=\'0\';document.body.style.marginRight=\'0\';};kill();if(!window.__k){window.__k=new MutationObserver(kill);window.__k.observe(document.documentElement,{childList:true,subtree:true});const s=document.createElement(\'style\');s.textContent=\'.simplify-jobs-shadow-root,speedyapply-modal,bettercanvas-reminders,iframe[src^="chrome-extension://"]{display:none!important}.grecaptcha-badge{visibility:hidden!important}html,body{margin-right:0!important}html{scrollbar-width:none}::-webkit-scrollbar{display:none}\';document.head.appendChild(s);}return [...document.querySelectorAll(\'body > *\')].map(e=>e.tagName+\'#\'+e.id+\'.\'+String(e.className).slice(0,30)).join(\' ; \')})()'
ENV = dict(os.environ, CHROME_DEVTOOLS_AXI_AUTO_CONNECT="1", CHROME_DEVTOOLS_AXI_SESSION="jobagent-demo")
def run(*args, timeout=90):
    r = subprocess.run(["chrome-devtools-axi", *args], env=ENV, cwd=WORKSPACE, capture_output=True, text=True, timeout=timeout)
    return r.stdout + r.stderr
def js(expr):
    out = run("eval", expr)
    m = re.search(r"result: (.*?)(\nhelp|\Z)", out, re.S)
    if not m: raise RuntimeError(out)
    s = m.group(1).strip()
    try:
        v = json.loads(s)
        if isinstance(v, str):
            try: return json.loads(v)
            except Exception: return v
        return v
    except Exception:
        return s
def snap(): return run("snapshot")
def uid_for(pattern, text=None):
    text = text or snap()
    for line in text.splitlines():
        if re.search(pattern, line):
            m = re.search(r"uid=(\S+)", line)
            if m: return m.group(1)
    return None

import json, re, time, os, sys
CAP = os.path.join(OUTDIR, "frames"); os.makedirs(CAP, exist_ok=True)
json.dump({"company": "Vercel", "role": "Software Engineering Intern"}, open(os.path.join(OUTDIR, "meta.json"), "w"))
MAN = []; N = [0]
RESUME = os.path.abspath(V["resume"])
RECTS_JS = """(()=>{const R=e=>{if(!e)return null;const r=e.getBoundingClientRect();return [r.x,r.y,r.width,r.height]};const q=s=>document.querySelector(s);
const ctl=id=>{const e=document.getElementById(id);return e?(e.closest('.select__control')||e):null};
const sel=%s;let t=null;if(sel){t=R(sel)}
const menus=[...document.querySelectorAll('[id$=-listbox]')].map(R);
return {t, masks:[R(q('#email')),R(q('#phone')),R(ctl('candidate-location'))].filter(Boolean), loc_menu:R(q('#react-select-candidate-location-listbox')), sy:scrollY}})()"""
def rects(target_js="null"):
    return js(RECTS_JS % target_js)
def shot(label, status, target_js="null", kind="frame", extra=None):
    js(HIDE); time.sleep(0.25)
    info = rects(target_js)
    N[0] += 1
    f = f"{CAP}/f{N[0]:04d}.png"
    run("screenshot", f)
    e = dict(img=f, label=label, status=status, kind=kind, **info)
    if extra: e.update(extra)
    MAN.append(e)
    json.dump(MAN, open(os.path.join(OUTDIR, "manifest.json"),"w"), indent=1)
    return e
def ensure_view(target_js):
    r = js("(()=>{const e=%s;const r=e.getBoundingClientRect();return [r.y,r.height]})()" % target_js)
    y, h = r
    if y < 150 or y + h > 620:
        js("window.scrollTo({top:scrollY+%f-220,behavior:'instant'})" % y)
        time.sleep(0.3)
        return True
    return False
def el(id_): return "document.getElementById('%s')" % id_
def ctl(id_): return "(document.getElementById('%s').closest('.select__control'))" % id_
def chunks(s, n):
    k = max(1, -(-len(s)//n)); return [s[i:i+k] for i in range(0, len(s), k)]

def text_field(id_, label_pat, value, status, n=4):
    t = el(id_)
    if ensure_view(t): shot("scroll", status, t, "scroll")
    shot("move", status, t, "move")
    js("(()=>{const e=%s;e.scrollIntoView({block:'nearest',behavior:'instant'});e.focus();e.click();return 1})()" % t)
    assert js("document.activeElement.id") == id_, ("focus", id_, js("document.activeElement.id"))
    js("(()=>{const e=%s;const p=Object.getPrototypeOf(e);Object.getOwnPropertyDescriptor(p,'value').set.call(e,'');e.dispatchEvent(new Event('input',{bubbles:true}));return 1})()" % t)
    typed = ""
    for c in chunks(value, n):
        assert js("document.activeElement.id") == id_, ("focus lost", id_)
        run("type", c); typed += c
        shot("type", status, t, "type", dict(typed=len(typed)))
    v = js(t + ".value")
    if v != value:
        print("MISMATCH", id_, repr(v)); print(run("fill", "@"+uid_for(label_pat), value)[:200])
        v = js(t + ".value"); print(" after fill:", repr(v))
        MAN[-1]["redo"]=True
        shot("type", status, t, "type")

def combo(id_, label_pat, option, status, filt=None, wait=0.4):
    t = ctl(id_)
    if ensure_view(t): shot("scroll", status, t, "scroll")
    shot("move", status, t, "move")
    for attempt in range(3):
        u = uid_for(r'combobox "' + label_pat); run("click", "@"+u); time.sleep(wait)
        if filt:
            if js("document.activeElement.id") != id_:
                js("document.getElementById('%s').focus()" % id_); time.sleep(0.2)
            assert js("document.activeElement.id") == id_, ("combo focus", id_, js("document.activeElement.id"))
            run("type", filt); time.sleep(1.5 if id_=="candidate-location" else 0.4)
        snapt = snap()
        if re.search(r'option "', snapt): break
        run("press", "Escape"); time.sleep(0.3)
    opt_js = "([...document.querySelectorAll('#react-select-%s-listbox [role=option]')].find(x=>{const t=x.innerText.trim();return t===%s||(%s&&t.startsWith(%s))}))" % (id_, json.dumps(option), "true" if filt else "false", json.dumps(option))
    if not js("!!" + opt_js): print("NO OPTION", id_, option, re.findall(r'option "([^"]*)"', snapt)[:10]); sys.exit(1)
    js("(()=>{const o=%s;o.scrollIntoView({block:'nearest'});return 1})()" % opt_js)
    shot("menu", status, opt_js, "menu")
    js("(()=>{const o=%s;o.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));o.click();return 1})()" % opt_js); time.sleep(0.7)
    got = js("(()=>{const c=%s;const v=c.querySelector('.select__single-value');return v?v.innerText:''})()" % t)
    print("PICK", id_, repr(got))
    if not got or (not filt and got != option):
        print("PICK FAILED", id_, got); sys.exit(1)
    shot("picked", status, t, "picked")

S = "Filling"
steps = sys.argv[1:] or ["all"]
run("emulate","--viewport","960x800x1"); run("reload"); time.sleep(5)
js(HIDE)
for _ in range(10):
    time.sleep(1); js(HIDE)
    pass
js("window.scrollTo({top:0,behavior:'instant'})"); time.sleep(0.3)
shot("open", "Opening posting", "null", "hold")
js("window.scrollTo({top:document.getElementById('first_name').getBoundingClientRect().top+scrollY-260,behavior:'instant'})"); time.sleep(0.3)
shot("read", "Reading form · 22 fields", "document.getElementById('application-form')||document.forms[0]", "read")
text_field("first_name", r'textbox "First Name"', V["first"], "Contact details", 2)
text_field("last_name", r'textbox "Last Name"', V["last"], "Contact details", 1)
text_field("email", r'textbox "Email"', V["email"], "Contact details", 3)
combo("country", "Country", "United States", "Contact details", filt="United States")
text_field("phone", r'textbox "Phone"', V["phone"], "Contact details", 3)
combo("candidate-location", r"Location \(City\)", V["city"], "Contact details", filt=V["city"])
# resume
t = el("resume")
tgt = "([...document.querySelectorAll('form *')].find(x=>x.childElementCount<3&&/^Resume\\/CV/.test(x.innerText||''))?.parentElement)"
if ensure_view(tgt): shot("scroll", "Uploading resume", tgt, "scroll")
shot("move", "Uploading resume", "[...document.querySelectorAll('button')].find(b=>b.innerText.trim()==='Attach')", "move")
u = uid_for(r'button "Attach" value="No file chosen"'); print(run("upload", "@"+u, RESUME)[-300:]); time.sleep(2)
shot("uploaded", "Uploading resume", tgt, "picked")
combo("school--0", "School", V["school"], "Education", filt=V["school"])
combo("end-month--0", "End date month", "May", "Education")
text_field("end-year--0", r'spinbutton "End date year"', "2028", "Education", 1)
combo("question_19871182004", "Are you currently based", "United States", "Eligibility")
combo("question_19871183004", "Will you require Visa", "No", "Eligibility")
combo("question_19871184004", "Your authorization", "I am authorized to work in the country due to my nationality", "Eligibility")
combo("question_19871185004", "Do you live in one", "No", "Eligibility")
combo("question_19908490004", "Please confirm which term", "Summer 2027", "Eligibility")
text_field("question_19908491004", r'textbox "Why are you interested', V["why"], "Writing answer", 9)
text_field("question_19908511004", r'textbox "What’s your favorite', V["project"], "Writing answer", 7)
text_field("question_19871188004", r'textbox "Github"', V["github"], "Links", 3)
combo("question_19871190004", "Where did you first hear", "Other job boards", "Final questions")
combo("question_19871191004", "By submitting my application", "Acknowledge/Confirm", "Final questions")
combo("question_19871192004", "Please double-check", "I have reviewed and confirmed that all the information provided is accurate and complete.", "Final questions")
combo("question_19908985004", "Do you expect to graduate", "Yes", "Final questions")
# read back
vals = js("""(()=>{const o={};document.querySelectorAll('form input,form textarea').forEach(e=>{if(e.id&&e.type!=='file')o[e.id]=e.value});o.singles=[...document.querySelectorAll('.select__single-value')].map(x=>x.innerText);o.files=[...document.querySelectorAll('form')].map(f=>f.innerText.match(/\\S+\\.pdf/g));return o})()""")
json.dump(vals, open(os.path.join(OUTDIR, "readback.json"),"w"), indent=1)
EXP = {"first_name":V["first"],"last_name":V["last"],"email":V["email"],"phone":V["phone_shown"],"end-year--0":"2028","question_19871188004":V["github"],"question_19908491004":V["why"],"question_19908511004":V["project"]}
bad = {k:(vals.get(k),v) for k,v in EXP.items() if vals.get(k)!=v}
print("READBACK", "OK" if not bad else bad, vals["singles"])
sub = "([...document.querySelectorAll('button')].find(b=>/Submit application/.test(b.innerText)))"
ensure_view(sub); shot("scroll", "Ready to submit", sub, "scroll")
run("hover", "@"+uid_for(r'button "Submit application"'))
shot("hover", "Ready to submit", sub, "final")
print("DONE", N[0])
