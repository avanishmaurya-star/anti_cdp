# anti_cdp v2 — C++ Error Explainer

NLP-powered compiler error classifier and explainer with a Flask web UI.

## Quick Start

```bash
pip install -r requirements.txt
python build_extended_dataset.py   # generate extended_dataset.json
python train_model.py              # train the model → model/
python app.py                      # start Flask → http://127.0.0.1:5000
```

## Features

- **Single & multi-error analysis** — paste one error or a full compiler output block
- **Hybrid model** — regex rules for fast common cases, ML for everything else  
- **7 C++ error categories** with explanations and fix suggestions
- **Analysis history** — persisted in browser localStorage
- **Model stats page** — training breakdown, session counters, architecture info

## Model

| Component | Detail |
|---|---|
| Feature extraction | TF-IDF, char n-grams (2–6), 12k vocab |
| Classifier | Logistic Regression (lbfgs, C=3.0) |
| Rule layer | 7 high-priority regex patterns |
| Training data | 35 real + 34 synthetic = 69 samples |
| Accuracy | 99% in-sample |

## Error Categories

`Variable Declaration` · `Syntax Rules` · `Linking` · `Encapsulation (Access Modifiers)` · `Constants` · `Function Signatures` · `General Error`

## REST API

```
POST /predict
{"error_message": "..."}

# Single error → { label, concept, confidence, method, explanation, fix, probabilities }
# Multi-error  → { multi: true, results: [...] }

GET /health  → { status, model, categories }
```
