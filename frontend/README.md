# xValue Web

Next.js frontend for the xValue model results: an xValue range of the transfer fee for each player–club record of the 2025/26 season, organised around Comprar, Vender, Comparar and Cómo funciona.

The server reads the model results Parquet and serves small pages to the browser:

`Parquet -> parquet-source -> repository -> /api/predictions -> client -> UI`

## Data

The compatible model results file is currently `predicciones_xvalue_final_v1.parquet`. It is not versioned (`data/processed/` is git-ignored), so a team member must obtain that file and either:

a) place it at the default location, `../data/processed/model_outputs/predicciones_xvalue_final_v1.parquet` (relative to `frontend/`); or
b) set `XVALUE_PREDICTIONS_PARQUET` to its absolute path before starting the app.

Without the file, the page starts but shows a load error.

Example with `XVALUE_PREDICTIONS_PARQUET` (bash):

```bash
XVALUE_PREDICTIONS_PARQUET=/path/to/predicciones_xvalue_final_v1.parquet npm run dev
```

PowerShell:

```powershell
$env:XVALUE_PREDICTIONS_PARQUET = "D:\path\to\predicciones_xvalue_final_v1.parquet"
npm run dev
```

## Local development

Validated with Node 24.18.0.

```bash
npm install
npm run dev
```

Then open `http://localhost:3000`.

## Validation

```bash
npm test
npm run lint
npm run build
```

Design decisions, checks and pending items are documented in [DEMO-NEURAL.md](DEMO-NEURAL.md).
