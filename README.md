***This is an ongoing work, not ready for use yet.***

# pdfls

pdfls is a PDF utility (a PDF processor) to investigate a PDF file. 

pdfls has its own ISO 32000-2:2000 PDF-2.0 compliant parser. It uses ccitt and lzw filter implementations of pdfminer.six project. 

## Installation

```
pip install pdfls
```

## Usage

## Copyright

- pdfls: [Copyright (C) 2022-2024 Mete Balci](LICENSE]

- [ccitt.py](pdfminer/ccitt.py) and [lzw.py](pdfminer/lzw.py) are part of [pdfminer.six](https://github.com/pdfminer/pdfminer.six): [Copyright (c) 2004-2016  Yusuke Shinyama \<yusuke at shinyama dot jp\>](LICENSE.pdfminer.six)

## Changes

### 0.3: (not released yet)

- major changes

### 0.2:
- pdfls.py moved to pdfls package, and setup changed accordingly
- pdfminer.six dependency removed, pdfls has its own PDF parser
- added more information regarding the license

### 0.1:
- first public release.
- probably unstable version, only for testing.
