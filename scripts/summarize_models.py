import os
import pickle
from pathlib import Path

models_dir = Path('models/catboost')
results = []

for metadata_file in sorted(models_dir.glob('*_metadata.pkl')):
    with open(metadata_file, 'rb') as f:
        meta = pickle.load(f)
        results.append((meta['symbol'], meta.get('auc', 0)))

print('TRAINED MODELS SUMMARY (sorted by AUC)')
print('='*50)
print(f"{'Symbol':<8} {'AUC':<10} {'Quality':<15}")
print('-'*50)

for symbol, auc in sorted(results, key=lambda x: x[1], reverse=True):
    if auc >= 0.70:
        quality = 'Excellent'
    elif auc >= 0.60:
        quality = 'Good'
    elif auc >= 0.55:
        quality = 'Moderate'
    else:
        quality = 'Poor'
    print(f'{symbol:<8} {auc:>6.4f}    {quality:<15}')

print('='*50)
print(f'Total models trained: {len(results)}')
print(f'Excellent (AUC ≥ 0.70): {sum(1 for _, auc in results if auc >= 0.70)}')
print(f'Good (AUC ≥ 0.60): {sum(1 for _, auc in results if 0.60 <= auc < 0.70)}')
print(f'Moderate (AUC ≥ 0.55): {sum(1 for _, auc in results if 0.55 <= auc < 0.60)}')
print(f'Poor (AUC < 0.55): {sum(1 for _, auc in results if auc < 0.55)}')
