import os
from PIL import Image

def resize_and_convert_images(base_dir, input_folder, output_folder, sizes):
    input_path = os.path.join(base_dir, input_folder)
    output_path = os.path.join(base_dir, output_folder)
    medium_folder = os.path.join(output_path, 'medium')
    small_folder = os.path.join(output_path, 'small')

    # Check and create input folder if it doesn't exist
    if not os.path.exists(input_path):
        os.makedirs(input_path)
        print(f"Created input folder at {input_path}. Please add images and rerun the script.")
        return

    # Create the output folder if it does not exist
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    # Create subfolders for medium and small sizes if they do not exist
    if not os.path.exists(medium_folder):
        os.makedirs(medium_folder)
    if not os.path.exists(small_folder):
        os.makedirs(small_folder)

    for filename in os.listdir(input_path):
        if filename.endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tga')):
            img_path = os.path.join(input_path, filename)
            img = Image.open(img_path)

            for size_label, size in sizes.items():
                resized_img = img.resize(size, Image.LANCZOS).convert('RGBA')
                output_filename = os.path.splitext(filename)[0] + '.tga'

                # Determine the output path based on the size
                if size_label == 'regular':
                    output_file_path = os.path.join(output_path, output_filename)
                elif size_label == 'medium':
                    output_file_path = os.path.join(medium_folder, output_filename)
                elif size_label == 'small':
                    output_file_path = os.path.join(small_folder, output_filename)

                resized_img.save(output_file_path, format='TGA')
                print(f"Resized and saved {output_filename} to {output_file_path}")

# Define the base directory as the directory of the script
base_dir = os.path.dirname(os.path.abspath(__file__))

# Define the input and output folder names
input_folder = 'input_folder'
output_folder = 'output_folder'

# Define sizes for regular, medium, and small flags
sizes = {
    'regular': (82, 52),  # Regular flag size
    'medium': (41, 26),   # Medium flag size
    'small': (10, 7)      # Small flag size
}

resize_and_convert_images(base_dir, input_folder, output_folder, sizes)
