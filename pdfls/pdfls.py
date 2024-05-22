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

import argparse
import logging
import sys
import traceback

from . import Document
from . import Tokenizer

logger = logging.getLogger(__name__)

def show_license_header():
    print('pdfls Copyright (C) 2022-2024 Mete Balci')
    print('This program comes with ABSOLUTELY NO WARRANTY; for details see GNU GPLv3.')
    print('This is free software, and you are welcome to redistribute it under certain conditions; for details see GNU GPLv3.')

def run():
    try:
        show_license_header()
        parser = argparse.ArgumentParser(
            prog='pdfls',
            description='shows the structure of a PDF file',
            epilog='')
        parser.add_argument('file',
                            help='pdf file')
        parser.add_argument('-j', '--json',
                            action='store_true',
                            help='generate a JSON file representing the structure of the PDF')
        parser.add_argument('-i', '--instructions',
                            action='store_true',
                            help='show instructions')
        parser.add_argument('-v', '--verbose',
                            action='store_true',
                            help='enable verbose/INFO logging (default is WARN)')
        parser.add_argument('-d', '--debug',
                            action='store_true',
                            help='enable DEBUG logging')
        parser.add_argument('--debug-parser',
                            action='store_true',
                            help='enable DEBUG logging in parser')
        parser.add_argument('--debug-tokenizer',
                            action='store_true',
                            help='enable DEBUG logging in tokenizer')
        args = parser.parse_args()

        loggingFormat = '%(levelname)s/%(filename)s: %(message)s'
        logging.basicConfig(format=loggingFormat)

        logger.debug(args)

        logging.getLogger('pdfls').setLevel(logging.WARNING)

        if args.debug:
            logging.getLogger('pdfls').setLevel(logging.DEBUG)
            logging.getLogger('pdfls.parser').setLevel(logging.WARNING)
            logging.getLogger('pdfls.objects').setLevel(logging.WARNING)
            logging.getLogger('pdfls.tokenizer').setLevel(logging.WARNING)
            logging.getLogger('pdfls.tokens').setLevel(logging.WARNING)
        elif args.verbose:
            logging.getLogger('pdfls').setLevel(logging.INFO)
            logging.getLogger('pdfls.parser').setLevel(logging.INFO)
            logging.getLogger('pdfls.objects').setLevel(logging.INFO)
            logging.getLogger('pdfls.tokenizer').setLevel(logging.INFO)
            logging.getLogger('pdfls.tokens').setLevel(logging.INFO)

        if args.debug_parser:
            logging.getLogger('pdfls.parser').setLevel(logging.DEBUG)
            logging.getLogger('pdfls.objects').setLevel(logging.DEBUG)

        if args.debug_tokenizer:
            logging.getLogger('pdfls.tokenizer').setLevel(logging.DEBUG)
            logging.getLogger('pdfls.tokens').setLevel(logging.DEBUG)

        with open(args.file, 'rb') as f:
            Document(f.read()).print_summary()

        return 0

    except Exception as e:  # pylint: disable=W0612,W0703
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(run())
