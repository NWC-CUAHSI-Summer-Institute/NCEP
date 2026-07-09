"""
Filename: download_hrrr.py
Author: Aldo Tapia
Date: 2026-07-09
Version: 0.1
Description: Script to inject HRRR data into MRMS template
"""

import xarray as xr
from xarray_regrid import regrid

MRMS_REPROJECTED_FILE = (
    "/Users/aldotapia/ngiab_preprocess_output/mrms-displacement/template/raw.nc"
)
HRRR_FILE = (
    "/Users/aldotapia/Documents/GitHub/NCEP/HRRR/out/hrrr_PRATE_20180527_1300.nc"
)
FILE_OUT = "/Users/aldotapia/ngiab_preprocess_output/mrms-displacement/template/hrrr.nc"

# opening the files
dsraw = xr.open_dataset(MRMS_REPROJECTED_FILE)
ds = xr.open_dataset(HRRR_FILE)

# I'm dropping the forecast hour 0, it's empty
ds = ds.loc[dict(step=ds.step.values[1:])]

# since step is a forecast hour in ns units, here I'm converting it to a datetime64[ns] object by adding it to the time coordinate
ds = ds.assign_coords(step=(ds.time.values + ds.step.values).astype("datetime64[ns]"))
ds = ds.drop_vars(["time"])
ds = ds.rename({"step": "time", "lat": "y", "lon": "x"})

# reprojecting HRRR to the template
ds = ds.regrid.linear(dsraw, time_dim="time")
dsraw["APCP_surface"].loc[dict(time=ds.time.values)] = ds["prate"]

dsraw.to_netcdf(FILE_OUT, engine="netcdf4")
