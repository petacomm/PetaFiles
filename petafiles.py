#!/usr/bin/env python3
"""
PetaFiles - Terminal File Manager
Vim-style, three-pane, blazingly fast.
Usage: python3 petafiles.py [path]
"""

import curses
import os
import sys
import stat
import shutil
import subprocess
import mimetypes
import time
import fnmatch
from pathlib import Path
from datetime import datetime

# ─── Globals ──────────────────────────────────────────────────────────────────

VERSION = "v1.2"
BOOKMARKS = {}       # key -> path
CLIPBOARD = []       # list of paths
CLIPBOARD_OP = None  # 'copy' or 'cut'
SELECTED = set()     # selected file indices per pane (absolute paths)
SEARCH_TERM = ""

# ─── Colors ───────────────────────────────────────────────────────────────────

def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1,  curses.COLOR_WHITE,   -1)           # normal
    curses.init_pair(2,  curses.COLOR_CYAN,    -1)           # directory
    curses.init_pair(3,  curses.COLOR_GREEN,   -1)           # executable
    curses.init_pair(4,  curses.COLOR_YELLOW,  -1)           # selected
    curses.init_pair(5,  curses.COLOR_BLACK,   curses.COLOR_CYAN)   # cursor
    curses.init_pair(6,  curses.COLOR_BLACK,   curses.COLOR_WHITE)  # statusbar
    curses.init_pair(7,  curses.COLOR_RED,     -1)           # error/symlink
    curses.init_pair(8,  curses.COLOR_MAGENTA, -1)           # archive
    curses.init_pair(9,  curses.COLOR_BLUE,    -1)           # header
    curses.init_pair(10, curses.COLOR_WHITE,   curses.COLOR_BLUE)   # active pane header

COL_NORMAL   = lambda: curses.color_pair(1)
COL_DIR      = lambda: curses.color_pair(2) | curses.A_BOLD
COL_EXEC     = lambda: curses.color_pair(3)
COL_SEL      = lambda: curses.color_pair(4) | curses.A_BOLD
COL_CURSOR   = lambda: curses.color_pair(5)
COL_STATUS   = lambda: curses.color_pair(6)
COL_SYMLINK  = lambda: curses.color_pair(7)
COL_ARCHIVE  = lambda: curses.color_pair(8)
COL_HEADER   = lambda: curses.color_pair(9)  | curses.A_BOLD
COL_ACTIVE   = lambda: curses.color_pair(10) | curses.A_BOLD

ARCHIVES = {'.zip','.tar','.gz','.bz2','.xz','.7z','.rar','.tgz','.tbz2'}
IMAGES   = {'.png','.jpg','.jpeg','.gif','.bmp','.webp','.svg','.ico'}
TEXT_EXT = {'.txt','.md','.py','.js','.ts','.html','.css','.json','.yaml',
            '.yml','.toml','.ini','.cfg','.sh','.bash','.zsh','.fish',
            '.c','.cpp','.h','.rs','.go','.java','.rb','.pl','.php',
            '.xml','.csv','.log','.conf','.env','.gitignore','.Makefile'}

# ─── File utilities ────────────────────────────────────────────────────────────

def list_dir(path):
    """Return sorted list of entries in path."""
    try:
        entries = []
        with os.scandir(path) as it:
            for e in it:
                entries.append(e.name)
        dirs  = sorted([n for n in entries if os.path.isdir(os.path.join(path, n))], key=str.lower)
        files = sorted([n for n in entries if not os.path.isdir(os.path.join(path, n))], key=str.lower)
        return dirs + files
    except PermissionError:
        return []
    except Exception:
        return []

def file_color(path, name):
    if os.path.islink(path):
        return COL_SYMLINK()
    if os.path.isdir(path):
        return COL_DIR()
    ext = Path(name).suffix.lower()
    if ext in ARCHIVES:
        return COL_ARCHIVE()
    try:
        if os.access(path, os.X_OK):
            return COL_EXEC()
    except Exception:
        pass
    return COL_NORMAL()

def human_size(size):
    for unit in ['B','K','M','G','T']:
        if size < 1024:
            return f"{size:.0f}{unit}" if unit == 'B' else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}P"

def file_info(path):
    try:
        st = os.stat(path)
        size = human_size(st.st_size)
        mtime = datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M')
        mode = stat.filemode(st.st_mode)
        return f"{mode}  {size:>7}  {mtime}"
    except Exception:
        return ""

# ─── Preview ──────────────────────────────────────────────────────────────────

def get_preview(path, max_lines, max_cols):
    """Return list of strings to show as preview."""
    if not os.path.exists(path):
        return ["(not found)"]

    if os.path.isdir(path):
        entries = list_dir(path)
        lines = []
        for e in entries[:max_lines]:
            p = os.path.join(path, e)
            prefix = "▶ " if os.path.isdir(p) else "  "
            lines.append(prefix + e)
        if len(entries) > max_lines:
            lines.append(f"  ... {len(entries)-max_lines} more")
        return lines or ["(empty)"]

    ext = Path(path).suffix.lower()

    # Image
    if ext in IMAGES:
        return [f"[image: {Path(path).name}]",
                f"size: {human_size(os.path.getsize(path))}",
                "(open with viewer)"]

    # Archive listing
    if ext in {'.zip'}:
        try:
            import zipfile
            with zipfile.ZipFile(path) as z:
                names = z.namelist()[:max_lines]
            return [f"[zip: {len(names)} entries]"] + names
        except Exception as ex:
            return [f"[zip error: {ex}]"]

    if ext in {'.tar','.gz','.bz2','.xz','.tgz','.tbz2'}:
        try:
            import tarfile
            with tarfile.open(path) as t:
                names = t.getnames()[:max_lines]
            return [f"[tar: {len(names)} entries]"] + names
        except Exception as ex:
            return [f"[tar error: {ex}]"]

    # Text / code
    try:
        with open(path, 'r', errors='replace') as f:
            lines = []
            for i, line in enumerate(f):
                if i >= max_lines:
                    break
                lines.append(line.rstrip('\n')[:max_cols])
        return lines or ["(empty file)"]
    except Exception:
        pass

    # Binary hex dump
    try:
        with open(path, 'rb') as f:
            data = f.read(max_lines * 16)
        lines = []
        for i in range(0, len(data), 16):
            chunk = data[i:i+16]
            hex_part  = ' '.join(f'{b:02x}' for b in chunk)
            ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
            lines.append(f"{i:04x}  {hex_part:<47}  {ascii_part}")
        return lines or ["(empty)"]
    except Exception:
        return ["(binary)"]

# ─── Input dialog ─────────────────────────────────────────────────────────────

def input_dialog(stdscr, prompt, default=""):
    h, w = stdscr.getmaxyx()
    curses.echo()
    curses.curs_set(1)
    stdscr.addstr(h-1, 0, " " * (w-1), COL_STATUS())
    stdscr.addstr(h-1, 0, f" {prompt}: {default}", COL_STATUS())
    stdscr.refresh()
    buf = list(default)
    while True:
        ch = stdscr.getch()
        if ch in (curses.KEY_ENTER, 10, 13):
            break
        elif ch in (curses.KEY_BACKSPACE, 127, 8):
            if buf:
                buf.pop()
        elif ch == 27:
            buf = []
            break
        elif 32 <= ch < 256:
            buf.append(chr(ch))
        stdscr.addstr(h-1, 0, " " * (w-1), COL_STATUS())
        stdscr.addstr(h-1, 0, f" {prompt}: {''.join(buf)}", COL_STATUS())
        stdscr.refresh()
    curses.noecho()
    curses.curs_set(0)
    return ''.join(buf)

def confirm_dialog(stdscr, prompt):
    h, w = stdscr.getmaxyx()
    stdscr.addstr(h-1, 0, " " * (w-1), COL_STATUS())
    stdscr.addstr(h-1, 0, f" {prompt} [y/N]: ", COL_STATUS())
    stdscr.refresh()
    ch = stdscr.getch()
    return ch in (ord('y'), ord('Y'))

# ─── Shell command ─────────────────────────────────────────────────────────────

def run_shell(stdscr, cmd, paths):
    """Run a shell command on selected paths, show output inline."""
    if not paths:
        return
    files_str = ' '.join(f'"{p}"' for p in paths)
    full_cmd = f"{cmd} {files_str}"
    curses.endwin()
    os.system(full_cmd)
    input("Press Enter to return...")
    stdscr.refresh()

def open_file(path):
    """Open file with default handler."""
    if sys.platform == 'darwin':
        subprocess.Popen(['open', path], stderr=subprocess.DEVNULL)
    else:
        for opener in ['xdg-open', 'rifle', 'mimeopen']:
            if shutil.which(opener):
                subprocess.Popen([opener, path], stderr=subprocess.DEVNULL)
                return
        # fallback: try $EDITOR for text
        editor = os.environ.get('EDITOR', 'nano')
        curses.endwin()
        os.system(f'{editor} "{path}"')

def open_editor(paths):
    editor = os.environ.get('EDITOR', 'micro')
    curses.endwin()
    if len(paths) == 1:
        os.system(f'{editor} "{paths[0]}"')
    else:
        os.system(f'{editor} ' + ' '.join(f'"{p}"' for p in paths))

# ─── Bulk rename ──────────────────────────────────────────────────────────────

def bulk_rename(stdscr, paths):
    """Open names in $EDITOR, rename on save."""
    import tempfile
    names = [os.path.basename(p) for p in paths]
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write('\n'.join(names))
        tmpfile = f.name
    editor = os.environ.get('EDITOR', 'micro')
    curses.endwin()
    os.system(f'{editor} "{tmpfile}"')
    curses.doupdate()
    with open(tmpfile) as f:
        new_names = [l.rstrip('\n') for l in f.readlines()]
    os.unlink(tmpfile)
    renamed = 0
    for old_path, new_name in zip(paths, new_names):
        if new_name and new_name != os.path.basename(old_path):
            new_path = os.path.join(os.path.dirname(old_path), new_name)
            try:
                os.rename(old_path, new_path)
                renamed += 1
            except Exception:
                pass
    return renamed

# ─── Pane ─────────────────────────────────────────────────────────────────────

class Pane:
    def __init__(self, path):
        self.path    = os.path.abspath(path)
        self.entries = []
        self.cursor  = 0
        self.offset  = 0   # scroll offset
        self.refresh()

    def refresh(self):
        self.entries = list_dir(self.path)
        self.cursor  = min(self.cursor, max(0, len(self.entries)-1))

    def current_path(self):
        if not self.entries:
            return None
        return os.path.join(self.path, self.entries[self.cursor])

    def current_name(self):
        if not self.entries:
            return None
        return self.entries[self.cursor]

    def go_up(self):
        if self.cursor > 0:
            self.cursor -= 1
        if self.cursor < self.offset:
            self.offset = self.cursor

    def go_down(self):
        if self.cursor < len(self.entries)-1:
            self.cursor += 1

    def go_top(self):
        self.cursor = 0
        self.offset = 0

    def go_bottom(self):
        self.cursor = max(0, len(self.entries)-1)

    def enter(self):
        p = self.current_path()
        if p and os.path.isdir(p):
            self.path = p
            self.cursor = 0
            self.offset = 0
            self.refresh()
            return True
        return False

    def go_parent(self):
        parent = os.path.dirname(self.path)
        if parent != self.path:
            old = os.path.basename(self.path)
            self.path = parent
            self.refresh()
            # restore cursor to the child we came from
            if old in self.entries:
                self.cursor = self.entries.index(old)
            else:
                self.cursor = 0
            self.offset = 0

    def search(self, term):
        """Move cursor to first match."""
        term = term.lower()
        for i, name in enumerate(self.entries):
            if term in name.lower():
                self.cursor = i
                return True
        return False

    def next_search(self, term):
        term = term.lower()
        start = self.cursor + 1
        for i in range(start, len(self.entries)):
            if term in self.entries[i].lower():
                self.cursor = i
                return True
        for i in range(0, start):
            if term in self.entries[i].lower():
                self.cursor = i
                return True
        return False

# ─── Drawing ──────────────────────────────────────────────────────────────────

def draw_pane(win, pane, active, selected_paths, title=None):
    h, w = win.getmaxyx()
    win.erase()

    # header
    hdr = f" {title or pane.path} "
    hdr = hdr[:w-1]
    attr = COL_ACTIVE() if active else COL_HEADER()
    try:
        win.addstr(0, 0, hdr.ljust(w-1), attr)
    except curses.error:
        pass

    if not pane.entries:
        try:
            win.addstr(1, 1, "(empty)", COL_NORMAL())
        except curses.error:
            pass
        win.noutrefresh()
        return

    visible = h - 2  # rows for entries (1 header + 1 status)
    # adjust scroll offset
    if pane.cursor >= pane.offset + visible:
        pane.offset = pane.cursor - visible + 1
    if pane.cursor < pane.offset:
        pane.offset = pane.cursor

    for i, name in enumerate(pane.entries[pane.offset:pane.offset+visible]):
        idx = i + pane.offset
        abs_path = os.path.join(pane.path, name)
        is_cursor = (idx == pane.cursor and active)
        is_sel    = abs_path in selected_paths

        # display name
        disp = name
        if os.path.isdir(abs_path):
            disp = name + "/"
        disp = disp[:w-3]

        prefix = "▶ " if is_sel else "  "
        line   = (prefix + disp)[:w-1]

        if is_cursor:
            col = COL_CURSOR()
        elif is_sel:
            col = COL_SEL()
        else:
            col = file_color(abs_path, name)

        try:
            win.addstr(i+1, 0, line.ljust(w-1), col)
        except curses.error:
            pass

    # bottom: item count
    info = f" {pane.cursor+1}/{len(pane.entries)}"
    try:
        win.addstr(h-1, 0, info[:w-1], COL_HEADER())
    except curses.error:
        pass

    win.noutrefresh()

def draw_preview(win, path, selected_paths):
    h, w = win.getmaxyx()
    win.erase()

    hdr = f" preview "
    try:
        win.addstr(0, 0, hdr.ljust(w-1), COL_HEADER())
    except curses.error:
        pass

    if not path:
        win.noutrefresh()
        return

    lines = get_preview(path, h-2, w-2)
    for i, line in enumerate(lines[:h-2]):
        try:
            win.addstr(i+1, 1, line[:w-2], COL_NORMAL())
        except curses.error:
            pass

    win.noutrefresh()

def draw_statusbar(stdscr, msg, pane, clipboard_op, clipboard, selected_paths, search_term):
    h, w = stdscr.getmaxyx()
    if msg:
        status = f" {msg}"
    else:
        cp = os.path.basename(pane.current_path() or "")
        info = file_info(pane.current_path()) if pane.current_path() else ""
        sel_info = f" [{len(selected_paths)} sel]" if selected_paths else ""
        cb_info  = f" [clip:{clipboard_op} {len(clipboard)}]" if clipboard else ""
        srch     = f" /{search_term}" if search_term else ""
        status = f" {cp}  {info}{sel_info}{cb_info}{srch}"
    try:
        stdscr.addstr(h-1, 0, status[:w-1].ljust(w-1), COL_STATUS())
    except curses.error:
        pass

def draw_keyhints(stdscr):
    h, w = stdscr.getmaxyx()
    hints = "h/l:nav  j/k:↕  g/G:top/bot  Enter:open  y:yank  p:paste  dd:delete  r/R:rename  m/':mark  /:search  Space:sel  !:shell  q:quit"
    try:
        stdscr.addstr(h-2, 0, hints[:w-1], COL_HEADER())
    except curses.error:
        pass

# ─── Main ─────────────────────────────────────────────────────────────────────

def main(stdscr):
    global BOOKMARKS, CLIPBOARD, CLIPBOARD_OP, SELECTED, SEARCH_TERM

    curses.curs_set(0)
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)
    init_colors()

    start_path = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()

    left_pane   = Pane(os.path.dirname(start_path) if os.path.isfile(start_path) else start_path)
    center_pane = Pane(start_path if os.path.isdir(start_path) else os.path.dirname(start_path))
    active_pane = center_pane   # which pane has focus

    status_msg  = ""
    status_time = 0

    def set_msg(msg):
        nonlocal status_msg, status_time
        status_msg  = msg
        status_time = time.time()

    def sync_left():
        """Keep left pane showing parent of center."""
        parent = os.path.dirname(center_pane.path)
        if left_pane.path != parent:
            left_pane.path = parent
            left_pane.refresh()
        # set left cursor to current dir
        base = os.path.basename(center_pane.path)
        if base in left_pane.entries:
            left_pane.cursor = left_pane.entries.index(base)

    dd_pending = False  # waiting for second 'd'

    while True:
        h, w = stdscr.getmaxyx()
        if h < 5 or w < 20:
            stdscr.clear()
            stdscr.addstr(0, 0, "Terminal too small!")
            stdscr.refresh()
            stdscr.getch()
            continue

        # clear status after 3s
        if status_msg and time.time() - status_time > 3:
            status_msg = ""

        sync_left()

        # layout: left 25%, center 40%, preview 35%
        lw = max(10, w // 4)
        rw = max(10, w * 35 // 100)
        cw = w - lw - rw

        # create windows
        left_win   = curses.newwin(h-2, lw,   0, 0)
        center_win = curses.newwin(h-2, cw,   0, lw)
        right_win  = curses.newwin(h-2, rw,   0, lw+cw)

        # draw
        cur_path = center_pane.current_path()
        draw_pane(left_win,   left_pane,   active_pane is left_pane,   SELECTED,
                  title=os.path.basename(left_pane.path) or left_pane.path)
        draw_pane(center_win, center_pane, active_pane is center_pane, SELECTED,
                  title=center_pane.path)
        draw_preview(right_win, cur_path, SELECTED)
        draw_statusbar(stdscr, status_msg, center_pane, CLIPBOARD_OP, CLIPBOARD, SELECTED, SEARCH_TERM)
        draw_keyhints(stdscr)

        # version tag
        try:
            stdscr.addstr(0, w-len(VERSION)-2, VERSION, COL_HEADER())
        except curses.error:
            pass

        curses.doupdate()
        stdscr.refresh()

        ch = stdscr.getch()

        # ── double-d pending ──────────────────────────────────────────────
        if dd_pending:
            dd_pending = False
            if ch == ord('d'):
                # delete
                targets = list(SELECTED) if SELECTED else ([cur_path] if cur_path else [])
                if targets and confirm_dialog(stdscr, f"Move {len(targets)} item(s) to trash?"):
                    trash = os.path.expanduser("~/.local/share/Trash/files/")
                    os.makedirs(trash, exist_ok=True)
                    for t in targets:
                        try:
                            shutil.move(t, trash)
                        except Exception as e:
                            set_msg(f"Error: {e}")
                    SELECTED.clear()
                    center_pane.refresh()
                    set_msg(f"Moved {len(targets)} item(s) to trash")
                continue
            # else: not dd, ignore

        # ── navigation ───────────────────────────────────────────────────
        if ch in (ord('h'), curses.KEY_LEFT):
            center_pane.go_parent()
            active_pane = center_pane

        elif ch in (ord('l'), curses.KEY_RIGHT, curses.KEY_ENTER, 10, 13):
            if cur_path:
                if os.path.isdir(cur_path):
                    center_pane.enter()
                    SELECTED.clear()
                    active_pane = center_pane
                else:
                    open_file(cur_path)
                    stdscr.refresh()

        elif ch in (ord('j'), curses.KEY_DOWN):
            center_pane.go_down()

        elif ch in (ord('k'), curses.KEY_UP):
            center_pane.go_up()

        elif ch == ord('g'):
            center_pane.go_top()

        elif ch == ord('G'):
            center_pane.go_bottom()

        # ── selection ─────────────────────────────────────────────────────
        elif ch == ord(' '):
            if cur_path:
                if cur_path in SELECTED:
                    SELECTED.discard(cur_path)
                else:
                    SELECTED.add(cur_path)
                center_pane.go_down()

        # ── yank / paste ──────────────────────────────────────────────────
        elif ch == ord('y'):
            targets = list(SELECTED) if SELECTED else ([cur_path] if cur_path else [])
            CLIPBOARD     = targets
            CLIPBOARD_OP  = 'copy'
            set_msg(f"Yanked {len(CLIPBOARD)} item(s)")

        elif ch == ord('p'):
            if not CLIPBOARD:
                set_msg("Clipboard is empty")
            else:
                dest = center_pane.path
                count = 0
                for src in CLIPBOARD:
                    try:
                        base = os.path.basename(src)
                        dst  = os.path.join(dest, base)
                        if CLIPBOARD_OP == 'copy':
                            if os.path.isdir(src):
                                shutil.copytree(src, dst)
                            else:
                                shutil.copy2(src, dst)
                        else:  # cut
                            shutil.move(src, dst)
                        count += 1
                    except Exception as e:
                        set_msg(f"Error: {e}")
                if CLIPBOARD_OP == 'cut':
                    CLIPBOARD = []
                    CLIPBOARD_OP = None
                center_pane.refresh()
                SELECTED.clear()
                set_msg(f"Pasted {count} item(s)")

        # ── cut ───────────────────────────────────────────────────────────
        elif ch == ord('x'):
            targets = list(SELECTED) if SELECTED else ([cur_path] if cur_path else [])
            CLIPBOARD     = targets
            CLIPBOARD_OP  = 'cut'
            set_msg(f"Cut {len(CLIPBOARD)} item(s)")

        # ── delete (dd) ───────────────────────────────────────────────────
        elif ch == ord('d'):
            dd_pending = True
            set_msg("Press d again to delete")

        # ── rename ────────────────────────────────────────────────────────
        elif ch == ord('r'):
            if cur_path:
                new_name = input_dialog(stdscr, "Rename", os.path.basename(cur_path))
                if new_name and new_name != os.path.basename(cur_path):
                    new_path = os.path.join(center_pane.path, new_name)
                    try:
                        os.rename(cur_path, new_path)
                        center_pane.refresh()
                        set_msg(f"Renamed → {new_name}")
                    except Exception as e:
                        set_msg(f"Error: {e}")

        elif ch == ord('R'):
            targets = list(SELECTED) if SELECTED else ([cur_path] if cur_path else [])
            if targets:
                count = bulk_rename(stdscr, targets)
                center_pane.refresh()
                SELECTED.clear()
                set_msg(f"Renamed {count} item(s)")
                stdscr.refresh()

        # ── bookmarks ────────────────────────────────────────────────────
        elif ch == ord('m'):
            key = input_dialog(stdscr, "Bookmark key (1 char)")
            if key:
                BOOKMARKS[key[0]] = center_pane.path
                set_msg(f"Bookmark '{key[0]}' → {center_pane.path}")

        elif ch == ord("'"):
            key = input_dialog(stdscr, "Jump to bookmark")
            if key and key[0] in BOOKMARKS:
                target = BOOKMARKS[key[0]]
                if os.path.isdir(target):
                    center_pane.path = target
                    center_pane.cursor = 0
                    center_pane.offset = 0
                    center_pane.refresh()
                    set_msg(f"Jumped to '{key[0]}'")
            else:
                set_msg("Bookmark not found")

        # ── search ────────────────────────────────────────────────────────
        elif ch == ord('/'):
            SEARCH_TERM = input_dialog(stdscr, "Search")
            if SEARCH_TERM:
                if not center_pane.search(SEARCH_TERM):
                    set_msg("Not found")

        elif ch == ord('n'):
            if SEARCH_TERM:
                if not center_pane.next_search(SEARCH_TERM):
                    set_msg("No more matches")

        # ── shell command ─────────────────────────────────────────────────
        elif ch == ord('!'):
            cmd = input_dialog(stdscr, "Shell command")
            if cmd:
                targets = list(SELECTED) if SELECTED else ([cur_path] if cur_path else [])
                run_shell(stdscr, cmd, targets)
                center_pane.refresh()

        # ── new dir / file ────────────────────────────────────────────────
        elif ch == ord('M'):  # mkdir
            name = input_dialog(stdscr, "New directory name")
            if name:
                try:
                    os.makedirs(os.path.join(center_pane.path, name))
                    center_pane.refresh()
                    set_msg(f"Created dir: {name}")
                except Exception as e:
                    set_msg(f"Error: {e}")

        elif ch == ord('N'):  # new file
            name = input_dialog(stdscr, "New file name")
            if name:
                try:
                    open(os.path.join(center_pane.path, name), 'w').close()
                    center_pane.refresh()
                    set_msg(f"Created: {name}")
                except Exception as e:
                    set_msg(f"Error: {e}")

        # ── open in editor ────────────────────────────────────────────────
        elif ch == ord('e'):
            targets = list(SELECTED) if SELECTED else ([cur_path] if cur_path else [])
            if targets:
                open_editor(targets)
                stdscr.refresh()

        # ── go to home ────────────────────────────────────────────────────
        elif ch == ord('~'):
            center_pane.path   = os.path.expanduser("~")
            center_pane.cursor = 0
            center_pane.offset = 0
            center_pane.refresh()

        # ── go to root ────────────────────────────────────────────────────
        elif ch == ord('\\'):
            center_pane.path   = "/"
            center_pane.cursor = 0
            center_pane.offset = 0
            center_pane.refresh()

        # ── refresh ───────────────────────────────────────────────────────
        elif ch == ord('R') or ch == curses.KEY_F5:
            center_pane.refresh()
            left_pane.refresh()
            set_msg("Refreshed")

        # ── clear selection ───────────────────────────────────────────────
        elif ch == 27:  # ESC
            SELECTED.clear()
            SEARCH_TERM = ""
            dd_pending  = False
            set_msg("Selection cleared")

        # ── quit ──────────────────────────────────────────────────────────
        elif ch in (ord('q'), ord('Q')):
            break

        # ── help ─────────────────────────────────────────────────────────
        elif ch == ord('?'):
            help_lines = [
                "  PetaFiles - Keyboard Shortcuts",
                "  ──────────────────────────────────────────",
                "  h / l      ← Navigate parent / enter dir",
                "  j / k      ↓ ↑ Move up and down",
                "  g / G      Jump to top / bottom",
                "  Enter      Open file / enter dir",
                "  Space      Toggle selection",
                "  y          Yank (copy) file(s)",
                "  x          Cut file(s)",
                "  p          Paste clipboard here",
                "  dd         Delete (move to trash)",
                "  r          Rename current file",
                "  R          Bulk rename (opens editor)",
                "  m          Set bookmark",
                "  '          Jump to bookmark",
                "  /          Fuzzy search",
                "  n          Next search result",
                "  !          Run shell command on file(s)",
                "  e          Edit in $EDITOR",
                "  M          New directory",
                "  N          New file",
                "  ~          Go to home",
                "  \\         Go to root /",
                "  ESC        Clear selection / search",
                "  ?          Show this help",
                "  q          Quit",
                "",
                "  Press any key to close...",
            ]
            stdscr.clear()
            for i, line in enumerate(help_lines):
                try:
                    stdscr.addstr(i, 0, line[:w-1], COL_NORMAL())
                except curses.error:
                    pass
            stdscr.refresh()
            stdscr.getch()

# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
