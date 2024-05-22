***This is an ongoing work, not ready for use yet.***

# pdfls

pdfls is a PDF utility (a PDF processor) to investigate PDF files. 

pdfls has its own ISO 32000-2:2000 PDF-2.0 compliant parser. It uses ccitt and lzw filter implementations of pdfminer.six project. 

## Installation

```
pip install pdfls
```

## Usage

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

## External Licenses

- [ccitt.py](pdfminer/ccitt.py) and [lzw.py](pdfminer/lzw.py) are part of [pdfminer.six](https://github.com/pdfminer/pdfminer.six): [Copyright (c) 2004-2016  Yusuke Shinyama \<yusuke at shinyama dot jp\>](LICENSE.pdfminer.six)

# License

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
