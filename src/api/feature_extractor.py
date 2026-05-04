import os
import pandas as pd
import numpy as np
import pickle

class FeatureExtractor:
    """
    Simula la extracción en tiempo real de features para la API.
    Para esta demo, extrae las últimas 24 horas de la estación solicitada 
    desde el master dataset histórico y le aplica el mismo MinMaxScaler de Colab.
    """
    
    def __init__(self):
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        self.dataset_path = os.path.join(self.project_root, 'data', 'processed', 'master_dataset_colab.csv')
        self.scaler_path = os.path.join(self.project_root, 'models', 'scaler_day7.pkl')
        
        self._load_data()
        self._load_scaler()
        
        # Mapeo de nombres de Lex a nombres reales en el dataset
        self.lex_to_station = {
            'francia': 'Francia',
            'av. frança': 'Francia',
            'moli del sol': 'Molí del Sol',
            'molí del sol': 'Molí del Sol',
            'pista de silla': 'Pista de Silla',
            'puerto valencia': 'Puerto Valencia',
            'port': 'Puerto Valencia',
            'politecnic': 'Universidad Politécnica',
            'politècnic': 'Universidad Politécnica',
            'universidad politecnica': 'Universidad Politécnica'
        }
        
    def _load_data(self):
        print(f"Cargando dataset base para extracción: {self.dataset_path}")
        self.df = pd.read_csv(self.dataset_path)
        # Ordenamos temporalmente por si acaso
        if 'fecha' in self.df.columns:
            self.df.sort_values(by=['station_name', 'fecha'], inplace=True)
            
    def _load_scaler(self):
        print(f"Cargando Scaler: {self.scaler_path}")
        if not os.path.exists(self.scaler_path):
            raise FileNotFoundError(f"No se encontró el scaler en {self.scaler_path}")
            
        with open(self.scaler_path, 'rb') as f:
            self.scaler = pickle.load(f)
            
    def get_features(self, station_name):
        """
        Extrae las últimas 24h de la estación, normaliza y devuelve un numpy array shape (1, 24, 20)
        """
        # 1. Normalizar nombre de estación
        normalized_name = station_name.lower().strip()
        real_station = self.lex_to_station.get(normalized_name, 'Pista de Silla') # Fallback a Pista de Silla
        
        # 2. Filtrar el dataframe por esa estación
        df_station = self.df[self.df['station_name'] == real_station]
        
        if df_station.empty:
            print(f"⚠️ Estación '{real_station}' no encontrada en el dataset. Usando Pista de Silla.")
            df_station = self.df[self.df['station_name'] == 'Pista de Silla']
            
        # 3. Coger las últimas 24 horas (últimas 24 filas)
        if len(df_station) < 24:
            raise ValueError(f"No hay suficientes datos (24h) para {real_station}")
            
        df_last_24h = df_station.tail(24).copy()
        
        # 4. Seleccionar sólo las columnas para el escalador
        cols_to_scale = [c for c in df_last_24h.columns if c not in ('fecha', 'station_name')]
        
        # Asegurarnos de que el orden coincide con el scaler (el orden de cols_to_scale debería coincidir con feature_names_in_)
        if hasattr(self.scaler, 'feature_names_in_'):
            cols_to_scale = list(self.scaler.feature_names_in_)
            
        data_to_scale = df_last_24h[cols_to_scale]
        
        # 5. Aplicar MinMaxScaler
        scaled_data = self.scaler.transform(data_to_scale)
        
        # 6. Reshape a (1, 24, n_features) para LSTM
        # scaled_data tiene shape (24, 20)
        final_features = np.expand_dims(scaled_data, axis=0)
        
        return final_features.tolist(), real_station

    def denormalize_pm25(self, normalized_value):
        """
        Convierte el valor [0, 1] predicho por el LSTM al valor real en µg/m³
        usando el scaler de Colab.
        """
        # El scaler espera una fila completa (20 columnas)
        # Creamos una fila dummy llena de ceros y ponemos el valor en la columna de pm25
        dummy_row = np.zeros((1, len(self.scaler.feature_names_in_)))
        
        # Encontrar el índice de pm25
        pm25_idx = list(self.scaler.feature_names_in_).index('pm25')
        dummy_row[0, pm25_idx] = normalized_value
        
        # Invertir transformación
        unscaled_row = self.scaler.inverse_transform(dummy_row)
        return float(unscaled_row[0, pm25_idx])
