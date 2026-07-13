"""
Filename: inject_hrrr.py
Author: Aldo Tapia
Date: 2026-07-13
Version: 0.1
Description: Script to inject HRRR data into MRMS template
"""

import xarray as xr
from xarray_regrid import regrid

MRMS_REPROJECTED_FILE = (
    "/Users/aldotapia/ngiab_preprocess_output/mrms-2022/ncep_data/conus_nextgen_filtered_v2-raw-gridded-data.nc"
)
HRRR_FILE = (
    "/Users/aldotapia/Documents/GitHub/NCEP/event2022/out/hrrr_PRATE_20220608_1800.nc"
)
FILE_OUT = "/Users/aldotapia/ngiab_preprocess_output/mrms-2022/ncep_data/HRRR_injected_data.nc"

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
