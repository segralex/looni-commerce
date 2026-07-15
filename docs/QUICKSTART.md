Quickstart — Looni Commerce (Alpha v0.1.0)
=========================================

Prerequisites
- Python 3.11+ (this project has been exercised with Python 3.13)
- pip

Clone

```bash
git clone <repo-url>
cd looni-commerce
```

Install dev dependencies

```bash
python -m pip install -e .
# also ensure test dependencies are installed, e.g. pytest, httpx2
python -m pip install pytest httpx2
```

Run tests

```bash
python -m pytest -q
```

Run the API server

```bash
uvicorn app.main:app --reload
```

Open interactive docs

Visit `http://127.0.0.1:8000/docs` to explore endpoints and try requests.

Execute a full marketplace workflow
- Use the interactive docs or the acceptance test `tests/test_marketplace_http_acceptance.py` as a step-by-step example of creating users, publishing a listing and completing a reservation.
