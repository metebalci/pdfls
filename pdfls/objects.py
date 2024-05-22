# Copyright (C) 2024 Mete Balci
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# pdfls: a utility to investigate PDF files
# Copyright (C) 2024 Mete Balci
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

import base64
import zlib

from pdfminer import ccitt
from pdfminer import lzw

class PdfObject:
    pass

# in all PdfDirectObject subclasses
# self.p holds the Python representation of PdfDirectObject
# self.p can be: bool, int, float, bytes, list, dict, None
class PdfDirectObject(PdfObject):

    def __eq__(self, other):
        if other is None:
            return False
        return self.p == other.p

    def __hash__(self):
        return hash(self.p)

# PDF: true or false
# Python: bool
class PdfBoolean(PdfDirectObject):

    def __init__(self, value):
        assert isinstance(value, bool), value
        self.p = value

    def __str__(self):
        return 'True' if self.p else 'False'

# Integer or Real
class PdfNumber(PdfDirectObject):
    pass

# PDF: 123
# Python: int
class PdfIntegerNumber(PdfNumber):

    def __init__(self, value):
        assert isinstance(value, int), value
        self.p = value

    def __str__(self):
        return '%d' % self.p

# PDF: 34.5
# Python: float
class PdfRealNumber(PdfNumber):

    def __init__(self, value):
        assert isinstance(value, float), value
        self.p = value

    def __str__(self):
        return '%g' % self.p

# Literal or Hexadecimal
class PdfString(PdfDirectObject):
    pass

# PDF: (This is a string)
# Python: bytes
class PdfLiteralString(PdfString):

    def __init__(self, value):
        assert isinstance(value, bytes), value
        self.p = value

    def __str__(self):
        try:
            return '(%s)' % self.p.decode('utf-8')
        except UnicodeError:
            s = []
            for b in self.p:
                if b >= 20 and b <= 126:
                    s.append(chr(b))
                else:
                    s.append('\\x%02x' % b)
            return '(%s)' % ''.join(s)

    def __repr__(self):
        return str(self)

# PDF: <4E6F762073686D6F7A206B6120706F702E>
# Python: bytes
class PdfHexadecimalString(PdfString):

    def __init__(self, value):
        assert isinstance(value, bytes), value
        self.p = value

    def __str__(self):
        if len(self.p) <= 16:
            return '<%s>' % self.p.hex()
        else:
            return '<%s... (len=%d)>' % (self.p[0:16].hex(), len(self.p))

    def __repr__(self):
        return '<%s>' % self.p.hex()

# PDF: /Name1
# Python: bytes (without / symbol)
class PdfName(PdfDirectObject):

    def __init__(self, value):
        if isinstance(value, str):
            value = value.encode('ascii')
        assert isinstance(value, bytes), value
        self.p = value

    # because this is used as key of PdfDictionary
    # eq and hash are explicitly implemented
    def __eq__(self, other):
        assert isinstance(other, PdfName), other
        return self.p == other.p

    def __hash__(self):
        return self.p.__hash__()

    def __str__(self):
        s = '/'
        for b in self.p:
            if b == ord('#'):
                s = '%s#23' % s
            elif b >= 0x20 and b <= 0x7E:
                s = '%s%s' % (s, chr(b))
            else:
                s = '%s#%d' % (s, b)
        return s

    def __repr__(self):
        return str(self)

# PDF: [549 3.14 false (Ralph) /SomeName]
# Python: array of PdfDirectObject entries
class PdfArray(PdfDirectObject):

    def __init__(self, p=[]):
        self.p = p

    def __str__(self):
        s = ''
        for e in self.p:
            if len(s) > 0:
                s = '%s, %s' % (s, e)
            else:
                s = '%s' % e
        return '[%s]' % s

    def __getitem__(self, idx):
        assert isinstance(idx, int), 'idx is not int'
        return self.p[idx]

    def append(self, value):
        assert isinstance(value, PdfDirectObject), 'value is not PdfObject'
        self.p.append(value)

# PDF: <</Key Value>>
# Python: dict of (PdfName, PdfDirectObject) entries
class PdfDictionary(PdfDirectObject):

    def __init__(self, p={}):
        self.p = p

    def __str__(self):
        s = ''
        for (k, v) in self.p.items():
            pass
        return '{%s}' % s

    def __contains__(self, key):
        assert isinstance(key, PdfName), 'key is not PdfName but %s' % type(key)
        return key in self.p

    def __getitem__(self, key):
        assert isinstance(key, PdfName), 'key is not PdfName but %s' % type(key)
        return self.p.get(key)

    def __setitem__(self, key, value):
        assert isinstance(key, PdfName), 'key is not PdfName but %s' % type(key)
        assert isinstance(value, PdfDirectObject), 'value is not PdfDirectObject but %s' % type(value)
        self.p[key] = value

    def get(self, key, default):
        assert isinstance(key, PdfName), 'key is not PdfName but %s' % type(key)
        return self.p.get(key, default)

# PDF:
# << dictionary >>
# stream
# ... bytes ...
# endstream
# Python: bytes
class PdfStream(PdfDirectObject):

    def __init__(self, stream_dictionary, stream_data):
        self.p = self._decode_stream(stream_dictionary, stream_data)
        self.stream_dictionary = stream_dictionary

    def __str__(self):
        return 'stream[%d]' % len(self.p)

    def _decode_stream(self, stream_dictionary, stream_data):
        stream_filter = stream_dictionary.get(PdfName('Filter'), None)
        decode_parms = stream_dictionary.get(PdfName('DecodeParms'), None)
        stream_filters = []
        decode_params = []
        if stream_filter is not None:
            if isinstance(stream_filter, PdfName):
                stream_filters.append(stream_filter.p)
                if decode_parms is None:
                    decode_params.append({})
                else:
                    decode_params.append(decode_parms.p)
            elif isinstance(stream_filter, PdfArray):
                for i in range(0, len(stream_filter)):
                    assert isinstance(stream_filter[i], PdfName), 'stream filter array should contain PdfName entries'
                    stream_filters.append(stream_filter[i].p)
                    if decode_parms is None:
                        decode_params.append({})
                    else:
                        decode_params.append(decode_parms[i].p.p)
                assert False, 'stream filter should be PdfName or PdfArray'
        for i in range(0, len(stream_filters)):
            stream_filter = stream_filters[i]
            decode_param = decode_params[i]
            # all stream filters defined in ISO 32000-2
            if stream_filter == b'ASCIIHexDecode':
                # TODO: should append 0 if len(stream_data) is odd
                stream_data = base64.b16decode(stream_data)
            elif stream_filter == b'ASCII85Decode':
                stream_data = base64.a85decode(stream_data, adobe=True)
            elif stream_filter == b'LZWDecode':
                predictor = decode_param.get('Predictor', 1)
                assert predictor == 1, "FlateDecode.Predictor != 1 but %d" % predictor
                stream_data = lzw.lzwdecode(stream_data)
            elif stream_filter == b'FlateDecode':
                predictor = decode_param.get('Predictor', 1)
                assert predictor == 1, "FlateDecode.Predictor != 1 but %d" % predictor
                stream_data = zlib.decompress(stream_data)
            elif stream_filter == b'RunLengthDecode':
                assert False, 'stream filter %s not implemented yet' % stream_filter.decode('ascii')
            elif stream_filter == b'CCITTFaxDecode':
                assert False, 'stream filter %s not implemented yet' % stream_filter.decode('ascii')
                # default values below are taken from PDF spec
                params = {"K": decode_param.get('K', 0),
                        "Columns": decode_param.get('Columns', 1728) ,
                        "EncodedByteAlign": decode_param.get('EncodedByteAlign', 'false') == 'true',
                        "BlackIs1": decode_param.get('BlackIs1', 'false') == 'true'}
                stream_data = ccitt.ccittfaxdecode(stream_data, params)
            elif stream_filter == b'JBIG2Decode':
                assert False, 'stream filter %s not implemented yet' % stream_filter.decode('ascii')
            elif stream_filter == b'DCTDecode':
                assert False, 'stream filter %s not implemented yet' % stream_filter.decode('ascii')
            elif stream_filter == b'JPXDecode':
                assert False, 'stream filter %s not implemented yet' % stream_filter.decode('ascii')
            elif stream_filter == b'Crypt':
                assert False, 'stream filter %s not implemented yet' % stream_filter.decode('ascii')
            else:
                assert False, "unknown stream filter %s" % stream_filter.decode('ascii', 'replace')
        return stream_data


# PDF: null
# Python: None
class PdfNull(PdfDirectObject):

    def __init__(self):
        self.p = None

    def __str__(self):
        return 'null'


# PdfIndirectObject is just wrapping a PdfDirectObject
# giving it an object number and generation number
# PDF:
# 12 0 obj
# (Brillig)
# endobj
# Python: tuple (object_number, generation_number, PdfDirectObject)
class PdfIndirectObject(PdfObject):

    def __init__(self,
                 object_number,
                 generation_number,
                 value):
        assert object_number > 0
        assert generation_number >= 0
        assert isinstance(value, PdfDirectObject)
        self.object_number = object_number
        self.generation_number = generation_number
        self.p = value

    def __str__(self):
        return '(%d, %d, %s)' % (self.object_number,
                                 self.generation_number,
                                 type(self.value))

    def indirect_reference(self):
        return PdfIndirectReference(self.object_number, self.generation_number)

# not sure if this is explicitly called a Pdf Object
# but it is used as values in Dictionary etc., so it has to be a Pdf Object
# PDF: 12 0 R
# Python: tuple (object_number, generation_number)
class PdfIndirectReference(PdfDirectObject):

    def __init__(self,
                 object_number,
                 generation_number):
        assert object_number > 0
        assert generation_number >= 0
        self.object_number = object_number
        self.generation_number = generation_number

    def __eq__(self, other):
        assert isinstance(other, PdfIndirectReference), other
        return (self.object_number == other.object_number and
                self.generation_number == other.generation_number)

    def __hash__(self):
        return hash('%s:%s' % (self.object_number, self.generation_number))

    def __str__(self):
        return '(%d, %d)' % (self.object_number,
                             self.generation_number)
