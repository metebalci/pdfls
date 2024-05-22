# SPDX-FileCopyrightText: 2024 Mete Balci
#
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

def with_debug(func):
    def inner(*args, **kwargs):
        logging.basicConfig(level=logging.DEBUG)
        func(*args, **kwargs)
        logging.basicConfig(level=logging.WARNING)
    return inner

