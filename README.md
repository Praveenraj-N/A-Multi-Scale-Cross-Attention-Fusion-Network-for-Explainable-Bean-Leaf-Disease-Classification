# MSCAF-Net

MSCAF-Net classifies bean leaf images as angular leaf spot, bean rust, or healthy. The web app displays the prediction, confidence scores, and a Grad-CAM overlay. Its outbreak-monitoring map shows reported observations and inspection priorities for nearby plantations.

## Run locally on Windows

Use Python 3.12, Node.js 22.12 or newer, and npm. Open the cloned repository in PowerShell.

### 1. Add the trained model

Copy the trained `baseline_mscaf_full_best.pth` file into the `checkpoints/` directory. Git excludes model weights, so a fresh clone needs a separate copy of this file. Ask the project maintainer for the checkpoint or train it using the [Kaggle training guide](KAGGLE_RUN.md).

### 2. Start the backend

Run these commands from the repository root. If `.venv` already exists, skip the first command.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Leave this terminal open. Check that the backend is ready at [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health).

### 3. Start the frontend

Open a second PowerShell terminal at the repository root and run:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

- [Dashboard](http://localhost:5173/) shows the model overview and research results.
- [Disease Prediction](http://localhost:5173/predict) lets you upload a bean leaf image and view the model's output.
- [Outbreak Monitoring](http://localhost:5173/outbreak) opens the map. To enable submissions, follow the access-key setup in the [outbreak monitoring guide](OUTBREAK_MONITORING.md).

### Preview the interface without model weights

In the `frontend` directory, run `npm.cmd ci` if dependencies are missing, then start the frontend in mock mode. The prediction page displays a labelled sample result.

```powershell
$env:VITE_USE_MOCK = 'true'
npm.cmd run dev
```

To return to live predictions, stop the frontend, run `Remove-Item Env:VITE_USE_MOCK` in that terminal, and restart it with the backend running.
