from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import torch
from sklearn.model_selection import train_test_split
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.cmapss import add_train_rul, build_sliding_windows, load_split, rmse
from app.ml_model import LSTMRULRegressor


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a small C-MAPSS LSTM baseline.")
    parser.add_argument("--data-dir", default="../data/cmapss")
    parser.add_argument("--subset", default="FD001")
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--window-size", type=int, default=50)
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    frame = add_train_rul(load_split(data_dir, subset=args.subset, split="train"))
    windows, labels, _ = build_sliding_windows(frame, window_size=args.window_size)
    x_train, x_val, y_train, y_val = train_test_split(windows, labels, test_size=0.2, random_state=42)

    model = LSTMRULRegressor(input_size=x_train.shape[-1])
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()
    loader = DataLoader(
        TensorDataset(torch.tensor(x_train), torch.tensor(y_train)),
        batch_size=128,
        shuffle=True,
    )

    for epoch in range(args.epochs):
        model.train()
        for batch_x, batch_y in loader:
            optimizer.zero_grad()
            loss = loss_fn(model(batch_x), batch_y)
            loss.backward()
            optimizer.step()
        model.eval()
        with torch.no_grad():
            prediction = model(torch.tensor(x_val)).numpy()
            print(f"epoch={epoch + 1} val_rmse={rmse(np.asarray(y_val), prediction):.3f}")

    output = Path("../data/models")
    output.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), output / f"cmapss_{args.subset.lower()}_lstm.pt")


if __name__ == "__main__":
    main()
