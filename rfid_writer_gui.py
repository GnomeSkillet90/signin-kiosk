import os
import csv
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# -------------------------
# CSV column headers (exact)
# -------------------------
COL_ID = "Student ID"
COL_NAME = "Full Name"
COL_GRADE = "Grade"
COL_EMAIL = "Email Address"

# Default paths: script folder + students_master.csv
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CSV = os.path.join(APP_DIR, "students_master.csv")


def clean_tag_text(text: str) -> str:
    """Remove null padding and whitespace from RFID text."""
    return (text or "").replace("\x00", "").strip()


def detect_delimiter(sample: str) -> str:
    """
    Prefer comma (true CSV). Fallback to tab only if it's very clearly TSV.
    """
    comma = sample.count(",")
    tab = sample.count("\t")
    if tab > comma * 2 and tab > 3:
        return "\t"
    return ","


class RFIDWriterApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("RFID Student Tag Writer (RC522)")

        # 800x480 kiosk display: fullscreen is usually best
        self.root.geometry("800x480")
        self.root.attributes("-fullscreen", True)  # press Esc to exit fullscreen

        self.students = []
        self.filtered = []
        self.file_path = None

        self.reader = None
        self.rfid_ready = False
        self.rfid_error = ""
        self._init_rfid()

        self._build_ui()

        # Esc to exit fullscreen
        self.root.bind("<Escape>", lambda e: self.root.attributes("-fullscreen", False))

        # Auto-load default CSV if present
        if os.path.exists(DEFAULT_CSV):
            self.root.after(150, lambda: self.load_file(DEFAULT_CSV))
        else:
            self.log(f"Default CSV not found: {DEFAULT_CSV}")

    def _init_rfid(self):
        try:
            import RPi.GPIO as GPIO
            GPIO.setwarnings(False)
            GPIO.cleanup()

            from mfrc522 import SimpleMFRC522
            self.reader = SimpleMFRC522()
            self.rfid_ready = True
        except Exception as e:
            self.rfid_ready = False
            self.rfid_error = str(e)

    def _build_ui(self):
        # Slightly tighter padding for small screen
        outer = ttk.Frame(self.root, padding=6)
        outer.pack(fill="both", expand=True)

        # ===== Top row: Load + RFID status + Exit =====
        top = ttk.Frame(outer)
        top.pack(fill="x")

        ttk.Button(top, text="Load CSV…", command=lambda: self.load_file(None)).pack(side="left")

        self.file_label = ttk.Label(top, text="students_master.csv (auto)" if os.path.exists(DEFAULT_CSV) else "No file loaded")
        self.file_label.pack(side="left", padx=8)

        self.rfid_label = ttk.Label(top, text=("RFID: Ready ✅" if self.rfid_ready else "RFID: Not ready ❌"))
        self.rfid_label.pack(side="right")

        ttk.Button(top, text="Exit", command=self.root.destroy).pack(side="right", padx=6)

        # ===== Row 2: Actions always visible =====
        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(6, 2))

        self.read_btn = ttk.Button(actions, text="READ TAG", command=self.read_tag)
        self.read_btn.pack(side="left", padx=(0, 8))

        self.write_btn = ttk.Button(actions, text="WRITE SELECTED ID TO TAG", command=self.write_selected)
        self.write_btn.pack(side="left")

        # ===== Row 3: Search =====
        search = ttk.Frame(outer)
        search.pack(fill="x", pady=(6, 2))

        ttk.Label(search, text="Search:").pack(side="left")

        self.search_var = tk.StringVar()
        entry = ttk.Entry(search, textvariable=self.search_var)
        entry.pack(side="left", fill="x", expand=True, padx=6)
        entry.bind("<Return>", lambda e: self.do_search())

        ttk.Button(search, text="Go", command=self.do_search).pack(side="left", padx=(0, 6))
        ttk.Button(search, text="Clear", command=self.clear_search).pack(side="left")

        self.match_label = ttk.Label(search, text="Matches: 0")
        self.match_label.pack(side="right")

        # ===== Row 4: Selected student summary =====
        sel = ttk.LabelFrame(outer, text="Selected Student", padding=6)
        sel.pack(fill="x", pady=(6, 4))

        self.sel_name = ttk.Label(sel, text="Name: (none)")
        self.sel_name.grid(row=0, column=0, sticky="w")

        self.sel_id = ttk.Label(sel, text="ID: (none)")
        self.sel_id.grid(row=0, column=1, sticky="w", padx=10)

        self.sel_grade = ttk.Label(sel, text="Grade: (none)")
        self.sel_grade.grid(row=1, column=0, sticky="w")

        self.sel_email = ttk.Label(sel, text="Email: (none)")
        self.sel_email.grid(row=1, column=1, sticky="w", padx=10)

        for i in range(2):
            sel.columnconfigure(i, weight=1)

        # ===== Row 5: Results table (compact: ID + Name only) =====
        results = ttk.LabelFrame(outer, text="Results (tap to select)", padding=6)
        results.pack(fill="both", expand=True)

        cols = ("id", "name", "grade")
        self.tree = ttk.Treeview(results, columns=cols, show="headings", height=6)

        self.tree.heading("id", text="Student ID")
        self.tree.heading("name", text="Full Name")
        self.tree.heading("grade", text="Grade")

        self.tree.column("id", width=160, anchor="w")
        self.tree.column("name", width=480, anchor="w")
        self.tree.column("grade", width=80, anchor="center")


        vsb = ttk.Scrollbar(results, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        # ===== Row 6: Status (single-line-ish) =====
        status = ttk.LabelFrame(outer, text="Status", padding=6)
        status.pack(fill="both", expand=True, pady=(4, 0))

        self.status_text = tk.Text(
            status,
            height=6,          # <-- taller display area
            wrap="word"
        )
        self.status_text.pack(fill="both", expand=True)


        if not self.rfid_ready:
            self.log(
                "RFID not ready. Fixes: enable SPI (raspi-config), confirm 3.3V, check wiring.\n"
                f"Error: {self.rfid_error}"
            )

    def log(self, msg: str):
        self.status_text.insert("end", msg + "\n")
        self.status_text.see("end")

    def load_file(self, path=None):
        if path is None:
            path = filedialog.askopenfilename(
                title="Select CSV file",
                initialdir=APP_DIR,
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if not path:
                return

        try:
            with open(path, "r", newline="", encoding="utf-8-sig") as f:
                sample = f.read(4096)
                f.seek(0)
                delim = detect_delimiter(sample)

                reader = csv.DictReader(f, delimiter=delim)
                headers = reader.fieldnames or []
                missing = [c for c in (COL_ID, COL_NAME, COL_GRADE, COL_EMAIL) if c not in headers]
                if missing:
                    messagebox.showerror(
                        "Header mismatch",
                        "Missing required headers:\n\n" + "\n".join(missing) +
                        "\n\nExpected headers:\nStudent ID, Full Name, Grade, Email Address"
                    )
                    return

                self.students = []
                for row in reader:
                    sid = (row.get(COL_ID, "") or "").strip()
                    name = (row.get(COL_NAME, "") or "").strip()
                    grade = (row.get(COL_GRADE, "") or "").strip()
                    email = (row.get(COL_EMAIL, "") or "").strip()
                    if sid and name:
                        self.students.append({"id": sid, "name": name, "grade": grade, "email": email})

            self.file_path = path
            self.file_label.config(text=os.path.basename(path))
            self.log(f"Loaded {len(self.students)} students. Delimiter: {'TAB' if delim == chr(9) else 'COMMA'}")
            self.clear_search()

        except Exception as e:
            messagebox.showerror("Load error", str(e))

    def clear_search(self):
        self.search_var.set("")
        self.filtered = list(self.students)
        self.refresh_tree()

    def do_search(self):
        if not self.students:
            messagebox.showinfo("No data", "CSV not loaded yet.")
            return

        q = self.search_var.get().strip().lower()
        if not q:
            self.filtered = list(self.students)
            self.refresh_tree()
            return

        q_digits = q.replace("-", "").isdigit()
        out = []
        for s in self.students:
            sid = s["id"].lower()
            name = s["name"].lower()
            if q_digits:
                if q.replace("-", "") in sid.replace("-", ""):
                    out.append(s)
            else:
                if q in name or q in sid:
                    out.append(s)

        self.filtered = out
        self.refresh_tree()

    def refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for s in self.filtered:
            self.tree.insert("", "end", values=(s["id"], s["name"], s["grade"]))
        self.match_label.config(text=f"Matches: {len(self.filtered)}")

        # Clear selection summary when list changes
        self._set_selected_summary(None)

    def _set_selected_summary(self, student):
        if not student:
            self.sel_name.config(text="Name: (none)")
            self.sel_id.config(text="ID: (none)")
            self.sel_grade.config(text="Grade: (none)")
            self.sel_email.config(text="Email: (none)")
            return

        self.sel_name.config(text=f"Name: {student['name']}")
        self.sel_id.config(text=f"ID: {student['id']}")
        self.sel_grade.config(text=f"Grade: {student['grade']}")
        self.sel_email.config(text=f"Email: {student['email']}")

    def get_selected(self):
        sel = self.tree.selection()
        if not sel:
            return None
        vals = self.tree.item(sel[0], "values")
        if not vals:
            return None
        sid = vals[0]

        # Find full record (grade/email) for summary + writing
        for s in self.filtered:
            if s["id"] == sid:
                return s
        # Fallback: search full list
        for s in self.students:
            if s["id"] == sid:
                return s
        return {
            "id": vals[0],
            "name": vals[1],
            "grade": vals[2],
            "email": ""
        }


    def on_select(self, _event=None):
        student = self.get_selected()
        self._set_selected_summary(student)

    def run_thread(self, fn):
        if not self.rfid_ready or self.reader is None:
            messagebox.showerror("RFID not ready", "RFID reader is not initialized.")
            return
        threading.Thread(target=fn, daemon=True).start()

    def read_tag(self):
        def task():
            import RPi.GPIO as GPIO
            GPIO.setwarnings(False)
            self.log("READ: hold a tag near the reader…")
            try:
                uid, text = self.reader.read()
                cleaned = clean_tag_text(text)
                self.log(f"UID: {uid} | Value: {cleaned if cleaned else '[empty]'}")
            except Exception as e:
                self.log(f"Read error: {e}")
            finally:
                GPIO.cleanup()

        self.run_thread(task)

    def write_selected(self):
        student = self.get_selected()
        if not student:
            messagebox.showinfo("No selection", "Tap a student in the results list first.")
            return

        sid = student["id"].strip()
        if not sid.isdigit():
            if not messagebox.askyesno("Non-numeric ID", f"ID '{sid}' isn't all digits.\nWrite anyway?"):
                return

        def task():
            import RPi.GPIO as GPIO
            GPIO.setwarnings(False)

            self.log(f"WRITE: selected {student['name']} ({sid})")
            self.log("Hold a tag near the reader… (we will read first)")

            try:
                uid, existing = self.reader.read()
                existing_clean = clean_tag_text(existing)
                self.log(f"Tag UID: {uid} | Current: {existing_clean if existing_clean else '[empty]'}")

                if existing_clean and existing_clean != sid:
                    ok = messagebox.askyesno(
                        "Overwrite tag?",
                        f"This tag currently has:\n\n{existing_clean}\n\nOverwrite with:\n\n{sid}\n\n"
                        "Yes = overwrite, No = cancel"
                    )
                    if not ok:
                        self.log("Canceled — tag not overwritten.")
                        return

                self.log("Writing… keep tag steady.")
                self.reader.write(sid)

                self.log("Verify: hold the SAME tag again…")
                uid2, verify = self.reader.read()
                verify_clean = clean_tag_text(verify)

                if verify_clean == sid:
                    self.log(f"✅ Verified OK: {verify_clean} (UID: {uid2})")
                else:
                    self.log(f"⚠️ Verification mismatch: {verify_clean} (UID: {uid2})")

            except Exception as e:
                self.log(f"Write error: {e}")
            finally:
                GPIO.cleanup()

        self.run_thread(task)


if __name__ == "__main__":
    root = tk.Tk()
    ttk.Style().theme_use("clam")
    app = RFIDWriterApp(root)
    root.mainloop()
