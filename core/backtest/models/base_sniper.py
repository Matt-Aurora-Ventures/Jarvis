import torch
import torch.nn as nn
import torch.nn.functional as F

class BaseSniperModel(nn.Module):
    """
    Standard PyTorch model interface bridging parameters and feature logic
    to execution heuristics.
    """
    def __init__(self, input_dim: int, hidden_dim: int = 64, num_layers: int = 2):
        super(BaseSniperModel, self).__init__()

        self.hidden_dim = hidden_dim
        self.num_layers = num_layers

        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=0.2 if num_layers > 1 else 0
        )

        # Readout layer for regression (predicting next step price standardized)
        self.fc = nn.Linear(hidden_dim, 1)

    def forward(self, x):
        """
        x shape: (batch_size, sequence_length, features)
        """
        # LSTM output format: batch_size, sequence_length, hidden_dim
        out, (h_n, c_n) = self.lstm(x)

        # Take the output of the last sequence step
        last_out = out[:, -1, :]

        score = self.fc(last_out)
        return score
