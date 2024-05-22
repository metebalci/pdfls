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

import collections
import logging
import re
import time
import sys

from . import Parser
from . import Page
from .objects import *
from .exceptions import *

logger = logging.getLogger(__name__)

# represents a PDF document
class Document:

    def __init__(self, buffer:bytes):
        self.buffer = buffer
        logger.debug("document buffer size = %0.2f MB" % (len(self.buffer)/1024.0/1024.0))
        self.parser = Parser(self.buffer)
        # tuple (major, minor)
        self.version = None
        # dict, final/merged xref table, obj_num -> (obj_offset, obj_gen, obj_free)
        self.xref = None
        # dict
        self.trailer = None
        # dict (obj_num, obj_gen) -> PdfIndirectObject
        self.objects = None
        # root of page tree of type PdfDictionary
        self.catalog = None
        # root page in page tree of type Page
        self.root_page = None
        # ordered list (by page num) of (leaf) Page objects
        self.pages = None
        # load document in self.buffer
        self._load()

    def _version_equal_or_greater_than(self, major, minor):
        if self.version[0] > major:
            return True
        elif self.version[0] == major and self.version[1] >= minor:
            return True
        else:
            return False

    def _find_last_xref_offset(self):
        logger.debug('_find_last_xref_offset')
        num_lines = self.parser.get_num_lines()
        only_numbers_re = re.compile(r"^[0-9]+$")
        for idx in range(num_lines-1, -1, -1):
            startxref = self.parser.get_line(idx)
            if startxref == b'startxref':
                assert idx < (num_lines-2), 'startxref cannot be the last line'
                try:
                    line = self.parser.get_line(idx+1).decode('ascii')
                    if only_numbers_re.match(line) is not None:
                        return int(line)
                except UnicodeError:
                    pass
                assert True, "document should have an offset after startxref"
                return None
        assert True, "document should have a startxref"
        return None

    # ISO 32000-2 7.5.4: Cross-reference table
    # xref entry has a fixed format
    # nnnnnnnnnn ggggg fEOL
    # EOL is one of SP CR, SP LF, CR LF
    def _read_xref_entry(self):
        logger.debug('_read_xref_entry')
        line = self.parser.next_line().decode('ascii')
        # 10-digit byte offset
        byte_offset = int(line[0:10])
        # 5-digit generation number
        generation_number = int(line[11:16])
        # 1 character: f (for free) or n (for in-use)
        is_free = line[17:18]
        if is_free == 'f':
            is_free = True
        elif is_free == 'n':
            is_free = False
        else:
            assert False, "xref entry in-use flag should be f or n, not %s" % str(free)
        return (byte_offset, generation_number, is_free)

    # ISO 32000-2 7.5.4: Cross-reference table
    # xref
    # first_obj_num num_entries
    # xref_entries* (see _read_xref_entry)
    def _read_xref(self, xref_offset):
        logger.debug('_read_xref')
        self.parser.seek(xref_offset)
        line = self.parser.next_line()
        assert line == b'xref', 'xref offset does not point to an xref'
        line = self.parser.next_line().decode('ascii')
        words = line.split(' ')
        first_obj_num = int(words[0])
        num_entries = int(words[1])
        logger.debug('xref.first_obj_num: %d' % first_obj_num)
        logger.debug('xref.num_entries: %d' % num_entries)
        xref_entries = []
        for obj_num in range(first_obj_num, first_obj_num + num_entries):
            xref_entry = self._read_xref_entry()
            xref_entries.append(xref_entry)
        return (first_obj_num, xref_entries)

    def _read_trailer(self):
        logger.debug('_read_trailer')
        num_lines = self.parser.get_num_lines()
        for idx in range(num_lines-1, -1, -1):
            trailer = self.parser.get_line(idx)
            if trailer == b'trailer':
                if idx >= (num_lines-1):
                    raise PdfConformanceException('trailer cannot be the last line')
                self.parser.seek_to_line(idx+1)
                trailer = self.parser.next()
                if not isinstance(trailer, PdfDictionary):
                    raise PdfConformanceException('trailer is not a dictionary')
                return trailer
        return None

    def _read_header(self):
        logger.debug('_read_header')
        header = self.parser.get_line(0)
        assert header[0:5] == b'%PDF-'
        version = header.decode('ascii')[5:]
        version_numbers = version.split('.')
        assert len(version_numbers) == 2
        self.version = (int(version_numbers[0]), int(version_numbers[1]))
        logger.info('version: %d.%d' % (self.version[0], self.version[1]))

    # this should be called in order
    # for the last xref th first
    # for the first xref the last
    def _load_objects_from_xref(self,
                                xref_first_obj_num:int,
                                xref_entries:list):
        logger.debug('_load_objects_from_xref')
        for i in range(0, len(xref_entries)):
            (obj_byte_offset, obj_gen, obj_is_free) = xref_entries[i]
            obj_num = xref_first_obj_num + i
            if not obj_is_free:
                logger.debug('obj %d:%d @ %d' % (obj_num, obj_gen, obj_byte_offset))
                ref = PdfIndirectReference(obj_num, obj_gen)
                if ref in self.objects:
                    self.debug('newer version of %s is already loaded' % ref)
                else:
                    self.parser.seek(obj_byte_offset)
                    obj = self.parser.next()
                    assert isinstance(obj, PdfIndirectObject), '%s:%s' % (obj, type(obj))
                    self.objects[ref] = obj

    def _load_objects(self):
        logger.debug('_load_objects')
        self.objects = {}

        last_xref_offset = self._find_last_xref_offset()
        logger.debug("startxref found: xref @ %d" % last_xref_offset)

        (xref_first_obj_num, xref_entries) = self._read_xref(last_xref_offset)
        logger.debug('%d xref entries starting from object number %d' % (len(xref_entries), xref_first_obj_num))

        self._load_objects_from_xref(xref_first_obj_num, xref_entries)

        trailer = self._read_trailer()
        assert trailer is not None, "there has to be at least one trailer"
        #logger.info('trailer: %s' % trailer)

        if PdfName('Size') not in trailer:
            raise PdfConformanceException('trailer dictionary should have a Size key')

        if PdfName('Root') not in trailer:
            raise PdfConformanceException('trailer dictionary should have a Root key')

        if PdfName('ID') not in trailer:
            if (self._version_equal_or_greater_than(2, 0) or
                PdfName('Encrypt') in trailer):
                    raise PdfConformanceException('trailer dictionary should have an ID key')

        if PdfName('Prev') in trailer:
            raise NotSupportedException('incrementally updated PDFs not supported yet')

        self.trailer = trailer

    def get_object(self, ref:PdfIndirectReference):
        assert isinstance(ref, PdfIndirectReference), ref
        return self.objects[ref]

    def _load_catalog(self):
        log.debug('_load_catalog')
        root_ref = self.trailer[PdfName('Root')]
        logger.info("trailer.Root (catalog dictionary): %s" % str(root_ref))
        self.catalog = self.get_object(root_ref).value
        #logger.info('Catalog: %s:%s' % (self.catalog, type(self.catalog)))
        assert PdfName('Type') in self.catalog, 'catalog has no Type'
        assert self.catalog[PdfName('Type')] == PdfName('Catalog'), 'catalog Type is not Catalog'
        assert PdfName('Pages') in self.catalog, 'catalog has no Pages'

    def add_leaf_page(self, page):
        logger.info('page #%d: %s' % (len(self.pages) + 1, str(page.ref)))
        self.pages.append(page)

    def _load_pages(self):
        self.pages = []
        self.root_page = Page(self,
                              None,
                              self.catalog['Pages'])

    def _load(self):
        self._read_header()
        self._load_objects()
        self._load_catalog()
        self._load_pages()

    def print_summary(self):

        print("PDF Version in Header: %s" % str(self.version))

        assert 'Version' not in self.catalog, 'Version in catalog is not supported yet'

        print("Catalog: %s" % self.catalog)

        if len(self.prevs) > 1:
            print("PDF contains %d incremental updates:" % (len(self.prevs)-1))
            for i in range(0, len(self.prevs)-1):
                (xref_type, xref, trailer) = self.prevs[i]
                print("> Incremental (%s) XREF #%d contains %d objects" % (
                    xref_type,
                    len(self.prevs)-i-1,
                    len(xref)))
        else:
            print("PDF contains no incremental updates");
        print("Base (%s) XREF contains %d objects" % (self.prevs[-1][0],
                                                      len(self.prevs[-1][1])))
        print("Final XREF contains %d objects" % len(self.objects))

        print("PDF contains %d pages:" % len(self.pages))

        for i in range(0, len(self.pages)):
            page = self.pages[i]
            print("Page #%d contains %d%sresources %d instructions" % (
                (i+1),
                len(page.resources),
                ' inherited ' if page.is_resources_inherited() else ' ',
                len(page.content)))
            for k,v in page.resources['Font'].items():
                print(k)
                print(self.get_object(v))
            for inst in page.content:
                try:
                    s = []
                    for i in range(len(inst),0,-1):
                        c = inst[i-1:i]
                        if c == b' ':
                            if len(s) > 0:
                                m = b''.join(reversed(s))
                                print(inst, m.decode('ascii'))
                                break
                        else:
                            s.append(c)
                except:
                    raise
