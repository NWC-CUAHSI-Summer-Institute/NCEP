"""
Filename: displace.py
Author: Aldo Tapia
Date: 2026-07-09
Version: 0.1
Description: Storm displacement utility for gridded WGS84 (lat/lon) netCDF data.
"""

import numpy as np
import xarray as xr
from scipy.ndimage import shift as ndi_shift
from pyproj import Geod

_GEOD = Geod(ellps="WGS84")


def displace_storm(
    da: xr.DataArray,
    angle_deg: float,
    distance_m: float,
    origin: tuple[float, float] | None = None,
    x_dim: str = "x",
    y_dim: str = "y",
    convention: str = "meteorological",
    order: int = 1,
    cval: float = 0.0,
) -> xr.DataArray:
    """
    Displace gridded storm data (WGS84 lat/lon) by a given direction and distance.

    Parameters
    ----------
    da : xr.DataArray
        Input data with dims that include y_dim and x_dim (e.g. time, y, x, in
        any order). Coordinates for x_dim/y_dim must be lon/lat in decimal
        degrees (WGS84). Any other dims (e.g. time) are left untouched.
    angle_deg : float
        Direction to move the storm, in degrees.
        - 'meteorological': 0 = North, 90 = East, clockwise
          (i.e. "the storm moves toward this compass bearing")
        - 'math': 0 = East, 90 = North, counter-clockwise (standard trig)
    distance_m : float
        Displacement distance in meters.
    origin : (lat, lon) tuple, optional
        The reference coordinate the angle/distance is measured from - e.g.
        the storm's actual centroid, a gauge/radar location, or any point of
        interest. The meters-to-degrees conversion (which depends on
        latitude, since a degree of longitude shrinks toward the poles) is
        computed exactly at this point using WGS84 geodesics, then the same
        degree offset is applied uniformly to the whole grid. If omitted,
        defaults to the grid's centroid (mean of x_dim/y_dim coords).
    x_dim, y_dim : str
        Names of the longitude and latitude dimensions/coordinates.
    convention : str
        'meteorological' or 'math'. See angle_deg.
    order : int
        Spline interpolation order for scipy.ndimage.shift.
        0 = nearest neighbor (fast, blocky), 1 = linear (recommended),
        3 = cubic (smoother, can overshoot/introduce small negatives on
        precip fields, so use with caution).
    cval : float
        Fill value for pixels exposed by the shift (default 0.0). No
        wraparound is applied.

    Returns
    -------
    xr.DataArray
        Displaced field, same shape/dims/coords as input.
    """
    lat = da[y_dim].values
    lon = da[x_dim].values

    if origin is None:
        origin_lat = float(np.mean(lat))
        origin_lon = float(np.mean(lon))
    else:
        origin_lat, origin_lon = origin

    # pyproj.Geod.fwd expects a compass bearing: 0 = North, clockwise.
    if convention == "meteorological":
        bearing = angle_deg % 360
    elif convention == "math":
        bearing = (90 - angle_deg) % 360
    else:
        raise ValueError("convention must be 'meteorological' or 'math'")

    # geodesic "direct" problem: where do you end up starting at `origin`,
    # heading along `bearing`, after travelling `distance_m` meters on WGS84?
    dest_lon, dest_lat, _back_az = _GEOD.fwd(
        origin_lon, origin_lat, bearing, distance_m
    )

    dlon = dest_lon - origin_lon
    dlat = dest_lat - origin_lat

    # signed pixel resolution - handles lat/lon ascending or descending
    lat_res = lat[1] - lat[0]
    lon_res = lon[1] - lon[0]

    shift_y_px = dlat / lat_res
    shift_x_px = dlon / lon_res

    # build the shift tuple in the same order as da.dims; any dim that
    # isn't x_dim/y_dim (e.g. time) gets shift 0
    shift_lookup = {y_dim: shift_y_px, x_dim: shift_x_px}
    shifts = tuple(shift_lookup.get(d, 0.0) for d in da.dims)

    displaced = ndi_shift(
        da.values,
        shift=shifts,
        order=order,
        mode="constant",
        cval=cval,
        prefilter=(order > 1),
    )

    out = da.copy(data=displaced)
    out.attrs["displacement_angle_deg"] = angle_deg
    out.attrs["displacement_distance_m"] = distance_m
    out.attrs["displacement_convention"] = convention
    return out
