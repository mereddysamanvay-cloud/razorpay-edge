# Razorpay EDGE: build the UI (first run) and serve everything on http://localhost:8000
$node = "C:\Users\saman\tools\node-v22.11.0-win-x64"
if (Test-Path $node) { $env:Path = "$node;$env:Path" }
if (-not (Test-Path web\node_modules)) { Push-Location web; npm install; Pop-Location }
if (-not (Test-Path web\dist)) { Push-Location web; npm run build; Pop-Location }
python -m uvicorn api.main:app --port 8000
