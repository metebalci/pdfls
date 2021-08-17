# pylint: disable=missing-module-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=invalid-name
# pylint: disable=global-statement
import sys
import argparse
import traceback
from pdfminer import pdftypes
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import PDFContentParser
from pdfminer.psparser import keyword_name, PSEOF, PSKeyword
from pdfminer.pdftypes import PDFStream


VERBOSE = False
SHOW_INSTRUCTIONS = False
PAGE_NUM = 1


def verbose(*s):
    if VERBOSE:
        print(*s)


def indent(level):
    #pylint: disable=unused-variable
    for i in range(0, level):
        print('\t', end='')


def handle_resources(page, level):
    resources_ref = page.get("Resources", None)
    if resources_ref is None:
        resources = dict()
    elif isinstance(resources_ref, dict):
        resources = resources_ref
    else:
        resources = resources_ref.resolve()
    verbose("resources:")
    verbose(resources)

    font = {}
    for k, v in resources.get("Font", dict()).items():
        font[k] = v.resolve()
    verbose("font:")
    verbose(font)

    xobject = {}
    for k, v in resources.get("XObject", dict()).items():
        xobject[k] = v.resolve()
    verbose("xobject:")
    verbose(xobject)
    indent(level+1)
    print("xobject.types: [", end='')
    for k, v in xobject.items():
        print(" ", end='')
        xo_type = v.attrs.get("Type", None)
        if xo_type is not None:
            xo_type = xo_type.name
            if xo_type == "XObject":
                xo_subtype = v.attrs.get("Subtype", None)
                if xo_subtype is not None:
                    xo_subtype = xo_subtype.name
                    if xo_subtype == "Image":
                        xo_filter = v.attrs.get("Filter", None)
                        xo_filter = xo_filter.name if xo_filter else ""
                        xo_width = v.attrs.get("Width", 0)
                        xo_height = v.attrs.get("Height", 0)
                        print("%s=%s.%s/%s.%dx%d" % (k,
                                                     xo_type,
                                                     xo_subtype,
                                                     xo_filter,
                                                     xo_width,
                                                     xo_height), end='')
    print(" ]")



def handle_contents(page, level):
    contents = pdftypes.resolve_all(page.get("Contents"))
    verbose("contents:")
    verbose(contents)
    # if it is a single PDFStream, make it a list
    if isinstance(contents, PDFStream):
        contents = [contents]
    indent(level+1)
    print("content.length: [", end='')
    for content in contents:
        print(" ", end='')
        print("%d" % len(content.rawdata), end='')
        content.decode()
        print("/%d" % len(content.data), end='')
    print(" ]")
    global SHOW_INSTRUCTIONS
    if SHOW_INSTRUCTIONS:
        opargs = []
        try:
            content_parser = PDFContentParser(contents)
        except PSEOF:
            return
        while 1:
            try:
                (_, obj) = content_parser.nextobject()
            except PSEOF:
                break
            if isinstance(obj, PSKeyword):
                name = keyword_name(obj)
                indent(level+1)
                print(name, end='')
                print("(%s)" % ", ".join([str(x) for x in opargs]))
                opargs = []
            else:
                opargs.append(obj)


def handle_page(page_ref, level):
    global PAGE_NUM
    verbose("page %d" % PAGE_NUM)
    indent(level)
    print("page[%d].objnum: %s" % (PAGE_NUM, page_ref.objid))
    page = page_ref.resolve()
    verbose(page)
    handle_resources(page, level)
    handle_contents(page, level)


def handle_pagetree(pagetree_ref, level=0):
    verbose("pagetree")
    indent(level)
    print("pagetree.objnum: %s" % pagetree_ref.objid)
    pagetree = pagetree_ref.resolve()
    verbose(pagetree)
    kids = pagetree.get("Kids")
    for kid_ref in kids:
        kid = kid_ref.resolve()
        if kid.get("Type").name == "Pages":
            handle_pagetree(kid_ref, level=level+1)
        elif kid.get("Type").name == "Page":
            handle_page(kid_ref, level=level+1)
            global PAGE_NUM
            PAGE_NUM = PAGE_NUM + 1


def handle_outline(outline_ref, level=0):
    if outline_ref is None:
        return
    item = outline_ref.resolve()
    verbose(item)
    title = item.get("Title")
    first = item.get("First")
    #last = item.get("Last")
    nxt = item.get("Next")
    #prev = item.get("Prev")
    indent(level)
    # no idea why and if this is always utf-16
    print(title.decode('utf-16'))
    handle_outline(first, level=level+1)
    handle_outline(nxt, level=level)


def handle_outlines(outlines_ref):
    verbose("outlines:")
    print("outlines:")
    outlines = outlines_ref.resolve()
    verbose(outlines)
    first = outlines.get("First")
    handle_outline(first)


def handle_catalog(catalog_ref):
    verbose("catalog")
    print("catalog.objnum: %s" % catalog_ref.objid)
    catalog = catalog_ref.resolve()
    verbose(catalog)
    outlines_ref = catalog.get("Outlines", None)
    handle_outlines(outlines_ref)
    pagetree_ref = catalog.get("Pages", None)
    handle_pagetree(pagetree_ref)


def handle_io(pdf_io):
    verbose("document")
    parser = PDFParser(pdf_io)
    doc = PDFDocument(parser, fallback=False)
    root_ref = None
    verbose("xrefs:")
    for xref in doc.xrefs:
        verbose(xref)
        trailer = xref.get_trailer()
        verbose(trailer)
        root_ref = trailer.get("Root", None)
        if root_ref is not None:
            break
    if root_ref is None:
        raise Exception("PDF file does not have a root (catalog) objref")
    handle_catalog(root_ref)


def handle_file(pdf_file):
    with open(pdf_file, 'rb') as raw_file:
        return handle_io(raw_file)


def run():
    try:
        parser = argparse.ArgumentParser(
            prog='pdfls',
            description='Shows the structure of a PDF file',
            epilog='')
        parser.add_argument('-p', '--pdf',
                            help='pdf file',
                            required=True)
        parser.add_argument('-i', '--instructions',
                            action='store_true',
                            help='show instructions')
        parser.add_argument('-v', '--verbose',
                            action='store_true',
                            help='enable verbose logging')
        args = parser.parse_args()
        # pylint: disable=W0603
        global VERBOSE, SHOW_INSTRUCTIONS
        VERBOSE = args.verbose
        SHOW_INSTRUCTIONS = args.instructions
        verbose(args)
        handle_file(args.pdf)
        return 0

    except Exception as e:  # pylint: disable=W0612,W0703
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(run())
