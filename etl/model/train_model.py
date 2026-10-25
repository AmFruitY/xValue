"""
train_model.py
==============
Trains the transfer-fee model on df_xvalue (Exploitation Zone) and keeps the
best model for the front end. Same model and experiments as the notebook
script_entrenamiento_modelo.ipynb: XGBoost on log(fee), with scikit-learn for
filling gaps and encoding categories, four experiments (global,
global+historial, field players, goalkeepers).

WHAT CHANGED FROM THE NOTEBOOK (so it can run unattended in Airflow)
    1. Reads df_xvalue from MinIO; writes everything to
       exploitation_zone/models/ instead of a local models/ folder.
    2. Stable train/test split. The notebook's split depended on the order in
       which rows arrived ("depende del orden de filas"), so each run could
       test on different transfers. Now each transfer goes to train or test by
       a fingerprint of its own values (player, season, club, window, fee):
       the same transfer always lands on the same side, whatever the order.
    3. Champion vs challenger. The notebook compared today's score with the
       best score ever saved, but those were measured on different test sets.
       Now the saved best model (champion) is re-scored on TODAY's test set,
       next to the new model (challenger); the better one is kept.
    4. n_jobs = 2 (the VM has 2 processor cores). The hyperparameter search
       stays OFF: it trains hundreds of models; run it by hand when needed.

OUTPUT (exploitation_zone/models/)
    xvalue_xgb_best.joblib        the model the front end uses
    best_metrics.json             its scores, parameters and date
    experimentos_metricas.csv     every experiment's scores, this run
    test_predictions.parquet      fee vs prediction on the test set, this run

SETTINGS: EXPLOITATION_ROOT (default s3://xvalue-data/exploitation_zone)
          MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY (only for MinIO)

RUN:   python train_model.py
"""

import hashlib
import io
import json
import os
import re
import sys
import time
from datetime import datetime

import duckdb
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBRegressor

# ---------------- Settings (as in the notebook) ----------------
TARGET = "fee"
TRAIN_FRAC = 0.80
USAR_PESOS = True            # sample_weight = log1p(fee), normalised
N_JOBS = 2                   # VM cores
REGISTERED = "global"        # the experiment that becomes the front end's model

COLS_NUM = [
    'season', 'age', 'avg_MP_acum', 'avg_Starts_acum', 'avg_Gls_acum', 'avg_Ast_acum', 'avg_G+A_acum',
    'avg_G-PK_acum', 'avg_PK_acum', 'avg_PK_perc_acum', 'avg_CrdY_acum',
    'avg_CrdR_acum', 'avg_Gls_1_acum', 'avg_Ast_1_acum', 'avg_G+A_1_acum',
    'avg_G+A-PK_acum', 'avg_Sh_acum', 'avg_SoT_acum',
    'avg_SoT%_acum', 'avg_Sh/90_acum', 'avg_SoT/90_acum', 'avg_G/Sh_acum',
    'avg_G/SoT_acum', 'avg_Mn/MP_acum', 'avg_Mn/Start_acum',
    'avg_Compl_acum', 'avg_Subs_acum', 'avg_Mn/Sub_acum', 'avg_unSub_acum',
    'avg_PPM_acum', 'avg_onG_acum', 'avg_onGA_acum', 'avg_+/-_acum',
    'avg_+/-90_acum', 'avg_On-Off_acum', 'avg_2CrdY_acum', 'avg_Fls_acum',
    'avg_Fld_acum', 'avg_Off_acum', 'avg_Crs_acum', 'avg_Int_acum',
    'avg_TklW_acum', 'avg_PKwon_acum', 'avg_PKcon_acum', 'avg_OG_acum',
    'num_equipos_acum', 'total_days_out', 'total_games_missed',
    'n_distinct_injuries', 'n_injury_records', 'max_same_injury_repeats',
    'has_recurrent_injury', 'age_at_last_injury', 'age_at_first_injury',
    'worst_injury_days',
]
COLS_CAT = ['league', 'club', 'window', 'nationality', 'position']

# Field-player stats: 86-99% empty for goalkeepers and unrelated to their value
GK_EXCLUIR = [
    'avg_Gls_acum', 'avg_Gls_1_acum', 'avg_Ast_acum', 'avg_Ast_1_acum', 'avg_G+A_acum',
    'avg_G+A_1_acum', 'avg_G-PK_acum', 'avg_G+A-PK_acum', 'avg_PK_acum', 'avg_PK_perc_acum',
    'avg_PKwon_acum', 'avg_PKcon_acum', 'avg_Sh_acum', 'avg_Sh/90_acum', 'avg_SoT_acum',
    'avg_SoT/90_acum', 'avg_SoT%_acum', 'avg_G/Sh_acum', 'avg_G/SoT_acum', 'avg_Crs_acum',
    'avg_TklW_acum', 'avg_Int_acum', 'avg_Off_acum', 'avg_Fld_acum', 'avg_OG_acum',
    'age_at_first_injury', 'age_at_last_injury',
]

PARAMS_GLOBAL = dict(n_estimators=1750, learning_rate=0.10, max_depth=3, min_child_weight=15,
                     subsample=0.9, colsample_bytree=0.5, reg_alpha=1.5, reg_lambda=5)
PARAMS_GK = dict(n_estimators=600, learning_rate=0.05, max_depth=3, min_child_weight=10,
                 subsample=0.8, colsample_bytree=0.6, reg_alpha=1.0, reg_lambda=5)


# ---------------- Storage: MinIO or a local folder ----------------
ROOT = os.environ.get("EXPLOITATION_ROOT", "s3://xvalue-data/exploitation_zone").rstrip("/")
ON_S3 = ROOT.startswith(("s3://", "s3a://"))
if ON_S3:
    from minio import Minio
    BUCKET, _, PREFIX = ROOT.split("://", 1)[1].partition("/")
    _endpoint = os.environ["MINIO_ENDPOINT"]
    MINIO = Minio(re.sub(r"^https?://", "", _endpoint), access_key=os.environ["MINIO_ACCESS_KEY"],
                  secret_key=os.environ["MINIO_SECRET_KEY"], secure=_endpoint.startswith("https"))


def save(rel: str, data: bytes):
    if ON_S3:
        MINIO.put_object(BUCKET, f"{PREFIX}/{rel}".lstrip("/"), io.BytesIO(data), len(data))
    else:
        path = os.path.join(ROOT, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
    print(f"  saved {ROOT}/{rel}")


def load(rel: str):
    """Bytes of a saved file, or None if it doesn't exist yet."""
    try:
        if ON_S3:
            response = MINIO.get_object(BUCKET, f"{PREFIX}/{rel}".lstrip("/"))
            return response.read()
        with open(os.path.join(ROOT, rel), "rb") as f:
            return f.read()
    except Exception:
        return None


def read_df_xvalue() -> pd.DataFrame:
    con = duckdb.connect()
    path = f"{ROOT}/df_xvalue/df_xvalue.parquet"
    if ON_S3:
        con.sql("INSTALL httpfs; LOAD httpfs;")
        con.execute(f"""CREATE SECRET (TYPE s3, KEY_ID '{os.environ["MINIO_ACCESS_KEY"]}',
            SECRET '{os.environ["MINIO_SECRET_KEY"]}', ENDPOINT '{re.sub(r"^https?://", "", _endpoint)}',
            URL_STYLE 'path', USE_SSL {str(_endpoint.startswith("https")).lower()})""")
        path = "s3://" + path.split("://", 1)[1]
    return con.sql(f"SELECT * FROM '{path}' WHERE fee IS NOT NULL AND fee > 0").df()


# ---------------- Model pieces (as in the notebook) ----------------
def construir_pipeline(num, cat, params):
    prep = ColumnTransformer([
        ("num", SimpleImputer(strategy="median"), num),
        ("cat", Pipeline([
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=True)),
        ]), cat),
    ])
    xgb = XGBRegressor(objective="reg:squarederror", n_jobs=N_JOBS, random_state=42, **params)
    return Pipeline([("preprocessor", prep), ("model", xgb)])


def pesos_log_fee(y_log):
    w = np.asarray(y_log, dtype=float)
    return w / w.mean()


def metricas(y_log_true, y_log_pred):
    y_log_true = np.asarray(y_log_true, dtype=float)
    y_log_pred = np.asarray(y_log_pred, dtype=float)
    y, p = np.expm1(y_log_true), np.maximum(np.expm1(y_log_pred), 0)
    return {
        "rmse_log": float(np.sqrt(mean_squared_error(y_log_true, y_log_pred))),
        "mae_log": float(mean_absolute_error(y_log_true, y_log_pred)),
        "r2_log": float(r2_score(y_log_true, y_log_pred)),
        "rmse_eur": float(np.sqrt(mean_squared_error(y, p))),
        "mae_eur": float(mean_absolute_error(y, p)),
        "r2_eur": float(r2_score(y, p)),
        "sesgo_log": float(np.mean(y_log_pred - y_log_true)),   # >0 = overestimates
    }


def in_train(row) -> bool:
    """Stable split: a fingerprint of the transfer's own values decides train
    or test, so the same transfer is always on the same side."""
    key = "|".join(str(row.get(c)) for c in ("player_name", "season", "club", "window", "fee"))
    fraction = int(hashlib.md5(key.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return fraction < TRAIN_FRAC


def main():
    t_start = time.time()
    df = read_df_xvalue()
    missing = [c for c in COLS_NUM + COLS_CAT if c not in df.columns]
    if missing:
        print(f"[WARN] columns not in df_xvalue, left out: {missing}")
    num = [c for c in COLS_NUM if c in df.columns]
    cat = [c for c in COLS_CAT if c in df.columns]

    num_float = [c for c in num if c != "season"]
    df[num_float] = df[num_float].astype("float64").replace([np.inf, -np.inf], np.nan)
    for c in cat:
        df[c] = df[c].astype("object").where(df[c].notna(), np.nan)
    df["grupo"] = np.where(df["position"].eq("Goalkeeper"), "GK", "Campo")
    df["tiene_historial"] = df["avg_MP_acum"].notna().astype(int) if "avg_MP_acum" in df else 0

    num_gk = [c for c in num if c not in GK_EXCLUIR] + ["tiene_historial"]
    cat_gk = [c for c in cat if c != "position"]

    mask = df.apply(in_train, axis=1)
    train, test = df[mask].copy(), df[~mask].copy()
    y_test_log = np.log1p(test[TARGET])
    print(f"Rows with fee > 0: {len(df):,}  |  train {len(train):,}  test {len(test):,}")
    if len(test) < 20 or len(train) < 50:
        sys.exit("[ERR] too few transfers to train and test reliably")

    experimentos = {
        "global":           (None,    num,                         cat,    PARAMS_GLOBAL),
        "global+historial": (None,    num + ["tiene_historial"],   cat,    PARAMS_GLOBAL),
        "campo":            ("Campo", num,                         cat,    PARAMS_GLOBAL),
        "gk":               ("GK",    num_gk,                      cat_gk, PARAMS_GK),
    }
    modelos, preds = {}, pd.DataFrame(index=test.index)
    for nombre, (grupo, n_cols, c_cols, params) in experimentos.items():
        tr = train if grupo is None else train[train["grupo"] == grupo]
        te = test if grupo is None else test[test["grupo"] == grupo]
        if len(tr) < 20 or len(te) == 0:
            print(f"{nombre:<18} skipped (too few rows)")
            continue
        y_tr = np.log1p(tr[TARGET])
        t0 = time.time()
        pipe = construir_pipeline(n_cols, c_cols, params)
        pipe.fit(tr[n_cols + c_cols], y_tr, model__sample_weight=pesos_log_fee(y_tr) if USAR_PESOS else None)
        preds.loc[te.index, nombre] = pipe.predict(te[n_cols + c_cols])
        modelos[nombre] = (pipe, n_cols + c_cols)
        rmse = np.sqrt(mean_squared_error(y_test_log.loc[te.index], preds.loc[te.index, nombre]))
        print(f"{nombre:<18} train={len(tr):>6,}  test={len(te):>5,}  RMSE log={rmse:.4f}  ({time.time() - t0:.0f}s)")
    if {"gk", "campo"} <= set(preds.columns):
        preds["mixto"] = preds["gk"].fillna(preds["campo"])

    # Metrics table for every experiment and subset
    subsets = {"GK": test.index[test["grupo"] == "GK"], "Campo": test.index[test["grupo"] == "Campo"],
               "Todos": test.index}
    rows = [{"subconjunto": s, "modelo": m, "n": len(idx), **metricas(y_test_log.loc[idx], preds.loc[idx, m])}
            for s, idx in subsets.items() for m in preds.columns
            if len(idx) and not preds.loc[idx, m].isna().any()]
    tabla = pd.DataFrame(rows)
    print("\n" + tabla.to_string(index=False, float_format=lambda x: f"{x:,.4f}" if abs(x) < 100 else f"{x:,.0f}"))

    # ── Champion vs challenger, both scored on TODAY's test set ──────────
    challenger, columns = modelos[REGISTERED]
    new = metricas(y_test_log, preds[REGISTERED])
    old, saved = None, load("models/xvalue_xgb_best.joblib")
    if saved is not None:
        try:
            champion = joblib.load(io.BytesIO(saved))
            old = metricas(y_test_log, champion.predict(test[columns]))
        except Exception as error:      # e.g. the features changed since it was saved
            print(f"\n[WARN] saved model can't be scored on today's data ({error}); replacing it")
    print(f"\nChallenger ({REGISTERED}): RMSE log {new['rmse_log']:.4f}"
          + (f"  |  champion on the same test set: {old['rmse_log']:.4f}" if old else "  |  no champion yet"))

    save("models/experimentos_metricas.csv", tabla.to_csv(index=False).encode())
    out = test[["player_name", "season", "position", "grupo", TARGET]].copy()
    for c in preds.columns:
        out[f"pred_{c}"] = np.maximum(np.expm1(preds[c]), 0)
    buf = io.BytesIO()
    out.to_parquet(buf, index=False)
    save("models/test_predictions.parquet", buf.getvalue())

    if old is None or new["rmse_log"] < old["rmse_log"]:
        buf = io.BytesIO()
        joblib.dump(challenger, buf)
        save("models/xvalue_xgb_best.joblib", buf.getvalue())
        record = {"timestamp": datetime.now().isoformat(timespec="seconds"), "experimento": REGISTERED,
                  "metrics": new, "champion_rmse_log_same_test": old["rmse_log"] if old else None,
                  "params": experimentos[REGISTERED][3], "features": columns,
                  "train_rows": int(len(train)), "test_rows": int(len(test))}
        save("models/best_metrics.json", json.dumps(record, indent=2, ensure_ascii=False).encode())
        print("New best model saved.")
    else:
        print("The champion is still better: kept.")
    print(f"Done in {time.time() - t_start:.0f}s")


if __name__ == "__main__":
    main()
