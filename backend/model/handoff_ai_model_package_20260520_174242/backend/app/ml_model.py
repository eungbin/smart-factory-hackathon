from __future__ import annotations

try:
    import torch
    from torch import nn
except Exception:  # pragma: no cover
    torch = None
    nn = None


if nn is not None:

    class LSTMRULRegressor(nn.Module):
        def __init__(self, input_size: int, hidden_size: int = 64, layers: int = 2, dropout: float = 0.1):
            super().__init__()
            self.encoder = nn.LSTM(
                input_size=input_size,
                hidden_size=hidden_size,
                num_layers=layers,
                batch_first=True,
                dropout=dropout if layers > 1 else 0.0,
            )
            self.head = nn.Sequential(
                nn.LayerNorm(hidden_size),
                nn.Linear(hidden_size, hidden_size // 2),
                nn.ReLU(),
                nn.Linear(hidden_size // 2, 1),
            )

        def forward(self, window):
            _, (hidden, _) = self.encoder(window)
            return self.head(hidden[-1]).squeeze(-1)


    class GRURULRegressor(nn.Module):
        def __init__(self, input_size: int, hidden_size: int = 64, layers: int = 1, dropout: float = 0.1):
            super().__init__()
            self.encoder = nn.GRU(
                input_size=input_size,
                hidden_size=hidden_size,
                num_layers=layers,
                batch_first=True,
                dropout=dropout if layers > 1 else 0.0,
            )
            self.head = nn.Sequential(
                nn.LayerNorm(hidden_size),
                nn.Linear(hidden_size, hidden_size // 2),
                nn.ReLU(),
                nn.Linear(hidden_size // 2, 1),
                nn.Sigmoid(),
            )

        def forward(self, window):
            _, hidden = self.encoder(window)
            return self.head(hidden[-1]).squeeze(-1)


    class NormalizedLSTMRULRegressor(nn.Module):
        def __init__(self, input_size: int, hidden_size: int = 64, layers: int = 1, dropout: float = 0.1):
            super().__init__()
            self.encoder = nn.LSTM(
                input_size=input_size,
                hidden_size=hidden_size,
                num_layers=layers,
                batch_first=True,
                dropout=dropout if layers > 1 else 0.0,
            )
            self.head = nn.Sequential(
                nn.LayerNorm(hidden_size),
                nn.Linear(hidden_size, hidden_size // 2),
                nn.ReLU(),
                nn.Linear(hidden_size // 2, 1),
                nn.Sigmoid(),
            )

        def forward(self, window):
            _, (hidden, _) = self.encoder(window)
            return self.head(hidden[-1]).squeeze(-1)


    class CNNGRURULRegressor(nn.Module):
        def __init__(self, input_size: int, hidden_size: int = 64, layers: int = 1, dropout: float = 0.1):
            super().__init__()
            self.conv = nn.Sequential(
                nn.Conv1d(input_size, hidden_size, kernel_size=5, padding=2),
                nn.ReLU(),
                nn.BatchNorm1d(hidden_size),
                nn.Conv1d(hidden_size, hidden_size, kernel_size=3, padding=1),
                nn.ReLU(),
            )
            self.encoder = nn.GRU(
                input_size=hidden_size,
                hidden_size=hidden_size,
                num_layers=layers,
                batch_first=True,
                dropout=dropout if layers > 1 else 0.0,
            )
            self.head = nn.Sequential(
                nn.LayerNorm(hidden_size),
                nn.Linear(hidden_size, hidden_size // 2),
                nn.ReLU(),
                nn.Linear(hidden_size // 2, 1),
                nn.Sigmoid(),
            )

        def forward(self, window):
            encoded = self.conv(window.transpose(1, 2)).transpose(1, 2)
            _, hidden = self.encoder(encoded)
            return self.head(hidden[-1]).squeeze(-1)


    class _TemporalBlock(nn.Module):
        def __init__(self, channels: int, kernel_size: int, dilation: int, dropout: float):
            super().__init__()
            padding = (kernel_size - 1) * dilation
            self.net = nn.Sequential(
                nn.Conv1d(channels, channels, kernel_size, padding=padding, dilation=dilation),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Conv1d(channels, channels, kernel_size, padding=padding, dilation=dilation),
                nn.ReLU(),
                nn.Dropout(dropout),
            )
            self.padding = padding

        def forward(self, x):
            out = self.net(x)
            if self.padding:
                out = out[:, :, : x.shape[-1]]
            return out + x


    class TCNRULRegressor(nn.Module):
        def __init__(
            self,
            input_size: int,
            hidden_size: int = 64,
            layers: int = 4,
            kernel_size: int = 3,
            dropout: float = 0.1,
        ):
            super().__init__()
            blocks = [nn.Conv1d(input_size, hidden_size, kernel_size=1), nn.ReLU()]
            for layer in range(layers):
                blocks.append(
                    _TemporalBlock(
                        channels=hidden_size,
                        kernel_size=kernel_size,
                        dilation=2**layer,
                        dropout=dropout,
                    )
                )
            self.encoder = nn.Sequential(*blocks)
            self.head = nn.Sequential(
                nn.LayerNorm(hidden_size),
                nn.Linear(hidden_size, hidden_size // 2),
                nn.ReLU(),
                nn.Linear(hidden_size // 2, 1),
                nn.Sigmoid(),
            )

        def forward(self, window):
            encoded = self.encoder(window.transpose(1, 2)).transpose(1, 2)
            return self.head(encoded[:, -1, :]).squeeze(-1)


    class PatchTSTRULRegressor(nn.Module):
        def __init__(
            self,
            input_size: int,
            hidden_size: int = 64,
            layers: int = 2,
            patch_len: int = 10,
            stride: int = 5,
            heads: int = 4,
            dropout: float = 0.1,
        ):
            super().__init__()
            self.patch_len = patch_len
            self.stride = stride
            self.patch_projection = nn.Linear(input_size * patch_len, hidden_size)
            self.position = nn.Parameter(torch.zeros(1, 64, hidden_size))
            encoder_layer = nn.TransformerEncoderLayer(
                d_model=hidden_size,
                nhead=max(1, min(heads, hidden_size // 16)),
                dim_feedforward=hidden_size * 4,
                dropout=dropout,
                batch_first=True,
                activation="gelu",
                norm_first=True,
            )
            self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=layers)
            self.head = nn.Sequential(
                nn.LayerNorm(hidden_size),
                nn.Linear(hidden_size, hidden_size // 2),
                nn.GELU(),
                nn.Linear(hidden_size // 2, 1),
                nn.Sigmoid(),
            )

        def forward(self, window):
            patches = window.unfold(dimension=1, size=self.patch_len, step=self.stride)
            patches = patches.transpose(2, 3).contiguous()
            batch, patch_count, _, _ = patches.shape
            tokens = self.patch_projection(patches.view(batch, patch_count, -1))
            tokens = tokens + self.position[:, :patch_count, :]
            encoded = self.encoder(tokens)
            return self.head(encoded.mean(dim=1)).squeeze(-1)


    class ITransformerRULRegressor(nn.Module):
        def __init__(
            self,
            input_size: int,
            hidden_size: int = 64,
            layers: int = 2,
            sequence_length: int = 50,
            heads: int = 4,
            dropout: float = 0.1,
        ):
            super().__init__()
            self.input_size = input_size
            self.sequence_length = sequence_length
            self.value_projection = nn.Linear(sequence_length, hidden_size)
            self.variable_embedding = nn.Parameter(torch.zeros(1, input_size, hidden_size))
            encoder_layer = nn.TransformerEncoderLayer(
                d_model=hidden_size,
                nhead=max(1, min(heads, hidden_size // 16)),
                dim_feedforward=hidden_size * 4,
                dropout=dropout,
                batch_first=True,
                activation="gelu",
                norm_first=True,
            )
            self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=layers)
            self.head = nn.Sequential(
                nn.LayerNorm(hidden_size),
                nn.Linear(hidden_size, hidden_size // 2),
                nn.GELU(),
                nn.Linear(hidden_size // 2, 1),
                nn.Sigmoid(),
            )

        def forward(self, window):
            variables = window.transpose(1, 2)
            tokens = self.value_projection(variables) + self.variable_embedding[:, : self.input_size, :]
            encoded = self.encoder(tokens)
            return self.head(encoded.mean(dim=1)).squeeze(-1)

else:
    LSTMRULRegressor = None
    GRURULRegressor = None
    NormalizedLSTMRULRegressor = None
    CNNGRURULRegressor = None
    TCNRULRegressor = None
    PatchTSTRULRegressor = None
    ITransformerRULRegressor = None
