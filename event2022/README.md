# Steps to evaluate the flash flood that happened in Ellicott City, MD on June 8, 2022

## Antecedents

**Event**: Flash Flood.  
**Flood cause**: Heavy rain.  
**State**: Maryland.  
**County**: Howard.  
**Data source (for identifying the event)**: Local Storm Report.  
**Report source**: Emergency Manager.  
**Begin Date**: 2022-06-08 20:03 EST-5.  
**Begin Location**: 0.53SSW ELLICOTT CITY.  
**End Date**: 2022-06-08 20:30 EST-5.  
**End Location**: 0.46.  

## Prepare the environment

Everything here has been run in the UV environment created for this project. Use the `pyproject.toml` file to create the environment and install the dependencies. The environment is called `ncep`, called however you want (or don't a label at all). 

## Steps

1. Use NGIAB to create the project and download the forcing data for the event
2. Download MRMS data and replace the forcing data in the project with the MRMS data
3. Run the model and get the QPE results
4. Download HRRR data and use the 18 hours forecast, injecting that data in the modified raw forcing data
5. Run the model again and get the QPF results (from the initial HRRR forecast)
6. Eval with NCEP

***Note**: instructions are provided with my local paths, you will need to change them to your own paths (not enough times to generalize and create the appropriate scripts for this)*

## Create the NGIAB project

This is not available in other files in the repo, since it's an basic command. Having `ngiab_data_preprocess` in an UV environment:

```
uv run -m ngiab_data_cli.forcing_cli \
  -i /Users/aldotapia/.ngiab/hydrofabric/v2.2/conus_nextgen_filtered_v2.gpkg \
  -o /Users/aldotapia/ngiab_preprocess_output/mrms-2022/forcings/forcings.nc \
  --source aorc \
  --start 2022-06-06 --end 2022-06-10
```

## Download MRMS data

From here to the end of the times, modify the paths of the files stores in `./scripts` folder.

Then, easily run:

```
cd event2022
uv run 01_download_mrms.py
```

## Replace the precipitation variable from the original forcing data with the MRMS data

```
uv run 02_mrms_reprojection.py
```

**Important**: Here we are not replacing the original forcing data, in the case you want to create a backup or review the file before the replacement.

## Run the model to create the QPE reference

For running the model, Docker should be installed and running. Then, the script for running the model is in `./scripts/03_zonal_stats_and_run.py`. You can run it with:

```
uv run 03_zonal_stats_and_run.py
```

## Use duhamel routing to get streamflow

**One note**: streamflow here is computed in mm/hr, not in m3/s. The only reason is to easily compare different catchments. Also, the results of the `ngen` and `troute` are stores in `./real_case` folder (created in the same directory where the NGIAB are), and in a subfolder based on the name of the run.

```
uv run scripts/04_build_corrected_output.py 
```

## Download HRRR data and inject it into the MRMS template

For downloading the HRRR data:

```
uv run scripts/05_download_hrrr.py
```

It will download the HRRR data for the forecast issued at 2022-06-08 18:00 UTC, it containts 18 hours of forecast. Then, for injecting this data into the MRMS template, run:

```
uv run scripts/06_inject_hrrr.py
```

**Note**: The HRRR data is downloaded in the `./out` folder, and the injected data is stored in the `./ncep_data` folder. The data is saved as `HRRR_injected_data.nc`, but for making compatible to the NGIAB project, change the name to `conus_nextgen_filtered_v2-raw-gridded-data.nc` and replace the original forcing data in the NGIAB project.

Then, for obtaining the products again, run the script `./scripts/07_zonal_stats_and_run.py` (it's the same than the previous one), I added just to avoid confusion between the steps, to follow a simple and clear workflow. The results will be stored in the `./real_case` folder, in a subfolder based on the name of the run.

## Use duhamel routing to get streamflow from the modified forcing data (with HRRR injected)

**One note**: streamflow here is computed in mm/hr, not in m3/s. The only reason is to easily compare different catchments. Also, the results of the `ngen` and `troute` are stores in `./real_case` folder (created in the same directory where the NGIAB are), and in a subfolder based on the name of the run.

```
uv run scripts/08_build_corrected_output.py 
```
