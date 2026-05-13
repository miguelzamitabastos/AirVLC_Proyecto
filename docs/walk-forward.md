# Validación Walk-Forward del modelo LSTM-Attention-Multi

## Por qué walk-forward y no train_test_split aleatorio

En series temporales, `train_test_split` con shuffle aleatorio (o incluso 
sin shuffle pero con una sola división) presenta dos problemas críticos:

1. **Fuga de información (data leakage)**: si el conjunto de test contiene
   observaciones temporalmente intercaladas con el de entrenamiento, el
   modelo aprende a "interpolar" en lugar de "predecir el futuro".

2. **Métricas dependientes del año**: una única división puede caer en un
   período atípico (pandemia, episodio de contaminación extremo, año
   especialmente cálido) y dar métricas no representativas.

## Diseño del experimento

[explicación de los 5 folds]

## Resultados

[tabla que generará el notebook en sección 11]

## Conclusión

[texto explicando que el modelo es estable y robusto]