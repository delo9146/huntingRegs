# Base: OSGeo GDAL image from GitHub Container Registry
FROM ghcr.io/osgeo/gdal:ubuntu-small-3.6.3

# 1. Install SAGA GIS
RUN apt-get update && apt-get install -y \
    saga \
    && rm -rf /var/lib/apt/lists/*

# 2. Install Tippecanoe from source (not in default repos)
RUN apt-get update && apt-get install -y \
    build-essential git pkg-config libsqlite3-dev zlib1g-dev \
    && git clone https://github.com/mapbox/tippecanoe.git \
    && cd tippecanoe \
    && make -j \
    && make install \
    && cd .. && rm -rf tippecanoe \
    && rm -rf /var/lib/apt/lists/*

# 3. Set the working directory inside the container
WORKDIR /data

# 4. Copy the terrain-processing script into the container
COPY process_dem.sh /usr/local/bin/

# 5. Make the script executable
RUN chmod +x /usr/local/bin/process_dem.sh

# 6. When the container starts, run the processing script
ENTRYPOINT ["/usr/local/bin/process_dem.sh"]