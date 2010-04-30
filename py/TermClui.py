#! /usr/bin/python3
r'''
a Python3 module offering a Command-Line User Interface

 from TermClui import *
 chosen = choose("A Title", a_list);  # single choice
 chosen = choose("A Title", a_list, multichoice=True)  # multiple choice
 x = choose("Which ?\n(Mouse, or Arrow-keys and Return)", w) # multi-line q
 confirm(text) and do_something()
 answer = ask(question)
 answer = ask(question, suggestion)
 password = ask_password("Enter password : ")
 newtext = edit(title, oldtext)
 edit(filename)
 view(title, text)  # if title is not a filename
 view(textfile)    # if textfile _is_ a filename
 edit(choose("Edit which file ?", list_of_files))
 file  = select_file(Readable=True, TopDir="/home", FPat="*.html")
 files = select_file(Chdir=False, multichoice=True, FPat="*.mp3")
 os.chdir(select_file(Directory=True, Path=os.getcwd()))

TermClui.py offers a high-level user interface to give the user
of command-line applications a consistent "look and feel".  Its
metaphor for the computer is as a human-like conversation-partner;
as each question/response is completed, it is summarised to one line
and remains on screen, so that the history of the session gradually
accumulates on the screen, available for review or for cut/paste.
This user-interface can be intermixed with standard applications
which write to STDOUT or STDERR, such as make, pgp, rcs etc.

For the user, choose() uses either (since 1.50) the mouse; or arrow
keys (or hjkl) and Return or q; also SpaceBar for multiple choices.
confirm() expects y, Y, n or N.  In general, ctrl-L redraws the
(currently active bit of the) screen.  edit() and view() use the
default EDITOR and PAGER if possible.  Window-size-changes are handled,
though the screen only gets redrawn after the next keystroke (e.g. ctrl-L)

choose(), ask() and confirm() all accept multi-line questions:
the first line should be the core question (typically it will
end in a question-mark) and will remain on the screen together
with the user's answer.  The subsequent lines appear beneath the
dialogue, and will disappear when the user has given the answer.

TermClui.py does not use curses (a whole-of-screen interface), it uses
a small and portable subset of vt100 sequences.  Also (since 1.50) the
SET_ANY_EVENT_MOUSE and kmous (terminfo) sequences, which are supported
by all xterm, rxvt, konsole, screen, linux, gnome and putty terminals.

Download TermClui.py from  www.pjb.com.au/midi/free/TermClui.py  or
from http://cpansearch.perl.org/src/PJB/Term-Clui-1.50/py/TermClui.py
and put it in your PYTHONPATH.  TermClui.py depends on Python3.

TermClui.py is a translation into Python3 of the Perl CPAN Modules
Term::Clui and Term::Clui::FileSelect.  This is version 1.50
'''
import re, sys, select, signal, subprocess, os, random
import termios, fcntl, struct, stat, time, dbm

VERSION = '1.50'

# ------------------------ vt100 stuff -------------------------

_A_NORMAL    =  0
_A_BOLD      =  1
_A_UNDERLINE =  2
_A_REVERSE   =  4
_KEY_UP    = 0o403
_KEY_LEFT  = 0o404
_KEY_RIGHT = 0o405
_KEY_DOWN  = 0o402
_KEY_ENTER = "\r"
_KEY_PPAGE = 0o523
_KEY_NPAGE = 0o522
_KEY_BTAB  = 0o541
_getchar = lambda: sys.stdin.read(1)
_ttyin   = 0
_ttyout  = 0
_AbsCursX = 0
_AbsCursY = 0
_TopRow = 0
_CursorRow = 0
_LastEventWasPress = 0   # in order to ignore left-over button-ups

_irow = 0   # maintained by _puts, _up, _down, _left and _right
_icol = 0
_irow_a = []  # maintined by _layout()
_icol_a = []

def _puts(s):
    global _ttyout, _irow, _icol
    _irow += s.count("\n")
    if re.search('\r$', s):
        _icol = 0
    else:
        _icol += len(s)
    print(s, end='', file=_ttyout)
    _ttyout.flush()

# could terminfo sgr0, bold, rev, cub1, cuu1, cuf1, cud1 ...
def _attrset(attr):
    global _ttyout, _A_BOLD, _A_REVERSE, _A_UNDERLINE
    if not attr:
        print("\033[0m", end='', file=_ttyout)
    else:
        if attr & _A_BOLD:
             print("\033[1m", end='', file=_ttyout)
        if attr & _A_REVERSE:
             print("\033[7m", end='', file=_ttyout)
        if attr & _A_UNDERLINE:
             print("\033[4m", end='', file=_ttyout)
    _ttyout.flush()

def _beep():
    global _ttyout
    print("\07", end='', file=_ttyout)
    _ttyout.flush()
def _clear():
    global _ttyout
    print("\033[H\033[J", end='', file=_ttyout)
    _ttyout.flush()
def _clrtoeol():
    global _ttyout
    print("\033[K", end='', file=_ttyout)
    _ttyout.flush()
def _black():
    global _ttyout
    print("\033[30m", end='', file=_ttyout)
    _ttyout.flush()
def _red():
    global _ttyout
    print("\033[31m", end='', file=_ttyout)
    _ttyout.flush()
def _green():
    global _ttyout
    print("\033[32m", end='', file=_ttyout)
    _ttyout.flush()
def _blue():
    global _ttyout
    print("\033[34m", end='', file=_ttyout)
    _ttyout.flush()
def _violet():
    global _ttyout
    print("\033[35m", end='', file=_ttyout)
    _ttyout.flush()

def _getc_wrapper(timeout):
    # may not work on openbsd...
    # on Py, the select.select seems to flush the remaining [A chars :-(
    global _getchar, _ttyin
    if timeout > 0.00001:
        nfound = select.select([_ttyin], [], [], timeout)
        if not nfound[0]:
            return None
    while (True):
        try:
            return _getchar()
        except (IOError):
            continue

def _getch():
    global _KEY_UP, _KEY_DOWN, _KEY_RIGHT, _KEY_LEFT
    global _KEY_PPAGE, _KEY_NPAGE, _KEY_BTAB
    global _AbsCursX, _AbsCursY
    c = _getc_wrapper(0)
    if c == "\033":
        c = _getc_wrapper(0)
        if (c == None):
            return("\033")
        if (c == 'A'):
            return(_KEY_UP)
        if (c == 'B'):
            return(_KEY_DOWN)
        if (c == 'C'):
            return(_KEY_RIGHT)
        if (c == 'D'):
            return(_KEY_LEFT)
        if (c == '5'):
            _getc_wrapper(0)
            return(_KEY_PPAGE)
        if (c == '6'):
            _getc_wrapper(0)
            return(_KEY_NPAGE)
        if (c == 'Z'):
            return(_KEY_BTAB)
        if (c == '['):
            c = _getc_wrapper(0)
            if (c == 'A'):
                return(_KEY_UP)
            if (c == 'B'):
                return(_KEY_DOWN)
            if (c == 'C'):
                return(_KEY_RIGHT)
            if (c == 'D'):
                return(_KEY_LEFT)
            if (c == 'M'):   # mouse report
                # http://invisible-island.net/xterm/ctlseqs/ctlseqs.html
                event_type = ord(_getc_wrapper(0))-32;
                x = ord(_getc_wrapper(0))-32;
                y = ord(_getc_wrapper(0))-32;
                # my $shift   = $event_type & 0x04; # used by wm
                # my $meta  = $event_type & 0x08;   # used by wm
                # my $control = $event_type & 0x10; # used by xterm
                button_drag = (event_type & 0x20) >> 5
                low3bits = event_type & 0x03
                if low3bits == 0x03:
                    button_pressed = 0
                else:  # button 4 means wheel-up, button 5 means wheel-down
                    if event_type & 0x40:
                         button_pressed = low3bits + 4
                    else:
                         button_pressed = low3bits + 1
                t = _handle_mouse(x,y,button_pressed,button_drag)
                if t != '':
                    return(t)
                else:
                    return(_getch())
            if re.search('\d', c) != None:
                c1 = _getc_wrapper(0)
                # _debug("c="+str(c)+" c1="+str(c1))
                if c1 == '~':
                    if (c == '5'):
                        return(_KEY_PPAGE)
                    if (c == '6'):
                        return(_KEY_NPAGE)
                else:  # cursor-position report, response to \033[6n
                    _AbsCursY = int(c)
                    # _debug("_AbsCursY="+str(_AbsCursY))
                    while True:
                        if c1 == ';':
                            break
                        _AbsCursY = 10*_AbsCursY + int(c1)
                        # debug("c1=$c1 AbsCursY=$AbsCursY");
                        c1 = _getc_wrapper(0)
                    _AbsCursX = 0
                    while True:
                        c1 = _getc_wrapper(0)
                        if c1 == 'R':
                            break
                        _AbsCursX = 10*_AbsCursX + int(c1)
                    return _getc_wrapper(0)

            if (c == 'Z'):
                return(_KEY_BTAB)
            return(c)
        return(c)
    #elif c == "\217":
    #    c = _getc_wrapper(0)
    #    if (c == 'A'):
    #        return(_KEY_UP)
    #    if (c == 'B'):
    #        return(_KEY_DOWN)
    #    if (c == 'C'):
    #        return(_KEY_RIGHT)
    #    if (c == 'D'):
    #        return(_KEY_LEFT)
    #    return(c)
    #elif c == "\233":
    #    c = _getc_wrapper(0)
    #    if (c == 'A'):
    #        return(_KEY_UP)
    #    if (c == 'B'):
    #        return(_KEY_DOWN)
    #    if (c == 'C'):
    #        return(_KEY_RIGHT)
    #    if (c == 'D'):
    #        return(_KEY_LEFT)
    #    if (c == '5'):
    #        _getc_wrapper(0)
    #        return(_KEY_PPAGE)
    #    if (c == '6'):
    #        _getc_wrapper(0)
    #        return(_KEY_NPAGE)
    #    if (c == 'Z'):
    #        return(_KEY_BTAB)
    #    return(c)
    else:
        return(c)

def _up(n):
    global _irow, _ttyout
    # if (n < 0) { &down(n); return; }
    print("\033[A"*n, end='', file=_ttyout)
    _ttyout.flush()
    _irow -= n

def _down(n):
    global _irow, _ttyout
    #if (n < 0) { &up(n); return; }
    # \033[B doesn't scroll, but \n needs stty ONLRET
    print("\n"*n, end='', file=_ttyout)
    _ttyout.flush()
    _irow += n

def _right(n):
    global _icol, _ttyout
    # if (n < 0) { &up(n); return; }
    print("\033[C"*n, end='', file=_ttyout)
    _ttyout.flush()
    _icol += n

def _left(n):
    global _icol, _ttyout
    # if (n < 0) { &up(n); return; }
    print("\033[D"*n, end='', file=_ttyout)
    _ttyout.flush()
    _icol -= n

def _goto(newcol,newrow):
    global _icol, _irow
    if (newcol == 0):
        print("\r", end='', file=_ttyout)
        _ttyout.flush()
        _icol = 0
    elif (newcol > _icol):
        _right(newcol-_icol)
    elif (newcol < _icol):
        _left(_icol-newcol)
 
    if (newrow > _irow):
        _down(newrow-_irow)
    elif (newrow < _irow):
        _up(_irow-newrow)

# def move(ix,iy):   Unused...
#     printf TTY "\033[%d;%dH",$iy+1,$ix+1; }



_InitscrAlreadyRun = 0   # its a counter
# tty = True
_ttyout_fnum = 0
_old_tcattr = 0
_IsMouseMode = False;
_WasMouseMode = False;

def _enter_mouse_mode ():   # 1.50  # do we need this in Python?
    global _ttyin, _IsMouseMode, _EncodingString
    if _IsMouseMode:
        warn("_enter_mouse_mode but already IsMouseMode\r\n")
        return 1
    if _EncodingString:
        _ttyin.close()
        _ttyin  = open("/dev/tty", mode="r")
    print("\033[?1003h", end='', file=_ttyout)  # sets SET_ANY_EVENT_MOUSE mode
    _ttyout.flush()
    _IsMouseMode = True
    return 1

def _leave_mouse_mode ():   # 1.50  # do we need this in Python?
    global _ttyin, _IsMouseMode, _EncodingString
    if _IsMouseMode:
        warn("_leave_mouse_mode but not IsMouseMode\r\n")
        return 1
    if _EncodingString:
        _ttyin.close()
        _ttyin  = open("/dev/tty", mode="r")
    print("\033[?1003l", end='', file=_ttyout)  # cancel SET_ANY_EVENT_MOUSE mode
    _ttyout.flush()
    _IsMouseMode = False
    return 1

def _initscr(mouse_mode=False):  # needed for 1.50
    global tty,_ttyout_fnum,_old_tcattr,_getchar, _ttyin,_ttyout, _InitscrAlreadyRun, _icol,_irow
    global _IsMouseMode, _WasMouseMode
    _icol = 0
    _irow = 0
    if _InitscrAlreadyRun > 0:
        _InitscrAlreadyRun+=1
        if not mouse_mode and _IsMouseMode:
            if not _leave_mouse_mode():
                return(False)
        elif mouse_mode and not _IsMouseMode:
            if not _enter_mouse_mode():
                return(False)
        _WasMouseMode = _IsMouseMode
        _icol = 0
        _irow = 0
        return
    else:
        _InitscrAlreadyRun = 1

    _ttyout = open("/dev/tty", mode="w")
    _ttyin  = open("/dev/tty", mode="r")

    if mouse_mode:
        _IsMouseMode = True
        # encoding_string = ':bytes';
        print("\033[?1003h", end='', file=_ttyout) # sets SET_ANY_EVENT_MOUSE
    else:
        _IsMouseMode = False
        #$encoding_string = $EncodingString;

    try:
        import tty
        _ttyout_fnum = _ttyout.fileno()
        _old_tcattr = tty.tcgetattr(_ttyout_fnum)
        tty.setcbreak(_ttyout_fnum)
        mode = tty.tcgetattr(_ttyout_fnum)
        OFLAG = 1
        mode[OFLAG] = mode[OFLAG] & ~(termios.ONLCR | termios.ONLRET)
        tty.tcsetattr(_ttyout_fnum, tty.TCSAFLUSH, mode)
        _getchar = lambda: _ttyin.read(1)
    except (ImportError, AttributeError):
        _ttyout_fnum = 0
        _getchar = lambda: _ttyin.readline()[:-1][:1]

def _endwin():
    global _ttyout, tty,_ttyout_fnum,_old_tcattr, _InitscrAlreadyRun
    global _IsMouseMode, _WasMouseMode
    print("\033[0m", end='', file=_ttyout)
    if _InitscrAlreadyRun > 1:
        if _IsMouseMode and not _WasMouseMode:
            _leave_mouse_mode()
        elif not _IsMouseMode and _WasMouseMode:
            _enter_mouse_mode()
        _InitscrAlreadyRun-=1
        return()
    print("\033[?1003l", end='', file=_ttyout)
    _ttyout.flush()
    if _InitscrAlreadyRun > 1:
        if _IsMouseMode and not _WasMouseMode:
            _leave_mouse_mode()
        elif not _IsMouseMode and _WasMouseMode:
            _enter_mouse_mode()
        _InitscrAlreadyRun-=1
        return
    if _ttyout_fnum:
        tty.tcsetattr(_ttyout_fnum, tty.TCSAFLUSH, _old_tcattr)
    _InitscrAlreadyRun = 0

# ----------------------- size handling ----------------------

_maxcols      = 79
_maxrows      = 24
_size_changed = True
_otherlines   = ''
_notherlines  = 0

def _check_size():
    global _size_changed, _maxcols, _maxrows, _ttyout_fnum
    global _otherlines, _notherlines
    if not _size_changed:
        return
    # http://bytes.com/groups/python/607757-getting-terminal-display-size
    s = struct.pack("HHHH", 0, 0, 0, 0)
    x = fcntl.ioctl(_ttyout_fnum, termios.TIOCGWINSZ, s)
    [_maxrows, _maxcols, xpixels, ypixels] = struct.unpack("HHHH", x)
    _maxcols -= 1

    if _notherlines:
        _otherlinesarray = _fmt(_otherlines)
        _notherlines = len(_otherlinesarray)
    _size_changed = False;

# $SIG{'WINCH'} = sub { $size_changed = 1; };
def _set_size_changed(signum,stackframe):
    global _size_changed
    _size_changed=True

signal.signal(28, _set_size_changed)

# ------------------------ ask stuff -------------------------

# Options such as integer, real, positive, >x, >=x, <x <=x,
# non-null, max-length, min-length, silent  ...
# default could be just one more option, and backward compatibilty
# could be preserved by checking whether the 2nd arg is a hashref ...

_silent = False
def ask_password(question):
    r'''Like ask, but with no echo. Use it for passwords.'''
    global _silent
    _silent = True
    ask(question)

def ask(question, default=''):
    r'''Prints the question and, on the same line, expects the user
to input a string. Left- and Right-arrow and Backspace work
as usual, ctrl-B goes to the beginning and ctrl-E to the end.
If default is specified, it appears on the line initially.
ask() returns the string when the user presses Enter.
'''
    global _silent, _KEY_LEFT, _KEY_RIGHT
    if not question:
        return ''
    _initscr()
    nol = _display_question(question);

    i = 0    # cursor position
    n = 0    # string length
    s_a = []   # list of letters in string
    if default:
        default = re.sub('\t', '    ', default)
        s_a = [y for y in default]
        n = len(default)
        i = n
        #for j in range(len(s_a)):
        #    _puts(s_a[j])
        _puts(default)
        #_left(n)

    while True:
        c = _getch()
        if (c == "\r" or c == "\n"):
            _erase_lines(1)
            break
        if _size_changed:
            _erase_lines(0)
            nol = _display_question(question)
        if c == _KEY_LEFT:
            if i > 0:
                i-=1
                _left(1)
        elif (c == _KEY_RIGHT) and (i < n):
            _puts('x') if _silent else _puts(s_a[i])
            i+=1
        elif (c == "\b") or (c == "\177"):
            if i > 0:
                 n -= 1
                 i -= 1
                 s_a.pop(i)   # splice(@s, $i, 1)
                 _left(1)
                 j = i
                 while j < n:
                     _puts(s_a[j])
                     j += 1
                 _clrtoeol()
                 _left(n-i)
        elif (c == "\003" or c == "\030" or c == "\004"):
             # clear ...
            _left(i)
            i = 0
            n = 0
            _clrtoeol()
            s_a = []
        elif c == "\002":
            _left(i)
            i = 0
        elif c == "\005":
            _right(n-i)
            i = n
        elif c == "\014":
            x = i  # do nothing
        elif str(type(c)) == "<class 'int'>":
            _beep()
        elif ord(c) > 255:
            _beep()
        elif re.match('^[\040-\376]$', c):
            # splice(@s, $i, 0, $c);
            s_a.insert(i, c)
            n+=1
            i+=1
            _puts('x') if _silent else _puts(c)
            j = i
            while j < n:
                _puts(s_a[j])
                j += 1
            _clrtoeol()
            _left(n-i)
        else:
            _beep()
    _endwin()
    _silent = False
    return "".join(s_a)

# ----------------------- choose stuff -------------------------
def _debug(string):
    tmp = open("/tmp/clui_debug", mode="a")
    print(string, file=tmp)
    tmp.close()

# my (%irow, %icol, $nrows, $clue_has_been_given, $choice, $this_cell);
random.seed(None)
_HOME = os.getenv('HOME') or os.getenv('LOGDIR') or os.path.expanduser('~')
_marked    = []
_clue_has_been_given = False
_this_cell = 0
_choice    = ''
_list      = []

def choose(question, a_list, multichoice=False):
    r'''
Prints the question, then a compact formatting of the list of strings
with one (the cursor) highlit. Initially, the cursor is on that string
which the user chose previously in response to this same question.
The user then uses arrow keys (or hjkl) and Return, or q to quit.
The Return key causes choose() to return the string under the cursor;
q for Quit causes choose() to return None.

If there are too many choices to fit on the screen, the user is
prompted for a (case-sensitive) clue, which is used to narrow down
the choices until they do fit.

If multichoice is set, the SpaceBar works to select (or deselect)
the various choices (the choice under the cursor when Return is
pressed is also selected), and choose() returns a list of strings.
'''
    # wantarray doesn't exist in Python because no $ or @
    global _maxcols, _marked, _list, _size_changed, _nrows, _icol_a, _irow_a
    global _irow
    global _ttyout, _this_cell, _clue_has_been_given, _choice, _CursorRow
    _list = a_list
    for i in range(len(_list)):
        _list[i] = re.sub('[\r\n]+$', '', _list[i])   # chop final \n if any
    a_list = _list
    icell = 0
    _marked = [False for item in _list]
    question = re.sub('[\r\n]+$', '', question)
    question = re.sub('^[\r\n]+', '', question)

    otherlines_a = []
    lines = re.split('\r?\n', question, 1)
    firstline = lines[0]
    firstlinelength = len(firstline)
    _choice = get_default(firstline)
    chosen = []
    _initscr(mouse_mode=True)
    _size_and_layout(0)
    if (len(lines) > 1):
       otherlines_a = _fmt(lines[1])
    #if len(otherlines_a):
    #    puts("\r\n" + "\r\n".join(otherlines_a) + "\r")
    #    goto(1+len(firstline), 0)
    _notherlines = len(otherlines_a)
    if multichoice:
        if (firstlinelength < _maxcols-30):
            _puts(firstline+" (multiple choice with spacebar)")
        elif (firstlinelength < _maxcols-16):
            _puts(firstline + "(multiple choice)")
        elif (firstlinelength < _maxcols-9):
            _puts(firstline + "(multiple)")
        else:
            _puts(firstline)

    else:
        _puts(firstline)
    _clrtoeol()

    if (_nrows >= _maxrows):
        _list = _narrow_the_search(_list)
        if not _list:
            _up(1)
            _clrtoeol()
            _endwin()
            _clue_has_been_given = False
            if multichoice:
                return []
            else:
                return None
    _wr_screen()
    print("\033[6n", end='', file=_ttyout)  # u7 will set _AbsCursX, _AbsCur
    _ttyout.flush()
    _CursorRow = _irow_a[_this_cell]  # global, needed by handle_mouse
    # _debug("_CursorRow="+str(_CursorRow))

    while True:
        c = _getch()
        if _size_changed:
            _size_and_layout(_nrows)
            if _nrows >= _maxrows:
                _list = _narrow_the_search(_list)
                if not _list:
                    _up(1)
                    _clrtoeol()
                    _endwin()
                    _clue_has_been_given = False
                    if multichoice:
                        return []
                    else:
                        return None
            _wr_screen()
        if (c == "q" or c == "\004"):
            _erase_lines(1)
            if _clue_has_been_given:
                re_clue = confirm("Do you want to change your clue ?")
                _up(1)
                _clrtoeol()   # erase the confirm
                if re_clue:
                    _irow = 1
                    _list = _narrow_the_search(a_list)
                    _wr_screen()
                    continue
                else:
                    _up(1)
                    _clrtoeol()
                    _endwin()
                    _clue_has_been_given = False
                    if multichoice:
                        return []
                    else:
                        return None
            _goto(0,0)
            _clrtoeol()
            _endwin()
            _clue_has_been_given = False
            if multichoice:
                return []
            else:
                return None
        elif (c == "\t") and (_this_cell < (len(_list)-1)):
            _this_cell+=1
            _wr_cell(_this_cell-1)
            _wr_cell(_this_cell)
        elif (((c == "l") or (c == _KEY_RIGHT)) and (_this_cell < (len(_list)-1)) and (_irow_a[_this_cell] == _irow_a[_this_cell+1])):
            _this_cell+=1
            _wr_cell(_this_cell-1)
            _wr_cell(_this_cell)
        elif (((c == "\010") or (c == _KEY_BTAB)) and (_this_cell > 0)):
            _this_cell-=1
            _wr_cell(_this_cell+1)
            _wr_cell(_this_cell)
        elif (((c == "h") or (c == _KEY_LEFT)) and (_this_cell > 0) and (_irow_a[_this_cell] == _irow_a[_this_cell-1])):
            _this_cell-=1
            _wr_cell(_this_cell+1)
            _wr_cell(_this_cell)
        elif (((c == "j") or (c == _KEY_DOWN)) and (_irow < _nrows)):
            mid_col = _icol_a[_this_cell] + int(0.5*len(_list[_this_cell]))
            left_of_target = 1000
            inew=_this_cell+1
            while inew < len(_list):
                if _icol_a[inew] < mid_col:
                    break    # skip rest of row
                inew+=1
            while inew < len(_list):
                new_mid_col = _icol_a[inew] + int(0.5*len(_list[inew]))
                if new_mid_col >= mid_col:        # we've reached it
                    break
                if (inew == (len(_list)-1)) or (_icol_a[inew+1]<=_icol_a[inew]):
                    break    # we're at EOL
                left_of_target = mid_col - new_mid_col
                inew+=1
            if ((new_mid_col - mid_col) > left_of_target):
                inew-=1
            iold = _this_cell
            _this_cell = inew
            _wr_cell(iold)
            _wr_cell(_this_cell)
        elif (((c == "k") or (c == _KEY_UP)) and (_irow > 1)):
            mid_col = _icol_a[_this_cell] + int(0.5*len(_list[_this_cell]))
            right_of_target = 1000
            inew = _this_cell-1
            while inew > 0:
                if _irow_a[inew] < _irow_a[_this_cell]:    # skip rest of row
                    break
                inew-=1
            while (inew > 0):
                if not _icol_a[inew]:
                    break
                new_mid_col = _icol_a[inew] + int(0.5*len(_list[inew]))
                if new_mid_col < mid_col:         # we're past it
                    break
                right_of_target = new_mid_col - mid_col
                inew-=1
            if ((mid_col - new_mid_col) > right_of_target):
                inew+=1
            iold = _this_cell
            _this_cell = inew
            _wr_cell(iold)
            _wr_cell(_this_cell)
        elif c == "\014":
            if _size_changed:
                _size_and_layout(_nrows)
                if _nrows >= _maxrows:
                    _list = _narrow_the_search(_list);
                    if not _list:
                        _up(1)
                        _clrtoeol()
                        _endwin()
                        _clue_has_been_given = False
                        if multichoice:
                            return []
                        else:
                            return None
            _wr_screen()
        elif (c == "\r") or (c == "\n"):
            _erase_lines(1)
            _goto(firstlinelength+1, 0)
            if multichoice:
                i = 0
                while i < len(_list):
                    if _marked[i] or (i==_this_cell):
                        chosen.append(_list[i])
                    i+=1
                _clrtoeol()
                remaining = _maxcols-firstlinelength
                last = chosen.pop()
                dotsprinted = False
                for item in chosen:
                    if ((remaining - len(item)) < 4):
                        dotsprinted = True
                        _puts("...")
                        remaining -= 3
                        break
                    else:
                        _puts(item+", ")
                        remaining -= (2 + len(item))
                if not dotsprinted:
                    if (remaining - len(last)) > 0:
                        _puts(last)
                    elif remaining > 2:
                        _puts('...')
                _puts("\n\r");
                chosen.append(last)
            else:
                _puts(_list[_this_cell]+"\n\r")
            _endwin()
            set_default(firstline, _list[_this_cell]); # join ($,,@chosen) ?
            _clue_has_been_given = False
            if multichoice:
                return chosen
            else:
                return _list[_this_cell]
        elif c == " ":
            if multichoice:
                _marked[_this_cell] = not _marked[_this_cell]
                # if (_this_cell < (len(_list)-1)):  # 1.50
                #    _this_cell+=1
                #    _wr_cell(_this_cell-1)
                _wr_cell(_this_cell)
            #elif (_this_cell < (len(_list)-1)):
            #    _this_cell+=1
            #    _wr_cell(_this_cell-1)
            #    _wr_cell(_this_cell)

    _endwin()
    print("choose: shouldn't reach here ...\n", file=sys.stderr)

def _layout(my_list):
    global _irow_a, _icol_a, _this_cell, _maxcols, _maxrows, _choice
    _irow_a = []
    _icol_a = []
    _this_cell = 0
    my_irow = 1
    my_icol = 0
    l = []
    i = 0
    while (i < len(my_list)):
        l.append(len(my_list[i]) + 2)
        if (l[i] > _maxcols-1):
            l[i] = _maxcols-1
        if ((my_icol + l[i]) >= _maxcols):
            my_irow += 1
            my_icol = 0

        if my_irow > _maxrows:
            return my_irow
        _irow_a.append(my_irow)
        _icol_a.append(my_icol)
        my_icol += l[i]
        if my_list[i] == _choice:
            _this_cell = i
        i += 1
    return my_irow

def _wr_screen():
    global _otherlines, _notherlines, _nrows, _maxrows, _list, _this_cell

    i = 0
    while (i < len(_list)):
        if not  i == _this_cell:
            _wr_cell(i)
        i += 1
    if (_notherlines and (_nrows+_notherlines) < _maxrows):
        _puts("\r\n" + "\r\n".join(_otherlines) + "\r")
    _wr_cell(_this_cell)

def _wr_cell(i):
    global _icol_a, _irow_a, _icol, _marked, _this_cell, _list
    global _A_BOLD, _A_REVERSE, _A_NORMAL, _A_UNDERLINE
    _goto(_icol_a[i], _irow_a[i]);
    if _marked[i]:
        _attrset(_A_BOLD | _A_UNDERLINE)
    if i == _this_cell:
        _attrset(_A_REVERSE)
    no_tabs = _list[i]
    no_tabs = re.sub("\t", " ", no_tabs)
    no_tabs = no_tabs[:_maxcols-1]  # 1.42
    _puts(" " + no_tabs + " ")
    if _marked[i] or (i == _this_cell):
        _attrset(_A_NORMAL)

def _size_and_layout(erase_rows):
    global _maxrows, _nrows, _list
    _check_size()
    if (erase_rows):
        if (erase_rows > _maxrows):
            erase_rows = _maxrows
        _erase_lines(1)
    _nrows = _layout(_list)

def _narrow_the_search(a_list):
    global _maxrows, _nrows, _KEY_LEFT, _KEY_RIGHT, _clue_has_been_given
    nchoices = len(a_list)
    n = 0
    i = 0
    s_a = []
    s = ''
    my_list = a_list
    _clue_has_been_given = True
    _ask_for_clue(nchoices, i, s);
    while True:
        c = _getch()
        if _size_changed:
            _size_and_layout(0)
            if _nrows < _maxrows:
                _erase_lines(1)
                return my_list
        if (c == _KEY_LEFT) and (i > 0):
             i-=1
             _left(1)
             continue
        elif c == _KEY_RIGHT:
            if i < n:
                _puts(s_a[i])
                i+=1
                continue
        elif (c == "\b") or (c == "\177"):
            if i > 0:
                n-=1
                i-=1
                s_a.pop(i)
                _left(1)
                j = i
                while j < n:
                    _puts(s_a[j])
                    j += 1
                _clrtoeol()
                _left(n-i)
        elif c == "\003" or c == "\030" or c == "\004":
            if not s_a:
                _clue_has_been_given = False
                _erase_lines(1)
                return []
            _left(i)
            i = 0
            n = 0
            s_a = []
            _clrtoeol()
        elif c == "\002":
            _left(i)
            i = 0
            continue
        elif c == "\005":
            _right(n-i)
            i = n
            continue
        elif c == "\014":
            x = i   # do nothing
        elif ord(c) > 255:
            _beep()
        elif nchoices and re.match('^[\040-\376]$', c):
            s_a.insert(i, c)
            n+=1
            i+=1
            _puts(c)
            j = i
            while j < n:
                _puts(s_a[j])
                j += 1
            _clrtoeol()
            _left(n-i)
        else:
            _beep()

        # grep, and if $nchoices=1 return
        s = "".join(s_a);
        # list = grep($[ <= index($_,$s), @biglist);
        if s:
            # a lambda function can't refer to s :-(
            # my_list = list(filter(lambda x: s.find(x)>=0, biglist))
            my_list = []
            for tmp_str in a_list:
                tmp_str.find(s)>=0 and my_list.append(tmp_str)
        else:
            my_list = a_list
        nchoices = len(my_list)
        _nrows = _layout(my_list)
        if (nchoices==1 or (nchoices and (_nrows<_maxrows))):
            _puts("\r")
            _clrtoeol()
            _up(1)
            _clrtoeol()
            return my_list
        _ask_for_clue(nchoices, i, s)

    print("_narrow_the_search: shouldn't reach here ...", file=sys.stderr)

def _ask_for_clue(nchoices, i, s):
    if nchoices:
        if s:
            headstr = "the choices won't fit; there are still";
            _goto(0,1)
            _puts(headstr+" "+str(nchoices)+" of them")
            _clrtoeol()
            _goto(0,2)
            _puts("lengthen the clue : ")
            _right(i)
        else:
            headstr = "the choices won't fit; there are"
            _goto(0,1)
            _puts(headstr+" "+str(nchoices)+" of them")
            _clrtoeol()
            _goto(0,2)
            _puts("   give me a clue :            (or ctrl-X to quit)")
            _left(30)
    else:
        _goto(0,1)
        _puts("No choices fit this clue !")
        _clrtoeol();
        _goto(0,2)
        _puts(" shorten the clue : ")
        _right(i)

def get_default(question):
    r'''Returns (what the dbm database remembers as) the choice the
user made the last time they were asked this question.
'''
    if os.getenv('CLUI_DIR') == 'OFF':
        return ''
    if not question:
        return ''
    n_tries = 5
    while n_tries > 0:
        try:
            CHOICES = dbm.open (_dbm_file(), 'c', 0o600)
            break
        except NameError:
            return ''
        except IOError:
            if n_tries < 2:
                return ''
            select.select([], [], [], random.uniform(0.0, 0.45))
        else:
            return ''
        n_tries -= 1
    my_choice = CHOICES.get(question)
    CHOICES.close()
    if my_choice:
        return my_choice.decode()
    else:
        return ''

def set_default(question, answer):
    r'''Overwrites the choice the user made the last time they
were confronted with this question. This can be useful in
an application where one task typically follows another,
to set the next default choice.
'''
    if os.getenv('CLUI_DIR') == 'OFF':
        return None
    if not question:
        return None
    n_tries = 5
    while n_tries > 0:
        try:
            CHOICES = dbm.open (_dbm_file(), 'c', 0o600)
            break
        except NameError:
            return None
        except IOError:
            if n_tries < 2:
                return ''
            select.select([], [], [], random.uniform(0.0, 0.45))
        else:
            return None
        n_tries -= 1
    CHOICES[question] = answer
    CHOICES.close()
    return answer

def _dbm_file():
    global _HOME
    if (os.getenv('CLUI_DIR') == 'OFF'):
        return None
    if (os.getenv('CLUI_DIR')):
        db_dir = os.getenv('CLUI_DIR')
        db_dir = re.sub('^~', _HOME, db_dir)
    else:
        db_dir = _HOME+"/.clui_dir"
    os.path.exists(db_dir) or os.mkdir(db_dir, 0o750)
    return db_dir+"/choices"

def _handle_mouse(x, y, button_pressed, button_drag):  # 1.50 
    # _debug("_handle_mouse: x="+str(x)+" y="+str(y))
    global _TopRow, _AbsCursY, _CursorRow, _LastEventWasPress
    global _this_cell, _irow_a, _icol_a, _list
    _TopRow = _AbsCursY - _CursorRow
    # _debug("_TopRow="+str(_TopRow)+" _AbsCursY="+str(_AbsCursY)+" _CursorRow="+str(_CursorRow))
    if _LastEventWasPress:
        _LastEventWasPress = False
        return('')
    if y < _TopRow:
        return('')
    mouse_row = y - _TopRow
    mouse_col = x - 1
    # _debug("x="+str(x)+" y="+str(y)+" mouse_row="+str(mouse_row));
    # _debug("button_pressed=$button_pressed button_drag=$button_drag");
    found = False
    for i in range(len(_irow_a)):
        if _irow_a[i] == mouse_row:
            # _debug("list[$i]=$list[$i] is the right row");
            if _icol_a[i] < mouse_col and (_icol_a[i]+len(_list[i])) >= mouse_col:
                found = True
                break
            if _irow_a[i] > mouse_row:
                break
        i += 1
    if not found:
        return()
    # if xterm doesn't receive a button-up event it thinks it's dragging
    return_char = ''
    if button_pressed == 1 and not button_drag:
        _LastEventWasPress = 1
        return_char = _KEY_ENTER
    elif button_pressed == 3 and not button_drag:
        _LastEventWasPress = 1
        return_char = ' '
    if i != _this_cell:
        t = _this_cell
        _this_cell = i
        _wr_cell(t)
        _wr_cell(_this_cell)
    return(return_char)

# ----------------------- confirm stuff -------------------------

def confirm(question):
    '''Print the question, and the user replies Yes or No using
"y", "Y", "n" or "N".  confirm() returns True or False.
'''
    global _ttyin, _ttyout
    if not question:
        return(False)
    # return(0) unless -t STDERR
    if not os.isatty(sys.stdout.fileno()):
        return(None)
    _initscr()
    nol = _display_question(question)
    _puts (" (y/n) ")
    while (True):
        response=_getch()
        if (re.match('[yYnN]', response)):
            break
        _beep()

    _left(6)
    _clrtoeol()
    if (re.match('[yY]', response)):
        _puts("Yes")
    else:
        _puts("No")
    _erase_lines(1)
    _endwin()
    if (re.match('[yY]', response)):
        return True
    else:
        return False

# ----------------------- edit stuff -------------------------

def edit(title='', text=''):
    r'''If there's no text and the "title" is a filename that exists
and is writeable, then the user's default EDITOR is invoked on
that file.  If the file is only readable, the user's default
PAGER is used.  If there is text, the editor is invoked on that
text, and the title is displayed within the temporary file-name.
In either case, the resulting text is returned.
'''
    # my ($dirname, $basename, $rcsdir, $rcsfile, $rcs_ok);

    editor = os.getenv('EDITOR') or "vi"; # should also get_default()
    if not title:    # start editor session with no preloaded file
        subprocess.call([editor])
    elif text:
        # must create tmp file with title embedded in name
        tmpdir = '/tmp/';
        safename = re.sub('[\W_]+', '_', title)
        fname = tmpdir + safename + str(os.getpid())
        try:
            fh = open(fname, mode="w")
        except EnvironmentError as err:
            sorry("can't open "+fname+": "+str(err))
            return ''
        print(text, file=fh)
        fh.close()
        subprocess.call([editor, fname])
        try:
            fh = open(fname, mode="r")
        except EnvironmentError as err:
            sorry("can't read "+fname+": "+str(err))
            return ''
        text = fh.read()
        fh.close()
        try:
            os.unlink(fname)
        except EnvironmentError as err:
            sorry("couldn't unlink "+fname+": "+str(err))
        return text
    else:    # its a file, we will try RCS ...
        file = title

        # weed out no-go situations
        file_stat = os.stat(file)
        # if os.path.isdir(file):  # less yukky, but does an extra stat
        if stat.S_ISDIR(file_stat.st_mode):  # YUK
            sorry(file+" is already a directory")
            return ''
        #if (-B _ and -s _):
        #    sorry(file+" is not a text file")
        #    return ''
        #if (-T _ and !-w _):
        if not _is_writeable(file_stat):
            view(file)
            return True

        # it's a writeable text file, so work out the locations
        if file.find(os.path.sep) >= 0:
            rcsdir   = os.path.dirname(file)+'/RCS'
            basename = os.path.basename(file)
            rcsfile  = rcsdir+os.path.sep+basename+',v'
        else:
            basename = file
            rcsdir   = "RCS"
            rcsfile  = rcsdir+os.path.sep+os.path.basename(file)+',v'

        rcslog = rcsdir+'/log'

        # we no longer create the RCS directory if it doesn't exist,
        # so you have to `mkdir RCS' to enable rcs in a directory ...
        rcs_ok = True
        if not os.path.isdir(rcsdir):
            rcs_ok = False
        elif not _is_writeable(rcsdir):
            rcs_ok = False
            print("can't write in "+rcsdir, file=sys.stderr)

        # if the file doesn't exist, but the RCS does, then check it out
        if rcs_ok and os.path.isfile(rcsfile) and not os.path.isfile(file):
            subprocess.call(["co", "-l", file, rcsfile])

        starttime = time.time()
        subprocess.call([editor, file])
        elapsedtime = time.time() - starttime;
        # could be output or logged, for worktime accounting

        # if (rcs_ok and -T file):     # check it in
        if rcs_ok:
            if not os.path.isfile(rcsfile):
                msg = ask (file+' is new. Please describe it:');
                if msg:
                    quotedmsg = re.sub("'","'\"'\"'", msg)
                    # system "ci -q -l -t-'$quotedmsg' -i $file $rcsfile";
                    subprocess.call(["ci", "-q", "-l", "-t-'"+quotedmsg+"'", file, rcsfile])
                    _logit(rcslog, basename, msg)
            else:
                msg = ask('What changes have you made to '+file+' ?')
                quotedmsg = re.sub(r"'", "'\"'\"'", msg)
                if msg:
                    subprocess.call(["ci", "-q", "-l", "-m'"+quotedmsg+"'", file, rcsfile])
                    _logit(rcslog, basename, msg)

def _logit(rcslog, file, msg):
    logfile = open(rcslog, mode="a")
    print(_timestamp()+' '+file+' '+os.getlogin()+' '+msg, file=logfile)
    logfile.close()

def _timestamp():
    # returns current date and time in "199403011 113520" format
    x = time.localtime(time.time())
    return '{0:0=4}{1:0=2}{2:0=2} {3:0=2}{4:0=2}{5:0=2}'.format(x.tm_year, x.tm_mon, x.tm_mday, x.tm_hour, x.tm_min, x.tm_sec)

# -------------------------- filetests --------------------------

def _re_grep(regexp, a_list):
    '''greps a regexp in a list of strings'''
    l = []
    for tmpstr in a_list:
        if re.match(regexp, tmpstr):
            l.append(tmpstr)
    return l

def _is_writeable(arg):
    my_type = str(type(arg))
    if my_type == "<class 'str'>":
        if not os.path.exists(arg):
            return False
        my_stat_result = os.stat(arg)
    elif my_type == "<class 'posix.stat_result'>":
        my_stat_result = arg
    else:
        return False
    my_euid = os.geteuid()
    my_groups = os.getgroups()
    my_fuid = my_stat_result.st_uid
    my_fgid = my_stat_result.st_gid
    my_mode = my_stat_result.st_mode
    if (my_euid == my_fuid) and (my_mode & 0o200):
        return True
    if my_mode & 0o20:
        for gid in my_groups:
            if gid == my_fgid:
                return True
    if my_mode & 0o2:
        return True
    return False

def _is_readable(arg):
    my_type = str(type(arg))
    if my_type == "<class 'str'>":
        if not os.path.exists(arg):
            return False
        my_stat_result = os.stat(arg)
    elif my_type == "<class 'posix.stat_result'>":
        my_stat_result = arg
    else:
        return False
    my_euid = os.geteuid()
    my_groups = os.getgroups()
    my_fuid = my_stat_result.st_uid
    my_fgid = my_stat_result.st_gid
    my_mode = my_stat_result.st_mode
    if (my_euid == my_fuid) and (my_mode & 0o400):
        return True
    if my_mode & 0o40:
        for gid in my_groups:
            if gid == my_fgid:
                return True
    if my_mode & 0o4:
        return True
    return False

def _is_executable(arg):
    my_type = str(type(arg))
    if my_type == "<class 'str'>":
        if not os.path.exists(arg):
            return False
        my_stat_result = os.stat(arg)
    elif my_type == "<class 'posix.stat_result'>":
        my_stat_result = arg
    else:
        return False
    my_euid = os.geteuid()
    my_groups = os.getgroups()
    my_fuid = my_stat_result.st_uid
    my_fgid = my_stat_result.st_gid
    my_mode = my_stat_result.st_mode
    if (my_euid == my_fuid) and (my_mode & 0o400) and (my_mode & 0o100):
        return True
    if (my_mode & 0o40) and (my_mode & 0o10):
        for gid in my_groups:
            if gid == my_fgid:
                return True
    if (my_mode & 0o4) and (my_mode & 0o1):
        return True
    return False


def _is_textfile(arg):   # arg must be a str, the filename
    my_type = str(type(arg))
    if my_type == "<class 'str'>":
        if not os.path.exists(arg):
            return False
    else:
        return False
    try:
        f = open(arg, mode='br')
    except EnvironmentError as err:
        print("can't open "+arg+": "+err, file=sys.stderr)
    ascii = 0
    nonascii = 0
    for byte in f.read(2048):
        # if ord(c) > 127:
        if (byte > 127) or (byte<9) or ((byte>14) and (byte<32)):
            nonascii += 1
        else:
            ascii += 1
    f.close()
    if ascii == 0:
        return None
    elif (nonascii/ascii) > 0.10:
        return False
    else:
        return True

def _is_owned(arg):
    my_type = str(type(arg))
    if my_type == "<class 'str'>":
        if not os.path.exists(arg):
            return False
        my_stat_result = os.stat(arg)
    elif my_type == "<class 'posix.stat_result'>":
        my_stat_result = arg
    else:
        return False
    my_euid = os.geteuid()
    my_fuid = my_stat_result.st_uid
    if my_euid == my_fuid:
        return True
    return False


# ----------------------- sorry stuff -------------------------

def sorry(msg):   # warns user of an error condition
    r'''Prints the message to stderr preceded by the word "Sorry, "
'''
    print('Sorry, '+str(msg), file=sys.stderr)

def inform(msg):
    r'''Prints the message to /dev/tty or to stderr.
'''
    msg = re.sub('[\r\n]+$', '', msg)
    try:
        ttyout = open('/dev/tty', mode='w')
        print(msg, file=ttyout)
        ttyout.close()
    except:
       print(str(msg), file=sys.stderr)

# ----------------------- view stuff -------------------------

def view(title='', text=''):    # or ($filename) =
    r'''If there's no text and the "title" is a filename that exists
and is readable, then a pager is invoked on that file.  Else,
a pager is invoked on the text, and the title is displayed
somewhere as a title.  If the text covers 60% or more of the
screen, the user's default PAGER is used; if the text is two lines
or less, it is just printed; in between, a built-in tiny pager is
used which offers the user the choices "q" to clear the text and
continue, or Enter to leave the text on the screen and continue.
'''
    global _OpenFile
    pager = os.getenv('PAGER')
    if not pager:
        for f in ["/usr/bin/less", "/usr/bin/more"]:
            if os.path.exists(f):
                default_pager = f
                break
    if (not text) and os.path.exists(title) and _Open(title, mode='r'):
        nlines = 0
        for line in _OpenFile:
            nlines += 1
            if (nlines > _maxrows):
                break
        _OpenFile.close()
        if (nlines > int(0.6*_maxrows)):
            subprocess.call(pager, title)
        else:
            fh = open(title, mode='r')
            text = fh.read()
            fh.close()
            _tiview(title, text);
    else:
        lines = re.split('\r?\n', text, _maxrows-1)
        if len(lines) < 21:
            _tiview (title, text)
        else:
            tmpdir = '/tmp/'
            safename = re.sub('[\W_]+', '_', title)
            fname = tmpdir + safename + os.getpid()
            if not _Open(fname, mode="w"):
                return ''
            _OpenFile.print(text)
            _OpenFile.close()
            subprocess.call(pager, fname)
            _Unlink(tmp)

def _tiview(title='', text=''):
    global _icol, _irow
    if not text:
        return False
    title = re.sub('\t', ' ', title)
    titlelength = len(title)

    _check_size()
    rows = _fmt(text, nofill=True);
    _initscr();
    if 3 > len(rows):
        _puts("\r\n".join(rows) + "\r\n")
        _endwin()
        return True
    if titlelength > (_maxcols-35):
        _puts (title+"\r\n")
    else:
        _puts (title+"   (<enter> to continue, q to clear)\r\n")

    _puts("\r" + "\r\n".join(rows) + "\r")  # the perl version does clrtoeol
    _icol = 0
    _irow = len(rows)
    _goto(titlelength+1, 0)

    while (True):
        c = _getch()
        if (c == 'q' or c == "\030" or c == "\027" or c == "\030" or c == "\003" or c == "\c\\"):
            _erase_lines(0)
            _endwin()
            return True
        elif (c == "\r" or c == "\n"):    # <enter> retains text on screen
            _clrtoeol()
            _goto(0, len(rows)+1)
            _endwin()
            return True
        elif (c == "\014"):
            _puts("\r")
            _endwin()
            _tiview(title, text)
            return True

    print("_tiview: shouldn't reach here\n", file=sys.stderr)
    return False

# -------------------------- infrastructure -------------------------

_OpenFile = 0
def _Open(filename, mode="r"):
    global _OpenFile
    try:
        _OpenFile = open(filename, mode=mode)
        return True
    except EnvironmentError as err:
        print("\ncan't open "+filename+': '+str(err), file=sys.stderr)
        return False

def _Unlink(filename):
    try:
        os.unlink(filename)
        return True
    except EnvironmentError as err:
        print("\ncan't unlink "+filename+": "+str(err), file=sys.stderr)
        return False

def _display_question(question, nofirstline=False):
    '''used by ask() and confirm(), but not by choose() ...'''
    _check_size()
    otherlines_a = []
    # my ($firstline, @otherlines);
    if nofirstline:
        otherlines_a = _fmt(question)
    else:
        # [firstline,otherlines] = re.split('\r?\n', question, 2)
        lines = re.split('\r?\n', question, 1)
        if (lines[0]):
            _puts(lines[0] + " ")
        if (len(lines) > 1):
           otherlines_a = _fmt(lines[1])
    if len(otherlines_a):
        _puts("\r\n" + "\r\n".join(otherlines_a) + "\r")
        _goto(1+len(lines[0]), 0)
    return len(otherlines_a)

def _erase_lines(nline):
    '''leaves cursor at beginning of line nline and clears rest of screen'''
    global _ttyout
    _goto(0, nline)
    print("\033[J", end='', file=_ttyout)
    _ttyout.flush()

def _fmt(text, nofill=False):
    '''Used by _tiview, ask and confirm; formats the text within maxcols cols'''
    # my (@i_words, $o_line, @o_lines, $o_length, $last_line_empty, $w_length);
    # my (@i_lines, $initial_space);
    global _maxcols
    o_line = ''
    o_lines = []
    o_length = 0
    last_line_empty = False
    i_lines = re.split('\r?\n',text)
    for i_line in i_lines:
        if (re.search('^\s*$', i_line)):
            if (o_line):
                o_lines.append(o_line)
                o_line=''
                o_length=0
            if (not last_line_empty):
               o_lines.append('')
               last_line_empty = True
            continue

        last_line_empty = False

        if nofill:
            o_lines.append(i_line[0:_maxcols])
            continue

        # if ($i_line =~ s/^(\s+)//) {   # line begins with space ?
        split_list = re.split(r'^(\s+)', i_line, 1)
        if (len(split_list) > 2):
            i_line = split_list[2]
            initial_space = re.sub(r'\t', '   ', split_list[1])
            if (o_line):
                o_lines.append(o_line)
            o_line = initial_space
            o_length = len(initial_space)
        else:
            initial_space = ''

        i_words = re.split(r'\s+', i_line)
        for i_word in i_words:
            w_length = len(i_word)
            if ((o_length + w_length) > _maxcols):
                o_lines.append(o_line)
                o_line = initial_space
                o_length = len(initial_space)

            if (w_length > _maxcols):   # chop it !
                o_lines,append(i_word[0:_maxcols])
                continue

            if (o_line):
                o_line += ' '
                o_length += 1
            o_line += i_word
            o_length += w_length

    if (o_line):
        o_lines.append(o_line)
    if (len(o_lines) < _maxrows-2):
        return (o_lines)
    else:
        return o_lines[0, _maxrows-2]

def back_up():
    r'''Moves the cursor up one line, to the beginning of the line,
and clears the line.  Useful if your application is validating
the results of an ask() and wishes to re-pose the question.
'''
    ttyout = open("/dev/tty", mode="w")
    print("\r\033[K\033[A\033[K", end='', file = ttyout)
    ttyout.close

def select_file(Chdir=True, Create=False, ShowAll=False,
    DisableShowAll=False, SelDir=False, FPat='*', File='',
    Path='', Title='', TopDir='/', TextFile=False, Readable=False,
    Writeable=False, Executable=False, Owned=False, Directory=False,
    multichoice=False):
    r'''
This function asks the user to select a file from the filesystem.
It offers Rescan and ShowAll buttons.  The options are modelled
on those of Tk::FileDialog but with various new options: TopDir,
TextFile, Readable, Writeable, Executable, Owned and Directory

Multiple choice is possible in a limited circumstance; when
select_file() is invoked with multichoice=True, with Chdir=False
and without Create.  It is not possible to select multiple files
lying in different directories.

Three problem filenames: 'Create New File', 'Show DotFiles' and
'Hide DotFiles' will, if present in your filesystem, cause confusion.

Chdir

Enable the user to change directories. The default is True.
If it is set to False, and multichoice to True, and Create is
not set, then the user can select multiple files.

Create

Enables the user to specify a file that does not exist.
The default is False.

ShowAll

Determines whether hidden files (.*) are displayed.
The default is False.

DisableShowAll

Disables the ability of the user to change the status of the
ShowAll flag. By default the user is allowed to change the status).

SelDir

If True, enables selection of a directory rather than a file.
The default is False.  To _enforce_ selection of a directory,
use the Directory option.

FPat

Sets the default file selection pattern, in glob format, e.g.
'*.html'.  Only files matching this pattern will be displayed.
If you want multiple patterns, you can use formats like
'*.[ch]' or see glob.glob for details.  The default is '*'.

File

The file selected, or the default file.  The default default
is whatever the user selected last time in this directory.

Path

The path of the selected file, or the initial path.
The default is $HOME.

Title

The Title of the dialog box.  If Title is specified, then
select_file() dynamically appends "in </where/ever>" to it.
The default title is "in directory /where/ever".

TopDir

Restricts the user to remain within a directory or its
subdirectories.  The default is "/".

TextFile

Only text files will be displayed. The default is False.

Readable

Only readable files will be displayed. The default is False.

Writeable

Only writeable files will be displayed. The default is False.

Executable

Only executable files will be displayed.  The default is False.

Owned

Only files owned by the current user will be displayed.  This is
useful if the user is being asked to choose a file for a os.chmod()
or chgrp operation, for example.  The default is False.

Directory

Only directories will be displayed.  The default is False.
    '''
    import glob
#    if (!defined $option{'-Path'}) { $option{'-Path'}=$option{'-initialdir'}; }
#    if (!defined $option{'-FPat'}) { $option{'-FPat'}=$option{'-filter'}; }
#    if (!defined $option{'-ShowAll'}) {$option{'-ShowAll'}=$option{'-dotfiles'};}
#    if ($option{'-Directory'}) { $option{'-Chdir'}=1; $option{'-SelDir'}=1; }
#    my $multichoice = 0;
#    if (wantarray && !$option{'-Chdir'} && !$option{'-Create'}) {
#        $option{'-DisableShowAll'} = 1;
#        $multichoice = 1;
    if multichoice and not Chdir and not Create:
        DisableShowAll = True
    else:
        multichoice = False
#    } elsif (!defined $option{'-Chdir'}) {
#        $option{'-Chdir'} = 1;
#    }

    if Path and os.path.isdir(Path):
        dir = re.sub('([^/])$', r'\1/', Path)
    else:
        dir = re.sub('([^/])$', r'\1/', _HOME)
 
    if TopDir:
        if os.path.isdir(TopDir):
            TopDir = re.sub('([^/])$', r'\1/', TopDir)
        if TopDir.find(dir) >= 0:
            dir = TopDir

    #my ($new, $file, @allfiles, @files, @dirs, @pre, @post, %seen, $isnew);
    #my @dotfiles;

    while True:
        if SelDir:
            pre = ['./']
        else:
            pre = []
        post = []
        try:
            allfiles = sorted(os.listdir(dir))
        except EnvironmentError as err:
            sorry(str(err))
            return None
        dotfiles = _re_grep(r'^\.', allfiles)
        if ShowAll:
            if dotfiles and not DisableShowAll:
                post=['Hide DotFiles']
        else:
            allfiles = _re_grep(r'^[^.]', allfiles)
            if dotfiles and not DisableShowAll:
                post=['Show DotFiles']
 
        # split @allfiles into @files and @dirs for option processing ...
        # @dirs  = grep(-d "$dir/$_" and -r "$dir/$_", @allfiles);
        dirs = []
        for f in allfiles:
            ff= os.path.join(dir, f)
            if os.path.isdir(ff) and _is_readable(ff):
                dirs.append(f)
        files = []
        if Directory:
            pass
        elif FPat:
            baselength = len(dir) + len(os.path.sep) -1
            for ff in glob.glob(os.path.join(dir,FPat)):
                if not os.path.isdir(ff):
                    f = ff[baselength:]
                    files.append(f)
        else:
            for f in allfiles:
                ff= os.path.join(dir, f)
                if not os.path.isdir(ff) and _is_readable(ff):
                    files.append(f)
 
        if Chdir:
            for i in range(len(dirs)):
                dirs[i] += os.path.sep
            if TopDir:
                up = re.sub('[^/]+/?$', '', dir)  # find parent directory
                if up.find(TopDir) >= 0:
                    pre.insert(0, '../')
                # must check for symlinks to outside the TopDir ...
            else:
                pre.insert(0, '../')
 
        elif not SelDir:
            dirs = []
 
        if Create:
            post.insert(0, 'Create New File')
        if TextFile:
            #@files = grep(-T "$dir/$_", @files); }
            i = 0
            while i < len(files):
                ff= os.path.join(dir, files[i])
                if not _is_textfile(ff):
                    files.pop(i)
                else:
                    i += 1
        if Owned:
            #@files = grep(-o "$dir/$_", @files); }
            i = 0
            while i < len(files):
                ff= os.path.join(dir, files[i])
                if not _is_owned(ff):
                    files.pop(i)
                else:
                    i += 1
        if Executable:
            #@files = grep(-x "$dir/$_", @files); }
            i = 0
            while i < len(files):
                ff= os.path.join(dir, files[i])
                if not _is_executable(ff):
                    files.pop(i)
                else:
                    i += 1
        if Writeable:
            #@files = grep(-w "$dir/$_", @files); }
            i = 0
            while i < len(files):
                ff= os.path.join(dir, files[i])
                if not _is_writeable(ff):
                    files.pop(i)
                else:
                    i += 1
        if Readable:
            #@files = grep(-r "$dir/$_", @files); }
            i = 0
            while i < len(files):
                ff= os.path.join(dir, files[i])
                if not _is_readable(ff):
                    files.pop(i)
                else:
                    i += 1

        allfiles = pre + sorted(dirs+files) + post  # reconstitute allfiles

        if Title:
            title = Title+" in "+dir
        else:
            title = "in directory "+dir+" ?"

        if File:
             set_default(title, File)
 
        if multichoice:
            new = choose(title, allfiles, multichoice=True)
            if not new:
                return []
            for i in range(len(new)):
                new[i] = dir+new[i]
            return new

        new = choose (title, allfiles)

        if (ShowAll and new == 'Hide DotFiles'):
            ShowAll = False
            _up(1)
            continue  # ARGHHHhhh no redo :-(
        elif (not ShowAll and new == 'Show DotFiles'):
            ShowAll = True
            _up(1)
            continue  # ARGHHHhhh no redo :-(
 
        if new == "Create New File":
            new = ask("new file name ?")  # validating this is a chore :-(
            if not new:
                continue
            if re.match('^/', new):
                file = new; 
            else:
                file = dir+new
            file = re.sub('//+', '/', file)  # simplify //// down to /
            while re.match(r'./\.\./', file):
                file = re.sub(r'[^/]*/\.\./', '', file)  # zap /../
            file = re.sub(r'/[^/]*/\.\.$', '', file)  # and /.. at end
            if TopDir:  # check against escape from TopDir
                if file.find(TopDir) > -1:
                    dir = TopDir
                    continue

            if os.path.isdir(file):  # pre-existing directory ?
                if SelDir:
                    return file
                else:
                    dir=file
                    if re.match('[^/]$', dir):
                        dir += '/'
                        continue
 
            #$file =~ m#^(.*/)([^/]+)$#;
            dirname = os.path.dirname(file)
            basename = os.path.basename(file)
            if os.path.exists(file):
                continue
            # must check for createbility (e.g. dir exists and is writeable)
            if os.path.isdir(dirname) and _is_writeable(dirname):
                return file
            if not _is_writeable(dirname):
                sorry ("directory "+dirname+" does not exist.")
                continue
            sorry ("directory "+dirname+" is not writeable.")
            continue

        if not new:
            return None
        if (new == './') and SelDir:
            return dir

        if re.match('^/', new):
            file = new      # abs filename
        else:
            file = dir+new  # rel filename (slash always at end)

        if (new == '../'):
            dir = re.sub('[^/]+/?$', '', dir)
            back_up()
            continue
        elif new == './':
            if SelDir:
                return dir
            file = dir
        elif re.search('/$', file):
            dir = file
            back_up()
            continue
        elif os.path.isfile(file):
            return file

