# SPDX-FileCopyrightText: 2024 Mete Balci
#
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import re

from . import Tokenizer
from .tokens import *
from .objects import *

logger = logging.getLogger(__name__)

integer_re = re.compile(r"^[\+\-]?[0-9]+$")
real1_re = re.compile(r"^[\+\-]?[0-9]*\.[0-9]+$")
real2_re = re.compile(r"^[\+\-]?[0-9]+\.[0-9]*$")

def is_integer(v):
    assert isinstance(v, str)
    return integer_re.match(v) is not None

def is_real(v):
    assert isinstance(v, str)
    return (real1_re.match(v) is not None) or (real2_re.match(v) is not None)

# parser for PDF data in buffer
class Parser:

    def __init__(self, buffer):
        self.buffer = buffer
        self.tokenizer = Tokenizer(self.buffer)
        self.line_offsets = []
        self._calculate_line_boundaries()

    # calculates line boundaries
    # skips the comments (introduced with % until EOL) except the first one
    # the first comment is header (starts at pos=0)
    def _calculate_line_boundaries(self):
        start = 0
        end = start
        skipping = False
        for pos in range(0, len(self.buffer)):
            ch = self.buffer[pos]
            # when % is found (not as first char)
            # start skipping the chars until EOL
            if pos > 0 and ch == ord('%'):
                skipping = True
            if not skipping:
                end = pos
            # LF
            if ch == 10:
                # if it is a pure comment line (end=start), skip it completely
                if end > start:
                    self.line_offsets.append((start, end))
                start = pos + 1
                end = start
                skipping = False
            # CR (only CR or CR LF)
            elif ch == 13:
                # if it is a pure comment line (end=start), skip it completely
                if end > start:
                    self.line_offsets.append((start, end))
                # if there is at least one more char
                if (pos+1) < len(self.buffer):
                    # if the next char is LF it means EOL is CR LF
                    # so skip this as well
                    if self.buffer[pos+1] == 10:
                        pos = pos + 1
                start = pos + 1
                end = start
                skipping = False
        logger.info("number of lines: %d" % len(self.line_offsets))

    def get_num_lines(self):
        return len(self.line_offsets)

    def get_line(self, line_number):
        assert line_number < len(self.line_offsets)
        (start, end) = self.line_offsets[line_number]
        return self.buffer[start:end]

    def _find_line(self, pos):
        logger.debug('finding line covering byte offset %d' % pos)
        for idx in range(0, len(self.line_offsets)):
            (start, end) = self.line_offsets[idx]
            if (start <= pos and
                pos < end):
                logger.debug('byte offset %d is in line %d [%d, %d)' % (pos,
                                                                      idx,
                                                                      start,
                                                                      end))
                return idx
        return None

    def next_line(self):
        line_number = self._find_line(self.tell())
        if line_number is None:
            return None
        (start, end) = self.line_offsets[line_number]
        line = self.buffer[start:end]
        logger.debug('line=%s 0x%s' % (line.decode('ascii', 'replace'),
                                     line[0:16].hex() if len(line) > 16 else line.hex()))
        # advance position to next line
        # if this is last line set to its end
        if (line_number+1) == len(self.line_offsets):
            self.seek(end)
        # if not, set to next start, EOL can be two chars CR LF
        else:
            (next_start, next_end) = self.line_offsets[line_number+1]
            self.seek(next_start)
        return line

    def reset(self):
        self.seek(0)

    def tell(self):
        return self.tokenizer.tell()

    def seek(self, pos):
        self.tokenizer.seek(pos)

    def seek_to_line(self, line_number):
        assert line_number < len(self.line_offsets)
        (start, end) = self.line_offsets[line_number]
        self.seek(start)

    def next(self):
        token = self.tokenizer.next()
        if isinstance(token, TokenLiteral):
            v = token.as_bytes().decode('ascii', 'replace')
            if v == 'true':
                return PdfBoolean(True)
            elif v == 'false':
                return PdfBoolean(False)
            elif v == 'null':
                return PdfNull()
            else:
                if is_integer(v):
                    logger.debug('v: %s' % v)
                    rollback_pos = self.tell()
                    object_number = int(v)
                    v2 = self.tokenizer.next()
                    logger.debug('v2: %s' % v2)
                    if (v2 is not None and
                        isinstance(v2, TokenLiteral) and
                        is_integer(v2.as_bytes().decode('ascii', 'replace'))):
                        generation_number = int(v2.as_ascii())
                        v3 = self.tokenizer.next()
                        logger.debug('v3: %s' % v3)
                        if (v3 is not None and
                            isinstance(v3, TokenLiteral)):
                            if (v3.as_bytes() == b'R'):
                                return PdfIndirectReference(object_number,
                                                            generation_number)
                            elif (v3.as_bytes() == b'obj'):
                                value = self.next()
                                stream_dictionary = None
                                stream_data = None
                                if isinstance(value, PdfDictionary):
                                    token = self.tokenizer.next()
                                    if isinstance(token, TokenLiteral):
                                        if token.as_bytes() == b'stream':
                                            logger.debug('found stream')
                                            stream_dictionary = value
                                            assert PdfName('Length') in stream_dictionary, 'stream dictionary does not have Length'
                                            # read stream data directly
                                            stream_length = stream_dictionary[PdfName('Length')].p
                                            logger.debug('stream_length: %d' % stream_length)
                                            stream_data = self.buffer[self.tell():self.tell() + stream_length]
                                            # advance
                                            self.seek(self.tell() + stream_length)
                                            token = self.tokenizer.next()
                                            assert isinstance(token, TokenLiteral)
                                            assert token.as_bytes() == b'endstream', 'stream does not end with endstream'
                                            token = self.tokenizer.next()
                                            assert isinstance(token, TokenLiteral)
                                            assert token.as_bytes() == b'endobj', 'stream does not end with endobj'
                                            return PdfIndirectObject(object_number,
                                                                     generation_number,
                                                                     PdfStream(stream_dictionary,
                                                                               stream_data))
                                return PdfIndirectObject(object_number,
                                                         generation_number,
                                                         value)
                    self.seek(rollback_pos)
                    return PdfIntegerNumber(int(v))
                elif is_real(v):
                    try:
                        return PdfRealNumber(float(v))
                    except ValueError:
                        raise PossibleBugException('not a real number? %s' % v)
                else:
                    assert False, 'not implemented'
        elif isinstance(token, TokenLiteralStringStart):
            string = self.tokenizer.next()
            assert isinstance(string, TokenLiteral), string
            end = self.tokenizer.next()
            assert isinstance(end, TokenLiteralStringEnd), end
            return PdfLiteralString(string.as_bytes())
        elif isinstance(token, TokenHexStringStart):
            string = self.tokenizer.next()
            assert isinstance(string, TokenLiteral), string
            end = self.tokenizer.next()
            assert isinstance(end, TokenHexStringEnd), end
            return PdfHexadecimalString(string.as_bytes())
        elif isinstance(token, TokenSolidus):
            token = self.tokenizer.next()
            return PdfName(token.as_bytes())
        elif isinstance(token, TokenArrayStart):
            array = PdfArray()
            while True:
                rollback_pos = self.tell()
                token = self.tokenizer.next()
                if isinstance(token, TokenArrayEnd):
                    return array
                else:
                    # rollback because entry or initial part of it is already read
                    self.seek(rollback_pos)
                    entry = self.next()
                    logger.debug('entry: %s' % entry)
                    array.append(entry)
        elif isinstance(token, TokenDictionaryStart):
            dictionary = PdfDictionary()
            while True:
                rollback_pos = self.tell()
                token = self.tokenizer.next()
                if isinstance(token, TokenDictionaryEnd):
                    return dictionary
                else:
                    assert isinstance(token, TokenSolidus)
                    # rollback because solidus is already read
                    self.seek(rollback_pos)
                    entry_key = self.next()
                    assert isinstance(entry_key, PdfName), entry_key
                    logger.debug('entry_key: %s' % entry_key)

                    entry_value = self.next()
                    assert isinstance(entry_key, PdfObject), entry_value

                    if (isinstance(entry_value, PdfArray) or
                        isinstance(entry_value, PdfDictionary)):
                        logger.debug('entry_value_type: %s' % type(entry_value))
                    else:
                        logger.debug('entry_value: %s' % entry_value)

                    if (entry_key == PdfName(b'Type') or
                        entry_key == PdfName(b'Subtype')):
                        if not isinstance(entry_value, PdfName):
                            raise PdfConformanceException('The value of Type and Subtype entries in a dictionary should be a Name')

                    # "A dictionary entry whose value is null
                    # shall be treated the same as if the entry does not exist"
                    # ISO 32000-2 7.3.7
                    if not isinstance(entry_value, PdfNull):
                        dictionary[entry_key] = entry_value
