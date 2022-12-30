import os
import signal
import sys
import termios
from dataclasses import dataclass
from enum import Enum, auto
from types import FrameType, TracebackType
from typing import Any, Generator, Iterable, Optional, TextIO


class Editor:
    _text: str
    _fpath: str
    _encoding: str
    _cursor: int
    _lines: list["EditorLine"]
    _line_idx: int

    def __init__(self, fobj: TextIO) -> None:
        if not fobj.readable():
            raise ValueError("Provided file is not readable")

        self._text = fobj.read()
        self._fpath = fobj.name
        self._encoding = fobj.encoding
        self._cursor = 0
        self._line_idx = 0
        self._lines = []
        self._recompute_lines()

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

    def delete_charecters(self, n: int = 1) -> None:
        if n < 1:
            raise ValueError("the number of characters to delete can not be less than 1")

        curr_line = self._get_current_line()
        if self._text[curr_line.begin:curr_line.end] in ("\n", ""):
            return

        self._text = (
            self._text[:self._cursor]
            + self._text[min(self._cursor + n, len(self._text)):])
        self._recompute_lines()
        curr_line = self._get_current_line()
        self._cursor = min(self._cursor, curr_line.end - 2)

    def delete_line(self) -> None:
        curr_line = self._get_current_line()
        self._text = self._text[:curr_line.begin] + self._text[curr_line.end + 1:]
        self._line_idx = max(self._line_idx - 1, 0)
        self._recompute_lines()
        curr_line = self._get_current_line()
        self._cursor = curr_line.begin

    def insert(self, text: str) -> None:
        self._text = self._text[:self._cursor] + text + self._text[self._cursor:]
        self._cursor += len(text)
        self._recompute_lines()

    def save(self) -> None:
        with open(self._fpath, "w", encoding=self._encoding) as fobj:
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
        curr_line = self._get_current_line()
        if self._cursor < curr_line.end - 2:
            self._cursor += 1

    def _recompute_lines(self) -> None:
        if self._lines is None:
            self._lines = []

        self._lines.clear()
        for idx, ch in enumerate(self._text):
            if ch == "\n" or idx == len(self._text) - 1:
                begin = 0 if not self._lines else self._lines[-1].end
                end = idx + 1
                self._lines.append(EditorLine(begin, end))

    def _go_to_line(self, line: int) -> None:
        offset = self.cursor_column - 1
        self._line_idx = max(min(line, len(self._lines) - 1), 0)
        curr_line = self._get_current_line()
        self._cursor = max(min(curr_line.begin + offset, curr_line.end - 1), 0)
        try:
            while self._text[self._cursor] == "\n" and self._cursor > 0:
                self._cursor -= 1
        except IndexError:
            pass

    def _go_to_coloumn(self, column: int) -> None:
        curr_line = self._get_current_line()
        column = max(min(column, curr_line.end - curr_line.begin), 0)
        self._cursor = curr_line.begin + column

    def _get_current_line(self) -> "EditorLine":
        curr = None if not self._lines else self._lines[self._line_idx]
        begin = 0 if not curr else curr.begin
        end = self._cursor if not curr else curr.end
        return EditorLine(begin, end)


class EditorMode(Enum):
    NORMAL = auto()
    INSERT = auto()


@dataclass
class EditorLine:
    begin: int
    end: int


class NoTTYException(Exception):
    pass


@dataclass
class TerminalSize:
    lines: int
    columns: int


class Terminal:
    CTRL_C = "\x03"
    CTRL_SPACE = "\x00"

    stdin: TextIO
    stdout: TextIO

    _term_settings: list[Any]

    def __init__(self, stdin: Optional[TextIO] = None, stdout: Optional[TextIO] = None):
        self.stdin = stdin or sys.stdin
        self.stdout = stdout or sys.stdout

        if not self.stdin.isatty() or not self.stdout.isatty():
            raise NoTTYException()

    @property
    def size(self):
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
        self.ansi_escape("[2J")
        self.ansi_escape("[H")

    def move_cursor(self, line: int, column: int):
        if line < 0: raise ValueError("line has to be greater than 0")
        if column < 0: raise ValueError("column has to be greater than 0")
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


class View:
    terminal: Terminal

    def __init__(self, terminal: Terminal):
        self.terminal = terminal

    def get_key(self):
        return self.terminal.read_key()

    def rerender(self, data: ViewData):
        self.terminal.clear()
        terminal_height = self.terminal.size.lines
        lines = (list(data.lines) or ["\n"])[:terminal_height - 1]
        tildas = ["~\n" for _ in range(len(lines) + 1, terminal_height - 1)]
        mode = ["-- INSERT --"] if data.mode == EditorMode.INSERT else []
        self.terminal.write("".join(lines + tildas + mode))
        self.terminal.move_cursor(data.cursor_line, data.cursor_column)
        self.terminal.flush()


class Controller:
    view: View
    editor: Editor

    mode: EditorMode

    def __init__(self, view: View, editor: Editor):
        self.mode = EditorMode.NORMAL
        self.editor = editor
        self.view = view

        def handle_resize(signal: int, frame: Optional[FrameType]) -> None:
            self.rerender()

        signal.signal(signal.SIGWINCH, handle_resize)

    def rerender(self):
        self.view.rerender(self._get_view_data())

    def loop(self) -> None:
        cmd = ""
        while True:
            self.rerender()
            cmd += self.view.get_key()
            if self.mode == EditorMode.NORMAL:
                match tuple(cmd):
                    case ("h",):
                        self.editor.move_left()
                        cmd = ""
                    case ("j",):
                        self.editor.move_down()
                        cmd = ""
                    case ("k",):
                        self.editor.move_up()
                        cmd = ""
                    case ("l",):
                        self.editor.move_right()
                        cmd = ""
                    case ("i",):
                        self.mode = EditorMode.INSERT
                        cmd = ""
                    case ("s",):
                        self.editor.save()
                        cmd = ""
                    case ("x",):
                        self.editor.delete_charecters(n = 1)
                        cmd = ""
                    case ("d",):
                        pass
                    case ("d", x):
                        if x == "d":
                            self.editor.delete_line()

                        cmd = ""
                    case ("q",):
                        return
                    case _:
                        cmd = ""
            elif self.mode == EditorMode.INSERT:
                match cmd:
                    case Terminal.CTRL_SPACE:
                        self.mode = EditorMode.NORMAL
                        cmd = ""
                    case _:
                        self.editor.insert(cmd)
                        cmd = ""

    def _get_view_data(self) -> ViewData:
        return ViewData(
            self.editor.get_lines(),
            self.mode,
            self.editor.cursor_line,
            self.editor.cursor_column)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("ERROR: no input file is provided", file=sys.stderr)
        print("Usage: python levi.py INPUT_FILE")
        return 1

    file_path = argv[1]
    try:
        with open(file_path, "r") as fobj, Terminal() as terminal:
            controller = Controller(View(terminal), Editor(fobj))
            controller.loop()
    except OSError as e:
        print(f"ERROR: could not open file {file_path}: {e}")
        return 1
    except NoTTYException:
        print(f"ERROR: please run in the terminal")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))