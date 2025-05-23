# Photocite

**Photocite** is a python script to append an image with citation text. I use this in [my genealogy research](https://pedigreepipeline.com) where I don't want the citation to become separated from the photo itself if the photo is distributed or otherwise moved around.

For example, if you have an image:

<!-- ![image without citation](example/crane.jpg) -->
<a href="example/crane.jpg">
  <img src="example/crane.jpg" alt="image without citation" width="400">
</a>

and a citation (markdown supported!):

```
$ cat "Charles and Rhoda and possibly Hubert Crane.md"
Photograph depicting Charles Irvin Crane, Rhoda Ellen (Jenkins) Crane, and possibly Hubert Crane, ca. late 1895. Original print, approx. 6 × 4.5 in.; privately held by Todd Wells, Seattle, Washington, 2025. Inscription in the cursive handwriting of Agnes Crane Wells on back reads: “Charles & Rhoda Crane (& Hubert??)”. 
```

then executing: 

```
$ photocite crane.jpg -c crane_citation.md -o crane_cite.jpg
Created 'crane_cite.jpg' using citation text from file: crane_citation.md
$ 
```

results in the a new image:

<a href="example/crane_cite.jpg">
  <img src="example/crane_cite.jpg" alt="image with citation" width="400">
</a>

Photocite chains together a few different command-line tools to do this:

- [ImageMagick](https://imagemagick.org) is a command-line swiss army knife for images, it's a great tool and very fast. It even has some built-in captioning capability. I spent a bunch of time unsuccessfully trying to get this to produce the type of captions I wanted, but I didn't have any luck. I particularly had problems with mixing regular and italic text and with positioning the captions how I wanted.
- [LaTeX](https://www.latex-project.org) is a document preparation and typesetting system. With this I found I could get the consistency and formatting I wanted in the citations.
- [Pandoc](https://pandoc.org) is a universal document converter. I use this for converting Markdown to LaTeX.
- PdfCrop comes with the LaTeX/TeX installation.

Installing and configuring the above tools is beyond the scope of this README.

```
usage: photocite.py [-h] [-co] [-t TEMPLATE] [-o OUTPUT] [-c CITE]
                    [image] [citation_text]

Add citation text to an image, or generate a citation image only.

positional arguments:
  image                 In standard mode: the image file; In citation-only
                        mode: citation file or text
  citation_text         Citation text in markdown format (only used in
                        standard mode)

options:
  -h, --help            show this help message and exit
  -co, --citation-only  Only generate the citation file without appending to
                        the original image
  -t, --template TEMPLATE
                        Path to a custom LaTeX template for pandoc (optional)
  -o, --output OUTPUT   Custom output filename (optional)
  -c, --cite CITE       Read citation text from this file (markdown format)

By default, the citation will be appended to the original image.
The output will be saved as "<original_image> with citation<extension>".

Usage examples:
1. Standard mode: photocite.py image.jpg "Citation text"
   The first argument is the image file, followed by citation text

2. Citation-only mode: photocite.py --citation-only b.md
   Generate just the citation from file b.md

3. Citation-only with direct text: photocite.py --citation-only "Citation text"
   Generate just the citation from the provided text

4. Using piped input: cat citation.md | photocite.py image.jpg
   Or: cat citation.md | photocite.py --citation-only
```



This project is licensed under the Apache License 2.0 – see the [LICENSE](LICENSE) file for details.