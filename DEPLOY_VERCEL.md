# Deploying Razorpay EDGE: GitHub, then Vercel

Result: a public `https://<your-project>.vercel.app` link. Not yet tested on Vercel itself (no account was available here); the app was tested locally in Vercel mode (`VERCEL=1`).

## What runs where

| Part | On Vercel |
|---|---|
| React UI (`web/`) | Built by Vercel (`npm run build`) and served as static files |
| FastAPI backend (`api/main.py`, plus `src/`, `config/`, `prompts/`, `knowledge/`) | One Python serverless function behind `/api/*` |
| `vercel.json` | Tells Vercel to build both and send `/api/*` to the function, everything else to the UI |

## Know the limits before you share the link

1. **Saved analyses are temporary.** A serverless function can only write to `/tmp`, which is not shared between instances and is cleared when an instance is recycled. An analysis can disappear a few minutes later or between clicks ("Analysis not found"). Re-upload and re-run. This is fine for a short review; it is not a place to keep work.
2. **Uploads over about 4.5 MB fail.** Vercel limits request bodies. The sample workbook is under 0.1 MB.
3. **Analysis runs inside the request.** A normal analysis takes a few seconds. The robustness test and the evaluation package take about 30 to 40 seconds, so the function's maximum duration must be at least 60 seconds (see step 7).
4. **The sample-workbook button will not work.** The competition workbook is deliberately not in the repository. Reviewers upload their own `.xlsx`.
5. **Claude-assisted analysis (about 115 paid calls) will probably time out.** Leave "Use Claude" off on Vercel. Ask EDGE open questions (one call each) are fine.
6. **For saved analyses that last, host the backend on a service that has a disk** (Railway, Fly.io, Hugging Face Spaces) and keep only the UI on Vercel. See "Option B" at the end.

## Part 1: put the code on GitHub

Do this once, in PowerShell, in the project folder.

1. Create the repository: go to https://github.com/new, name it `razorpay-edge`, choose **Private**, leave every box unticked, click **Create repository**.
2. Commit the Vercel changes:

```bash
git add -A
git commit -m "Add Vercel deployment"
```

3. Connect and push (replace `YOUR-USERNAME`):

```bash
git remote add origin https://github.com/YOUR-USERNAME/razorpay-edge.git
git push -u origin main
```

GitHub will ask you to sign in the first time.

4. Check on the repository page that there is **no** `.env` file and no `data/` folder. Both are excluded by `.gitignore`. Your API key must never be in the repository.

## Part 2: deploy on Vercel

1. Go to https://vercel.com and choose **Sign Up**, then **Continue with GitHub**.
2. Click **Add New**, then **Project**. If asked, allow Vercel to see the `razorpay-edge` repository.
3. Click **Import** next to `razorpay-edge`.
4. On the configure screen:
   - **Framework Preset:** `Other`.
   - **Root Directory:** leave as the repository root.
   - **Build and Output settings:** leave everything alone. `vercel.json` controls the build.
5. Open **Environment Variables** and add (names exactly as written):

| Name | Value | Needed? |
|---|---|---|
| `ANTHROPIC_API_KEY` | your key | Only if reviewers should use open-ended Ask EDGE questions or Claude drafts. Leave it out otherwise. |
| `CLAUDE_MODEL` | `claude-sonnet-5-5` | Optional |
| `LLM_MAX_CALLS` | `130` | Optional spending cap |
| `EDGE_ACCESS_PASSWORD` | a password | Recommended: stops anyone with the link running analyses on your key. The browser asks for a login the first time the app calls the API. |
| `EDGE_ACCESS_USER` | `edge` | Optional (this is the default) |

6. Click **Deploy** and wait for the build (a few minutes). When it finishes, Vercel shows your link: `https://razorpay-edge-xxxx.vercel.app`.
7. **Raise the function time limit:** open the project, then **Settings**, then **Functions** (or **Fluid Compute**), and set **Max Duration** to 60 seconds or more. Then go to **Deployments**, open the latest, and choose **Redeploy**.
8. **Make the link public:** **Settings**, then **Deployment Protection**. Turn **Vercel Authentication** off if reviewers do not have Vercel accounts. Use `EDGE_ACCESS_PASSWORD` as your protection instead.
9. Open the link, click **Start a New Analysis**, upload a workbook, and check the Overview loads.

Every later `git push` to `main` redeploys automatically.

## If something goes wrong

| Symptom | Likely cause and fix |
|---|---|
| Build fails: function larger than 250 MB | The Python packages (pandas, numpy and so on) are near the limit. Remove `anthropic` from `requirements.txt` if you do not need Claude, then redeploy. |
| Page loads but every action shows an error | Open `https://your-link/api/health`. If it is a 404 or a Python error, open **Deployments**, then the latest one, then **Functions** logs. |
| Every page, including the home page, shows "404 NOT_FOUND" | The UI build is published under `/web`, so the `vercel.json` routes must send pages to `/web/index.html`. Use the current `vercel.json` from the repository, push, and let Vercel redeploy. If it persists, open **Deployments**, then the latest, then **Build Logs**, and check that the build finished without errors. |
| "Analysis not found" after a minute | Saved analyses are temporary on Vercel (limit 1). Re-run, or use Option B. |
| Upload fails with 413 | The file is over about 4.5 MB. |
| Robustness test or evaluation package times out | Raise Max Duration (step 7). |

## Option B: UI on Vercel, backend on a host with a disk

If you want analyses to persist:

1. Deploy the backend to Railway, Fly.io or Hugging Face Spaces using the included `Dockerfile` (it serves the API and the UI on `$PORT`). Note its URL, for example `https://edge-api.example.com`.
2. In `vercel.json`, replace the whole contents with:

```json
{
  "version": 2,
  "builds": [{ "src": "web/package.json", "use": "@vercel/static-build", "config": { "distDir": "dist" } }],
  "routes": [
    { "src": "/api/(.*)", "dest": "https://edge-api.example.com/api/$1" },
    { "src": "/assets/(.*)", "dest": "/web/assets/$1" },
    { "src": "/(.*\\.(?:webp|png|svg|ico|txt|json|js|css|map|woff2?))", "dest": "/web/$1" },
    { "src": "/(.*)", "dest": "/web/index.html" }
  ]
}
```

3. Push. Vercel then serves only the UI and forwards `/api/*` to your backend. Set the API key and `EDGE_ACCESS_PASSWORD` on the backend host instead of on Vercel.

## What changed in the code for Vercel

- `src/config.py`: when `VERCEL` is set, saved files go to a temp folder (`EDGE_DATA_DIR` overrides it).
- `api/main.py`: background jobs run before the reply when on Vercel.
- `vercel.json`, `.vercelignore`, `.python-version`: build and routing.
- `requirements.txt` is runtime only; test tools moved to `requirements-dev.txt` (use `pip install -r requirements-dev.txt` to run the tests).
- `tests/test_serverless.py` runs an upload, analysis, robustness test and export in Vercel mode.
