FROM osgeo/gdal:ubuntu-small-3.6.3

# Install additional tools (Tippecanoe, SAGA GIS)
RUN apt-get update && apt-get install -y \
    tippecanoe \
    saga \
    && rm -rf /var/lib/apt/lists/*

# Set working directory inside the container
WORKDIR /data

# Copy and make executable the processing script
COPY process_dem.sh /usr/local/bin/process_dem.sh
RUN chmod +x /usr/local/bin/process_dem.sh

# When the container starts, run the pipeline script
ENTRYPOINT ["/usr/local/bin/process_dem.sh"]