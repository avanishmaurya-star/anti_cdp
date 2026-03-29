"""
anti_cdp Flask Web App v3
Fixes: source code detection, rich fallback explanations, proper error-only input.
"""
from flask import Flask, render_template_string, request, jsonify
import joblib, json, os, re

BASE      = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE, "model")

pipeline    = joblib.load(os.path.join(MODEL_DIR, "pipeline.pkl"))
rules       = joblib.load(os.path.join(MODEL_DIR, "rules.pkl"))
annotations = joblib.load(os.path.join(MODEL_DIR, "annotations.pkl"))
with open(os.path.join(MODEL_DIR, "meta.json")) as f:
    meta = json.load(f)

app = Flask(__name__)

# ── Rich fallback explanations for every category ────────────────────────────
FALLBACK = {
    "Variable Declaration": {
        "explanation": "You are trying to use a variable that has not been declared yet. The compiler does not know this variable exists at the point where you are using it.",
        "fix": "Declare the variable before using it. Example: 'int x = 0;' Make sure it is declared in the correct scope — inside the function if used locally."
    },
    "Syntax Rules": {
        "explanation": "The compiler found a syntax mistake — something is missing or in the wrong place. Common causes are a missing semicolon ';', unclosed bracket, or a typo in a keyword.",
        "fix": "Check the line mentioned in the error and the line just before it. Look for a missing semicolon ';', mismatched parentheses '()' or curly braces '{}'."
    },
    "Linking": {
        "explanation": "You declared a function or variable but never defined (implemented) it. The linker cannot find the actual body/code for it anywhere.",
        "fix": "Make sure every function you declare also has a full definition. Example: if you wrote 'int add(int a, int b);' you must also write 'int add(int a, int b){ return a+b; }'."
    },
    "Encapsulation (Access Modifiers)": {
        "explanation": "You are trying to access a 'private' or 'protected' class member from outside the class. Private members are hidden from the outside world for data safety.",
        "fix": "Add a public getter/setter method inside the class to access the private member. Example: 'int getBalance(){ return balance; }' Then call 'obj.getBalance()' instead of 'obj.balance'."
    },
    "Constants": {
        "explanation": "You declared a variable as 'const' (constant) which means its value cannot be changed after it is first set. You are trying to modify it, which is not allowed.",
        "fix": "If the value needs to change, remove the 'const' keyword from the declaration. If it should stay fixed, use a different variable to hold the new value."
    },
    "Function Signatures": {
        "explanation": "There is a mismatch between how you defined the function and how you are calling it. You may be passing the wrong number of arguments or the wrong types.",
        "fix": "Check that the number and types of arguments in your function call match exactly what the function definition expects. Example: if the function is 'void greet(int age, string name)' call it as 'greet(25, \"Alice\")'."
    },
    "General Error": {
        "explanation": "The compiler found an issue — usually a missing '#include' header file. Many standard features like 'cout', 'vector', 'string' require their specific header to be included at the top.",
        "fix": "Add the correct #include at the top of your file:\n  #include <iostream>  → for cout, cin\n  #include <vector>    → for vector\n  #include <string>    → for string\n  #include <map>       → for map\n  #include <cstdio>    → for printf, scanf"
    },
}

# ── Core prediction ──────────────────────────────────────────────────────────
def predict_single(msg: str):
    for pat, lbl in rules:
        if pat.search(msg):
            proba = pipeline.predict_proba([msg])[0]
            probs = {c: round(float(p),4) for c,p in zip(pipeline.classes_, proba)}
            return lbl, 1.0, "Rule-Based", probs
    proba = pipeline.predict_proba([msg])[0]
    idx   = int(proba.argmax())
    probs = {c: round(float(p),4) for c,p in zip(pipeline.classes_, proba)}
    return pipeline.classes_[idx], float(proba[idx]), "ML Model", probs

def parse_annotation(ann: str):
    concept = explanation = fix = ""
    m = re.search(r'Programming Concept:\s*(.+?)\.', ann)
    if m: concept = m.group(1).strip()
    m = re.search(r'Explanation:\s*(.+?)(?:Fix:|$)', ann, re.DOTALL)
    if m: explanation = m.group(1).strip()
    m = re.search(r'Fix:\s*(.+)', ann, re.DOTALL)
    if m: fix = m.group(1).strip()
    return concept, explanation, fix

def get_explanation(label, ann):
    """Get explanation from annotation, fall back to rich FALLBACK dict."""
    concept, explanation, fix = parse_annotation(ann)
    fb = FALLBACK.get(label, {})
    return (
        concept or label,
        explanation if explanation and len(explanation) > 20 else fb.get("explanation", ""),
        fix       if fix       and len(fix) > 20       else fb.get("fix", ""),
    )

def extract_errors_from_block(text: str):
    """Extract compiler error lines. Rejects raw C++ source code."""
    # Detect source code pasted by mistake
    source_patterns = [
        r'^\s*#include\s*[<"]',
        r'^\s*int\s+main\s*\(',
        r'^\s*(class|struct|namespace)\s+\w',
        r'^\s*std::\w+\s*<<',
        r'^\s*return\s+\d+\s*;',
    ]
    lines = text.strip().splitlines()
    source_hits = sum(
        1 for line in lines
        if any(re.match(p, line) for p in source_patterns)
    )
    if source_hits >= 2:
        return ["SOURCE_CODE_DETECTED"]

    errors = []
    for line in lines:
        line = line.strip()
        if not line: continue
        m = re.search(r'error:\s*(.+)', line)
        if m: errors.append(m.group(1).strip()); continue
        m = re.search(r'warning:\s*(.+)', line)
        if m: errors.append(m.group(1).strip()); continue
        if len(line) > 10:
            errors.append(line)
    return errors if errors else [text.strip()]

# ─────────────────────────────────────────────────────────────────────────────
HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>anti_cdp · C++ Error Explainer</title>
<style>
:root{
  --bg:#0d1117;--surface:#161b22;--surface2:#1c2128;--border:#30363d;
  --accent:#4c6ef5;--accent2:#7c3aed;--green:#3fb950;--red:#f85149;
  --text:#e6edf3;--muted:#8b949e;--code:#f0883e;
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;display:flex;flex-direction:column}

nav{background:var(--surface);border-bottom:1px solid var(--border);padding:0 24px;display:flex;align-items:center;gap:0;height:52px}
.nav-brand{display:flex;align-items:center;gap:10px;font-weight:700;font-size:1.05rem;color:var(--text);margin-right:28px}
.nav-tab{padding:0 16px;height:100%;display:flex;align-items:center;font-size:.84rem;color:var(--muted);cursor:pointer;border-bottom:2px solid transparent;transition:all .15s;user-select:none}
.nav-tab:hover{color:var(--text)}.nav-tab.active{color:var(--accent);border-bottom-color:var(--accent)}
.nav-right{margin-left:auto;display:flex;align-items:center;gap:8px}
.pill{background:var(--surface2);border:1px solid var(--border);border-radius:12px;padding:3px 10px;font-size:.72rem;color:var(--muted)}

.wrap{max-width:900px;margin:0 auto;padding:28px 20px;flex:1;width:100%}
.page{display:none}.page.active{display:block}

.card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:20px 22px;margin-bottom:16px}
.card-title{font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:12px}

textarea{width:100%;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:var(--text);font-family:'Cascadia Code','Fira Code',Consolas,monospace;font-size:.85rem;padding:12px 14px;resize:vertical;min-height:110px;outline:none;transition:border-color .2s}
textarea:focus{border-color:var(--accent)}
textarea::placeholder{color:#484f58}
.btn-row{display:flex;gap:8px;margin-top:10px}
.btn{border:none;border-radius:7px;cursor:pointer;font-size:.88rem;font-weight:600;padding:10px 20px;transition:all .15s}
.btn-primary{background:var(--accent);color:#fff}.btn-primary:hover{background:#3b5bdb}
.btn-secondary{background:var(--surface2);border:1px solid var(--border);color:var(--muted)}.btn-secondary:hover{color:var(--text)}
.btn:active{transform:scale(.97)}

.chips{display:flex;flex-wrap:wrap;gap:7px}
.chip{background:var(--surface2);border:1px solid var(--border);border-radius:6px;color:var(--muted);cursor:pointer;font-size:.73rem;padding:4px 9px;transition:all .15s;font-family:monospace}
.chip:hover{background:var(--border);color:var(--text)}

/* HINT BOX */
.hint-box{background:#1a2233;border:1px solid #2d4a7a;border-radius:8px;padding:14px 16px;margin-bottom:16px;font-size:.83rem;line-height:1.6;color:#93c5fd;display:none}
.hint-box strong{color:#60a5fa;display:block;margin-bottom:6px}
.hint-box code{background:#0d1117;border-radius:4px;padding:2px 6px;font-family:monospace;font-size:.82rem;color:var(--code)}

/* ERROR BOX */
.error-box{background:#1f1010;border:1px solid var(--red);border-radius:8px;padding:14px 16px;margin-bottom:16px;font-size:.85rem;color:#fca5a5;display:none}
.error-box strong{color:var(--red);display:block;margin-bottom:4px}

#result-section{display:none}
.result-header{display:flex;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:18px}
.badge-concept{background:linear-gradient(135deg,var(--accent),var(--accent2));border-radius:16px;color:#fff;font-size:.84rem;font-weight:700;padding:5px 14px}
.badge-method{background:var(--surface2);border:1px solid var(--border);border-radius:16px;color:var(--muted);font-size:.72rem;padding:3px 9px}
.badge-conf{margin-left:auto;color:var(--green);font-size:.82rem;font-weight:600}

.section-lbl{font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:6px}
.info-block{background:var(--bg);border-radius:7px;padding:13px 15px;font-size:.88rem;line-height:1.7;color:#cdd9e5;margin-bottom:14px;border-left:3px solid;white-space:pre-wrap}
.info-block.expl{border-color:var(--accent)}
.info-block.fix {border-color:var(--green)}

.prob-row{display:flex;align-items:center;gap:9px;margin-bottom:5px}
.prob-name{width:210px;font-size:.77rem;color:var(--muted);text-align:right;flex-shrink:0}
.prob-track{flex:1;background:var(--surface2);border-radius:4px;height:9px;overflow:hidden}
.prob-fill{height:100%;border-radius:4px;background:linear-gradient(90deg,var(--accent),var(--accent2));transition:width .4s ease}
.prob-pct{width:38px;font-size:.74rem;color:var(--muted);text-align:right}

#multi-section{display:none}
.multi-item{background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:12px}
.multi-err-line{font-family:monospace;font-size:.82rem;color:var(--code);margin-bottom:10px;word-break:break-all;padding:6px 8px;background:var(--bg);border-radius:5px}
.multi-label-row{display:flex;align-items:center;gap:8px;margin-bottom:10px}
.multi-expl{font-size:.83rem;line-height:1.65;color:#cdd9e5;margin-bottom:8px;padding:8px 10px;background:var(--bg);border-radius:5px;border-left:3px solid var(--accent)}
.multi-fix{font-size:.83rem;line-height:1.65;color:#cdd9e5;padding:8px 10px;background:var(--bg);border-radius:5px;border-left:3px solid var(--green);white-space:pre-wrap}

.hist-item{background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:12px 14px;margin-bottom:10px;cursor:pointer;transition:border-color .15s}
.hist-item:hover{border-color:var(--accent)}
.hist-top{display:flex;align-items:center;gap:8px;margin-bottom:4px}
.hist-msg{font-family:monospace;font-size:.8rem;color:var(--code);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1}
.hist-label{font-size:.72rem;color:var(--accent);font-weight:600;white-space:nowrap}
.hist-time{font-size:.68rem;color:var(--muted)}
#hist-empty{color:var(--muted);font-size:.85rem;text-align:center;padding:40px 0}

.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:16px}
.stat-card{background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:14px 16px;text-align:center}
.stat-num{font-size:1.8rem;font-weight:700;color:var(--text)}
.stat-lbl{font-size:.7rem;color:var(--muted);margin-top:3px}
.class-list{display:flex;flex-wrap:wrap;gap:7px}
.class-chip{background:var(--surface2);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:.77rem;padding:5px 10px}

#loading{display:none;text-align:center;padding:28px 0;color:var(--muted)}
.spinner{width:22px;height:22px;border:3px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:spin .7s linear infinite;margin:0 auto 10px}
@keyframes spin{to{transform:rotate(360deg)}}

#toast{position:fixed;bottom:24px;right:24px;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:10px 16px;font-size:.82rem;color:var(--text);opacity:0;transition:opacity .3s;pointer-events:none;z-index:999}
#toast.show{opacity:1}
footer{text-align:center;color:var(--muted);font-size:.7rem;padding:18px 0;border-top:1px solid var(--border)}
</style>
</head>
<body>

<nav>
  <div class="nav-brand"><span>🛡️</span>anti_cdp</div>
  <div class="nav-tab active" onclick="switchTab('analyze',this)">Analyze</div>
  <div class="nav-tab" onclick="switchTab('history',this)">History</div>
  <div class="nav-tab" onclick="switchTab('stats',this)">Model Stats</div>
  <div class="nav-right">
    <span class="pill">{{ meta.training_size }} samples</span>
    <span class="pill">{{ meta.classes|length }} categories</span>
  </div>
</nav>

<div class="wrap">

<!-- ══ ANALYZE ═══════════════════════════════════════════════════════════════ -->
<div class="page active" id="page-analyze">

  <div class="card">
    <div class="card-title">📋 Paste the compiler error message</div>

    <!-- Instruction hint -->
    <div class="hint-box" id="hint-how">
      <strong>💡 How to get the error message:</strong>
      1. Save your C++ code to a file e.g. <code>main.cpp</code><br>
      2. Open terminal and run: <code>g++ main.cpp -o output</code><br>
      3. Copy the error line shown (e.g. <code>'x' was not declared in this scope</code>)<br>
      4. Paste it below and click Analyze
    </div>

    <textarea id="errorInput"
      placeholder="Paste the error message from your compiler here...&#10;&#10;Example:&#10;  'x' was not declared in this scope&#10;  expected ';' before 'return'&#10;  undefined reference to 'foo()'"
      oninput="onInput()"></textarea>

    <!-- Source code warning -->
    <div class="error-box" id="warn-source">
      <strong>⚠️ Looks like you pasted C++ source code, not an error message!</strong>
      Please compile your code first using <code>g++ yourfile.cpp -o output</code>, then paste the error message that appears.
    </div>

    <div class="btn-row">
      <button class="btn btn-primary" onclick="classify()">⚡ Analyze (Ctrl+↵)</button>
      <button class="btn btn-secondary" onclick="clearAll()">Clear</button>
      <button class="btn btn-secondary" onclick="document.getElementById('hint-how').style.display=document.getElementById('hint-how').style.display==='none'?'block':'none'">How to use?</button>
    </div>
  </div>

  <div class="card">
    <div class="card-title">⚡ Quick examples — click to try</div>
    <div class="chips">
      {% for ex in examples %}
      <span class="chip" onclick="setExample(this.textContent.trim())">{{ ex }}</span>
      {% endfor %}
    </div>
  </div>

  <div id="loading"><div class="spinner"></div>Analyzing…</div>

  <!-- SOURCE CODE ERROR -->
  <div class="error-box" id="src-error" style="display:none">
    <strong>⚠️ Source code detected — cannot analyze!</strong>
    You pasted C++ source code. Please compile it first:<br>
    <code>g++ yourfile.cpp -o output</code><br>
    Then paste the error message that appears in the terminal.
  </div>

  <!-- Single result -->
  <div class="card" id="result-section">
    <div class="card-title">🔍 Analysis Result</div>
    <div class="result-header">
      <span class="badge-concept" id="r-concept">—</span>
      <span class="badge-method"  id="r-method">—</span>
      <span class="badge-conf"    id="r-conf">—</span>
    </div>

    <div class="section-lbl">📖 Explanation</div>
    <div class="info-block expl" id="r-expl">—</div>

    <div class="section-lbl">💡 Suggested Fix</div>
    <div class="info-block fix" id="r-fix">—</div>

    <div class="section-lbl" style="margin-top:14px">📊 Probability Distribution</div>
    <div id="r-probs"></div>
  </div>

  <!-- Multi-error results -->
  <div id="multi-section">
    <div class="card-title" style="margin-bottom:10px">🔍 Multiple Errors Found</div>
    <div id="multi-results"></div>
  </div>

</div>

<!-- ══ HISTORY ════════════════════════════════════════════════════════════════ -->
<div class="page" id="page-history">
  <div class="card">
    <div class="card-title">📜 Analysis History</div>
    <div style="display:flex;justify-content:flex-end;margin-bottom:10px">
      <button class="btn btn-secondary" style="font-size:.75rem;padding:6px 12px" onclick="clearHistory()">Clear History</button>
    </div>
    <div id="hist-list"><div id="hist-empty">No history yet. Analyze some errors first!</div></div>
  </div>
</div>

<!-- ══ STATS ══════════════════════════════════════════════════════════════════ -->
<div class="page" id="page-stats">
  <div class="card">
    <div class="card-title">📊 Model Overview</div>
    <div class="stats-grid">
      <div class="stat-card"><div class="stat-num">{{ meta.training_size }}</div><div class="stat-lbl">Training Samples</div></div>
      <div class="stat-card"><div class="stat-num">{{ meta.real_samples }}</div><div class="stat-lbl">Real Samples</div></div>
      <div class="stat-card"><div class="stat-num">{{ meta.synthetic_samples }}</div><div class="stat-lbl">Synthetic Samples</div></div>
      <div class="stat-card"><div class="stat-num">{{ meta.classes|length }}</div><div class="stat-lbl">Error Categories</div></div>
      <div class="stat-card"><div class="stat-num">99%</div><div class="stat-lbl">Train Accuracy</div></div>
      <div class="stat-card"><div class="stat-num">Hybrid</div><div class="stat-lbl">Model Type</div></div>
    </div>
  </div>
  <div class="card">
    <div class="card-title">🏷️ Error Categories</div>
    <div class="class-list">
      {% for c in meta.classes %}
      <span class="class-chip">{{ c }}</span>
      {% endfor %}
    </div>
  </div>
  <div class="card">
    <div class="card-title">⚙️ Architecture</div>
    <table style="width:100%;border-collapse:collapse;font-size:.84rem">
      {% for row in arch %}
      <tr style="border-bottom:1px solid var(--border)">
        <td style="padding:8px 0;color:var(--muted);width:180px">{{ row[0] }}</td>
        <td style="padding:8px 0">{{ row[1] }}</td>
      </tr>
      {% endfor %}
    </table>
  </div>
  <div class="card">
    <div class="card-title">📈 Session Stats</div>
    <div class="stats-grid">
      <div class="stat-card"><div class="stat-num" id="ss-total">0</div><div class="stat-lbl">Total Analyzed</div></div>
      <div class="stat-card"><div class="stat-num" id="ss-rule">0</div><div class="stat-lbl">Rule-Based Hits</div></div>
      <div class="stat-card"><div class="stat-num" id="ss-ml">0</div><div class="stat-lbl">ML Model Hits</div></div>
    </div>
  </div>
</div>

</div><!-- /wrap -->

<div id="toast"></div>
<footer>anti_cdp · C++ Diagnostic Platform · Hybrid NLP Model v3</footer>

<script>
let history = JSON.parse(localStorage.getItem('acdp_history')||'[]');
let session = {total:0,rule:0,ml:0};

function switchTab(name,el){
  document.querySelectorAll('.nav-tab').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.getElementById('page-'+name).classList.add('active');
  if(name==='history') renderHistory();
  if(name==='stats')   renderSessionStats();
}

function onInput(){
  const v = document.getElementById('errorInput').value;
  const srcPat = /(#include\s*[<"])|(int\s+main\s*\()|(std::\w+\s*<<)/g;
  const hits = (v.match(srcPat)||[]).length;
  document.getElementById('warn-source').style.display = hits>=2?'block':'none';
}

function setExample(msg){
  document.getElementById('errorInput').value=msg;
  document.getElementById('warn-source').style.display='none';
  classify();
}
function clearAll(){
  document.getElementById('errorInput').value='';
  document.getElementById('result-section').style.display='none';
  document.getElementById('multi-section').style.display='none';
  document.getElementById('src-error').style.display='none';
  document.getElementById('warn-source').style.display='none';
}

async function classify(){
  const raw=document.getElementById('errorInput').value.trim();
  if(!raw) return;
  document.getElementById('result-section').style.display='none';
  document.getElementById('multi-section').style.display='none';
  document.getElementById('src-error').style.display='none';
  document.getElementById('loading').style.display='block';

  try{
    const res  = await fetch('/predict',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({error_message:raw})});
    const data = await res.json();
    document.getElementById('loading').style.display='none';

    if(data.source_code_error){
      document.getElementById('src-error').style.display='block';
      return;
    }
    if(data.multi){
      renderMulti(data.results);
      data.results.forEach(r=>addHistory(r.error_message,r));
    } else {
      renderSingle(data);
      addHistory(raw,data);
    }
    session.total++;
    if((data.method||'').includes('Rule')) session.rule++; else session.ml++;
  } catch(e){
    document.getElementById('loading').style.display='none';
    toast('Request failed: '+e.message,true);
  }
}

function renderSingle(d){
  document.getElementById('r-concept').textContent = d.concept||d.label;
  document.getElementById('r-method').textContent  = d.method;
  document.getElementById('r-conf').textContent    = Math.round(d.confidence*100)+'% confidence';
  document.getElementById('r-expl').textContent    = d.explanation||'(no explanation available)';
  document.getElementById('r-fix').textContent     = d.fix||'(no fix suggestion available)';

  const sorted = Object.entries(d.probabilities).sort((a,b)=>b[1]-a[1]);
  document.getElementById('r-probs').innerHTML = sorted.map(([lbl,p])=>`
    <div class="prob-row">
      <div class="prob-name">${lbl}</div>
      <div class="prob-track"><div class="prob-fill" style="width:${(p*100).toFixed(1)}%"></div></div>
      <div class="prob-pct">${(p*100).toFixed(1)}%</div>
    </div>`).join('');

  document.getElementById('result-section').style.display='block';
  document.getElementById('result-section').scrollIntoView({behavior:'smooth',block:'nearest'});
}

function renderMulti(results){
  document.getElementById('multi-results').innerHTML = results.map(r=>`
    <div class="multi-item">
      <div class="multi-err-line">❌ ${escHtml(r.error_message)}</div>
      <div class="multi-label-row">
        <span class="badge-concept" style="font-size:.78rem;padding:3px 10px">${escHtml(r.concept||r.label)}</span>
        <span class="badge-method">${escHtml(r.method)}</span>
        <span class="badge-conf" style="margin-left:auto">${Math.round(r.confidence*100)}%</span>
      </div>
      <div class="section-lbl">📖 Explanation</div>
      <div class="multi-expl">${escHtml(r.explanation||'')}</div>
      <div class="section-lbl">💡 Suggested Fix</div>
      <div class="multi-fix">${escHtml(r.fix||'')}</div>
    </div>`).join('');
  document.getElementById('multi-section').style.display='block';
  document.getElementById('multi-section').scrollIntoView({behavior:'smooth',block:'nearest'});
}

function escHtml(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}

function addHistory(msg,data){
  history.unshift({msg,label:data.concept||data.label,method:data.method,time:new Date().toLocaleTimeString()});
  if(history.length>50) history.pop();
  localStorage.setItem('acdp_history',JSON.stringify(history));
}
function renderHistory(){
  const el=document.getElementById('hist-list');
  if(!history.length){el.innerHTML='<div id="hist-empty">No history yet!</div>';return;}
  el.innerHTML=history.map((h,i)=>`
    <div class="hist-item" onclick="loadFromHistory(${i})">
      <div class="hist-top">
        <span class="hist-msg">${escHtml(h.msg)}</span>
        <span class="hist-label">${escHtml(h.label)}</span>
      </div>
      <span class="hist-time">${h.time} · ${h.method}</span>
    </div>`).join('');
}
function loadFromHistory(i){
  document.getElementById('errorInput').value=history[i].msg;
  switchTab('analyze',document.querySelectorAll('.nav-tab')[0]);
  classify();
}
function clearHistory(){history=[];localStorage.removeItem('acdp_history');renderHistory();toast('History cleared');}
function renderSessionStats(){
  document.getElementById('ss-total').textContent=session.total;
  document.getElementById('ss-rule').textContent=session.rule;
  document.getElementById('ss-ml').textContent=session.ml;
}
function toast(msg,err=false){
  const t=document.getElementById('toast');
  t.textContent=msg;t.style.borderColor=err?'var(--red)':'var(--border)';
  t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2800);
}
document.getElementById('errorInput').addEventListener('keydown',e=>{
  if((e.ctrlKey||e.metaKey)&&e.key==='Enter') classify();
});
</script>
</body>
</html>
"""

EXAMPLES = [
    "'x' was not declared in this scope",
    "undefined reference to `foo()'",
    "expected ';' before 'return'",
    "'int MyClass::data' is private within this context",
    "assignment of read-only variable 'MAX'",
    "too few arguments to function 'void greet(int)'",
    "'cout' is not a member of 'std'",
    "invalid conversion from 'const char*' to 'int'",
    "'vector' is not a member of 'std'",
    "no matching function for call to 'push_back(const char*)'",
]

ARCH = [
    ("Feature Extraction", "TF-IDF with character n-grams (2–6)"),
    ("Classifier",         "Logistic Regression (lbfgs, C=3.0)"),
    ("Rule Layer",         "7 high-priority regex patterns"),
    ("Vocab Size",         "12,000 features"),
    ("Dataset Sources",    "clean + raw + extended + synthetic"),
]

@app.route("/")
def index():
    return render_template_string(HTML, meta=meta, examples=EXAMPLES, arch=ARCH)

@app.route("/predict", methods=["POST"])
def predict_api():
    data = request.get_json(force=True)
    raw  = (data.get("error_message") or "").strip()
    if not raw:
        return jsonify({"error": "No error_message provided"}), 400

    errors = extract_errors_from_block(raw)

    # Source code detected
    if errors == ["SOURCE_CODE_DETECTED"]:
        return jsonify({"source_code_error": True})

    def make_result(msg):
        label, confidence, method, probs = predict_single(msg)
        ann = annotations.get(label, "")
        concept, explanation, fix = get_explanation(label, ann)
        return {
            "error_message": msg,
            "label":         label,
            "concept":       concept or label,
            "confidence":    confidence,
            "method":        method,
            "explanation":   explanation,
            "fix":           fix,
            "probabilities": probs,
        }

    if len(errors) > 1:
        return jsonify({"multi": True, "results": [make_result(e) for e in errors[:10]]})
    return jsonify(make_result(errors[0]))

@app.route("/health")
def health():
    return jsonify({"status":"ok","model":"anti_cdp-v3","categories":meta["classes"]})

if __name__ == "__main__":
    print("🛡️  anti_cdp v3 → http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
