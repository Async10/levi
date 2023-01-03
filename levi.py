import os
import signal
import string
import sys
import termios
from dataclasses import dataclass
from enum import Enum, auto
from types import FrameType, TracebackType
from typing import Any, Generator, Iterable, Optional, TextIO


@dataclass
class File:
    text: str
    path: str
    encoding: str = "ascii"


class Editor:
    TAB_WIDTH = 4

    _mode: "EditorMode"
    _text: str
    _file_path: str
    _encoding: str
    _cursor: int
    _lines: list["EditorLine"]
    _line_idx: int

    def __init__(self, file: File) -> None:
        self._mode = EditorMode.NORMAL
        self._text = file.text
        self._file_path = file.path
        self._encoding = file.encoding
        self._cursor = 0
        self._line_idx = 0
        self._lines = []
        self._recompute_lines()

    @property
    def mode(self):
        return self._mode

    @property
    def cursor_column(self) -> int:
        column = 0
        if not self._lines:
            column = self._cursor
        else:
            column = self._cursor - self._lines[self._line_idx].begin
        return column + 1

    @property
    def cursor_line(self) -> int:
        return self._line_idx + 1

    def switch_to_insert_mode(self, append: bool = False):
        if self.mode == EditorMode.INSERT:
            return

        self._mode = EditorMode.INSERT
        if append:
            current_line = self._get_current_line()
            if self._cursor < current_line.end:
                self._cursor += 1

    def switch_to_normal_mode(self):
        if self.mode == EditorMode.NORMAL:
            return

        self._mode = EditorMode.NORMAL
        self._correct_cursor_position()

    def back_delete_character(self) -> None:
        if self._cursor <= 0:
            return

        idx = max(self._cursor - 1, 0)
        self._text = self._text[:idx] + self._text[idx + 1:]
        total_lines = len(self._lines)
        self._recompute_lines()
        if total_lines > len(self._lines):
            self._line_idx = max(self._line_idx - 1, 0)

        self._recompute_lines()
        self._cursor = idx

    def delete_character(self) -> None:
        current_line = self._get_current_line()
        if len(current_line) <= 0:
            return

        idx = self._cursor
        self._text = self._text[:idx] + self._text[idx + 1:]
        total_lines = len(self._lines)
        self._recompute_lines()
        if total_lines > len(self._lines):
            self._line_idx = max(self._line_idx - 1, 0)

        current_line = self._get_current_line()
        self._cursor = min(self._cursor, current_line.end)

    def insert(self, text: str) -> None:
        text = text.replace("\t", " " * Editor.TAB_WIDTH)
        self._text = self._text[:self._cursor] + text + self._text[self._cursor:]
        self._cursor += len(text)
        total_lines = len(self._lines)
        self._recompute_lines()
        if len(self._lines) > total_lines:
            self._line_idx = max(min(self._line_idx + 1, len(self._lines) - 1), 0)
            current_line = self._get_current_line()
            self._cursor = current_line.begin

    def insert_newline_above(self):
        self.move_to_beginning_of_line()
        self.insert("\n")
        self.move_up()

    def insert_newline_below(self):
        current_line = self._get_current_line()
        self._cursor = current_line.end
        self.insert("\n")

    def save(self) -> None:
        with open(self._file_path, "w", encoding=self._encoding) as fobj:
            fobj.write(self._text)

    def get_lines(self) -> Generator[str, None, None]:
        for lv in self._lines:
            yield self._text[lv.begin:lv.end]

    def move_left(self) -> None:
        curr_line = self._get_current_line()
        if self._cursor > curr_line.begin:
            self._cursor -= 1

    def move_down(self) -> None:
        self._go_to_line(self._line_idx + 1)

    def move_up(self) -> None:
        self._go_to_line(self._line_idx - 1)

    def move_right(self) -> None:
        current_line = self._get_current_line()
        nc = self._cursor + 1
        if nc < current_line.end and self._text[nc] != "\n":
            self._cursor = nc

    def move_word_forward(self) -> None:
        self.move_to_end_of_word()
        self._skip_whitespace_forward()
        self._correct_cursor_position()

    def move_word_backward(self) -> None:
        cursor = self._skip_whitespace_backward()
        nxt_cursor = 0
        while cursor > 0:
            if self._text[cursor] in string.whitespace:
                nxt_cursor = cursor + 1
                break

            cursor -= 1

        self._cursor = nxt_cursor
        self._correct_cursor_position()

    def move_to_end_of_word(self) -> None:
        cursor = self._skip_whitespace_forward()
        current_line = self._get_current_line()
        new_cursor = current_line.end - 1
        while cursor < current_line.end - 1:
            if self._text[cursor] in string.whitespace:
                new_cursor = cursor - 1
                break

            cursor += 1

        self._cursor = new_cursor
        self._correct_cursor_position()

    def move_paragraph_forward(self) -> None:
        nxt_cursor = self._cursor + 1
        while nxt_cursor + 1 < len(self._text):
            if self._text[nxt_cursor] == "\n":
                self._line_idx += 1
                if self._text[nxt_cursor-1] == "\n":
                    break

            nxt_cursor += 1

        self._cursor = min(nxt_cursor, len(self._text) - 1)
        self._correct_cursor_position()

    def move_paragraph_backward(self) -> None:
        nxt_cursor = self._cursor - 1
        while nxt_cursor > 0:
            if self._text[nxt_cursor] == "\n":
                self._line_idx -= 1
                if self._text[nxt_cursor+1] == "\n":
                    break

            nxt_cursor -= 1

        self._cursor = max(nxt_cursor, 0)
        self._correct_cursor_position()

    def move_to_beginning_of_line(self) -> None:
        current_line = self._get_current_line()
        self._cursor = current_line.begin

    def move_to_end_of_line(self) -> None:
        current_line = self._get_current_line()
        self._cursor = current_line.end - 1
        self._correct_cursor_position()

    def _recompute_lines(self) -> None:
        if self._lines is None:
            self._lines = []

        self._lines.clear()
        if self._text:
            for idx, ch in enumerate(self._text):
                is_newline = ch == "\n"
                is_last_character = idx + 1 == len(self._text)
                if is_newline or is_last_character:
                    begin = 0 if not self._lines else self._lines[-1].end
                    end = idx + 1
                    self._lines.append(EditorLine(begin, end))

                if is_last_character and is_newline:
                    begin = self._lines[-1].end
                    self._lines.append(EditorLine(begin, begin))
        else:
            self._lines.append(EditorLine(0, 0))

    def _go_to_line(self, line: int) -> None:
        current_line = self._get_current_line()
        offset = max(self._cursor - current_line.begin, 0)
        self._line_idx = max(min(line, len(self._lines) - 1), 0)
        current_line = self._get_current_line()
        self._cursor = max(min(current_line.begin + offset, max(current_line.end - 1, current_line.begin)), 0)
        self._correct_cursor_position()

    def _go_to_coloumn(self, column: int) -> None:
        curr_line = self._get_current_line()
        column = max(min(column, curr_line.end - curr_line.begin), 0)
        self._cursor = curr_line.begin + column

    def _get_current_line(self) -> "EditorLine":
        curr = None if not self._lines else self._lines[self._line_idx]
        begin = 0 if curr is None else curr.begin
        end = self._cursor if not curr else curr.end
        return EditorLine(begin, end)

    def _get_line_text(self, line: "EditorLine") -> str:
        return self._text[line.begin:line.end]

    def _correct_cursor_position(self) -> None:
        current_line = self._get_current_line()
        self._cursor = min(self._cursor, current_line.end - 1)
        if len(current_line) > 1 and self._text[self._cursor] == "\n":
            self._cursor -= 1

        self._cursor = max(self._cursor, current_line.begin)

    def _skip_whitespace_forward(self) -> int:
        idx = self._cursor + 1
        while idx + 1 < len(self._text) and self._text[idx] in string.whitespace:
            if self._text[idx] == "\n":
                self._line_idx += 1

            idx += 1

        self._cursor = idx
        return idx

    def _skip_whitespace_backward(self) -> int:
        idx = self._cursor - 1
        while idx > 0 and self._text[idx] in string.whitespace:
            if self._text[idx] == "\n":
                self._line_idx -= 1

            idx -= 1

        self._cursor = idx
        return idx


class EditorMode(Enum):
    NORMAL = auto()
    INSERT = auto()


@dataclass
class EditorLine:
    begin: int
    end: int

    def __len__(self) -> int:
        return max(self.end - self.begin, 0)


class NoTTYException(Exception):
    pass


@dataclass
class TerminalSize:
    lines: int
    columns: int


class Terminal:
    CTRL_C = "\x03"
    CTRL_SPACE = "\x00"
    BS = "\x7F"
    DEL = "\x1b[3~"

    stdin: TextIO
    stdout: TextIO

    _term_settings: list[Any]

    def __init__(self, stdin: Optional[TextIO] = None, stdout: Optional[TextIO] = None):
        self.stdin = stdin or sys.stdin
        self.stdout = stdout or sys.stdout

        if not self.stdin.isatty() or not self.stdout.isatty():
            raise NoTTYException()

    def get_size(self):
        tmp = os.get_terminal_size(self.stdout.fileno())
        return TerminalSize(tmp.lines, tmp.columns)

    def read_char(self) -> str:
        return sys.stdin.read(1)

    def read_key(self) -> str:
        c1 = self.read_char()

        if c1 == Terminal.CTRL_C:
            raise KeyboardInterrupt

        if c1 != "\x1B":
            return c1

        c2 = self.read_char()
        if c2 not in "\x4F\x5B":
            return c1 + c2

        c3 = self.read_char()
        if c3 not in "\x31\x32\x33\x35\x36":
            return c1 + c2 + c3

        c4 = self.read_char()
        if c4 not in "\x30\x31\x33\x34\x35\x37\x38\x39":
            return c1 + c2 + c3 + c4

        c5 = self.read_char()
        return c1 + c2 + c3 + c4 + c5

    def write(self, text: str) -> None:
        self.stdout.write(text)

    def flush(self) -> None:
        self.stdout.flush()

    def clear(self):
        self.ansi_escape("[H")
        self.ansi_escape("[J")

    def move_cursor(self, line: int, column: int):
        size = self.get_size()
        if line < 0 or line > size.lines:
            raise ValueError(f"line has to be greater than 0 and less than {size.lines + 1}")
        if column < 0 or column > size.columns:
            raise ValueError(f"column has to be greater than 0 and less than {size.columns + 1}")
        self.ansi_escape(f"[{line};{column}H")

    def ansi_escape(self, code: str) -> None:
        self.write(f"\033{code}")

    def __enter__(self) -> "Terminal":
        fd = self.stdin.fileno()
        self._term_settings = termios.tcgetattr(fd)
        settings = termios.tcgetattr(fd)
        settings[3] &= ~(termios.ECHO | termios.ICANON | termios.IGNBRK | termios.BRKINT)
        termios.tcsetattr(fd, termios.TCSAFLUSH, settings)
        return self

    def __exit__(
            self,
            exc_type: Optional[type[BaseException]],
            exc_val: Optional[BaseException],
            exc_tb: Optional[TracebackType]) -> None:
        self.clear()
        termios.tcsetattr(self.stdin.fileno(), termios.TCSADRAIN, self._term_settings)


@dataclass
class ViewData:
    lines: Iterable[str]
    mode: EditorMode
    cursor_line: int
    cursor_column: int


@dataclass
class ViewCursor:
    line: int
    column: int


class View:
    MIN_LINE_NUMBER_WIDTH = 5

    terminal: Terminal

    def __init__(self, terminal: Terminal) -> None:
        self.terminal = terminal

    def get_key(self) -> str:
        return self.terminal.read_key()

    def rerender(self, data: ViewData) -> None:
        self.terminal.clear()
        line_number_width, lines = self._get_view_lines(data)
        lines.append(self._get_mode_line(data))
        assert len(lines) == self.terminal.get_size().lines
        self.terminal.write("".join(lines))
        view_cursor = self._get_cursor(data, line_number_width)
        self.terminal.move_cursor(
            view_cursor.line, view_cursor.column)
        self.terminal.flush()

    def _get_cursor(self, data: ViewData, line_number_width: int) -> ViewCursor:
        assert line_number_width >= View.MIN_LINE_NUMBER_WIDTH
        max_view_lines = self.terminal.get_size().lines - 1
        view_cursor_line = data.cursor_line - max(data.cursor_line - max_view_lines, 0)
        columns = self.terminal.get_size().columns
        view_cursor_column = (line_number_width
                              + data.cursor_column
                              - max(data.cursor_column - columns, 0))
        return ViewCursor(view_cursor_line, view_cursor_column)

    def _get_view_lines(self, data: ViewData) -> tuple[int, list[str]]:
        res: list[str] = []
        max_view_lines = self.terminal.get_size().lines - 1
        begin = max(data.cursor_line - max_view_lines, 0)
        end = begin + max_view_lines
        lines = list(data.lines)
        max_line_number = len(lines)
        line_number_width = max(len(str(max_line_number)) + 2, View.MIN_LINE_NUMBER_WIDTH)
        for line_number, line in enumerate(lines[begin:end], start = begin + 1):
            formatted = self._format_line_number(
                line_number, data.cursor_line, line_number_width)
            res.append(self._get_view_line(line, data.cursor_column, formatted))

        empty_view_lines = max_view_lines - len(res)
        while empty_view_lines:
            res.append("~\n")
            empty_view_lines -= 1

        return (line_number_width, res)

    def _format_line_number(
            self,
            line_number: int,
            cursor_line: int,
            line_number_width: int) -> str:
        padding = 1 if line_number != cursor_line else 2
        return (str(line_number).rjust(line_number_width - padding, " ")
                + " " * padding)

    def _get_view_line(self, line: str, cursor_column: int, line_number: str) -> str:
        columns = self.terminal.get_size().columns - len(line_number)
        begin = max(cursor_column - columns, 0)
        view_line = line_number + line[begin:begin+columns]
        if view_line.endswith("\n"): return view_line
        return view_line + "\n"

    def _get_mode_line(self, data: ViewData) -> str:
        pos = f"Ln {data.cursor_line}, Col {data.cursor_column}"
        mode_string = f"-- {'INSERT' if data.mode == EditorMode.INSERT else 'NORMAL'} --"
        columns = self.terminal.get_size().columns
        return mode_string + pos.rjust(columns - len(mode_string), " ")


class Controller:
    view: View
    editor: Editor

    def __init__(self, view: View, editor: Editor):
        self.editor = editor
        self.view = view

        def handle_resize(signal: int, frame: Optional[FrameType]) -> None:
            self.rerender()

        signal.signal(signal.SIGWINCH, handle_resize)

    def rerender(self):
        self.view.rerender(self._get_view_data())

    def loop(self) -> None:
        while True:
            self.rerender()
            cmd = self.view.get_key()
            if self.editor.mode == EditorMode.NORMAL:
                match cmd:
                    case "h": self.editor.move_left()
                    case "j": self.editor.move_down()
                    case "k": self.editor.move_up()
                    case "l": self.editor.move_right()
                    case "w": self.editor.move_word_forward()
                    case "b": self.editor.move_word_backward()
                    case "e": self.editor.move_to_end_of_word()
                    case "0": self.editor.move_to_beginning_of_line()
                    case "$": self.editor.move_to_end_of_line()
                    case "{": self.editor.move_paragraph_backward()
                    case "}": self.editor.move_paragraph_forward()
                    case "a": self.editor.switch_to_insert_mode(append=True)
                    case "A":
                        self.editor.move_to_end_of_line()
                        self.editor.switch_to_insert_mode(append=True)
                    case "i": self.editor.switch_to_insert_mode()
                    case "I":
                        self.editor.move_to_beginning_of_line()
                        self.editor.switch_to_insert_mode()
                    case "o":
                        self.editor.insert_newline_below()
                        self.editor.switch_to_insert_mode()
                    case "O":
                        self.editor.insert_newline_above()
                        self.editor.switch_to_insert_mode()
                    case "x" | Terminal.DEL: self.editor.delete_character()
                    case "s": self.editor.save()
                    case "q": return
                    case _: pass
            elif self.editor.mode == EditorMode.INSERT:
                match cmd:
                    case Terminal.CTRL_SPACE: self.editor.switch_to_normal_mode()
                    case Terminal.BS: self.editor.back_delete_character()
                    case Terminal.DEL: self.editor.delete_character()
                    case _:
                        if cmd in string.printable:
                            self.editor.insert(cmd)

    def _get_view_data(self) -> ViewData:
        return ViewData(
            self.editor.get_lines(),
            self.editor.mode,
            self.editor.cursor_line,
            self.editor.cursor_column)


def get_file(file_path: str) -> File:
    try:
        with open(file_path, "r") as f:
            return File(f.read(), f.name, f.encoding)
    except FileNotFoundError:
        return File(text="", path=file_path)


def error(msg: str) -> int:
    print(f"ERROR: {msg}", file=sys.stderr)
    return 1

def main(argv: list[str]) -> int:
    if len(argv) < 2:
        rv = error("no input file provided")
        print("Usage: python levi.py INPUT_FILE")
        return rv

    file_path = argv[1]
    try:
        with Terminal() as terminal:
            controller = Controller(
                View(terminal), Editor(get_file(file_path)))
            controller.loop()
    except OSError as e:
        return error(f"could not open file {file_path}: {e}")
    except NoTTYException:
        return error(f"please run in the terminal")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

# TODO: Delete line
# TODO: Delete word
# TODO: Change line
# TODO: Change word
# TODO: Make commands take a count
# TODO: Undo edit / redo edit
# TODO: Search / Replace