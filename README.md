# LEVI

LEVI or Lesser VI is a VI-like text editor for the terminal that I develop for
fun. I started the project to get a better understanding of how text editors
work.  My goal is to bring LEVI to a point where users will be able to
comfortably navigate and edit relatively large text files in it.

## Requirements

1. Python 3.10 or newer
2. A POSIX-compliant terminal

## Start editing

```console
$ python levi.py input.txt
```

## Manual

LEVI supports two modes:

- Normal mode for navigating and editing text and
- insert Mode for inserting new characters.

### Normal Mode

| Key                                      | Description                             |
|------------------------------------------|-----------------------------------------|
| <kbd>q</kbd>                             | Quit the editor                         |
| <kbd>s</kbd>                             | Save file                               |
| <kbd>h</kbd>                             | Move left one character                 |
| <kbd>j</kbd>                             | Move down one line                      |
| <kbd>k</kbd>                             | Move up one line                        |
| <kbd>l</kbd>                             | Move right one character                |
| <kbd>w</kbd>                             | Move word forward                       |
| <kbd>b</kbd>                             | Move word backward                      |
| <kbd>e</kbd>                             | Move to the end of the word             |
| <kbd>0</kbd>                             | Move to the beginning of the line       |
| <kbd>$</kbd>                             | Move to the end of the line             |
| <kbd>{</kbd>                             | Move paragraph backward                 |
| <kbd>}</kbd>                             | Move paragraph forward                  |
| <kbd>x</kbd>                             | Delete character under the cursor       |
| <kbd>DELETE</kdb>                        | Delete character under the cursor       |
| <kbd>i</kbd>                             | Insert text before the cursor           |
| <kbd>I</kbd>                             | Insert text at the begining of the line |
| <kbd>a</kbd>                             | Append text after the cursor            |
| <kbd>A</kbd>                             | Append text ath the end of the line     |

## Insert Mode

| Key                                        | Description                            |
|--------------------------------------------|----------------------------------------|
| <kbd>ENTER</kbd>                           | Insert new line                        |
| <kbd>Any displayable ASCII character</kbd> | Insert the character                   |
| <kbd>BACKSPACE</kbd>                       | Delete one character before the cursor |
| <kbd>DELETE</kdb>                          | Delete one character at the cursor     |
| <kbd>CTRL+SPACE</kbd>                      | Switch to normal mode                  |
