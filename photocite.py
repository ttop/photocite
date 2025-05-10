# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Copyright [yyyy] [Your Name or Organization]

import subprocess
import tempfile
import sys
import os
import argparse
import re

# Embedded LaTeX template
CITATION_TEMPLATE = r'''\documentclass[12pt]{article}
\usepackage{fontspec}
\setmainfont{Times New Roman}
\usepackage{ragged2e}
\usepackage[paperwidth=8.5in, margin=0.2in]{geometry}
\pagestyle{empty} % no headers or footers
\usepackage{parskip}
\usepackage{microtype}

\begin{document}
\RaggedRight
\hyphenpenalty=10000
\exhyphenpenalty=10000
\emergencystretch=3em
$body$
\end{document}
'''

def generate_citation_png_from_markdown(markdown_text: str,
                                        output_png: str = "citation_pandoc.png",
                                        pandoc_template_content: str = CITATION_TEMPLATE,
                                        dpi: int = 300,
                                        debug: bool = False):
    """
    Converts a markdown string into a cropped, high-resolution PNG image using
    pandoc → pdfcrop → magick.
    
    Args:
        markdown_text (str): The citation content in markdown.
        output_png (str): Path to the final PNG output.
        pandoc_template_content (str): Content of the LaTeX template.
        dpi (int): Resolution in dots per inch for the output image.
        debug (bool): If True, outputs the temporary filenames used during processing.
    """
    temp_pdf_path = None
    cropped_pdf_path = None
    template_file_path = None
    
    try:
        # Create temporary files
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_pdf:
            temp_pdf_path = temp_pdf.name
            
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as cropped_pdf:
            cropped_pdf_path = cropped_pdf.name
            
        with tempfile.NamedTemporaryFile(suffix=".tex", delete=False) as template_file:
            template_file_path = template_file.name
            template_file.write(pandoc_template_content.encode('utf-8'))
            template_file.flush()

        if debug:
            print(f"Temporary LaTeX template file: {template_file_path}")
            print(f"Temporary PDF file: {temp_pdf_path}")
            print(f"Temporary cropped PDF file: {cropped_pdf_path}")

        # Step 1: Generate the PDF from markdown using Pandoc
        pandoc_cmd = [
            "pandoc",
            "-f", "markdown",
            "--pdf-engine=xelatex",
            "--template", template_file_path,
            "-o", temp_pdf_path
        ]
        subprocess.run(pandoc_cmd, input=markdown_text.encode('utf-8'), check=True)

        # Step 2: Crop the PDF using pdfcrop
        pdfcrop_cmd = [
            "pdfcrop",
            "--quiet",
            "--margins", "20",
            temp_pdf_path,
            cropped_pdf_path
        ]
        subprocess.run(pdfcrop_cmd, check=True)

        # Step 3: Convert the cropped PDF to PNG using ImageMagick with the specified DPI
        magick_cmd = [
            "magick",
            "-density", str(dpi),
            cropped_pdf_path,
            "-background", "white",
            "-alpha", "remove",
            "-alpha", "off",
            output_png
        ]
        subprocess.run(magick_cmd, check=True)
        return output_png
    finally:
        # Clean up intermediate files
        if not debug:
            for path in [temp_pdf_path, cropped_pdf_path, template_file_path]:
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except Exception as e:
                        print(f"Warning: Could not remove temporary file {path}: {e}")

def get_image_dimensions(filename):
    """
    Get the width and height of an image in pixels.
    
    Args:
        filename (str): Path to the image file.
        
    Returns:
        tuple: (width, height) in pixels or None if an error occurs.
    """
    try:
        result = subprocess.run(
            ["magick", "identify", "-format", "%wx%h", filename],
            check=True,
            capture_output=True,
            text=True
        )
        dimensions = result.stdout.strip()
        width, height = map(int, dimensions.split('x'))
        return width, height
    except subprocess.CalledProcessError as e:
        print(f"Error occurred while identifying dimensions: {e}")
        return None

def get_image_dpi(filename):
    """
    Get the DPI (dots per inch) of an image.
    
    Args:
        filename (str): Path to the image file.
        
    Returns:
        int: The image DPI or 300 if it cannot be determined.
    """
    try:
        result = subprocess.run(
            ["magick", "identify", "-format", "%x", filename],
            check=True,
            capture_output=True,
            text=True
        )
        x_dpi = result.stdout.strip()
        # ImageMagick returns resolution as "NNN PixelsPerInch"
        dpi = int(float(x_dpi.split()[0]))
        return dpi if dpi > 0 else 300
    except (subprocess.CalledProcessError, ValueError, IndexError) as e:
        print(f"Warning: Could not determine DPI from image, using screen resolution default (300): {e}")
        return 300

def get_image_quality(filename):
    """
    Get the JPEG quality level of an image.
    
    Args:
        filename (str): Path to the image file.
        
    Returns:
        int: The image quality (0-100) or 92 (default) if it cannot be determined.
    """
    if not os.path.exists(filename):
        return 92  # Default quality
        
    # Check if the file is a JPEG
    try:
        result = subprocess.run(
            ["magick", "identify", "-format", "%m", filename],
            check=True,
            capture_output=True,
            text=True
        )
        image_format = result.stdout.strip()
        if image_format not in ["JPEG", "JPG"]:
            return 92  # Default for non-JPEG formats
    except subprocess.CalledProcessError:
        return 92  # Default if format cannot be determined
        
    # Get JPEG quality
    try:
        result = subprocess.run(
            ["magick", "identify", "-verbose", filename],
            check=True,
            capture_output=True,
            text=True
        )
        output = result.stdout.strip()
        
        # Look for "Quality: XX" in the output
        quality_match = re.search(r"Quality: (\d+)", output)
        if quality_match:
            quality = int(quality_match.group(1))
            return quality
        
        return 92  # Default if not found
    except subprocess.CalledProcessError:
        return 92  # Default if command fails
    
def resize_image(filename, width, dpi):
    """
    Resize an image to a specific width maintaining aspect ratio and DPI.
    
    Args:
        filename (str): Path to the image file.
        width (int): Target width in pixels.
        dpi (int): Resolution in dots per inch.
        
    Returns:
        str: Path to the resized image or None if an error occurs.
    """
    temp_filename = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
    try:
        subprocess.run(
            ["magick", filename, "-resize", str(width), "-density", str(dpi), temp_filename],
            check=True
        )
        # print(f"Resized {filename} to width {width} at {dpi} DPI: {temp_filename}")
        return temp_filename
    except subprocess.CalledProcessError as e:
        print(f"Error occurred while resizing: {e}")
        if os.path.exists(temp_filename):
            try:
                os.remove(temp_filename)
            except Exception as cleanup_error:
                print(f"Warning: Could not remove temporary file {temp_filename}: {cleanup_error}")
        return None

def center_on_canvas(citation_filename, source_width, dpi):
    """
    Center an image on a canvas of specified width, maintaining DPI.
    
    Args:
        citation_filename (str): Path to the image file.
        source_width (int): Width of the canvas in pixels.
        dpi (int): Resolution in dots per inch.
        
    Returns:
        str: Path to the centered image or None if an error occurs.
    """
    citation_canvas_filename = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name    
    try:
        subprocess.run(
            ["magick", citation_filename, "-gravity", "center", "-background", "white", 
             "-extent", f"{source_width}x", "-density", str(dpi), citation_canvas_filename],
            check=True
        )
        return citation_canvas_filename
    except subprocess.CalledProcessError as e:
        print(f"Error occurred while compositing: {e}")
        if os.path.exists(citation_canvas_filename):
            try:
                os.remove(citation_canvas_filename)
            except Exception as cleanup_error:
                print(f"Warning: Could not remove temporary file {citation_canvas_filename}: {cleanup_error}")
        return None

def append_files(input_file, citation_file, output_file, quality=92):
    """
    Append two images vertically (input on top, citation at bottom).
    
    Args:
        input_file (str): Path to the input image.
        citation_file (str): Path to the citation image.
        output_file (str): Path to save the resulting image.
        quality (int): JPEG quality (0-100) when saving the output.
        
    Returns:
        bool: True if successful, False otherwise.
    """
    try:
        # Get the file extension to determine format
        _, ext = os.path.splitext(output_file)
        ext = ext.lower()
        
        cmd = ["magick", input_file, citation_file, "-append"]
        
        # Add format-specific options
        if ext in [".jpg", ".jpeg"]:
            cmd.extend(["-quality", str(quality)])
        elif ext == ".png":
            # testing showed very diminishing returns for compression levels
            # above 4 -- much slower for little gain
            cmd.extend(["-define", "png:compression-level=4"])
        
        cmd.append(output_file)
        
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error occurred while appending: {e}")
        return False

def parse_arguments():
    parser = argparse.ArgumentParser(
        description='Add citation text to an image, or generate a citation image only.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='By default, the citation will be appended to the original image.\n'
               'The output will be saved as "<original_image> with citation<extension>".\n\n'
               'Usage examples:\n'
               '1. Standard mode: photocite.py image.jpg "Citation text"\n'
               '   The first argument is the image file, followed by citation text\n\n'
               '2. Citation-only mode: photocite.py --citation-only b.md\n'
               '   Generate just the citation from file b.md\n\n'
               '3. Citation-only with direct text: photocite.py --citation-only "Citation text"\n'
               '   Generate just the citation from the provided text\n\n'
               '4. Using piped input: cat citation.md | photocite.py image.jpg\n'
               '   Or: cat citation.md | photocite.py --citation-only\n'
    )
    
    # Add citation-only mode flag
    parser.add_argument('-co', '--citation-only', action='store_true',
                       help='Only generate the citation file without appending to the original image')
    
    parser.add_argument('-l', '--latex', 
                       help='Path to a custom LaTeX template for pandoc (optional)')
    parser.add_argument('-o', '--output', help='Custom output filename (optional)')
    parser.add_argument('-c', '--cite', help='Read citation text from this file (markdown format)')
    parser.add_argument('-d', '--debug', action='store_true',
                       help='Enable debug mode for verbose output')
    
    # Add a positional argument that can be either the image file or the citation text
    # depending on whether we're in citation-only mode
    parser.add_argument('image', nargs='?', 
                       help='In standard mode: the image file; In citation-only mode: citation file or text')
    
    # Add second positional argument which is only used in standard mode
    parser.add_argument('citation_text', nargs='?',
                       help='Citation text in markdown format (only used in standard mode)')
    
    args = parser.parse_args()
    
    # In standard mode, the image argument is required (it's the image file)
    if not args.citation_only and args.image is None:
        parser.error("In standard mode, you must provide an image file as the first argument")
    
    return args

def clean_up_files(files_to_clean):
    """Helper function to clean up a list of temporary files"""
    for file_path in files_to_clean:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                # print(f"Cleaned up temporary file: {file_path}")
            except Exception as e:
                print(f"Warning: Could not remove temporary file {file_path}: {e}")

def main():
    args = parse_arguments()

    # Enable verbose output if debug mode is on
    if args.debug:
        print("Debug mode enabled. Verbose output will be shown.")
        print(f"Arguments: {args}")
    
    citation = None
    citation_source = None
    citation_file = None
    
    # First, determine the citation text source

    if args.cite:
        # Cite flag has highest priority
        if not os.path.exists(args.cite):
            print(f"Error: Citation file '{args.cite}' does not exist.")
            sys.exit(1)
        
        with open(args.cite, "r") as file:
            citation = file.read()
            citation_source = f"file: {args.cite}"
            citation_file = args.cite
    elif args.citation_only and args.image:
        # Citation-only mode with image argument
        # Check if it's a file or direct text
        if os.path.exists(args.image):
            # It's a file
            with open(args.image, "r") as file:
                citation = file.read()
                citation_source = f"file: {args.image}"
                citation_file = args.image
        else:
            # Treat as direct text
            citation = args.image
            citation_source = "command line argument"
            citation_file = None
    elif not args.citation_only and args.citation_text:
        # Standard mode with second positional argument
        citation = args.citation_text
        citation_source = "command line argument"
        citation_file = None
    else:
        # Check for piped input
        if not sys.stdin.isatty():
            citation = sys.stdin.read()
            citation_source = "stdin (piped input)"
            citation_file = None
        else:
            print("Error: No citation text provided. Please provide it as an argument, from a file with --cite, or pipe it to stdin.")
            sys.exit(1)
    
    # Handle template option
    template_content = CITATION_TEMPLATE
    if args.latex and os.path.exists(args.latex):
        with open(args.latex, 'r') as template_file:
            template_content = template_file.read()
    
    # Initialize temporary files list for cleanup
    temp_files = []
    
    try:
        # Now process based on mode
        if args.citation_only:
            # Citation-only mode
            # Define citation output filename
            if args.output:
                citation_image = args.output
            elif citation_file:
                # Base output filename on the input file if it exists
                citation_base = os.path.splitext(citation_file)[0]
                citation_image = citation_base + " citation.png"
            else:
                # Default name if no file was used
                citation_image = "citation.png"
            
            # Use screen resolution DPI for citation-only mode (72 DPI)
            # This is just a reasonable default since there's no source image
            dpi = 72
            # print(f"Using screen resolution DPI ({dpi}) for citation-only mode")
            
            # Generate the citation PNG
            generate_citation_png_from_markdown(citation, citation_image, template_content, dpi, args.debug)
            print(f"Citation only mode: Generated citation file at '{citation_image}' using text from {citation_source}")
            
        else:
            # Standard mode
            # Check if image file exists
            if not os.path.exists(args.image):
                print(f"Error: Image file '{args.image}' does not exist.")
                sys.exit(1)
            
            # Get dimensions for the image
            original_width, original_height = get_image_dimensions(args.image)
            if original_width is None or original_height is None:
                print("Error: Could not determine image dimensions.")
                sys.exit(1)
            
            # Get the DPI of the original image
            dpi = get_image_dpi(args.image)
            # print(f"Using source image DPI: {dpi}")
            
            # Get the quality of the original image (for JPEGs)
            quality = get_image_quality(args.image)
            # print(f"Using source image quality: {quality}")
            
            # Set up filenames
            source_file_without_extension = os.path.splitext(args.image)[0]
            source_file_extension = os.path.splitext(args.image)[1]
            citation_image = source_file_without_extension + " citation.png"
            temp_files.append(citation_image)
            
            # Generate the citation PNG with the original image's DPI
            generate_citation_png_from_markdown(citation, citation_image, template_content, dpi, args.debug)

            # Resize and center the citation
            is_landscape = original_width > original_height
            if is_landscape:
                citation_image_width = int(original_width * 0.50)
            else:
                citation_image_width = int(original_width * 0.80)

            resized_citation_file = resize_image(citation_image, citation_image_width, dpi)
            if not resized_citation_file:
                print("Error: Failed to resize citation image.")
                sys.exit(1)
            temp_files.append(resized_citation_file)
            
            citation_filename = center_on_canvas(resized_citation_file, original_width, dpi)
            if not citation_filename:
                print("Error: Failed to center citation on canvas.")
                sys.exit(1)
            temp_files.append(citation_filename)
            
            # Set output filename
            if args.output:
                output_filename = args.output
            else:
                output_filename = source_file_without_extension + " with citation" + source_file_extension
                
            # Append the citation to the original image using the source image's quality
            success = append_files(args.image, citation_filename, output_filename, quality)
            if success:
                print(f"Created '{output_filename}' using citation text from {citation_source}")
            else:
                print(f"Failed to create output file '{output_filename}'")
                sys.exit(1)

    finally:
        # Clean up all temporary files, even if an error occurred
        if not args.debug:
            clean_up_files(temp_files)

if __name__ == "__main__":
    main()