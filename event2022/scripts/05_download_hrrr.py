"""
Filename: download_hrrr.py
Author: Aldo Tapia
Date: 2026-07-10
Version: 0.1
Description: Script to download HRRR data for multiple dates and hours using FastHerbie
"""

import re
from herbie import FastHerbie
import pandas as pd
import xarray as xr
import numpy as np
from pyresample import geometry, kd_tree

# General parameters
DATE_FORECAST = "2022-06-08"
HOUR_FORECAST = "18:00"
VAR = "PRATE"
OUT_DIR = "out"
FXX = list(range(0, 19))  # forecast hours to download
# bbox for clipping to a region of interest (lon_min, lon_max, lat_min, lat_max) (raw dataset is for the entire conus)
BBOX = [
    -80.6478075000399031,
    -72.3314735000466271,
    36.0868564999999890,
    42.4366024999999922,
]

# Download the HRRR data using FastHerbie (multiple dates+hours, and multiple forecast hours can be specified - only one date + hour here tho)
H = FastHerbie(
    [pd.to_datetime(DATE_FORECAST + " " + HOUR_FORECAST)],
    model="hrrr",
    fxx=FXX,
    save_dir=OUT_DIR,
)
ds = H.xarray(VAR)

# note: longitudes and latotudes are 2D arrays, not 1D
# here a way to regrid the data to a regular lat/lon grid using pyresample
lat2d = ds.latitude.values
lon2d = ds.longitude.values
lon2d = np.where(lon2d > 180, lon2d - 360, lon2d)

lon_min, lon_max, lat_min, lat_max = BBOX
buffer = 0.2  # degrees, extra margin so edge cells aren't clipped
mask = (
    (lat2d >= lat_min - buffer)
    & (lat2d <= lat_max + buffer)
    & (lon2d >= lon_min - buffer)
    & (lon2d <= lon_max + buffer)
)
rows = np.where(mask.any(axis=1))[0]
cols = np.where(mask.any(axis=0))[0]
y_slice = slice(rows.min(), rows.max() + 1)
x_slice = slice(cols.min(), cols.max() + 1)

ds = ds.isel(y=y_slice, x=x_slice)
lat2d = ds.latitude.values
lon2d = np.where(
    ds.longitude.values > 180, ds.longitude.values - 360, ds.longitude.values
)

RES = 0.03  # degrees, ~ matches native ~3 km HRRR spacing

lon_min, lon_max, lat_min, lat_max = BBOX
buffer = 0.2  # degrees, extra margin so edge cells aren't clipped
mask = (
    (lat2d >= lat_min - buffer)
    & (lat2d <= lat_max + buffer)
    & (lon2d >= lon_min - buffer)
    & (lon2d <= lon_max + buffer)
)
rows = np.where(mask.any(axis=1))[0]
cols = np.where(mask.any(axis=0))[0]
y_slice = slice(rows.min(), rows.max() + 1)
x_slice = slice(cols.min(), cols.max() + 1)

ds = ds.isel(y=y_slice, x=x_slice)
lat2d = ds.latitude.values
lon2d = np.where(
    ds.longitude.values > 180, ds.longitude.values - 360, ds.longitude.values
)

target_lat = np.arange(lat_min, lat_max, RES)
target_lon = np.arange(lon_min, lon_max, RES)
target_lon2d, target_lat2d = np.meshgrid(target_lon, target_lat)

orig_def = geometry.SwathDefinition(lons=lon2d, lats=lat2d)
target_def = geometry.SwathDefinition(lons=target_lon2d, lats=target_lat2d)

regridded_vars = {}
extra_dims = None
for name, da in ds.data_vars.items():
    print(f"Regridding {name}...")
    spatial_dims = ("y", "x")
    lead_dims = [d for d in da.dims if d not in spatial_dims]
    extra_dims = lead_dims  # same for all vars here

    data = da.values
    if lead_dims:
        lead_shape = data.shape[: len(lead_dims)]
        flat = data.reshape(-1, *data.shape[len(lead_dims) :])
        out = np.empty(
            (flat.shape[0], target_lat.size, target_lon.size), dtype=np.float32
        )
        for i in range(flat.shape[0]):
            out[i] = kd_tree.resample_nearest(
                orig_def,
                flat[i],
                target_def,
                radius_of_influence=5000,
                fill_value=np.nan,
            )
        out = out.reshape(*lead_shape, target_lat.size, target_lon.size)
        regridded_vars[name] = ((*lead_dims, "lat", "lon"), out)
    else:
        out = kd_tree.resample_nearest(
            orig_def,
            data,
            target_def,
            radius_of_influence=5000,
            fill_value=np.nan,
        )
        regridded_vars[name] = (("lat", "lon"), out)

coords = {"lat": target_lat, "lon": target_lon}
for d in extra_dims or []:
    coords[d] = ds[d].values
if "time" in ds.coords:
    coords["time"] = ds.time.values

out_ds = xr.Dataset(regridded_vars, coords=coords, attrs=ds.attrs)

# since prate is in kg/m^2/s, multiply by 3600 to get mm/hr
out_ds[name] = out_ds[name] * 3600
out_ds[name].attrs["units"] = "mm/hr"
out_ds[name].attrs["long_name"] = "Precipitation Rate in mm/hr, NOT IN kg/m^2/s!"
out_ds.attrs["description"] = (
    "Regridded HRRR data to a regular lat/lon grid using pyresample. Original data downloaded using FastHerbie."
)
out_ds.to_netcdf(
    f"{OUT_DIR}/hrrr_{VAR}_{re.sub(r'[^0-9]', '', DATE_FORECAST)}_{HOUR_FORECAST.replace(':', '')}.nc",
    engine="netcdf4",
)
