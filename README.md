# Directory Compare (Windows local app)

A lightweight **Beyond Compare-like** local tool for Windows that lets you:

- Select two folders.
- Compare all files and subfolders in a hierarchical tree view.
- See color-coded status for each node (`same`, `changed`, `left_only`, `right_only`).
- Click a changed text file to view a unified line-by-line diff.
- Export the full comparison summary to a `.txt` file.

## Technology

- Python 3.10+
- Tkinter GUI (bundled with standard Python on Windows)

## Run locally on Windows

1. Install Python 3.10+ from python.org.
2. Open Command Prompt or PowerShell in this project folder.
3. Run:

```powershell
python app.py
```

## Build as a standalone `.exe` (optional)

```powershell
pip install pyinstaller
pyinstaller --noconsole --onefile --name DirectoryCompare app.py
```

The generated executable will be in `dist\DirectoryCompare.exe`.

## Notes

- Binary files are detected and marked as changed/same by hash, but textual side-by-side diff preview is only shown for decodable text files.
- Very large folders can take time because files are hashed to detect changes reliably.
