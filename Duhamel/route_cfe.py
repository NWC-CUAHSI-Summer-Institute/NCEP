"""
Filename: route_cfe.py
Author: Aldo Tapia
Date: 2026-07-09
Version: 0.1
Description: Duhamel routing for headwater catchments using a gamma unit hydrograph.
"""

import sys
from math import gamma, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

DT = 1.0  # timestep [hr]
COEF = (
    "/Users/aldotapia/Documents/GitHub/NCEP/Duhamel/routing_coefficients_study_area.csv"
)
NGEN = Path("/Users/aldotapia/ngiab_preprocess_output/mrms-displacement/outputs/ngen")
OUTDIR = Path(
    "/Users/aldotapia/ngiab_preprocess_output/mrms-displacement/outputs/routed"
)


def gamma_uh(n, k, dt=DT):
    """Normalized gamma unit hydrograph (sums to 1).

    Args:
        n (float): gamma shape (number of reservoirs)
        k (float): gamma scale / storage coefficient [hr]
        dt (float): timestep [hr]

    Returns:
        np.ndarray: unit hydrograph ordinates
    """
    m = int((n * k + 5 * sqrt(n) * k) / dt) + 5  # cover the tail
    t = (np.arange(m) + 1) * dt
    u = (t / k) ** (n - 1) * np.exp(-t / k) / (k * gamma(n))
    return u / u.sum()


def route(q_out, area_m2, n, k, dt=DT):
    """Route CFE runoff into streamflow.

    Args:
        q_out (np.ndarray): CFE Q_OUT [m/hr]
        area_m2 (float): catchment area [m2]
        n (float): gamma shape
        k (float): gamma scale [hr]
        dt (float): timestep [hr]

    Returns:
        np.ndarray: routed streamflow [m3/s]
    """
    q_cms = q_out * area_m2 / 3600.0
    return np.convolve(q_cms, gamma_uh(n, k, dt))[: len(q_cms)]


def run_one(cat_id, area_m2, n, k):
    """Route one catchment and write its streamflow csv.

    Args:
        cat_id (int): catchment id
        area_m2 (float): catchment area [m2]
        n (float): gamma shape
        k (float): gamma scale [hr]

    Returns:
        Path: output csv path
    """
    df = pd.read_csv(NGEN / f"cat-{cat_id}.csv")
    df["Q_CMS"] = df["Q_OUT"] * area_m2 / 3600.0
    df["Q_ROUTED"] = route(df["Q_OUT"].to_numpy(), area_m2, n, k)
    out = OUTDIR / f"cat-{cat_id}_streamflow.csv"
    df[["Time", "Q_CMS", "Q_ROUTED"]].to_csv(out, index=False)
    return out


if __name__ == "__main__":
    OUTDIR.mkdir(parents=True, exist_ok=True)
    coef = pd.read_csv(COEF).set_index("cat_id")
    ids = [int(a) for a in sys.argv[1:]] or coef.index.tolist()
    for cat_id in ids:
        row = coef.loc[cat_id]
        out = run_one(cat_id, row.area_m2, row.N, row.K)
        print(f"cat-{cat_id}: N={row.N:.2f} K={row.K:.2f} h -> {out.name}")
    print(f"\n{len(ids)} catchments routed -> {OUTDIR}")
