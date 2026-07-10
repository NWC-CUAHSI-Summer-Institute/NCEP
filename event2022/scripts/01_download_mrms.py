"""
Filename: download_mrms.py
Author: Aldo Tapia
Date: 2026-07-10
Version: 0.1
Description: Script to download MRMS data for multiple dates and hours using S3 and the Iowa State HTTP archive
"""

import os
import gzip
import tempfile
import urllib
import urllib.request
import os
import xarray as xr
import s3fs

aws = s3fs.S3FileSystem(anon=True)

BBOX = [
    -80.6478075000399031,
    -72.3314735000466271,
    36.0868564999999890,
    42.4366024999999922,
]

BASE_DIR = '/Users/aldotapia/ngiab_preprocess_output/mrms-2022'
OUT_DIR = f'{BASE_DIR}/ncep_data'
CACHE_DIR = os.path.expanduser("~/.mrms_cache")
NAME_OUT = "MRMS_data.nc"
VAR = "MultiSensor_Pass2"

DATES = ["202206" + str(val).zfill(2) for val in range(6, 11)]
HHS = [str(val).zfill(2) + "0000" for val in range(0, 24)]

os.makedirs(OUT_DIR, exist_ok=True)

IASTATE_DIR = {
    "PrecipRate": "PrecipRate",
    "RadarOnly_QPE_01H": "RadarOnly_QPE_01H",
    "MultiSensor_Pass1": "MultiSensor_QPE_01H_Pass1",
    "MultiSensor_Pass2": "MultiSensor_QPE_01H_Pass2",
    "GaugeCorr_QPE_01H": "GaugeCorr_QPE_01H",
}


# Functions from Humberto Vergara and Mohamed Abdelkader
# ----
def _decode_grib2_gz(raw_gz, varname):
    """Turn raw compressed GRIB2 bytes into an xarray Dataset.
    Steps: (1) decompress the .gz bytes, (2) write them to a temp file,
    (3) let cfgrib read that file, (4) give the data field a friendly name."""
    with tempfile.NamedTemporaryFile(suffix=".grib2") as f:
        f.write(gzip.decompress(raw_gz))  # step 1 and 2
        f.flush()
        ds = xr.load_dataset(f.name, engine="cfgrib", decode_timedelta=False)  # step 3
    return ds.rename({"unknown": varname})  # step 4 (MRMS calls the field "unknown")


def fetch_iastate(product, date, hhmmss, varname="qpe"):
    """Download the SAME kind of file, but from the Iowa State HTTP archive.
    Here we use a normal web download (urllib) instead of S3."""
    y, m, d = date[:4], date[4:6], date[6:8]
    pdir = IASTATE_DIR[product]
    url = (
        f"https://mtarchive.geol.iastate.edu/{y}/{m}/{d}/mrms/ncep/"
        f"{pdir}/{pdir}_00.00_{date}-{hhmmss}.grib2.gz"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "si2026-mrms/1.0"})
    raw = urllib.request.urlopen(req, timeout=120).read()
    return _decode_grib2_gz(raw, varname)


def subset_to_bbox(ds, varname, bbox):
    """Cut the big national grid down to a small map area (our 'box').
    bbox = [West, East, South, North] in normal -180..180 longitudes.
    We also hide missing values (MRMS marks them as negative numbers)."""
    W, E, S, N = bbox
    # MRMS latitudes run high to low, so we slice North then South.
    # MRMS longitudes run 0..360, so we shift our box into that range with % 360.
    ds = ds.sel(latitude=slice(N, S), longitude=slice(W % 360, E % 360))
    # Convert longitudes back to -180..180 so maps label them as, e.g., -99 not 261.
    ds = ds.assign_coords(longitude=(((ds.longitude + 180) % 360) - 180))
    return ds.where(ds[varname] >= 0)  # keep only valid (non-negative) values


# ----

os.makedirs(CACHE_DIR, exist_ok=True)

fs = s3fs.S3FileSystem(anon=True)

data_list = []

for date in DATES:
    print(f"Processing date: {date}")
    for hh in HHS:
        try:
            data = fetch_iastate(VAR, date, hh)
            data = subset_to_bbox(data, "qpe", BBOX)
            data_list.append(data)
        except Exception as e:
            print(f"Error fetching data for {variable} on {date} at hour {hh}: {e}")
            raise Exception(f"No files found for {variable} on {date} at hour {hh}.")

ds = xr.concat(data_list, dim="time")
ds.to_netcdf(f"{OUT_DIR}/{NAME_OUT}")
