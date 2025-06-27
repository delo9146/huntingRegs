#!/usr/bin/env bash
set -euo pipefail

# Usage: process_dem.sh <input_dem.tif> <output_prefix>
if [ "$#" -lt 2 ]; then
  echo "Usage: $0 input_dem.tif output_prefix"
  exit 1
fi

INPUT_DEM="$1"
PREFIX="$2"

# 1. Reproject to UTM Zone 12N (EPSG:32612)
gdalwarp -t_srs EPSG:32612 "$INPUT_DEM" "${PREFIX}_utm.tif"

# 2. Fill no-data holes
gdal_fillnodata.py "${PREFIX}_utm.tif" "${PREFIX}_filled.tif"

# 3. Compute terrain derivatives
gdaldem slope     "${PREFIX}_filled.tif" "${PREFIX}_slope.tif"     -compute_edges
gdaldem aspect    "${PREFIX}_filled.tif" "${PREFIX}_aspect.tif"
gdaldem hillshade "${PREFIX}_filled.tif" "${PREFIX}_hillshade.tif" -az 315 -alt 45
gdaldem TPI       "${PREFIX}_filled.tif"   "${PREFIX}_tpi.tif"
gdaldem roughness "${PREFIX}_filled.tif" "${PREFIX}_roughness.tif"
gdaldem TRI       "${PREFIX}_filled.tif" "${PREFIX}_tri.tif"


# 4. Convert all outputs to Cloud-Optimized GeoTIFFs (COGs)
for file in ${PREFIX}_*.tif; do
  gdal_translate \
    -co TILED=YES \
    -co COPY_SRC_OVERVIEWS=YES \
    -co COMPRESS=LZW \
    "$file" "cog_$(basename "$file")"
done

# Summary of generated COGs
echo "Processing complete. Generated the following COGs:"
echo "  cog_${PREFIX}_utm.tif"
echo "  cog_${PREFIX}_filled.tif"
echo "  cog_${PREFIX}_slope.tif"
echo "  cog_${PREFIX}_aspect.tif"
echo "  cog_${PREFIX}_hillshade.tif"
echo "  cog_${PREFIX}_tpi.tif"
echo "  cog_${PREFIX}_roughness.tif"
echo "  cog_${PREFIX}_tri.tif"