"""
Filename: copy_forcings_and_run.py
Author: Aldo Tapia
Date: 2026-07-09
Version: 0.1
Description: Script to copy modified forcings to the NGIAB data folder and run the CFE model using Docker.
"""

import xarray as xr
import geopandas as gpd
import os


import subprocess
from data_processing.file_paths import FilePaths
import shutil
from datetime import datetime
from data_processing.create_realization import create_realization
from data_processing.dataset_utils import validate_dataset_format
import data_processing.forcings as forcings

name = "mrms-displacement"

path = f"/Users/aldotapia/ngiab_preprocess_output/{name}"

general_path = f"/Users/aldotapia/ngiab_preprocess_output/{name}"

GDF_ORIGIN_PATH = (
    "/Users/aldotapia/.ngiab/hydrofabric/v2.2/conus_nextgen_filtered_v2.gpkg"
)

gdf_file = f"{general_path}/config/{name}_subset.gpkg"

template_dir = f"{general_path}/template/forcings.nc"
output_file = f"{general_path}/forcings/forcings.nc"
output_folder = f"{general_path}"

# forcings_to_copy = (
#    "/Users/aldotapia/ngiab_preprocess_output/mrms-displacement/template/raw.nc"
# )
forcings_to_copy = (
    "/Users/aldotapia/ngiab_preprocess_output/mrms-displacement/template/hrrr.nc"
)

gridded_file = f"{general_path}/forcings/conus_nextgen_filtered_v2-raw-gridded-data.nc"

YEAR_INI, MONTH_INI, DAY_INI = 2018, 5, 26
YEAR_END, MONTH_END, DAY_END = 2018, 5, 30

ORIGIN_COORDS = (39.26915, -76.79622)
ANGLE = 0
DISTANCE = 100000


def run_ngen_docker():
    cmd = [
        "docker",
        "run",
        "--rm",
        "-it",
        "-v",
        f"{path}:/ngen/ngen/data",
        "awiciroh/ciroh-ngen-image:latest",
        "/ngen/ngen/data/",
        "auto",
        "11",
        "local",
    ]
    subprocess.run(cmd, check=True)


def main():
    try:
        os.remove(gridded_file)
    except OSError:
        pass

    shutil.copy(
        forcings_to_copy,
        gridded_file,
    )

    paths = FilePaths(name)

    paths.geopackage_path.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy(
        GDF_ORIGIN_PATH,
        paths.geopackage_path,
    )

    create_realization(
        name,
        start_time=datetime(YEAR_INI, MONTH_INI, DAY_INI),
        end_time=datetime(YEAR_END, MONTH_END, DAY_END),
    )

    gdf = gpd.read_file(gdf_file, layer="divides")

    ds = xr.open_dataset(gridded_file)

    gdf = gdf.to_crs(ds.crs)
    validate_dataset_format(ds)

    forcing_paths = FilePaths(output_folder)

    os.makedirs(forcing_paths.forcings_dir / "temp", exist_ok=True)

    forcings.compute_zonal_stats(gdf, ds, forcing_paths.forcings_dir)

    run_ngen_docker()


if __name__ == "__main__":
    main()
