---
language:
- es
license: cc-by-nc-4.0
library_name: xgboost
pipeline_tag: tabular-regression
tags:
- football
- soccer
- transfer-fee
- tabular
- xgboost
- injuries
- regression
---

# Modelo de predicción de fees de fichaje en fútbol (XGBoost)

Regresor XGBoost que estima el importe (fee) de un fichaje de fútbol a partir del
rendimiento acumulado del jugador, su perfil y su historial de lesiones.
Desarrollado en el marco de un Trabajo Fin de Máster (TFM).

- **Autor:** Alejandro Diaz & Joshua Lorenzana & Sebastian Saldias
- **Institución / máster:** Universidad Politécnica de Cataluña - Máster en Big Data, Data Science & Engineering
- **Versión:** 1
- **Contacto:** alexdiruz@gmail.com

## Detalles del modelo

- **Tipo:** `XGBRegressor` dentro de un `Pipeline` de scikit-learn
  (imputación + one-hot encoding + modelo). El preprocesado va incluido en el
  pipeline, por lo que se puede predecir directamente sobre un DataFrame con las
  columnas originales.
- **Target:** `log1p(fee)`. Las predicciones se revierten con `expm1` para obtener euros.
- **Objetivo de entrenamiento:** `reg:squarederror`, con pesos de muestra proporcionales
  a `log1p(fee)` (normalizados por su media) para reducir la subestimación en los
  fichajes caros.

## Usos previstos

- Estimar el fee de un fichaje a partir de estadísticas de rendimiento, perfil
  del jugador y antecedentes de lesiones.
- Comparar la predicción del modelo con el valor de mercado de Transfermarkt, como se
  hace en el TFM (diferencia absoluta entre el fee real y la predicción frente a la
  diferencia entre el valor de mercado y la predicción).

## Usos no recomendados y limitaciones

- **No está pensado para decisiones reales** de contratación, valoración económica
  ni apuestas. Es un trabajo académico.
- **Solo cubre fichajes con fee positivo.** Se entrenó con `fee > 0`, así que no
  modela cesiones ni traspasos gratuitos.
- **Subestimación en fichajes caros.** El análisis de residuos mostró un sesgo
  sistemático en la cola alta: los percentiles P95-P100 concentran ~67% del error
  cuadrático con menos del 5% de los casos. Los pesos de muestra mitigan el problema
  pero no lo eliminan.
- **Capacidad explicativa moderada.** El R² en escala log es 0.54 (ver evaluación).
- **Posibles sesgos** por liga, club o nacionalidad, que entran como variables
  categóricas y pueden reflejar desigualdades históricas del mercado de fichajes.
- **Dependencia del periodo.** El mercado de fichajes cambia con el tiempo (inflación
  de fees, nuevos actores). Las predicciones sobre periodos fuera del rango de
  entrenamiento pueden ser poco fiables.
- Incluye las temporadas desde 2010/2011 hasta 2024/2025 de las 5 principales ligas de Europa (La Liga, Premier League, Bundesliga, Serie A y Ligue One)

## Datos de entrenamiento

- **Fuente:** [PENDIENTE: origen de las estadísticas de rendimiento, de las lesiones y de los fees]
- **Periodo:** desde la temporada 2010/2011.
- **Filtros:** `fee IS NOT NULL` y `fee > 0`.
- **Partición:** 80% train / 20% test, aleatoria, con semilla 42.
  La búsqueda de hiperparámetros usa validación cruzada solo sobre train.

### Variables de entrada

**Numéricas**

- Contexto: `season`, `age`, `num_equipos_acum`.
- Rendimiento acumulado por temporada (prefijo `avg_`, sufijo `_acum`): partidos,
  titularidades, goles, asistencias, penaltis, tarjetas, tiros, tiros a puerta,
  minutos por partido, suplencias, goles a favor y en contra con el jugador en
  campo, faltas, centros, intercepciones, entre otras.
- Lesiones: `total_days_out`, `total_games_missed`, `n_distinct_injuries`,
  `n_injury_records`, `max_same_injury_repeats`, `has_recurrent_injury`,
  `age_at_first_injury`, `age_at_last_injury`, `worst_injury_days`.

**Categóricas:** `league`, `club`, `window`, `nationality`, `position`.

**Excluidas del modelo:** `player_id`, `avg_Min_acum`, `avg_90s_acum`,
`avg_G-PK_1_acum`, `avg_PKatt_acum`, `avg_Min%_acum`.

### Preprocesado

1. Los valores infinitos se sustituyen por NaN.
2. Variables numéricas: imputación por mediana.
3. Variables categóricas: imputación por moda y one-hot encoding con
   `handle_unknown="ignore"`.

## Entrenamiento

- **Búsqueda de hiperparámetros:** `RandomizedSearchCV`, 60 iteraciones, CV de 3 folds
  sobre train, métrica `neg_root_mean_squared_error` sobre `log1p(fee)`.
- **Espacio de búsqueda:**

| Hiperparámetro | Valores |
|---|---|
| `max_depth` | 3, 4, 5 |
| `learning_rate` | 0.05, 0.07, 0.08, 0.10 |
| `n_estimators` | 1000, 1250, 1500, 1750 |
| `min_child_weight` | 7, 10, 15 |
| `subsample` | 0.8, 0.9, 1.0 |
| `colsample_bytree` | 0.5, 0.6, 0.7 |
| `reg_alpha` | 0.5, 1.0, 1.5, 2.0 |
| `reg_lambda` | 2, 3, 5 |

- **Mejores hiperparámetros:**
| Hiperparámetro | Valor |
|---|---|
| `subsample` | 0.8 |
| `reg_lambda` | 5 |
| `reg_alpha` | 0.5 |
| `n_estimators` | 1500 |
| `min_child_weight` | 7 |
| `max_depth` | 5 |
| `learning_rate` | 0.05 |
| `colsample_bytree` | 0.5 |

- **Hardware / tiempo de entrenamiento:** 5m 16.4s

## Evaluación

Métricas sobre el conjunto de test (20% de los datos, semilla 42).

| Escala | RMSE | MAE | R² |
|---|---|---|---|
| Log (`log1p(fee)`) | 1.0262 | 0.7422 | 0.5377 |
| Euros (€) | 6,661,431.81 | 3,255,870.18 | 0.6089 |

Referencia frente a una versión anterior del modelo (entrenada con otro periodo de
datos y sin pesos de muestra, por lo que la comparación es **orientativa**):

| Métrica (log) | Versión anterior | Versión actual |
|---|---|---|
| RMSE | 1.0101 | 1.0262 |
| MAE | ~0.70 | 0.7422 |
| R² | 0.5171 | 0.5377 |

El R² mejora, mientras que RMSE y MAE en escala log empeoran ligeramente. Es un
comportamiento esperable al ponderar más los fichajes caros: el modelo cede algo de
precisión en los fichajes baratos a cambio de acercarse más a los caros, lo que se
refleja en un R² de 0.61 en euros.

## Cómo usarlo

```python
import joblib
import numpy as np
import pandas as pd

# [PENDIENTE: subir el archivo best_model_2.joblib al repositorio]
model = joblib.load("best_model_2.joblib")

# X debe contener las mismas columnas numéricas y categóricas usadas en el entrenamiento
X = pd.read_parquet("jugadores.parquet")

pred_log = model.predict(X)
fee_estimado = np.expm1(pred_log)  # fee estimado en euros
```

## Citación

```bibtex
@mastersthesis{2026xvalue,
  author  = {Diaz, Alejandro and Lorenzana, Joshua and Saldias, Sebastian},
  title   = {[xValue]},
  school  = {Universitat Politècnica de Catalunya},
  type    = {Trabajo Final de Máster},
  year    = {2026},
  url     = {[enlace al repositorio UPCommons o a tu GitHub]}
}
```
