"""
Filename: build_corrected_output.py
Author: Aldo Tapia
Date: 2026-07-10
Version: 0.1
Description: Same than route_cfe, but with *.nc creation as well
"""

import sys
from math import gamma, sqrt
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

DEFAULT_RUN = Path("/Users/aldotapia/ngiab_preprocess_output/mrms-displacement/real_case/mrms")
COEF_FILE = (
    "/Users/aldotapia/Documents/GitHub/NCEP/Duhamel/routing_coefficients_study_area.csv"
)
OUTPUT_PATH = (
    "/Users/aldotapia/ngiab_preprocess_output/mrms-displacement/real_case/routed"
)
DT = 1.0  # routing timestep [hr]


def gamma_uh(n, k, dt=DT):
    """Normalized gamma unit hydrograph (sums to 1, so mass conserving).

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


def route_headwaters(coef, ngen_dir):
    """Route CFE Q_OUT into corrected streamflow [mm/hr] per headwater.

    Q_OUT is catchment-averaged depth [m/hr], so convolving it with the
    normalized unit hydrograph gives routed depth [m/hr]; *1000 gives mm/hr.

    Args:
        coef (pd.DataFrame): coefficients table (cat_id, N, K)
        ngen_dir (Path): folder with the CFE cat-<id>.csv outputs

    Returns:
        xr.Dataset: flow [mm/hr] with dims (feature_id, time)
    """
    ngen_dir = Path(ngen_dir)
    ids, flows, time = [], [], None
    for row in coef.itertuples():
        cat_file = ngen_dir / f"cat-{row.cat_id}.csv"
        if not cat_file.exists():
            continue
        df = pd.read_csv(cat_file)
        uh = gamma_uh(row.N, row.K)
        routed = (
            np.convolve(df["Q_OUT"].to_numpy(), uh)[: len(df)] * 1000
        )  # m/hr -> mm/hr
        ids.append(row.cat_id)
        flows.append(routed.astype(np.float32))
        if time is None:
            time = pd.to_datetime(df["Time"]).to_numpy()

    ds = xr.Dataset(
        {"flow": (("feature_id", "time"), np.vstack(flows))},
        coords={"feature_id": np.array(ids, dtype=np.int64), "time": time},
    )
    ds["flow"].attrs["units"] = "mm/hr"
    ds["flow"].attrs["source_note"] = "CFE Q_OUT routed with a gamma unit hydrograph"
    return ds


def find_troute(run):
    """Return the t-route output NetCDF for a run, or None.

    Args:
        run (Path): run directory containing troute/

    Returns:
        Path or None: first troute_output_*.nc found
    """
    files = sorted((Path(run) / "troute").glob("troute_output_*.nc"))
    return files[0] if files else None


def build(run, coef_file=COEF_FILE, output_path=OUTPUT_PATH):
    """Rebuild the corrected flow file from the run's CFE output.

    Args:
        run (Path): run directory with ngen/ (and troute/ for the filter)
        coef_file (Path): routing coefficients csv (cat_id, N, K)
        output_path (str, Path or None): where to save the NetCDF. None -> the
            default <run>/flow_corrected.nc. A directory (or any path without a
            .nc suffix) -> <output_path>/<run_name>_flow_corrected.nc. A path
            ending in .nc -> used as-is.

    Returns:
        Path: the written NetCDF path
    """
    run = Path(run)
    print(f"\n{run}")
    coef = pd.read_csv(coef_file)
    routed = route_headwaters(coef, run / "ngen")

    # filter by the original experiment: keep feature_ids present in t-route
    troute = find_troute(run)
    if troute is not None:
        with xr.open_dataset(troute) as tr:
            exp_fids = set(int(f) for f in tr["feature_id"].values)
        keep = np.array([int(f) in exp_fids for f in routed["feature_id"].values])
        dropped = int((~keep).sum())
        routed = routed.isel(feature_id=np.where(keep)[0])
        print(
            f"  filtered to {troute.name}: "
            f'{routed.sizes["feature_id"]} kept, {dropped} dropped'
        )
    else:
        print(
            "  [warn] no troute/troute_output_*.nc; writing all headwaters unfiltered"
        )

    if output_path is None:
        out_nc = run / "flow_corrected.nc"
    else:
        out_nc = Path(output_path)
        # treat a directory (existing, or any path without a .nc suffix) as a
        # folder to drop a per-run file into, so batch runs don't collide
        if out_nc.is_dir() or out_nc.suffix != ".nc":
            out_nc = out_nc / f"{run.name}_flow_corrected.nc"
    out_nc.parent.mkdir(parents=True, exist_ok=True)
    routed.to_netcdf(out_nc, engine="netcdf4")
    print(
        f'  -> {out_nc} (flow[{routed.sizes["feature_id"]}, {routed.sizes["time"]}], mm/hr)'
    )
    return out_nc


def main():
    """Rebuild the corrected flow file for every run given (default: DEFAULT_RUN)."""
    runs = [Path(a) for a in sys.argv[1:]] or [DEFAULT_RUN]
    for run in runs:
        build(run, output_path=OUTPUT_PATH)


if __name__ == "__main__":
    main()
