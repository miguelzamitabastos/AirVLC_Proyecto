# Goal Description

The user has completed training of the LSTM model for air quality forecasting (PM2.5) using the notebook `05_Colab_LSTM_Model.ipynb`.  The notebook reports basic exploratory statistics, a baseline LSTM architecture (2–3 stacked LSTM layers with dropout), and evaluation metrics (MAE, MSE, R²) on the validation set.  The user now wants a concrete, high‑quality plan for the next three days (Tuesday 6, Wednesday 7, Thursday 8) of **Week 2** to further improve the model.

The plan should:

1. **Analyse the current training results** – interpret loss curves, validation scores, and data distribution.
2. **Identify concrete improvement steps** – hyper‑parameter search, architectural tweaks, regularisation, feature engineering, and evaluation strategy.
3. **Provide a day‑by‑day task list** that the user can follow, with clear deliverables and verification criteria.
4. **Prepare the groundwork** for later weeks (e.g., automated training pipeline, experiment tracking).

---

## User Review Required

Please confirm that the following high‑level objectives match your expectations:

- **Day 6 (Tuesday)** – Systematic hyper‑parameter exploration (learning‑rate, batch size, optimizer, sequence length, dropout). 
- **Day 7 (Wednesday)** – Model architecture experiments (stacked LSTM depth, bidirectional layers, attention, residual connections, richer input features such as cyclical time encodings). 
- **Day 8 (Thursday)** – Advanced training tricks (early stopping, learning‑rate schedules, regularisation, ensembling) and rigorous evaluation (cross‑validation, error analysis, visual diagnostics).

If you would like to add, remove, or reorder any of these items, let me know.

---

## Open Questions

| Question | Impact | Suggested Resolution |
|----------|--------|---------------------|
| **Metric priority** – Do you prefer to minimise MAE, RMSE, or maximise R² for the production model? | Determines the loss function and early‑stopping criterion. | Choose one (e.g., MAE) and I will configure the experiments accordingly. |
| **Computational budget** – How many training runs can you afford per day (GPU hours / Colab limits)? | Affects the granularity of the hyper‑parameter grid. | Rough estimate (e.g., 4–6 runs per day) will help me size the search. |
| **Sequence length** – Currently the notebook uses a fixed window (e.g., 24 h). Would you like to experiment with longer windows (48 h, 72 h) or multi‑step forecasts? | Influences data preparation and model input shape. | Confirm the desired horizon(s). |
| **Feature set** – Do you want to add additional engineered features (e.g., sin/cos hour‑of‑day, lagged weather variables, rolling statistics) now or later? | Impacts data pipeline complexity. | I will propose a small set for Day 7 and can extend later. |
| **Experiment tracking** – Do you have a preferred tool (MLflow, Weights & Biases, simple CSV logs)? | Helps automate reproducibility. | Suggest a lightweight CSV logger for now. |

---

## Proposed Changes

### Day 6 – Hyper‑Parameter Exploration (Tuesday)

| Task | Description | Deliverable |
|------|-------------|------------|
| 6.1 | **Define a small grid** for learning‑rate (1e‑4, 5e‑4, 1e‑3), batch size (32, 64), optimizer (Adam, RMSprop), and dropout (0.2, 0.4). | `hyperparams_grid.json` |
| 6.2 | **Create a reusable training function** (`train_lstm`) that accepts the hyper‑parameters, logs loss/MAE for train & val, and saves the best checkpoint. | `train_lstm.py` (or a new notebook cell) |
| 6.3 | **Run the grid** (2‑3 runs per night) on Colab, using `%%time` to record runtime. | CSV log `day6_hyperparams_results.csv` |
| 6.4 | **Analyse results** – Plot heat‑maps of validation MAE vs learning‑rate / dropout, identify the top‑2 configurations. | Plot PNG `day6_hyperparam_heatmap.png` |
| 6.5 | **Select the best config** and **store the checkpoint** for Day 7. | `best_checkpoint.h5` |

### Day 7 – Architecture & Feature Engineering (Wednesday)

| Task | Description | Deliverable |
|------|-------------|------------|
| 7.1 | **Add cyclical time encodings** (sin/cos of hour‑of‑day and day‑of‑week) to the feature matrix. | Updated DataFrame with columns `hour_sin`, `hour_cos`, `dow_sin`, `dow_cos` |
| 7.2 | **Experiment with deeper LSTM** – 2‑layer vs 3‑layer, optional **Bidirectional** wrapper. | New model definitions in notebook (e.g., `model_bidirectional`) |
| 7.3 | **Introduce attention** – simple Bahdanau attention after the final LSTM output. | `AttentionLayer` class and integrated model |
| 7.4 | **Residual connections** – add a shortcut from input to penultimate dense layer (optional). | Modified model architecture |
| 7.5 | **Train each architecture** using the best hyper‑parameters from Day 6 (learning‑rate, dropout). Log the same metrics. | `day7_architecture_results.csv` |
| 7.6 | **Visualise** training curves and compare validation MAE/RMSE across architectures. | Plot `day7_architecture_comparison.png` |
| 7.7 | **Select the winning architecture** (lowest validation MAE) and save its checkpoint. | `best_architecture_checkpoint.h5` |

### Day 8 – Advanced Training Tricks & Evaluation (Thursday)

| Task | Description | Deliverable |
|------|-------------|------------|
| 8.1 | **Early stopping** – monitor validation MAE with patience 5, restore best weights. | Updated `train_lstm` with callback |
| 8.2 | **Learning‑rate scheduler** – ReduceLROnPlateau (factor 0.5, cooldown 2). | Callback added |
| 8.3 | **Regularisation** – add L2 weight decay (1e‑4) and/or Gaussian noise to inputs. | Model re‑compiled |
| 8.4 | **Ensemble** – train three models with different seeds, average predictions. | `ensemble_predict.py` that loads three checkpoints and averages forecasts |
| 8.5 | **Cross‑validation** – 5‑fold time‑series split (respecting chronology). Compute mean/standard deviation of MAE across folds. | CSV `day8_cv_results.csv` |
| 8.6 | **Error analysis** – plot true vs predicted PM2.5 for a few stations, compute residual distribution, identify systematic bias (e.g., under‑prediction at high values). | Figures `prediction_vs_true_stationX.png`, `residual_hist.png` |
| 8.7 | **Documentation** – update the notebook with a “Training & Evaluation” section summarising the findings, hyper‑parameters, and final performance. | Updated notebook cell markdown |

---

## Verification Plan

### Automated Checks

- **Metric thresholds** – After Day 8, the final ensemble should achieve **MAE < 12 µg/m³** (the baseline in the current notebook is ~13 µg/m³). This will be verified by a simple Python assertion on the CV results CSV.
- **Reproducibility** – All training scripts must accept a `seed` argument and set NumPy/TensorFlow seeds accordingly. Running the same script twice should yield identical validation scores (within Monte‑Carlo noise < 0.1 MAE).
- **Artifact existence** – The output files listed above (`*_results.csv`, PNG plots, final checkpoint) will be programmatically checked for existence.

### Manual Review

- **Plot inspection** – Ensure loss curves are smooth, no divergence, and that early‑stopping actually truncates training.
- **Residual analysis** – Verify that residuals are approximately zero‑mean and homoscedastic; if not, note recommendations for next week.
- **Notebook readability** – Confirm markdown sections clearly explain each experiment and that code cells are runnable end‑to‑end.

---

## Next‑Week Preparation (Preview)

- **Automated pipeline** – wrap the whole training‑evaluation flow into a single script (`run_experiment.py`) that can be scheduled via cron or a CI job.
- **Model serving** – export the final Keras model to TensorFlow SavedModel format for downstream inference.
- **Feature store** – store the engineered time‑features and lags in a Parquet file for fast loading.

---

**Please review the above plan** and reply with any adjustments (e.g., different metric focus, additional features, or constraints). Once approved, I will start implementing the scripts and logging infrastructure on Day 6.
