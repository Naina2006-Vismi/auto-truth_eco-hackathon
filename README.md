# AutoTruth — EV Transparency Intelligence Platform

AutoTruth is a Flask-based web app that analyzes EV sustainability disclosures and generates a Lifecycle Transparency Score (LTS). It supports:

- Company-level and model-level EV analysis
- Comparison mode across companies
- PDF report analysis (with EV domain detection)
- Interactive dashboard visualizations and explainable metrics

## Live App

- Production URL: [https://auto-truth-eco-hackathon.onrender.com](https://auto-truth-eco-hackathon.onrender.com)

## 1. Project Structure

```text
/Users/namburunainavismi/Desktop/Tasks/Eco Hackathon
├── app.py
├── requirements.txt
├── render.yaml
├── EV Energy Efficiency Dataset.csv
├── data/
│   └── companies.json
├── engine/
│   ├── scoring.py
│   ├── lifecycle_scorer.py
│   ├── nlp_engine.py
│   └── offset_detector.py
├── templates/
│   ├── index.html
│   └── dashboard.html
└── static/
    ├── css/
    └── js/
```

## 2. Prerequisites

- Python 3.11+
- `pip`
- Git

## 3. Run Locally (Step-by-Step)

1. Open terminal and go to the project:
```bash
cd "/Users/namburunainavismi/Desktop/Tasks/Eco Hackathon"
```

2. Create virtual environment:
```bash
python3 -m venv .venv
```

3. Activate virtual environment:
```bash
source .venv/bin/activate
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Start the app:
```bash
python app.py
```

6. Open in browser:
- Landing page: [http://localhost:5001/](http://localhost:5001/)
- Dashboard: [http://localhost:5001/dashboard](http://localhost:5001/dashboard)

## 4. Core API Endpoints

- `GET /api/companies` → list available EV companies
- `GET /api/models/<company_id>` → list models for selected company
- `GET /api/analyze/<company_id>?model=<model_name>` → run LTS analysis
- `GET /api/compare?ids=id1,id2,id3` → compare companies
- `POST /api/analyze-pdf` → upload PDF for analysis

## 5. PDF Analysis Rules

- File type: `.pdf`
- Max size: **60 MB**
- Max pages processed: **30**
- Includes EV domain detection output:
  - EV-focused: continue directly
  - Potential non-EV: prompt user to re-upload or continue anyway

## 6. Dataset Configuration

Primary dataset:
- `EV Energy Efficiency Dataset.csv`

Fallback dataset:
- `data/companies.json`

The app automatically uses CSV first. If CSV is missing/invalid, it falls back to JSON.

## 7. Deploy on Render (Step-by-Step)

This repo already includes `render.yaml`.

1. Push code to GitHub.
2. In Render, click **New +** → **Blueprint**.
3. Connect your GitHub repo.
4. Render will detect `render.yaml` and create the web service.
5. Wait for build + deploy.
6. Open deployed URL:
   - `https://auto-truth-eco-hackathon.onrender.com`

Configured Render start command:
```bash
gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
```

## 8. Push Updates to GitHub

```bash
cd "/Users/namburunainavismi/Desktop/Tasks/Eco Hackathon"
git add .
git commit -m "your message"
git push origin main
```

## 9. Common Issues + Fixes

1. Redirects to localhost from deployed site:
- Ensure latest `templates/index.html` is pushed (contains Render-safe redirect logic).
- Re-deploy Render after push.

2. PDF parsing fails:
- Try text-based PDF (not scanned image only).
- Keep file under 60MB.

3. No models shown for a company:
- Check CSV has valid `Make` and `Model` values.

## 10. Quick Dev Notes

- Main backend: `app.py`
- Main dashboard logic: `static/js/dashboard.js`
- Landing page interactions: `templates/index.html`
- Dashboard layout: `templates/dashboard.html`

---
Author

Naina Vismi N
