import argparse
import json
import numpy as np
import rasterio
from rasterio.mask import mask
import geopandas as gpd
from shapely.geometry import box


def get_raster_bounds(raster_path):
    """
    Open a raster and return its bounds and CRS.
    """
    with rasterio.open(raster_path) as src:
        return src.bounds, src.crs


def generate_fishnet(bounds, crs, nx=10, ny=10):
    """
    Create a fishnet (grid) GeoDataFrame covering the given bounds.
    bounds: (minx, miny, maxx, maxy)
    crs: Coordinate reference system of the grid
    nx, ny: number of columns and rows
    """
    minx, miny, maxx, maxy = bounds
    dx = (maxx - minx) / nx
    dy = (maxy - miny) / ny
    cells = []
    for i in range(nx):
        for j in range(ny):
            x1 = minx + i * dx
            y1 = miny + j * dy
            x2 = x1 + dx
            y2 = y1 + dy
            geom = box(x1, y1, x2, y2)
            cells.append({"tile": f"{i}-{j}", "geometry": geom})
    return gpd.GeoDataFrame(cells, crs=crs)


def compute_stats_for_raster(raster_path, grid_gdf, nodata_val=None):
    """
    For each polygon in grid_gdf, mask the raster and compute mean, median, std.
    Automatically uses raster's native nodata value if nodata_val is None.
    """
    stats_list = []
    with rasterio.open(raster_path) as src:
        native_nodata = src.nodata
        nodata = nodata_val if nodata_val is not None else native_nodata
        for _, row in grid_gdf.iterrows():
            try:
                data, _ = mask(src, [row.geometry], crop=True, nodata=nodata)
                arr = data[0]
                # Filter out nodata or NaNs
                if nodata is not None:
                    arr = arr[arr != nodata]
                arr = arr[~np.isnan(arr)]
                stats = {
                    "mean": float(np.nanmean(arr)),
                    "median": float(np.nanmedian(arr)),
                    "std": float(np.nanstd(arr))
                }
            except Exception:
                stats = {"mean": None, "median": None, "std": None}
            stats_list.append(stats)
    return stats_list


def merge_stats(grid_gdf, raster_map):
    """
    Compute and merge statistics for multiple rasters into a single records list.
    raster_map: dict of { raster_path: prefix }
    """
    # Determine nodata for each raster and compute stats
    stats_data = {}
    for path in raster_map:
        stats_data[path] = compute_stats_for_raster(path, grid_gdf)

    output = []
    for idx, row in grid_gdf.iterrows():
        rec = {"tile": row["tile"],
               "centroid": [row.geometry.centroid.y, row.geometry.centroid.x]}
        for path, prefix in raster_map.items():
            stats = stats_data[path][idx]
            for key, value in stats.items():
                rec[f"{prefix}_{key}"] = value
        output.append(rec)
    return output


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate grid and compute stats for COG rasters"
    )
    parser.add_argument(
        "--rasters", nargs="+", required=True,
        help="List of raster_path:prefix entries, e.g. data\\cog_filled.tif:filled"
    )
    parser.add_argument(
        "--grid-size", type=int, nargs=2, default=[10, 10], metavar=("NX", "NY"),
        help="Grid dimensions (columns rows)"
    )
    parser.add_argument(
        "--grid-out", default="data/grid.geojson",
        help="Output path for grid GeoJSON"
    )
    parser.add_argument(
        "--stats-out", default="data/stats.json",
        help="Output path for stats JSON"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Parse rasters entries into a map of path->prefix
    raster_map = {}
    for entry in args.rasters:
        path, prefix = entry.split(":", 1) if ":" in entry else (entry, None)
        if prefix is None:
            prefix = entry.split("/")[-1].split(".")[0]
        raster_map[path] = prefix

    # Generate fishnet grid from first raster's bounds
    first_raster = next(iter(raster_map))
    bounds, crs = get_raster_bounds(first_raster)
    nx, ny = args.grid_size
    grid = generate_fishnet(bounds, crs, nx, ny)
    grid.to_file(args.grid_out, driver="GeoJSON")
    print(f"Saved grid ({len(grid)} tiles) → {args.grid_out}")

    # Compute and merge stats
    records = merge_stats(grid, raster_map)
    with open(args.stats_out, "w") as f:
        json.dump(records, f, indent=2)
    print(f"Saved statistics for {len(records)} tiles → {args.stats_out}")


if __name__ == "__main__":
    main()