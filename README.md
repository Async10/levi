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
$ yes The five boxing wizards jump quickly. | head -n 1000 > input.txt
$ python levi.py input.txt
```

## Manual

LEVI supports two modes

- Normal Mode for navigating and editing text and
- Insert Mode for inserting new characters.

### Normal Mode

| Key                                      | Description                        |
|------------------------------------------|------------------------------------|
| <kbd>q</kbd>                             | Quit the editor                    |
| <kbd>h</kbd>                             | Move left one character            |
| <kbd>j</kbd>                             | Move down one line                 |
| <kbd>k</kbd>                             | Move up one line                   |
| <kbd>l</kbd>                             | Move right one character           |
| <kbd>x</kbd>                             | Delete one character at the cursor |

## Insert Mode

| Key                                        | Description                            |
|--------------------------------------------|--------------------------------------- |
| <kbd>ENTER</kbd>                           | Insert new line                        |
| <kbd>Any displayable ASCII character</kbd> | Insert the character                   |
| <kbd>BACKSPACE</kbd>                       | Delete one character before the cursor |
| <kbd>CTRL+SPACE</kbd>                      | Switch to Normal Mode                  |
