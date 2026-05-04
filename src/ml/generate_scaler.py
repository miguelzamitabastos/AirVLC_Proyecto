import pandas as pd
from sklearn.preprocessing import MinMaxScaler
import pickle
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
dataset_path = os.path.join(PROJECT_ROOT, 'data/processed/master_dataset_colab.csv')
models_dir = os.path.join(PROJECT_ROOT, 'models')
scaler_path = os.path.join(models_dir, 'scaler_day7.pkl')

print(f"Leyendo dataset: {dataset_path}")
df = pd.read_csv(dataset_path)

# Las columnas a escalar son todas excepto 'fecha' y 'station_name'
cols_to_scale = [c for c in df.columns if c not in ('fecha', 'station_name')]

print(f"Features ({len(cols_to_scale)}): {cols_to_scale}")

scaler = MinMaxScaler()
scaler.fit(df[cols_to_scale])

with open(scaler_path, 'wb') as f:
    pickle.dump(scaler, f)

print(f"✅ Scaler guardado en: {scaler_path}")
