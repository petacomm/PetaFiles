# PetaFiles

> The file manager your terminal deserved.

PetaFiles is a three-pane terminal file manager built for Linux power users. Vim-style navigation, instant preview, bulk operations and network filesystem support — starts in 0.04 seconds.

---

## Features

- **Three-pane layout** — parent · current · preview in one view
- **Vim-style navigation** — hjkl, g/G, /, n, N
- **File preview** — text, images, PDF, archives, binary hex dump
- **Bulk operations** — select with Space, operate on all selected
- **Bookmarks** — `m` to mark, `'` to jump
- **NFS, SMB, SSHFS** — browse network filesystems seamlessly
- **Shell integration** — run any command on selected files with `!`
- **Bulk rename** — edit all names in your `$EDITOR` at once
- **Zero dependencies** — only Python 3 standard library

---

## Installation

### Ubuntu / Debian (via Kotech Petacomm repo)

```bash
# Add GPG key
curl -fsSL https://repo.kotechsoft.com/kotech-petacomm.gpg | sudo gpg --dearmor -o /etc/apt/keyrings/kotech.gpg

# Add repository
echo "deb [signed-by=/etc/apt/keyrings/kotech.gpg] https://repo.kotechsoft.com stable main" | sudo tee /etc/apt/sources.list.d/kotech.list

# Install
sudo apt update && sudo apt install petafiles
```

### Quick install script

```bash
curl -fsSL https://repo.kotechsoft.com/petafiles/pfinstall.sh | sudo bash
```

The script will:
- Add the Kotech Petacomm APT repository if not already present
- Check if `micro` is in the repo, add it if not
- Ask which editor you want as default (nano or micro)
- Install PetaFiles and set up `~/.config/petafiles/`

### Manual / Portable

```bash
curl -fsSL https://repo.kotechsoft.com/petafiles/petafiles.py -o petafiles.py
chmod +x petafiles.py
python3 petafiles.py
```

---

## Usage

```bash
petafiles              # start in current directory
petafiles ~/projects   # start in a specific directory
```

---

## Keyboard Shortcuts

| Key       | Action        | Description                              |
|-----------|---------------|------------------------------------------|
| `h / l`   | ← → panes     | Move between parent / current / preview  |
| `j / k`   | ↑ ↓ list      | Move up and down in current pane         |
| `g / G`   | top / bottom  | Jump to first or last item               |
| `Enter`   | open          | Open file with default handler           |
| `Space`   | select        | Toggle selection on current item         |
| `y`       | yank          | Copy selected file(s) to clipboard       |
| `x`       | cut           | Cut selected file(s)                     |
| `p`       | paste         | Paste to current directory               |
| `dd`      | delete        | Move selected file(s) to trash           |
| `r`       | rename        | Rename current file                      |
| `R`       | bulk rename   | Edit all names in `$EDITOR`              |
| `m`       | bookmark      | Bookmark current directory               |
| `'`       | jump          | Jump to a bookmark                       |
| `/`       | search        | Fuzzy search in current directory        |
| `n`       | next          | Next search result                       |
| `!`       | shell         | Run a shell command on selected files    |
| `e`       | edit          | Open file(s) in `$EDITOR`               |
| `M`       | mkdir         | Create a new directory                   |
| `N`       | new file      | Create a new file                        |
| `~`       | home          | Go to home directory                     |
| `\`       | root          | Go to root `/`                           |
| `ESC`     | clear         | Clear selection and search               |
| `?`       | help          | Show keyboard shortcuts                  |
| `q`       | quit          | Quit PetaFiles                           |

---

## vs Ranger

|               | PetaFiles | Ranger   |
|---------------|-----------|----------|
| Start time    | 0.04s     | 0.72s    |
| Memory usage  | 3 MB      | 28 MB    |
| Dependencies  | 0         | Python 3 |
| Network FS    | Built-in  | Manual   |

---

## Requirements

- Python 3.6+
- Linux (tested on Ubuntu, Debian, Arch, RHEL)
- A terminal with 256-color support

---

## Configuration

Config directory: `~/.config/petafiles/`

Custom key bindings can be placed in `~/.config/petafiles/keys` (coming in v1.3).

---

## License

GPL-3.0 — see [LICENSE](LICENSE)

---

## Links

- Website: [kotechsoft.com/petafiles](https://kotechsoft.com/petafiles.html)
- Repository: [repo.kotechsoft.com](https://repo.kotechsoft.com)
- Maintainer: [Petacomm](https://petacomm.io)
- Discord: [discord.gg/jxMMJmGwsh](https://discord.gg/jxMMJmGwsh)
