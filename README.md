# pdfls

[![Build Status](https://travis-ci.com/metebalci/pdfls.svg?branch=master)](https://travis-ci.com/metebalci/pdfls)

pdfls is a small utility to debug a PDF file.

pdftitle uses pdfminer.six project to parse PDF document.

## Installation

```
pip install pdfls
```

## Usage

`pdfls -p <pdf-file>` displays the structure of the PDF file.

For example:

```
$ pdfls -p knuth65.pdf

catalog.objnum: 713
outlines:
pagetree.objnum: 709
  page[1].objnum: 715
		xobject.types: [ Im1=XObject.Image/CCITTFaxDecode.1710x2580 ]
		content.length: [ 654/2094 548/2092 556/2090 600/2094 605/2103 595/2090 560/2096 615/2066 ]
	page[2].objnum: 1
		xobject.types: [ Im1=XObject.Image/CCITTFaxDecode.1710x2580 ]
		content.length: [ 113/134 4054/22698 41/39 11/3 ]
	page[3].objnum: 13
		xobject.types: [ Im1=XObject.Image/CCITTFaxDecode.1710x2580 ]
		content.length: [ 172/332 2784/14487 79/80 41/39 11/3 ]
...
...
```

shows the catalog, page tree and first 3 page objects. For each page object, xobjects and contents (content streams) are shown. For each XObject, its type.subtype/filter.widthxheight is shown. For each content stream, its raw data len/decoded data len is shown.

If `-i` option is given, it also shows the instructions.

More info can be seen in verbose mode with `-v`. This is mostly for development and debugging of pdfls.

## Changes

0.1:
  - first public release.
  - probably unstable version, only for testing.
