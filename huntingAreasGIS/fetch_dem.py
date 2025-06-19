# huntingAreasGIS/fetch_dem.py

import rasterio
from rasterio.windows import from_bounds
from pystac_client import Client
import planetary_computer

west, south, east, north = -112.18481, 45.5464, -112.14111, 45.5689

catalog = Client.open("https://planetarycomputer.microsoft.com/api/stac/v1")
search  = catalog.search(collections=["nasadem"],
                         bbox=[west, south, east, north],
                         limit=1)
items = list(search.items())
if not items:
    raise RuntimeError("No NASADEM items found for that bbox")
item = items[0]

print("Available asset keys:", list(item.assets.keys()))

asset     = item.assets["elevation"]
signed    = planetary_computer.sign(asset)
cog_url   = signed.href
vsicurl   = "/vsicurl/" + cog_url

out_tif = "huntingAreasGIS/data/dem_test.tif"
with rasterio.Env():
    with rasterio.open(vsicurl) as src:
        window    = from_bounds(west, south, east, north, src.transform)
        data      = src.read(1, window=window)
        transform = src.window_transform(window)

        profile = src.profile.copy()
        profile.update({
            "driver"   : "GTiff",
            "height"   : data.shape[0],
            "width"    : data.shape[1],
            "transform": transform
        })

        with rasterio.open(out_tif, "w", **profile) as dst:
            dst.write(data, 1)

print("✅ dem_test.tif written to", out_tif)
