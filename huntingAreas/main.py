import os
from hunting.ConfigManager import ConfigManager
from hunting.fileManager import fileManager
from hunting.imageAnalysis import ImageAnalysisManager
from hunting.waypointDrawer import WaypointDrawer

def main():
    print("🐾 Welcome to the Hunting Area Analyzer")
    species = input("Enter the species you're hunting (e.g., elk, black_bear, mule_deer): ").strip()
    state_abbr = input("Enter the 2-letter state abbreviation you're hunting in (e.g., MT, CO, WY):").strip()
    month = input("Enter the month you're hunting in (e.g., September, October): ").strip()

    
    valid_months = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    if month.capitalize() not in valid_months:
        raise ValueError(f"Invalid month '{month}'. Please enter a full month name like 'September' or 'October'.")


    try:
        base_prompt = ConfigManager.load_species_prompt(species)
        legend_info = ConfigManager.get_map_legend_description()
        full_state_name = ConfigManager.get_full_state_name(state_abbr)
        schema_prompt = ConfigManager.get_response_schema()



        print(f"\n Loaded prompt for '{species}'.\n")
        print(f"\n You are hunting in '{full_state_name}' during the month of {month.capitalize()}. \n")

        image_paths = fileManager.get_input_images()
        if not image_paths:
            print("  No image files found in data/input. Add screenshots and try again.")
            return

        analyzer = ImageAnalysisManager()

        for image_path in image_paths:
            print(f" Processing image: {os.path.basename(image_path)}")

            top_left, bottom_right = ConfigManager.get_map_coordinates(image_path)
            gps_context = (
            f"The top-left corner of the image corresponds to latitude {top_left[0]:.6f}, "
            f"longitude {top_left[1]:.6f}; and the bottom-right corner corresponds to "
            f"latitude {bottom_right[0]:.6f}, longitude {bottom_right[1]:.6f}.\n\n"
        )
            full_prompt = (
            f"You are analyzing a hunting map for the state of {full_state_name} during the month of {month.capitalize()}.\n\n"
            f"{gps_context}"
            f"{base_prompt.strip()}\n\n"
            f"{legend_info.strip()}\n\n"
            f"{schema_prompt.strip()}"
        )


            try:
                gpt_response = analyzer.analyze_image(image_path, prompt=full_prompt)
                print(f" GPT Response for {os.path.basename(image_path)}:\n{gpt_response}\n{'-'*60}\n")
                
                output_image_path = WaypointDrawer.draw_waypoints(image_path, gpt_response)
                print(f" ✅ Marked-up map saved to: {output_image_path}\n")

            except Exception as e:
                print(f" ❌ Failed to process {image_path}: {e}")

    except ValueError as ve:
        print(f"\n {ve}")
    except Exception as e:
        print(f"\n Unexpected error: {e}")

if __name__ == "__main__":
    main()
