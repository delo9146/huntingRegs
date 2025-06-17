import os
import base64
from PIL import Image
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class ImageAnalysisManager:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-4o" 

    def encode_image_to_base64(self, image_path):
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode("utf-8")

    def analyze_image(self, image_path, prompt):
        #putting the grid and image together
        grid_path = self.add_overlay_grid(image_path)
        image_b64 = self.encode_image_to_base64(grid_path)
        image_data_url = f"data:image/png;base64,{image_b64}"

        #few-shot example
        example_img = "data/fewShot/oldBaldyFire_grid.png"
        example_grid = self.add_overlay_grid(example_img)
        example_b64 = self.encode_image_to_base64(example_grid)
        example_data_url = f"data:image/png;base64,{example_b64}"

        #few-shot JSON
        example_json_path = "data/fewShot/few-shot.json"
        with open(example_json_path, "r") as f:
            example_json = f.read()
        
        prompt += "\n\nThe image includes a 20x20 grid overlay labeled A1 to T20. Return 3 hunting spots using those grid labels as 'grid_location'. Format your response as JSON."

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a seasoned hunting guide skilled at analyzing maps to find optimal game locations."
                    "Assume map orientation is standard: North is at the top of the image, South is the bottom of the image, East is the right of the image, and West is the left of the image. "
                    "You are also an expert in reading topographical and satellite imagery.  When presented with a map you will:\n\n Read contour lines: tightly spaced lines indicate steep slopes, widely spaced lines gentler terrain; identify ridgelines, saddles, benches and valley bottoms.\n Use hillshade or relief shading to confirm slope aspects and detect subtle terrain undulations.\n Interpret color cues on satellite layers: deep greens for dense forest, lighter greens or tans for open grasslands or bare earth, blues for water bodies, and seasonal variations in vegetation.\n Locate water sources (streams, ponds, riparian corridors) by following V‐shaped contour patterns or blue channels.\n Assess habitat transitions (forest edge, meadows, clearcuts) for game travel corridors and feeding areas.\n Read any overlaid grid or waypoint labels: gray waypoints include coordinate info to the left of the image—use those to tie your analysis back to real‐world lat/long or UTM coordinates.\n\nAlways translate what you see into actionable hunting advice—where animals are likely to bed, feed, or travel, and how to approach undetected given the terrain. Contour lines rising in elevation to north, northeast, or northwest of the image are south facing slopes and are typically lighter in color in satellite imagery as they are sun-lit. Contour lines rising in elevation to the south, southeast, and southwest are north facing slopes and are typically darker in color in satellite imagery as they are shaded."
                    "An arrow indicating North is in the botoom right of the image. Confirm slope orientation by following this structured analysis: \n\n Identify peaks, ridges, and valleys clearly visible in the image \n\n Observe shading: darker shading on slopes indicates less sunlight exposure (typically north-facing). Lighter slopes have direct sunlight exposure (typically south-facing). \n\n Confirm your analysis using contour lines and clearly marked feature (roads, rivers, ridges) \n\n Classify each identified slope explicitly as either north-facing, south-facing, east facing, west facing, or combinations of those based on above criteria. \n\n Avoid misclassifying slopes by carefully examining shading direction relative to the map's orientation."
                )

            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Here’s an example map. Return JSON in the schema I’ll ask for next."},
                    {"type": "image_url", "image_url": {"url": example_data_url}}
                ]
            },
            {
                "role": "assistant",
                "content": example_json
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url}}
                ]
            }
        ]
        response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=2000,
            )
        return response.choices[0].message.content
        
    
    def add_overlay_grid(self, image_path: str, grid_size: int = 20) -> str:
        from PIL import ImageDraw, ImageFont
        img = Image.open(image_path).convert("RGB")
        draw = ImageDraw.Draw(img)
        width, height = img.size

        
        cell_width = width // grid_size
        cell_height = height // grid_size

        
        for i in range(grid_size):
            for j in range(grid_size):
                x0 = j * cell_width
                y0 = i * cell_height
                x1 = x0 + cell_width
                y1 = y0 + cell_height
                draw.rectangle([x0, y0, x1, y1], outline="gray")

                label = f"{chr(65 + i)}{j+1}"
                try:
                    font = ImageFont.truetype("arial.ttf", 9)
                except IOError:
                    font = ImageFont.load_default()
                draw.text((x0 + 5, y0 + 5), label, fill="black", font=font)


        overlay_path = image_path.replace(".png", "_grid.png")

        arrow_length = 50
        padding = 20
        x_center = width - padding
        y_center = height - padding

        draw.line([(x_center, y_center), (x_center, y_center - arrow_length)], fill="black", width=4)

        draw.polygon([
            (x_center - 5, y_center - arrow_length + 10),
            (x_center + 5, y_center - arrow_length + 10),
            (x_center, y_center - arrow_length)
        ], fill="black")

        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except IOError:
            font = ImageFont.load_default()
        draw.text((x_center - 7, y_center - arrow_length - 25), "N", fill="black", font=font)

        img.save(overlay_path)
        return overlay_path

