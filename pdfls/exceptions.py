# SPDX-FileCopyrightText: 2024 Mete Balci
#
# SPDX-License-Identifier: GPL-3.0-or-later

class BaseException(Exception):
    pass

class PdfConformanceException(Exception):
    pass

class PossibleBugException(Exception):
    pass

class NotSupportedException(Exception):
    pass
