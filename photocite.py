# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import subprocess
import tempfile
import sys
import os
import argparse
import re


CITATION_TEMPLATE = r"""\PassOptionsToPackage{unicode}{hyperref}
\PassOptionsToPackage{hyphens}{url}
\documentclass[12pt]{article}
\usepackage{fontspec}
\setmainfont{Times New Roman}
\usepackage{ragged2e}
\usepackage[paperwidth=8.5in, margin=0.2in]{geometry}
\pagestyle{empty}
\usepackage{parskip}
\usepackage{microtype}
\usepackage{hyperref}
\usepackage{xurl}
\urlstyle{same}

% URL-breaking configuration (from your working template)
\Urlmuskip=0mu plus 0.5mu
\makeatletter
\def\UrlBreakPenalty{250}
\def\UrlBigBreakPenalty{60}

% Make "_" an ordinary URL char so breaks are legal around it…
\def\UrlOrds{\do\_\do\.\do\~} % keep a small, explicit set of ords

% …but ONLY allow breaks at these separators:
\def\UrlBreaks{\do\/\do\?\do\&\do\=\do\#\do\:\do\.\do\-\do\_}

% Prefer the “big” ones among them
\def\UrlBigBreaks{\do\/\do\?\do\&\do\=\do\#}
\makeatother

\hypersetup{breaklinks=true}

\begin{document}
\RaggedRight
\sloppy
\large
\hyphenpenalty=10000
\exhyphenpenalty=10000
\emergencystretch=3em
$body$
\end{document}
"""

CITATION_TEMPLATE_NARROW = r"""\PassOptionsToPackage{unicode}{hyperref}
\PassOptionsToPackage{hyphens}{url}
\documentclass[12pt]{article}
\usepackage{fontspec}
\setmainfont{Times New Roman}
\usepackage{ragged2e}
\usepackage[paperwidth=6.2in, margin=0.45in]{geometry}
\pagestyle{empty}
\usepackage{parskip}
\usepackage{microtype}
\usepackage{hyperref}
\usepackage{xurl}
\urlstyle{same}

% URL-breaking configuration (from your working template)
\Urlmuskip=0mu plus 0.5mu
\makeatletter
\def\UrlBreakPenalty{250}
\def\UrlBigBreakPenalty{60}
\def\UrlOrds{\do\_\do\.\do\~}
\def\UrlBreaks{\do\/\do\?\do\&\do\=\do\#\do\:\do\.\do\-\do\_}
\def\UrlBigBreaks{\do\/\do\?\do\&\do\=\do\#}
\makeatother

\hypersetup{breaklinks=true}

\begin{document}
\RaggedRight
\sloppy
\large
\hyphenpenalty=10000
\exhyphenpenalty=10000
\emergencystretch=3em
$body$
\end{document}
"""


URL_REGEX = re.compile(r'(https?://[^\s)]+)')


def wrap_urls_for_latex(markdown_text: str) -> str:
    """
    Wrap bare http/https URLs in \\url{...} so LaTeX's url/xurl
    machinery (and our \\UrlBreaks settings) actually apply.
    """

    def _repl(match: re.Match) -> str:
        url = match.group(1)
        if url.startswith(r'\url{'):
            return url
        return r'\url{' + url + '}'

    return URL_REGEX.sub(_repl, markdown_text)


def generate_citation_png_from_markdown(markdown_text: str,
                                        output_png: str = "citation_pandoc.png",
                                        pandoc_template_content: str = CITATION_TEMPLATE,
                                        dpi: int = 300,
                                        debug: bool = False):
    """
    Converts a markdown string into a cropped, high-resolution PNG image using
    pandoc → pdfcrop → magick.
    """
    temp_pdf_path = None
    cropped_pdf_path = None
    template_file_path = None

    try:
        # Preprocess markdown to ensure bare URLs become \url{...}
        markdown_text = wrap_urls_for_latex(markdown_text)

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

        pandoc_cmd = [
            "pandoc",
            "--pdf-engine=xelatex",
            "-V", "classoption=oneside",
            "-V", "geometry:margin=1in",
            "--template", template_file_path,
            "-o", temp_pdf_path
        ]

        if debug:
            print("Running pandoc:", " ".join(pandoc_cmd))

        pandoc_process = subprocess.Popen(
            pandoc_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        pandoc_stdout, pandoc_stderr = pandoc_process.communicate(
            input=markdown_text.encode('utf-8')
        )

        if debug:
            print("Pandoc stdout:")
            print(pandoc_stdout.decode('utf-8'))
            print("Pandoc stderr:")
            print(pandoc_stderr.decode('utf-8'))

        if pandoc_process.returncode != 0:
            print("Error: Pandoc failed to generate PDF.")
            print("Pandoc stderr output:")
            print(pandoc_stderr.decode('utf-8'))
            raise subprocess.CalledProcessError(pandoc_process.returncode, pandoc_cmd)

        # Crop the PDF with a small margin so glyphs are never right at the edge
        pdfcrop_cmd = [
            "pdfcrop",
            "--margin", "10",
            temp_pdf_path,
            cropped_pdf_path,
        ]

        if debug:
            print("Running pdfcrop:", " ".join(pdfcrop_cmd))

        subprocess.run(pdfcrop_cmd, check=True)

        # Convert the cropped PDF to PNG using ImageMagick with specified DPI
        magick_cmd = [
            "magick",
            "-density", str(dpi),
            cropped_pdf_path,
            "-background", "white",
            "-alpha", "remove",
            "-alpha", "off",
            output_png
        ]

        if debug:
            print("Running magick:", " ".join(magick_cmd))

        subprocess.run(magick_cmd, check=True)
        return output_png
    finally:
        if not debug:
            for path in [temp_pdf_path, cropped_pdf_path, template_file_path]:
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except Exception as e:
                        print(f"Warning: Could not remove temporary file {path}: {e}")


def get_image_dpi(filename):
    """
    Get the DPI of an image using ImageMagick.
    """
    if not os.path.exists(filename):
        return 300  # Default DPI

    try:
        result = subprocess.run(
            ["magick", "identify", "-format", "%x %y", filename],
            check=True,
            capture_output=True,
            text=True,
        )
        output = result.stdout.strip()
        if not output:
            return 300

        x_str, y_str = output.split()
        x_dpi = float(x_str.split("dpi")[0])
        y_dpi = float(y_str.split("dpi")[0])

        if x_dpi <= 0 or y_dpi <= 0:
            return 300

        return int(round((x_dpi + y_dpi) / 2))
    except (subprocess.CalledProcessError, ValueError, IndexError):
        return 300


def get_image_quality(filename):
    """
    Get the quality setting of a JPEG image.
    """
    if not os.path.exists(filename):
        return 92  # Default quality

    try:
        result = subprocess.run(
            ["magick", "identify", "-format", "%m", filename],
            check=True,
            capture_output=True,
            text=True,
        )
        format_str = result.stdout.strip().upper()
        if format_str not in ["JPEG", "JPG"]:
            return 92

        result = subprocess.run(
            ["magick", "identify", "-format", "%Q", filename],
            check=True,
            capture_output=True,
            text=True,
        )
        quality_str = result.stdout.strip()
        quality = int(quality_str)
        if 0 < quality <= 100:
            return quality
        return 92
    except (subprocess.CalledProcessError, ValueError):
        return 92


def get_image_dimensions(filename):
    """
    Get the width and height of an image using ImageMagick.
    """
    if not os.path.exists(filename):
        return None, None

    try:
        result = subprocess.run(
            ["magick", "identify", "-format", "%w %h", filename],
            check=True,
            capture_output=True,
            text=True,
        )
        output = result.stdout.strip()
        if not output:
            return None, None

        width_str, height_str = output.split()
        width = int(width_str)
        height = int(height_str)
        return width, height
    except (subprocess.CalledProcessError, ValueError, IndexError):
        return None, None


def resize_image(filename, width, dpi):
    """
    Resize an image to a specific width maintaining aspect ratio and DPI.
    """
    temp_filename = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
    try:
        subprocess.run(
            ["magick", filename, "-resize", str(width),
             "-density", str(dpi), temp_filename],
            check=True
        )
        return temp_filename
    except subprocess.CalledProcessError as e:
        print(f"Error occurred while resizing: {e}")
        if os.path.exists(temp_filename):
            try:
                os.remove(temp_filename)
            except Exception as cleanup_error:
                print(
                    f"Warning: Could not remove temporary file "
                    f"{temp_filename}: {cleanup_error}"
                )
        return None


def center_on_canvas(citation_filename, source_width, dpi,
                     top_margin=0, side_padding=0):
    """
    Center an image on a canvas of specified width, maintaining DPI.
    """
    citation_canvas_filename = tempfile.NamedTemporaryFile(
        suffix=".png", delete=False
    ).name
    try:
        w, h = get_image_dimensions(citation_filename)
        if w is None or h is None:
            return None

        new_height = h + top_margin if top_margin > 0 else h

        cmd = [
            "magick",
            citation_filename,
            "-background", "white",
            "-gravity", "center",
        ]

        if top_margin > 0:
            cmd.extend(["-extent", f"{source_width}x{new_height}"])
        else:
            cmd.extend(["-extent", f"{source_width}x"])

        cmd.extend(["-density", str(dpi), citation_canvas_filename])

        subprocess.run(cmd, check=True)
        return citation_canvas_filename
    except subprocess.CalledProcessError as e:
        print(f"Error occurred while compositing: {e}")
        if os.path.exists(citation_canvas_filename):
            try:
                os.remove(citation_canvas_filename)
            except Exception as cleanup_error:
                print(
                    "Warning: Could not remove temporary file "
                    f"{citation_canvas_filename}: {cleanup_error}"
                )
        return None


def append_files(input_file, citation_file, output_file, quality=92):
    """
    Append two images vertically (input on top, citation at bottom).
    """
    try:
        _, ext = os.path.splitext(output_file)
        ext = ext.lower()

        cmd = ["magick", input_file, citation_file, "-append"]

        if ext in [".jpg", ".jpeg"]:
            cmd.extend(["-quality", str(quality)])
        elif ext == ".png":
            cmd.extend(["-define", "png:compression-level=4"])

        cmd.append(output_file)

        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error occurred while appending: {e}")
        return False


def append_files_side_by_side(input_file, citation_file, output_file,
                              quality=92):
    """
    Place two images side by side (input on left, citation on right).
    """
    try:
        _, ext = os.path.splitext(output_file)
        ext = ext.lower()

        cmd = ["magick", input_file, citation_file, "+append"]

        if ext in [".jpg", ".jpeg"]:
            cmd.extend(["-quality", str(quality)])
        elif ext == ".png":
            cmd.extend(["-define", "png:compression-level=4"])

        cmd.append(output_file)

        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error occurred while side-by-side appending: {e}")
        return False


def parse_arguments():
    parser = argparse.ArgumentParser(
        description='Add citation text to an image, '
                    'or generate a citation image only.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='By default, the citation will be appended to the '
               'original image.\n'
               'The output will be saved as '
               '"<original_image> with citation<extension>".\n\n'
               'Usage examples:\n'
               '1. Standard mode: photocite.py image.jpg "Citation text"\n'
               '   The first argument is the image file, followed by '
               'citation text\n\n'
               '2. Citation-only mode: photocite.py --citation-only b.md\n'
               '   Generate just the citation from file b.md\n\n'
               '3. Citation-only with direct text: '
               'photocite.py --citation-only "Citation text"\n'
               '   Generate just the citation from the provided text\n\n'
               '4. Using piped input: '
               'cat citation.md | photocite.py image.jpg\n'
               '   Or: cat citation.md | photocite.py --citation-only\n'
    )

    parser.add_argument(
        '-c', '--cite',
        help='Citation text file in markdown format'
    )
    parser.add_argument(
        '-o', '--output',
        help='Output filename for the resulting image'
    )
    parser.add_argument(
        '--citation-only', action='store_true',
        help='Generate only the citation as an image'
    )
    parser.add_argument(
        '--debug', action='store_true',
        help='Keep temporary files for debugging'
    )
    parser.add_argument(
        '--latex', metavar='TEXFILE',
        help='Use a custom LaTeX template file instead of the embedded ones'
    )
    parser.add_argument(
        'image', nargs='?',
        help='Image file to which the citation will be appended'
    )
    parser.add_argument(
        'citation_text', nargs='?',
        help='Citation text provided directly (if not using -c or stdin)'
    )
    parser.add_argument(
        '-i', '--image',
        help='Alternate way to specify citation text or citation file in '
             'citation-only mode'
    )

    args = parser.parse_args()

    if args.citation_only and not (args.cite or args.citation_text or
                                   args.image or not sys.stdin.isatty()):
        parser.error(
            "In citation-only mode, provide citation via -c, citation_text, "
            "--image, or stdin."
        )
    if not args.citation_only and not args.image:
        parser.error(
            "In standard mode, you must provide the image file "
            "as the first argument."
        )

    return args


def clean_up_files(file_list):
    """
    Clean up temporary files.
    """
    for file_path in file_list:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                print(
                    f"Warning: Could not remove temporary file "
                    f"{file_path}: {e}"
                )


def width_factor_from_aspect_ratio(ar: float) -> float:
    """
    Map aspect ratio to a width factor for the citation.
    """
    lo_ar, hi_ar = 1.0, 2.0
    lo_f, hi_f = 0.80, 0.95
    if ar <= lo_ar:
        return lo_f
    if ar >= hi_ar:
        return hi_f
    return lo_f + (hi_f - lo_f) * ((ar - lo_ar) / (hi_ar - lo_ar))


def main():
    args = parse_arguments()

    citation = None
    citation_source = None
    citation_file = None

    if args.citation_only:
        if args.cite:
            with open(args.cite, "r") as file:
                citation = file.read()
                citation_source = f"file: {args.cite}"
                citation_file = args.cite
        elif args.citation_text:
            citation = args.citation_text
            citation_source = "command line argument (second positional)"
            citation_file = None
        elif args.image:
            if os.path.exists(args.image):
                with open(args.image, "r") as file:
                    citation = file.read()
                    citation_source = f"file: {args.image}"
                    citation_file = args.image
            else:
                citation = args.image
                citation_source = "command line argument"
                citation_file = None
        elif not sys.stdin.isatty():
            citation = sys.stdin.read()
            citation_source = "stdin (piped input)"
            citation_file = None
        else:
            print(
                "Error: No citation text provided. Please supply it as an "
                "argument, from a file with --cite, or pipe it to stdin."
            )
            sys.exit(1)

        if args.output:
            citation_image = args.output
        else:
            if citation_file:
                base_name = os.path.splitext(os.path.basename(citation_file))[0]
            else:
                base_name = "citation"
            citation_image = base_name + ".png"

        base_template_content = CITATION_TEMPLATE
        if args.latex:
            if not os.path.exists(args.latex):
                print(f"Error: LaTeX template file '{args.latex}' not found.")
                sys.exit(1)
            with open(args.latex, "r") as f:
                base_template_content = f.read()

        template_content = base_template_content

        # Fixed very high DPI for crisp citation image
        citation_dpi = 1500
        generate_citation_png_from_markdown(
            citation, citation_image, template_content, citation_dpi, args.debug
        )
        print(
            "Citation only mode: Generated citation file at "
            f"'{citation_image}' using text from {citation_source}"
        )

    else:
        if not os.path.exists(args.image):
            print(f"Error: Image file '{args.image}' does not exist.")
            sys.exit(1)

        original_width, original_height = get_image_dimensions(args.image)
        if original_width is None or original_height is None:
            print("Error: Could not determine image dimensions.")
            sys.exit(1)
        height_to_width = original_height / max(1, original_width)
        is_very_tall = height_to_width >= 2.0

        base_template_content = CITATION_TEMPLATE
        if args.latex:
            if not os.path.exists(args.latex):
                print(f"Error: LaTeX template file '{args.latex}' not found.")
                sys.exit(1)
            with open(args.latex, "r") as f:
                base_template_content = f.read()

        template_content = base_template_content
        if is_very_tall and not args.latex:
            template_content = CITATION_TEMPLATE_NARROW

        # Source image DPI (used for final composite)
        dpi = get_image_dpi(args.image)
        quality = get_image_quality(args.image)

        # Fixed high DPI for citation rendering
        citation_dpi = 1500

        source_file_without_extension = os.path.splitext(args.image)[0]
        source_file_extension = os.path.splitext(args.image)[1]
        citation_image = source_file_without_extension + " citation.png"
        temp_files = [citation_image]

        if args.cite:
            with open(args.cite, "r") as file:
                citation = file.read()
                citation_source = f"file: {args.cite}"
        elif args.citation_text:
            citation = args.citation_text
            citation_source = "command line argument (second positional)"
        elif args.image:
            if os.path.exists(args.image):
                with open(args.image, "r") as file:
                    citation = file.read()
                    citation_source = f"file: {args.image}"
            else:
                citation = args.image
                citation_source = "command line argument"
        elif not sys.stdin.isatty():
            citation = sys.stdin.read()
            citation_source = "stdin (piped input)"
        else:
            print(
                "Error: No citation text provided. Please supply it as an "
                "argument, from a file with --cite, or pipe it to stdin."
            )
            sys.exit(1)

        generate_citation_png_from_markdown(
            citation, citation_image,
            template_content, citation_dpi, args.debug
        )

        try:
            aspect_ratio = original_width / max(1, original_height)
            if is_very_tall:
                right_canvas_width = int(original_width * 2.0)
                factor = 0.75
                side_padding = 0
            else:
                right_canvas_width = original_width
                factor = width_factor_from_aspect_ratio(aspect_ratio)
                side_padding = 0

            citation_image_width = int(right_canvas_width * factor)

            # When we resize for compositing, match the source image DPI
            resized_citation_file = resize_image(
                citation_image, citation_image_width, dpi
            )
            if not resized_citation_file:
                print("Error: Failed to resize citation image.")
                sys.exit(1)
            temp_files.append(resized_citation_file)

            top_margin = 160 if is_very_tall else 0
            citation_filename = center_on_canvas(
                resized_citation_file,
                right_canvas_width,
                dpi,
                top_margin=top_margin,
                side_padding=side_padding
            )
            if not citation_filename:
                print("Error: Failed to center citation on canvas.")
                sys.exit(1)
            temp_files.append(citation_filename)

            if args.output:
                output_filename = args.output
            else:
                output_filename = (
                    source_file_without_extension
                    + " with citation"
                    + source_file_extension
                )

            if is_very_tall:
                success = append_files_side_by_side(
                    args.image, citation_filename,
                    output_filename, quality
                )
            else:
                success = append_files(
                    args.image, citation_filename,
                    output_filename, quality
                )

            if success:
                print(
                    f"Created '{output_filename}' using citation text "
                    f"from {citation_source}"
                )
            else:
                print(
                    f"Failed to create output file '{output_filename}'"
                )
                sys.exit(1)

        finally:
            if not args.debug:
                clean_up_files(temp_files)


if __name__ == "__main__":
    main()