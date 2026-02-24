import torch
from torch.utils.data import Dataset
import pandas as pd
import numpy as np

class CryptoTimeSeriesDataset(Dataset):
    """
    Standardizes Pandas DataFrame containing OHLCV and market cap data
    into a sequence prediction dataset suitable for LSTM/Transformer architectures.
    """
    def __init__(self, df: pd.DataFrame, window_size: int = 60, horizon: int = 1):
        """
        Args:
            df: Normalized pandas dataframe with 'timestamp', 'price', 'volume', etc.
            window_size: How many historical data points to look at.
            horizon: How many steps into the future we predict.
        """
        self.window_size = window_size
        self.horizon = horizon

        # We assume df is already ordered by timestamp correctly
        # Drop timestamp for network intake, just keeping features
        self.feature_cols = [col for col in df.columns if col != 'timestamp']

        # In a real model, we would apply StandardScaler / MinMax here.
        # For boilerplate, just taking raw values scaled naively.
        raw_data = df[self.feature_cols].values

        # Naive approach: avoid division by zero
        means = np.mean(raw_data, axis=0)
        stds = np.std(raw_data, axis=0)
        stds[stds == 0] = 1.0

        self.data = (raw_data - means) / stds

    def __len__(self):
        # Total sequences possible
        return len(self.data) - self.window_size - self.horizon + 1

    def __getitem__(self, idx: int):
        """Returns input sequence X and target y"""
        X = self.data[idx : idx + self.window_size]

        # y could be price change prediction.
        # Price is at index 0 of features. We predict the price at `horizon`
        y = self.data[idx + self.window_size + self.horizon - 1, 0]

        # Convert to torch tensor
        return torch.tensor(X, dtype=torch.float32), torch.tensor(y, dtype=torch.float32)

