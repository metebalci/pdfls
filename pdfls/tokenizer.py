# SPDX-FileCopyrightText: 2024 Mete Balci
#
# SPDX-License-Identifier: GPL-3.0+

import logging
import re

from .tokens import *
from .exceptions import *

logger = logging.getLogger(__name__)

hexdigit_re = re.compile(r"[0-9A-Fa-f]+")

def is_hexdigit(v):
    return hexdigit_re.match(v) is not None

def hexdigit_to_int(v):
    if (v >= ord('0') and v <= ord('9')):
        return v - ord('0')
    elif (v >= ord('A') and v <= ord('F')):
        return v - ord('A') + 10
    elif (v >= ord('a') and v <= ord('f')):
        return v - ord('a') + 10
    else:
        return None

# ISO/DIS 32000-2 7.2.3 Character set
# Character set is divided into three classes
# rules are applicable to everything except strings, streams and comments

# any consecutive whitespace characters (not in a string or stream)
#   is considered as one character

# ISO/DIS 32000-2 Table 1
WHITESPACE_CHARACTERS = {0x00, 0x09, 0x0C, 0x20}
# actually EOL are also WHITESPACE, but they are defined separately here
# because the tokenizer code is written this way
# EOL markers are LF, CR or CR LF, CR LF is considered as single EOL marker
LF = 0x0A
CR = 0x0D
EOL_CHARACTERS = {LF, CR}

# ISO/DIS 32000-2 Table 2
DELIMITER_CHARACTERS = {ord('('), ord(')'),
                        ord('<'), ord('>'),
                        ord('['), ord(']'),
                        ord('{'), ord('}'),
                        ord('/'), ord('%')}

# all other characters are called REGULAR CHARACTERS

# because Comment, String and Name has special syntax
# tokenizer is stateful
_TOKENIZER_CONTEXT_FREE = 0
_TOKENIZER_CONTEXT_COMMENT = 1
_TOKENIZER_CONTEXT_LITERAL_STRING = 2
_TOKENIZER_CONTEXT_HEX_STRING = 3
_TOKENIZER_CONTEXT_NAME = 4

# tokenizer for PDF data in buffer:bytes-like object
class Tokenizer:

    # if skip_comments=True, comments are not returned
    # meaning no TokenComment and no TokenLiteral for the comment content is
    # returned
    def __init__(self, buffer:bytes, skip_comments:bool=True):
        self.buffer = buffer
        self.skip_comments = skip_comments
        self.context:int = _TOKENIZER_CONTEXT_FREE
        self.pos:int = 0

    def reset(self):
        self.seek(0)

    def tell(self) -> int:
        return self.pos

    # seek resets the state because there is no way to know
    # be careful to not miss state changing positions when seeking
    def seek(self, pos:int):
        logger.debug('tokenizer.pos = %d' % pos)
        self.pos = pos
        self.context = _TOKENIZER_CONTEXT_FREE

    # this function returns:
    # - the byte in current position if position < len(self.buffer)
    #   but skips LF in CR LF because CR LF is considered as a single EOL marker
    # - None when exhausted
    def _read_char(self) -> int | None:
        if self.pos == len(self.buffer):
            return None
        ch = self.buffer[self.pos]
        if ch >= 20 and ch <= 126:
            logger.debug('[%d] = "%s" %s' % (self.pos, chr(ch), hex(ch)))
        else:
            logger.debug('[%d] = %s' % (self.pos, hex(ch)))
        self.pos = self.pos + 1
        # LF, CR or CR LF is EOL
        # if ch is CR, check if next is LF, and skip it silently
        # thus this function returns only LF or CR
        if ch == CR:
            if self.pos < len(self.buffer):
                if self.buffer[self.pos] == LF:
                    logger.debug('skipping LF in CRLF')
                    self.pos = self.pos + 1
        return ch

    # read the buffer for comment after it is introduced with %
    # because it has different rules
    # it does only terminate with EOL
    def _read_comment_content(self) -> Token:
        logger.debug('_read_comment_content')
        assert self.context == _TOKENIZER_CONTEXT_COMMENT
        token = TokenLiteral()
        while True:
            ch = self._read_char()
            if ch is None:
                assert False, 'PDF exhausted before comment is terminated'
            elif ch in EOL_CHARACTERS:
                logger.debug('eol')
                break
            else:
                token.push(ch)
        return token

    # read the buffer for literal string after it is introduced with (
    # because it has different rules
    def _read_literal_string_content(self) -> Token:
        logger.debug('_read_literal_string_content')
        assert self.context == _TOKENIZER_CONTEXT_LITERAL_STRING
        token = TokenLiteral()
        balanced_parantheses = 0
        # read literal string here, it has different rules
        while True:
            ch = self._read_char()
            if ch is None:
                raise PdfConformanceException('PDF exhausted when reading literal string before )')
            elif ch in EOL_CHARACTERS:
                # without escape (\) EOL markers (CR or LF or both) means 0x0A
                # there is no EOL in literal string, to terminate ) is needed
                token.push(0x0A)
            # reverse solidus is escape character
            elif ch == ord('\\'):
                ch = self._read_char()
                if ch is None:
                    raise PdfConformanceException('PDF exhausted when reading literal string before )')
                elif ch == 'n':
                    token.push(0x0A)
                elif ch == 'r':
                    token.push(0x0D)
                elif ch == 't':
                    token.push(0x09)
                elif ch == 'b':
                    token.push(0x08)
                elif ch == 'f':
                    token.push(0x0C)
                elif ch == '(':
                    token.push('(')
                elif ch == ')':
                    token.push(')')
                elif ch == '\\':
                    token.push('\\')
                elif ch in EOL_CHARACTERS:
                    # skip \EOL
                    # literal continues on the next line
                    pass
                elif ch < ord('0') or ch > ord('9'):
                    # unknown escape character, ignore silently
                    pass
                else:
                    # check for /d or /dd or /dd
                    ch1 = ch
                    ch2 = self._read_char()
                    if ch2 == None:
                        raise PdfConformanceException('PDF exhausted when reading literal string (\ddd 2) before )')
                    elif ch2 < ord('0') or ch2 > ord('9'):
                        # found \d, reread the last char (ch2)
                        logger.debug('found \\d: \\%s' % chr(ch1))
                        self.seek(self.tell() - 1)
                        # -ord('0')  because ch1 contains the ascii code
                        token.push(ch1 - ord('0'))
                    else:
                        ch3 = self._read_char()
                        if ch3 == None:
                            raise PdfConformanceException('PDF exhausted when reading literal string (\ddd 3) before )')
                        elif ch3 < ord('0') or ch3 > ord('9'):
                            # found \dd, reread the last char (ch3)
                            logger.debug('found \\dd: \\%s%s' % (chr(ch1), chr(ch2)))
                            self.seek(self.tell() - 1)
                            token.push(8 * (ch1 - ord('0')) + (ch2 - ord('0')))
                        else:
                            # found \ddd
                            logger.debug('found \\ddd: \\%s%s%s' % (chr(ch1),
                                                                    chr(ch2),
                                                                    chr(ch3)))
                            ddd = (8 * 8 * (ch1 - ord('0')) +
                                   8 * (ch2 - ord('0')) +
                                   (ch3 - ord('0')))
                            if ddd >= 0xFF:
                                raise PdfConformanceException('\ddd is greater than 0xFF')
                            token.push(ddd)
            # literal string may contain
            # balanced pair of parantheses without escaping e.g. (())
            elif ch == ord('('):
                balanced_parantheses = balanced_parantheses + 1
                token.push(ch)
            elif ch == ord(')'):
                if balanced_parantheses > 0:
                    balanced_parantheses = balanced_parantheses - 1
                    token.push(ch)
                else:
                    self.seek(self.tell() - 1)
                    break
            else:
                token.push(ch)
        return token

    # read the buffer for hexadecimal string after it is introduced with <
    # because it has different rules
    def _read_hexadecimal_string_content(self) -> Token:
        logger.debug('_read_hexadecimal_string_content')
        assert self.context == _TOKENIZER_CONTEXT_HEX_STRING
        token = TokenLiteral()
        last_val = None
        while True:
            ch = self._read_char()
            if ch is None:
                raise PdfConformanceException('PDF exhausted when reading hexadecimal string before >')
            elif ch == ord('>'):
                self.seek(self.tell() - 1)
                break
            else:
                val = hexdigit_to_int(ch)
                if val is None:
                    raise PdfConformanceException('non hexadecimal character \\x%02x in hex string' % ch)
                if last_val is None:
                    last_val = val
                else:
                    token.push((last_val << 4) | val)
                    last_val = None

        # if there are odd number of hex digits, append a 0 at the end
        if last_val is not None:
            token.push(last_val << 4)
        return token

    def _read_name_content(self) -> Token:
        logger.debug('_read_name_content')
        assert self.context == _TOKENIZER_CONTEXT_NAME
        token = TokenLiteral()
        while True:
            ch = self._read_char()
            if ch is None:
                break
            elif ch == ord('#'):
                ch = self._read_char()
                if ch == None:
                    raise PdfConformanceException('PDF exhausted when reading name (#)')
                elif ch == ord('#'):
                    token.push(ch)
                else:
                    v1 = hexdigit_to_int(ch)
                    if v1 is None:
                        raise PdfConformanceException('non hexadecimal character \\x%02x in hex string' % ch)
                    ch = self._read_char()
                    if ch is None:
                        raise PdfConformanceException('PDF exhausted when reading name (#dd)')
                    v2 = hexdigit_to_int(ch)
                    if v2 is None:
                        raise PdfConformanceException('non hexadecimal character \\x%02x in hex string' % ch)
                    token.push((v1 << 4) | v2)
            elif ch in WHITESPACE_CHARACTERS:
                break
            elif ch in EOL_CHARACTERS:
                break
            elif ch in DELIMITER_CHARACTERS:
                self.seek(self.tell() - 1)
                break
            else:
                token.push(ch)

        if len(token.stack) == 0:
            raise PdfConformanceException('zero-length name')
        return token

    def next(self) -> Token | None:
        token = None
        if self.context == _TOKENIZER_CONTEXT_FREE:
            literal = None
            while token is None:
                ch = self._read_char()
                if ch is None:
                    logger.debug('none/exhausted')
                    if literal is not None:
                        token = literal
                    # have to break here otherwise
                    # an infinite loop might happen
                    break
                elif ch in WHITESPACE_CHARACTERS:
                    logger.debug('whitespace')
                    if literal is not None:
                        token = literal
                elif ch in EOL_CHARACTERS:
                    logger.debug('eol')
                    if literal is not None:
                        token = literal
                elif ch in DELIMITER_CHARACTERS:
                    logger.debug('delimiter')
                    if literal is not None:
                        self.seek(self.tell() - 1)
                        token = literal
                    elif ch == ord('('):
                        self.context = _TOKENIZER_CONTEXT_LITERAL_STRING
                        token = TokenLiteralStringStart()
                    elif ch == ord(')'):
                        self.context = _TOKENIZER_CONTEXT_FREE
                        token = TokenLiteralStringEnd()
                    elif ch == ord('<'):
                        ch = self._read_char()
                        if ch == ord('<'):
                            token = TokenDictionaryStart()
                        else:
                            self.seek(self.tell() - 1)
                            self.context = _TOKENIZER_CONTEXT_HEX_STRING
                            token = TokenHexStringStart()
                    elif ch == ord('>'):
                        ch = self._read_char()
                        if ch == ord('>'):
                            token = TokenDictionaryEnd()
                        else:
                            self.seek(self.tell() - 1)
                            token = TokenHexStringEnd()
                    elif ch == ord('['):
                        token = TokenArrayStart()
                    elif ch == ord(']'):
                        token = TokenArrayEnd()
                    elif ch == ord('{'):
                        assert False, '{ not supported'
                    elif ch == ord('}'):
                        assert False, '} not supported'
                    elif ch == ord('/'):
                        self.context = _TOKENIZER_CONTEXT_NAME
                        token = TokenSolidus()
                    elif ch == ord('%'):
                        if self.skip_comments:
                            # read comment content first
                            # then read the next token and return that
                            self.context = _TOKENIZER_CONTEXT_COMMENT
                            self._read_comment_content()
                            self.context = _TOKENIZER_CONTEXT_FREE
                            return self.next()
                        else:
                            self.context = _TOKENIZER_CONTEXT_COMMENT
                            token = TokenComment()
                    else:
                        raise PossibleBugException('\\x%02x is not a delimiter character' % ch)
                else:
                    logger.debug('regular')

                    if literal is None:
                        literal = TokenLiteral()
                        literal.push(ch)
                    else:
                        literal.push(ch)

                    logger.debug('literal: %s' % literal)

        elif self.context == _TOKENIZER_CONTEXT_COMMENT:

            token = self._read_comment_content()
            self.context = _TOKENIZER_CONTEXT_FREE

        elif self.context == _TOKENIZER_CONTEXT_LITERAL_STRING:

            token = self._read_literal_string_content()
            self.context = _TOKENIZER_CONTEXT_FREE

        elif self.context == _TOKENIZER_CONTEXT_HEX_STRING:

            token = self._read_hexadecimal_string_content()
            self.context = _TOKENIZER_CONTEXT_FREE

        elif self.context == _TOKENIZER_CONTEXT_NAME:

            token = self._read_name_content()
            self.context = _TOKENIZER_CONTEXT_FREE

        else:

            raise PossibleBugException('unknown context')

        logger.debug('final token: %s' % token)
        return token
