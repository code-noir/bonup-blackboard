# Running Blackboard Locally

## Option A — Two terminals (recommended for active development)

Open two terminal tabs, then:

**Terminal 1 — Backend**
```bash
./dev/start-backend.sh
```

**Terminal 2 — Frontend**
```bash
./dev/start-frontend.sh
```

Both servers reload automatically on file changes. `Ctrl-C` in each terminal stops it.

---

## Option B — Background (both at once)

```bash
./dev/start-all.sh          # starts both, logs to dev/logs/
./dev/stop-all.sh           # stops both
tail -f dev/logs/backend.log dev/logs/frontend.log   # watch output
```

---

## URLs

| Service  | URL                     |
|----------|-------------------------|
| Frontend | http://localhost:5173   |
| Backend  | http://localhost:8000   |
| API root | http://localhost:8000/api/ |

---

## First-time setup (already done, just for reference)

```bash
# Backend
cd /home/bonup/bonup-blackboard
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd frontend
npm install
```
