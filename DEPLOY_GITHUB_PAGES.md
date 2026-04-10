# Publish to GitHub Pages (`github.io`)

GitHub Pages only serves **static files**. This repo ships:

- **Dashboard + charts** (bundled React)
- **Executive briefing + forecast backtest** from `public/static-demo.json` (regenerated in CI from your AEO data)
- **No Python / FastAPI on Pages** — live AI chat is off unless you point the build at a hosted API

## One-time setup

1. Create a GitHub repository and push this project (include `public/static-demo.json`; CI regenerates it on each deploy).
2. **Settings → Pages → Build and deployment → Source:** GitHub Actions.
3. Push to `main` (or `master`). The workflow **Deploy GitHub Pages** runs automatically.
4. Open: `https://<your-username>.github.io/<repository-name>/`

If the site is blank, check that **Settings → Pages** shows the latest workflow run and that `VITE_BASE_PATH` matches your repo name (the workflow sets it to `/repository-name/`).

### User / org site (`username.github.io`)

If the repo is named exactly `username.github.io`, the site is served from the **root** (`/`), not a subpath. Edit `.github/workflows/deploy-pages.yml` and set:

```yaml
VITE_BASE_PATH: /
```

## Refresh static numbers after changing 10-K data

```bash
python3 scripts/export_static_demo.py
git add public/static-demo.json && git commit -m "Refresh static demo JSON" && git push
```

## Full live chat on the public site (optional)

1. Host `src/04_api_server.py` somewhere with HTTPS (e.g. Railway, Render, Fly.io) and set `OPENAI_API_KEY` there.
2. Add a repository secret **`VITE_API_BASE_URL`** = `https://your-api.example.com` (no trailing slash).
3. In the workflow, **remove** `VITE_STATIC_ONLY: "true"` and pass:

```yaml
env:
  VITE_BASE_PATH: /${{ github.event.repository.name }}/
  VITE_API_BASE_URL: ${{ secrets.VITE_API_BASE_URL }}
```

Rebuild. The UI will call your API; keep keys only on the server, never in the frontend bundle.
