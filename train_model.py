"""
anti_cdp NLP Model Trainer v2
Combines real + extended + synthetic data.
Outputs: pipeline.pkl, rules.pkl, annotations.pkl, meta.json
"""
import json, re, joblib, os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import VotingClassifier
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, confusion_matrix
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))

def load_json(path):
    with open(path) as f: return json.load(f)

clean    = load_json(os.path.join(BASE, "anti_cdp/data/clean_dataset.json"))
raw      = load_json(os.path.join(BASE, "anti_cdp/data/raw_dataset.json"))
extended = load_json(os.path.join(BASE, "anti_cdp/data/extended_dataset.json"))

# Merge and deduplicate by error_message
seen, dataset = set(), []
for d in clean + raw + extended:
    key = d["error_message"]
    if key not in seen:
        seen.add(key); dataset.append(d)
print(f"Unique real/extended entries: {len(dataset)}")

def extract_label(item):
    m = re.search(r'Programming Concept:\s*(.+?)\.', item.get("annotation",""))
    return m.group(1).strip() if m else "General Error"

def build_text(item):
    msg     = item.get("error_message","")
    snippet = " ".join(s.get("text","") for s in item.get("ast_context",{}).get("source_snippet",[]))
    return f"{msg} {snippet}".strip()

# ── Synthetic augmentation ───────────────────────────────────────────────────
SYNTHETIC = [
    # Variable Declaration
    ("'total' was not declared in this scope",          "Variable Declaration"),
    ("'ptr' was not declared in this scope",            "Variable Declaration"),
    ("'temp' was not declared in this scope",           "Variable Declaration"),
    ("'idx' was not declared in this scope",            "Variable Declaration"),
    ("'val' was not declared in this scope",            "Variable Declaration"),
    ("'num' was not declared in this scope",            "Variable Declaration"),
    # Syntax Rules
    ("expected ';' before '}'",                        "Syntax Rules"),
    ("expected '}' at end of input",                   "Syntax Rules"),
    ("expected primary-expression before 'int'",       "Syntax Rules"),
    ("expected unqualified-id before '{' token",       "Syntax Rules"),
    ("missing terminating '\"' character",             "Syntax Rules"),
    ("expected ')' before ';' token",                  "Syntax Rules"),
    # Linking
    ("undefined reference to 'compute(double)'",       "Linking"),
    ("undefined reference to 'MyClass::init()'",       "Linking"),
    ("undefined reference to 'operator+(MyClass)'",    "Linking"),
    # Encapsulation
    ("'int Node::next' is private within this context","Encapsulation (Access Modifiers)"),
    ("member 'balance' is private",                    "Encapsulation (Access Modifiers)"),
    ("'char Account::pin' is private within this context","Encapsulation (Access Modifiers)"),
    # Constants
    ("assignment of read-only variable 'LIMIT'",       "Constants"),
    ("assignment of read-only variable 'SIZE'",        "Constants"),
    ("increment of read-only variable 'K'",            "Constants"),
    ("cannot assign to variable 'cfg' with const-qualified type","Constants"),
    # Function Signatures
    ("too few arguments to function 'void log(int, int)'",   "Function Signatures"),
    ("too many arguments to function 'void reset()'",        "Function Signatures"),
    ("no matching function for call to 'draw(float, float)'","Function Signatures"),
    ("invalid conversion from 'double' to 'int'",            "Function Signatures"),
    ("invalid conversion from 'char*' to 'std::string'",     "Function Signatures"),
    # General Error
    ("'deque' is not a member of 'std'",               "General Error"),
    ("'pair' is not a member of 'std'",                "General Error"),
    ("'abs' is not a member of 'std'",                 "General Error"),
    ("'cin' is not a member of 'std'",                 "General Error"),
    ("'list' is not a member of 'std'",                "General Error"),
    ("'sprintf' was not declared in this scope",       "General Error"),
    ("'fopen' was not declared in this scope",         "General Error"),
]

X, y = [], []
for item in dataset:
    txt   = build_text(item)
    label = extract_label(item)
    if txt and label:
        X.append(txt); y.append(label)
for msg, label in SYNTHETIC:
    X.append(msg); y.append(label)

print(f"Total training samples: {len(X)}")
dist = Counter(y)
for lbl, cnt in sorted(dist.items()):
    print(f"  {cnt:>2}x  {lbl}")

# ── Pipeline (TF-IDF + LR) ──────────────────────────────────────────────────
pipeline = Pipeline([
    ("tfidf", TfidfVectorizer(
        analyzer="char_wb", ngram_range=(2,6),
        max_features=12000, sublinear_tf=True, min_df=1,
    )),
    ("clf", LogisticRegression(C=3.0, max_iter=3000, solver="lbfgs", random_state=42)),
])
pipeline.fit(X, y)

y_pred = pipeline.predict(X)
print("\n── Classification Report ──────────────────────────────")
print(classification_report(y, y_pred, zero_division=0))

# ── Confusion matrix ─────────────────────────────────────────────────────────
classes = list(pipeline.classes_)
cm = confusion_matrix(y, y_pred, labels=classes)
print("── Confusion Matrix ───────────────────────────────────")
header = "".join(f"{c[:4]:>6}" for c in classes)
print(f"{'':22}{header}")
for i, row in enumerate(cm):
    print(f"  {classes[i][:20]:20}  {''.join(f'{v:>6}' for v in row)}")

# ── Rule-based patterns (ordered, most specific first) ──────────────────────
RULES = [
    (re.compile(r"was not declared in this scope"),                      "Variable Declaration"),
    (re.compile(r"expected\s+['\"]?[;,{}()\[\]]['\"]?|expected\s+primary-expression|expected unqualified|expected\s+'[,;)']}"),
                                                                          "Syntax Rules"),
    (re.compile(r"undefined reference to"),                              "Linking"),
    (re.compile(r"is private within this context|is protected within this context|member .+ is private"),
                                                                          "Encapsulation (Access Modifiers)"),
    (re.compile(r"assignment of read-only|increment of read-only|cannot assign to variable .+const"),
                                                                          "Constants"),
    (re.compile(r"too (few|many) arguments|no matching function for call"),
                                                                          "Function Signatures"),
    (re.compile(r"invalid conversion from"),                             "Function Signatures"),
    (re.compile(r"is not a member of 'std'|was not declared in this scope"),
                                                                          "General Error"),
]

# ── Annotation map: label → full annotation text ────────────────────────────
annotations_by_label = {}
for item in dataset:
    label = extract_label(item)
    ann   = item.get("annotation","")
    if label not in annotations_by_label and ann:
        annotations_by_label[label] = ann

# ── Save ─────────────────────────────────────────────────────────────────────
MODEL_DIR = os.path.join(BASE, "model")
os.makedirs(MODEL_DIR, exist_ok=True)
joblib.dump(pipeline,            os.path.join(MODEL_DIR, "pipeline.pkl"))
joblib.dump(RULES,               os.path.join(MODEL_DIR, "rules.pkl"))
joblib.dump(annotations_by_label,os.path.join(MODEL_DIR, "annotations.pkl"))

meta = {
    "classes":         list(pipeline.classes_),
    "training_size":   len(X),
    "real_samples":    len(dataset),
    "synthetic_samples": len(SYNTHETIC),
}
with open(os.path.join(MODEL_DIR, "meta.json"), "w") as f:
    json.dump(meta, f, indent=2)

print(f"\n✔  Saved model → {MODEL_DIR}/")

# ── Quick sanity tests ───────────────────────────────────────────────────────
def predict_hybrid(msg):
    for pat, lbl in RULES:
        if pat.search(msg): return lbl, 1.0, "rule-based"
    proba = pipeline.predict_proba([msg])[0]
    idx = proba.argmax()
    return pipeline.classes_[idx], float(proba[idx]), "ml-model"

tests = [
    ("'z' was not declared in this scope",                "Variable Declaration"),
    ("expected ';' before 'return'",                     "Syntax Rules"),
    ("undefined reference to 'helper()'",               "Linking"),
    ("'int Foo::bar' is private within this context",   "Encapsulation (Access Modifiers)"),
    ("assignment of read-only variable 'PI'",           "Constants"),
    ("too few arguments to function 'void f(int)'",     "Function Signatures"),
    ("'cout' is not a member of 'std'",                 "General Error"),
]
print("\n── Sanity Tests ─────────────────────────────────────")
all_ok = True
for msg, expected in tests:
    got, conf, method = predict_hybrid(msg)
    ok = "✔" if got == expected else "✗"
    if got != expected: all_ok = False
    print(f"  {ok} [{method:10s}] {got:35s} | {msg[:50]}")
print("\n✔  All tests passed!" if all_ok else "\n⚠  Some tests failed — check rules.")
