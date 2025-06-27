#!/usr/bin/env python3
"""
habitat_selector.py: Query OpenAI Responses API (gpt-4o) to select top 3 elk habitat grid tiles with rounded metrics
"""
import os
import json
from dotenv import load_dotenv
from openai import OpenAI


def main():
    # Load environment variables (expects OPENAI_API_KEY in .env)
    load_dotenv()
    client = OpenAI()

    # Load grid statistics
    stats_file = os.path.join("data", "stats.json")
    with open(stats_file, "r") as f:
        stats = json.load(f)

    # Round float metrics to 5 decimal places -- single-decimal values like 70.0 remain unchanged
    for tile in stats:
        for k, v in tile.items():
            if isinstance(v, float):
                tile[k] = round(v, 5)

    # Build the prompt
    prompt = f"""
You are an expert wildlife habitat analyst. Below is a JSON array of 100 grid tiles covering a hunting area.
Each tile has the following metrics:
- filled_mean: mean elevation (m)
- slope_mean: mean slope (°)
- aspect_mean: mean aspect (°)
- hillshade_mean: mean hillshade brightness (0–255)
- tpi_mean: Topographic Position Index
- roughness_mean: local surface roughness (m)
- tri_mean: Terrain Ruggedness Index

For our target species (elk in October), ideal habitat parameters are:
- Elevation: 2000–2500 m
- Slope: 8–20°
- Aspect: 120–180° (southeast-facing)
- Hillshade: 60–90
- TPI: > 0 (higher ground preferred)
- Roughness: 1.0–3.0
- TRI: 1.0–4.0

Select the top 3 tiles that best match these criteria. For each selected tile, provide:
1. The tile ID
2. A brief rationale referencing its key metric values

Here is the JSON data (with values rounded to 5 decimal places):
{json.dumps(stats, indent=2)}
"""

    # Call the Responses API
    response = client.responses.create(
        model="gpt-4o",
        input=[{"role": "user", "content": prompt}]
    )

    # Output the response
    print("=== Top 3 Elk Habitat Tiles ===")
    print(response.output_text)


if __name__ == "__main__":
    main()
