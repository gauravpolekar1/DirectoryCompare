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
    name: str
    parent_path: str | None
    entry_type: str  # "file" | "folder"
    status: str      # "same" | "changed" | "left_only" | "right_only"


class DirectoryCompareApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Directory Compare (Beyond Compare style)")
        self.geometry("1220x780")
        self.minsize(1000, 660)

        self.left_dir = tk.StringVar()
        self.right_dir = tk.StringVar()
        self.entries_by_path: dict[str, DiffEntry] = {}
        self.tree_iid_to_path: dict[str, str] = {}
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
        ttk.Button(action_row, text="Expand All", command=self.expand_all).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(action_row, text="Collapse All", command=self.collapse_all).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(action_row, text="Export Summary", command=self.export_summary).pack(side=tk.LEFT, padx=8)

        legend = ttk.Label(
            action_row,
            text="Legend: same=green, changed=orange, left_only=red, right_only=blue",
        )
        legend.pack(side=tk.RIGHT)

        main_pane = ttk.PanedWindow(root, orient=tk.VERTICAL)
        main_pane.pack(fill=tk.BOTH, expand=True)

        results_frame = ttk.LabelFrame(main_pane, text="Tree Comparison", padding=8)
        main_pane.add(results_frame, weight=3)

        columns = ("type", "status", "relative_path")
        self.tree = ttk.Treeview(results_frame, columns=columns, show="tree headings", height=16)
        self.tree.heading("#0", text="Name")
        self.tree.heading("type", text="Type")
        self.tree.heading("status", text="Status")
        self.tree.heading("relative_path", text="Relative Path")
        self.tree.column("#0", width=380, anchor="w")
        self.tree.column("type", width=100, anchor="center")
        self.tree.column("status", width=110, anchor="center")
        self.tree.column("relative_path", width=620, anchor="w")

        scroll_y = ttk.Scrollbar(results_frame, orient="vertical", command=self.tree.yview)
        scroll_x = ttk.Scrollbar(results_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")

        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)

        self.tree.tag_configure("same", foreground="#157f1f")
        self.tree.tag_configure("changed", foreground="#a35a00")
        self.tree.tag_configure("left_only", foreground="#b10808")
        self.tree.tag_configure("right_only", foreground="#0a4ea8")

        self.tree.bind("<<TreeviewSelect>>", self.show_file_diff)

        diff_frame = ttk.LabelFrame(main_pane, text="File Diff (select a changed file)", padding=8)
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
        """Return map: relative path -> 'file'/'folder' (without '.' root node)."""
        mapping: dict[str, str] = {}
        for dirpath, dirnames, filenames in os.walk(root):
            current = Path(dirpath)
            rel_dir = current.relative_to(root)
            if str(rel_dir) != ".":
                mapping[rel_dir.as_posix()] = "folder"
            for name in dirnames:
                mapping[(rel_dir / name).as_posix()] = "folder"
            for name in filenames:
                mapping[(rel_dir / name).as_posix()] = "file"
        return mapping

    @staticmethod
    def _file_hash(path: Path) -> str:
        hasher = hashlib.sha256()
        with path.open("rb") as f:
            while chunk := f.read(1024 * 1024):
                hasher.update(chunk)
        return hasher.hexdigest()

    @staticmethod
    def _parent_path(rel_path: str) -> str | None:
        parent = Path(rel_path).parent.as_posix()
        return None if parent == "." else parent

    def compare_directories(self) -> None:
        left = Path(self.left_dir.get()).expanduser()
        right = Path(self.right_dir.get()).expanduser()

        if not left.is_dir() or not right.is_dir():
            messagebox.showerror("Invalid input", "Please choose two valid directories.")
            return

        left_map = self._collect_entries(left)
        right_map = self._collect_entries(right)

        all_paths = sorted(set(left_map) | set(right_map), key=lambda p: (p.count("/"), p.lower()))
        built: dict[str, DiffEntry] = {}

        for rel_path in all_paths:
            left_type = left_map.get(rel_path)
            right_type = right_map.get(rel_path)

            if left_type and not right_type:
                entry_type = left_type
                status = "left_only"
            elif right_type and not left_type:
                entry_type = right_type
                status = "right_only"
            else:
                assert left_type is not None and right_type is not None
                if left_type != right_type:
                    entry_type = "file"
                    status = "changed"
                elif left_type == "folder":
                    entry_type = "folder"
                    status = "same"
                else:
                    entry_type = "file"
                    try:
                        status = "same" if self._file_hash(left / rel_path) == self._file_hash(right / rel_path) else "changed"
                    except OSError:
                        status = "changed"

            built[rel_path] = DiffEntry(
                relative_path=rel_path,
                name=Path(rel_path).name,
                parent_path=self._parent_path(rel_path),
                entry_type=entry_type,
                status=status,
            )

        self.entries_by_path = built
        self._propagate_folder_statuses()
        self._refresh_tree()

        changed_count = sum(1 for x in self.entries_by_path.values() if x.status == "changed")
        left_only_count = sum(1 for x in self.entries_by_path.values() if x.status == "left_only")
        right_only_count = sum(1 for x in self.entries_by_path.values() if x.status == "right_only")
        self._set_diff_text(
            f"Total entries: {len(self.entries_by_path)} | changed: {changed_count} | "
            f"left_only: {left_only_count} | right_only: {right_only_count}"
        )

    def _propagate_folder_statuses(self) -> None:
        children: dict[str | None, list[str]] = {}
        for path, entry in self.entries_by_path.items():
            children.setdefault(entry.parent_path, []).append(path)

        folder_paths = sorted(
            (p for p, e in self.entries_by_path.items() if e.entry_type == "folder"),
            key=lambda p: p.count("/"),
            reverse=True,
        )

        for folder_path in folder_paths:
            folder = self.entries_by_path[folder_path]
            child_statuses = {self.entries_by_path[ch].status for ch in children.get(folder_path, [])}
            if not child_statuses:
                continue
            if "left_only" in child_statuses and "right_only" in child_statuses:
                folder.status = "changed"
            elif "left_only" in child_statuses:
                folder.status = "left_only" if child_statuses <= {"left_only"} else "changed"
            elif "right_only" in child_statuses:
                folder.status = "right_only" if child_statuses <= {"right_only"} else "changed"
            elif "changed" in child_statuses:
                folder.status = "changed"
            else:
                folder.status = "same"

    def _refresh_tree(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.tree_iid_to_path.clear()

        sorted_entries = sorted(self.entries_by_path.values(), key=lambda e: (e.relative_path.count("/"), e.relative_path.lower()))
        iid_for_path: dict[str, str] = {}

        for entry in sorted_entries:
            parent_iid = iid_for_path.get(entry.parent_path or "")
            iid = entry.relative_path
            iid_for_path[entry.relative_path] = iid
            self.tree_iid_to_path[iid] = entry.relative_path
            self.tree.insert(
                parent_iid if parent_iid else "",
                "end",
                iid=iid,
                text=entry.name,
                values=(entry.entry_type, entry.status, entry.relative_path),
                tags=(entry.status,),
                open=False,
            )

    def expand_all(self) -> None:
        for iid in self.tree.get_children(""):
            self._set_open_recursive(iid, True)

    def collapse_all(self) -> None:
        for iid in self.tree.get_children(""):
            self._set_open_recursive(iid, False)

    def _set_open_recursive(self, iid: str, open_state: bool) -> None:
        self.tree.item(iid, open=open_state)
        for child in self.tree.get_children(iid):
            self._set_open_recursive(child, open_state)

    def show_file_diff(self, _event=None) -> None:
        selected = self.tree.selection()
        if not selected:
            return

        rel_path = self.tree_iid_to_path.get(selected[0])
        if not rel_path:
            return
        entry = self.entries_by_path[rel_path]

        if entry.entry_type != "file" or entry.status != "changed":
            self._set_diff_text("Select a changed file to view line-by-line diff.")
            return

        left_file = Path(self.left_dir.get()) / entry.relative_path
        right_file = Path(self.right_dir.get()) / entry.relative_path

        left_text = self._safe_read_text(left_file)
        right_text = self._safe_read_text(right_file)

        if left_text is None or right_text is None:
            self._set_diff_text("Unable to show textual diff (likely binary file or decode issue).")
            return

        diff = difflib.unified_diff(
            left_text.splitlines(),
            right_text.splitlines(),
            fromfile=f"left/{entry.relative_path}",
            tofile=f"right/{entry.relative_path}",
            lineterm="",
        )
        self._set_diff_text("\n".join(diff) or "Files differ by encoding/metadata or newline style.")

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
        if not self.entries_by_path:
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

        rows = ["Type\tStatus\tRelative Path"]
        for rel_path in sorted(self.entries_by_path):
            e = self.entries_by_path[rel_path]
            rows.append(f"{e.entry_type}\t{e.status}\t{e.relative_path}")

        try:
            Path(save_path).write_text("\n".join(rows), encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("Save failed", f"Could not save file:\n{exc}")
            return

        messagebox.showinfo("Export complete", f"Summary exported to:\n{save_path}")


if __name__ == "__main__":
    app = DirectoryCompareApp()
    app.mainloop()
