# SPDX-FileCopyrightText: 2024 Mete Balci
#
# SPDX-License-Identifier: GPL-3.0-or-later

import base64
import collections
import logging
import time
import sys
import zlib

from . import Parser
from .objects import *

logger = logging.getLogger(__name__)

class Page:
    def __init__(self, document, parent, ref):
        self.document = document
        self.parent = parent
        self.ref = ref
        logger.info('Page: %s/%s' % (parent.ref if parent is not None else '.', ref))
        self.node = self.document.get_object(self.ref).value()
        assert PdfName('Type') in self.node, 'page node does not have Type'
        self.node_type = self.node[PdfName('Type')]
        self.parent_ref = self.node.get(PdfName('Parent'), None)
        if self.node_type == PdfName('Pages'):
            logger.info('Pages')
            if PdfName('Kids') not in self.node:
                raise PdfConformanceException('Page [%s] does not specify Kids')
            if PdfName('Count') not in self.node:
                raise PdfConformanceException('Page [%s] does not specify Count')
            self.node[PdfName('Kids')]

            assert PdfName('Kids') in self.node, 'page node does not have Kids'
            assert PdfName('Count') in self.node, 'page node does not have Count'
        elif self.node_type == PdfName('Page'):
            logger.info('Page')
        elif self.node_type == PdfName('Template'):
            logger.info('Template')
        else:
            assert False, "unknown page node type: %s" % self.node_type
        # resources can be inherited
        # so the nodes value is set to _resources
        # but actual self.resources are accessed with property function
        # which looks at resources in parents
        self._resources = self.node.get(PdfName('Resources'), None)
        # this effectively implements non-recursive DFS for loading pagetree
        # the pages with actual content (type=Page) are leaf pages
        # document is called back for leaf pages to keep an ordered list
        if self.is_pages():
            self.kids = []
            for kid_ref in self.node[PdfName('Kids')]:
                logger.debug('page kid: %s' % kid_ref)
                self.kids.append(Page(self.document, self, kid_ref))
        elif self.is_page():
            self.document.add_leaf_page(self)
            self.content = []
            if PdfName('Contents') in self.node:
                content_stream_refs = collections.deque()
                # Contents can be a stream (ref) or an array of streams (refs)
                v = self.node.get(PdfName('Contents'), None)
                if v is None:
                    pass
                else:
                    print(type(v))
                    print(v)
                    v = v.p()
                    if isinstance(v, tuple):
                        content_stream_refs.append(v)
                    elif isinstance(v, list):
                        content_stream_refs.extend(v)
                    else:
                        assert False, "page.Contents is neither a tuple or a list"
                merged_content = []
                while len(content_stream_refs) > 0:
                    ref = content_stream_refs.popleft()
                    stream = self.document.get_object(ref)
                    # strange but what content points can be another list
                    # which contains content streams
                    if isinstance(stream, list):
                        content_stream_refs.extend(stream)
                        continue
                    stream_data = stream.get('_stream_data_', None)
                    if stream_data is not None:
                        merged_content.append(stream_data)
                merged_content = b''.join(merged_content)
                with open('/tmp/content.%d' % self.ref[0], 'wb') as fp:
                    fp.write(merged_content)
                contents = []
                stack = []
                for i in range(0, len(merged_content)):
                    ch = merged_content[i:i+1]
                    if ch == b'\r':
                        if len(stack) > 0:
                            contents.append(b''.join(stack))
                            stack = []
                    else:
                        stack.append(ch)
                self.content = contents

    @property
    def resources(self):
        if self._resources is not None:
            return self._resources
        elif self.parent is not None:
            return self.parent.resources
        else:
            return None

    def is_resources_inherited(self):
        return self._resources == None

    def is_page(self):
        return self.node_type == PdfName('Page')

    def is_pages(self):
        return self.node_type == PdfName('Pages')

    def is_template(self):
        return self.node_type == PdfName('Template')
