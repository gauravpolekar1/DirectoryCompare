import difflib
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


@dataclass
class DiffEntry:
    relative_path: str
    entry_type: str  # "file" | "folder"
    status: str      # "same" | "changed" | "left_only" | "right_only"


class DirectoryCompareApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Directory Compare (Beyond Compare style)")
        self.geometry("1200x760")
        self.minsize(980, 640)

        self.left_dir = tk.StringVar()
        self.right_dir = tk.StringVar()
        self.entries: list[DiffEntry] = []
        self.entry_by_iid: dict[str, DiffEntry] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=10)
        root.pack(fill=tk.BOTH, expand=True)

        path_frame = ttk.LabelFrame(root, text="Folders", padding=10)
        path_frame.pack(fill=tk.X)

        ttk.Label(path_frame, text="Left folder:").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(path_frame, textvariable=self.left_dir).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Button(path_frame, text="Browse...", command=self._browse_left).grid(row=0, column=2, padx=(8, 0), pady=4)

        ttk.Label(path_frame, text="Right folder:").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(path_frame, textvariable=self.right_dir).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Button(path_frame, text="Browse...", command=self._browse_right).grid(row=1, column=2, padx=(8, 0), pady=4)

        path_frame.columnconfigure(1, weight=1)

        action_row = ttk.Frame(root)
        action_row.pack(fill=tk.X, pady=(10, 8))

        ttk.Button(action_row, text="Compare", command=self.compare_directories).pack(side=tk.LEFT)
        ttk.Button(action_row, text="Export Summary", command=self.export_summary).pack(side=tk.LEFT, padx=8)

        legend = ttk.Label(
            action_row,
            text="Legend: same=green, changed=orange, left_only=red, right_only=blue",
        )
        legend.pack(side=tk.RIGHT)

        main_pane = ttk.PanedWindow(root, orient=tk.VERTICAL)
        main_pane.pack(fill=tk.BOTH, expand=True)

        results_frame = ttk.LabelFrame(main_pane, text="Comparison Results", padding=8)
        main_pane.add(results_frame, weight=3)

        columns = ("type", "status")
        self.tree = ttk.Treeview(results_frame, columns=columns, show="tree headings", height=16)
        self.tree.heading("#0", text="Relative Path")
        self.tree.heading("type", text="Type")
        self.tree.heading("status", text="Status")
        self.tree.column("#0", width=800, anchor="w")
        self.tree.column("type", width=90, anchor="center")
        self.tree.column("status", width=110, anchor="center")

        scroll = ttk.Scrollbar(results_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.tag_configure("same", foreground="#157f1f")
        self.tree.tag_configure("changed", foreground="#a35a00")
        self.tree.tag_configure("left_only", foreground="#b10808")
        self.tree.tag_configure("right_only", foreground="#0a4ea8")

        self.tree.bind("<<TreeviewSelect>>", self.show_file_diff)

        diff_frame = ttk.LabelFrame(main_pane, text="File Diff (for selected changed file)", padding=8)
        main_pane.add(diff_frame, weight=2)

        self.diff_text = tk.Text(diff_frame, wrap="none", font=("Consolas", 10))
        self.diff_text.configure(state=tk.DISABLED)
        diff_v = ttk.Scrollbar(diff_frame, orient="vertical", command=self.diff_text.yview)
        diff_h = ttk.Scrollbar(diff_frame, orient="horizontal", command=self.diff_text.xview)
        self.diff_text.configure(yscrollcommand=diff_v.set, xscrollcommand=diff_h.set)

        self.diff_text.grid(row=0, column=0, sticky="nsew")
        diff_v.grid(row=0, column=1, sticky="ns")
        diff_h.grid(row=1, column=0, sticky="ew")

        diff_frame.columnconfigure(0, weight=1)
        diff_frame.rowconfigure(0, weight=1)

    def _browse_left(self) -> None:
        selected = filedialog.askdirectory(title="Select left directory")
        if selected:
            self.left_dir.set(selected)

    def _browse_right(self) -> None:
        selected = filedialog.askdirectory(title="Select right directory")
        if selected:
            self.right_dir.set(selected)

    @staticmethod
    def _collect_entries(root: Path) -> dict[str, str]:
        """Return map: relative path -> 'file'/'folder'."""
        mapping: dict[str, str] = {}
        for dirpath, dirnames, filenames in os.walk(root):
            current = Path(dirpath)
            rel_dir = current.relative_to(root)
            rel_dir_str = "." if str(rel_dir) == "." else rel_dir.as_posix()
            mapping[rel_dir_str] = "folder"
            for name in dirnames:
                rel = (rel_dir / name).as_posix()
                mapping[rel] = "folder"
            for name in filenames:
                rel = (rel_dir / name).as_posix()
                mapping[rel] = "file"
        return mapping

    @staticmethod
    def _file_hash(path: Path) -> str:
        hasher = hashlib.sha256()
        with path.open("rb") as f:
            while chunk := f.read(1024 * 1024):
                hasher.update(chunk)
        return hasher.hexdigest()

    def compare_directories(self) -> None:
        left = Path(self.left_dir.get()).expanduser()
        right = Path(self.right_dir.get()).expanduser()

        if not left.is_dir() or not right.is_dir():
            messagebox.showerror("Invalid input", "Please choose two valid directories.")
            return

        left_map = self._collect_entries(left)
        right_map = self._collect_entries(right)

        all_paths = sorted(set(left_map) | set(right_map))
        result: list[DiffEntry] = []

        for rel_path in all_paths:
            left_type = left_map.get(rel_path)
            right_type = right_map.get(rel_path)

            if left_type and not right_type:
                result.append(DiffEntry(rel_path, left_type, "left_only"))
                continue
            if right_type and not left_type:
                result.append(DiffEntry(rel_path, right_type, "right_only"))
                continue

            assert left_type is not None and right_type is not None

            if left_type != right_type:
                result.append(DiffEntry(rel_path, "file", "changed"))
                continue

            if left_type == "folder":
                result.append(DiffEntry(rel_path, "folder", "same"))
                continue

            left_file = left / rel_path
            right_file = right / rel_path
            try:
                status = "same" if self._file_hash(left_file) == self._file_hash(right_file) else "changed"
            except OSError:
                status = "changed"
            result.append(DiffEntry(rel_path, "file", status))

        self.entries = result
        self._refresh_tree()
        changed_count = sum(1 for x in result if x.status == "changed")
        left_only_count = sum(1 for x in result if x.status == "left_only")
        right_only_count = sum(1 for x in result if x.status == "right_only")
        summary = (
            f"Total entries: {len(result)} | changed: {changed_count} | "
            f"left_only: {left_only_count} | right_only: {right_only_count}"
        )
        self._set_diff_text(summary)

    def _refresh_tree(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.entry_by_iid.clear()

        path_map = {entry.relative_path: entry for entry in self.entries}

        # Ensure every parent folder path is present so the tree can expand/collapse.
        for rel_path in list(path_map):
            if rel_path in (".", ""):
                continue
            parent = Path(rel_path).parent
            while str(parent) not in (".", ""):
                parent_key = parent.as_posix()
                if parent_key not in path_map:
                    path_map[parent_key] = DiffEntry(parent_key, "folder", "same")
                parent = parent.parent

        def sort_key(item: tuple[str, DiffEntry]) -> tuple[int, str]:
            rel_path, _entry = item
            depth = 0 if rel_path == "." else rel_path.count("/") + 1
            return depth, rel_path

        for rel_path, entry in sorted(path_map.items(), key=sort_key):
            parent_path = "" if rel_path in (".", "") else Path(rel_path).parent.as_posix()
            parent_iid = "" if parent_path in (".", "") else parent_path
            iid = rel_path
            label = "." if rel_path in (".", "") else Path(rel_path).name

            self.tree.insert(
                parent_iid,
                "end",
                iid=iid,
                text=label,
                values=(entry.entry_type, entry.status),
                tags=(entry.status,),
                open=(rel_path in (".", "")),
            )
            self.entry_by_iid[iid] = entry

    def show_file_diff(self, _event=None) -> None:
        selected = self.tree.selection()
        if not selected:
            return

        entry = self.entry_by_iid.get(selected[0])
        if entry is None:
            self._set_diff_text("No entry is associated with the selected node.")
            return
        if entry.entry_type != "file" or entry.status != "changed":
            self._set_diff_text("Select a changed file to view line-by-line diff.")
            return

        left_file = Path(self.left_dir.get()) / entry.relative_path
        right_file = Path(self.right_dir.get()) / entry.relative_path

        left_text = self._safe_read_text(left_file)
        right_text = self._safe_read_text(right_file)

        if left_text is None or right_text is None:
            self._set_diff_text(
                "Unable to show textual diff (likely binary file or decode issue)."
            )
            return

        diff = difflib.unified_diff(
            left_text.splitlines(),
            right_text.splitlines(),
            fromfile=f"left/{entry.relative_path}",
            tofile=f"right/{entry.relative_path}",
            lineterm="",
        )
        diff_content = "\n".join(diff) or "Files differ by encoding/metadata or newline style."
        self._set_diff_text(diff_content)

    @staticmethod
    def _safe_read_text(path: Path) -> str | None:
        try:
            raw = path.read_bytes()
        except OSError:
            return None

        if b"\x00" in raw:
            return None

        for encoding in ("utf-8", "utf-16", "cp1252", "latin-1"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return None

    def _set_diff_text(self, content: str) -> None:
        self.diff_text.configure(state=tk.NORMAL)
        self.diff_text.delete("1.0", tk.END)
        self.diff_text.insert(tk.END, content)
        self.diff_text.configure(state=tk.DISABLED)

    def export_summary(self) -> None:
        if not self.entries:
            messagebox.showinfo("Nothing to export", "Run a comparison first.")
            return

        save_path = filedialog.asksaveasfilename(
            title="Save comparison summary",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile="directory_compare_summary.txt",
        )
        if not save_path:
            return

        lines = ["Type\tStatus\tRelative Path"]
        lines.extend(f"{e.entry_type}\t{e.status}\t{e.relative_path}" for e in self.entries)

        try:
            Path(save_path).write_text("\n".join(lines), encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("Save failed", f"Could not save file:\n{exc}")
            return

        messagebox.showinfo("Export complete", f"Summary exported to:\n{save_path}")


if __name__ == "__main__":
    app = DirectoryCompareApp()
    app.mainloop()
