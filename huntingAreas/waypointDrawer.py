import os
import json
import re
from PIL import Image, ImageDraw, ImageFont
from hunting.ConfigManager import ConfigManager

class WaypointDrawer:
    @staticmethod
    def clean_and_parse_response(gpt_response: str):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", gpt_response.strip(), flags=re.IGNORECASE)
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            raise ValueError("Failed to parse GPT response as JSON.")

        if isinstance(parsed, dict) and "hunting_spots" in parsed:
            return parsed["hunting_spots"]

        raise ValueError("Expected JSON object with 'hunting_spots' key.")
    
    @staticmethod  
    def pixel_to_latlon(px, py, image_width, image_height, top_left, bottom_right):
        lat1, lon1 = top_left
        lat2, lon2 = bottom_right

        
        x_frac = px / (image_width - 1)
        y_frac = py / (image_height - 1)

        # Linearly interpolate
        lat = lat1 + (lat2 - lat1) * y_frac
        lon = lon1 + (lon2 - lon1) * x_frac

        return lat, lon

    @staticmethod
    def draw_waypoints(image_path: str, gpt_response: str, output_dir: str = None) -> str:
        locations = WaypointDrawer.clean_and_parse_response(gpt_response)

        with Image.open(image_path) as img:
            draw = ImageDraw.Draw(img)
            width, height = img.size
            radius = 6
            grid_size = 20
            cell_width = width // grid_size
            cell_height = height // grid_size

            top_left, bottom_right = ConfigManager.get_map_coordinates(image_path)
            gps_waypoints = []

            try:
                font = ImageFont.truetype("arial.ttf", 20)
            except IOError:
                font = ImageFont.load_default()

            for i, loc in enumerate(locations):
                grid_label = loc.get("grid_location")
                if not grid_label or len(grid_label) < 2:
                    continue

                row_letter = grid_label[0].upper()
                col_number = int(grid_label[1:])

                row_index = ord(row_letter) - ord("A")
                col_index = col_number - 1

                x = col_index * cell_width + cell_width // 2
                y = row_index * cell_height + cell_height // 2

                lat, lon = WaypointDrawer.pixel_to_latlon(x, y, width, height, top_left, bottom_right)
                loc["latitude"] = lat
                loc["longitude"] = lon

                draw.ellipse([(x - radius, y - radius), (x + radius, y + radius)], fill="red", outline="black")
                draw.text((x + radius + 5, y - radius), f"{i + 1}", fill="red", font=font)

            base = os.path.basename(image_path)
            name, ext = os.path.splitext(base)

            if output_dir is None:
                output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "output")

            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f"{name}_waypoints{ext}")
            img.save(output_path)

            return output_path, {"hunting_spots": locations}
        


