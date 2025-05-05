import tkinter as tk
from tkinter import ttk, messagebox
import duckdb
import os
import sys
import glob
import json
from datetime import datetime
import pandas as pd


BASE_DIR = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__))
COASTAL_DIR = os.path.join(BASE_DIR, "Coastal")
RIVERINE_DIR = os.path.join(BASE_DIR, "Riverine")
CONFIG_PATH = os.path.join(BASE_DIR, "dropdown_config.json")
conn = duckdb.connect()

class SearchApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Flood Data Search Tool")
        self.search_folder = tk.StringVar(value="Coastal")
        self.dropdown_widgets = {}
        self.search_results = None

        self.latitude = tk.Entry(root)
        self.longitude = tk.Entry(root)

        self.tree = ttk.Treeview(root, show="headings")
        self.tree_scroll_x = ttk.Scrollbar(root, orient="horizontal", command=self.tree.xview)
        self.tree_scroll_y = ttk.Scrollbar(root, orient="vertical", command=self.tree.yview)
        self.tree.configure(xscrollcommand=self.tree_scroll_x.set, yscrollcommand=self.tree_scroll_y.set)

        self._create_widgets()
        self._generate_dropdown_config()
        self._populate_dropdowns()

    def _create_widgets(self):
        frame = tk.Frame(self.root)
        frame.grid(row=0, column=0, sticky="w", padx=10, pady=10)

        tk.Radiobutton(frame, text="Coastal", variable=self.search_folder, value="Coastal",
                       command=self._populate_dropdowns).grid(row=0, column=0, sticky="w")
        tk.Radiobutton(frame, text="Riverine", variable=self.search_folder, value="Riverine",
                       command=self._populate_dropdowns).grid(row=0, column=1, sticky="w")

        self.entries_frame = tk.Frame(self.root)
        self.entries_frame.grid(row=1, column=0, sticky="w", padx=10)

        tk.Label(self.entries_frame, text="Latitude").grid(row=0, column=0, sticky="w")
        self.latitude.grid(row=0, column=1, sticky="w")
        tk.Label(self.entries_frame, text="Longitude").grid(row=1, column=0, sticky="w")
        self.longitude.grid(row=1, column=1, sticky="w")

        self.dropdown_frame = tk.Frame(self.root)
        self.dropdown_frame.grid(row=2, column=0, sticky="w", padx=10)

        tk.Button(self.root, text="Search", command=self.search).grid(row=3, column=0, pady=10, padx=10, sticky="w")
        tk.Button(self.root, text="Export to CSV", command=self.export_to_csv).grid(row=3, column=0, pady=10, padx=120, sticky="w")

        self.tree.grid(row=4, column=0, padx=10, pady=10, sticky="nsew")
        self.tree_scroll_x.grid(row=5, column=0, sticky="ew", padx=10)
        self.tree_scroll_y.grid(row=4, column=1, sticky="ns")

        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(4, weight=1)

    def _generate_dropdown_config(self):
        dropdown_data = {"Coastal": {}, "Riverine": {}}

        for folder_key, folder, fields in [
            ("Coastal", COASTAL_DIR, ["ClimateScenario", "Subsidence", "Year", "ReturnPeriod", "SeaLevelRiseScenario"]),
            ("Riverine", RIVERINE_DIR, ["ClimateScenario", "GlobalCirculationModel", "Year", "ReturnPeriod"])
        ]:
            values_dict = {field: set() for field in fields}
            for file in glob.glob(os.path.join(folder, "*.csv")):
                base = os.path.basename(file)
                parts = base.replace(".csv", "").split("_")
                if folder_key == "Coastal" and len(parts) >= 6:
                    values_dict["ClimateScenario"].add(parts[1])
                    values_dict["Subsidence"].add(parts[2])
                    values_dict["Year"].add(parts[3])
                    values_dict["ReturnPeriod"].add(parts[4])
                    values_dict["SeaLevelRiseScenario"].add("_".join(parts[5:]))
                elif folder_key == "Riverine" and len(parts) >= 5:
                    values_dict["ClimateScenario"].add(parts[1])
                    values_dict["GlobalCirculationModel"].add(parts[2])
                    values_dict["Year"].add(parts[3])
                    values_dict["ReturnPeriod"].add(parts[4])
            dropdown_data[folder_key] = {k: sorted(v) for k, v in values_dict.items()}

        with open(CONFIG_PATH, "w") as f:
            json.dump(dropdown_data, f, indent=2)

    def _populate_dropdowns(self):
        for widget in self.dropdown_frame.winfo_children():
            widget.destroy()
        self.dropdown_widgets.clear()

        folder_key = self.search_folder.get()
        fields = list(json.load(open(CONFIG_PATH)).get(folder_key, {}).keys())

        for i, field in enumerate(fields):
            label = tk.Label(self.dropdown_frame, text=field)
            label.grid(row=i, column=0, sticky="w")
            cb = ttk.Combobox(self.dropdown_frame, state="readonly")
            cb.grid(row=i, column=1, sticky="w")
            self.dropdown_widgets[field] = cb

        with open(CONFIG_PATH, "r") as f:
            dropdown_data = json.load(f)
        for field in fields:
            values = dropdown_data.get(folder_key, {}).get(field, [])
            self.dropdown_widgets[field]['values'] = ["All"] + values
            self.dropdown_widgets[field].set("All")

    def _build_target_file(self, values):
        if self.search_folder.get() == "Coastal":
            required = ["ClimateScenario", "Subsidence", "Year", "ReturnPeriod", "SeaLevelRiseScenario"]
            if all(values.get(k) != "All" for k in required):
                return f"inuncoast_{values['ClimateScenario']}_{values['Subsidence']}_{values['Year']}" \
                       f"_{values['ReturnPeriod']}_{values['SeaLevelRiseScenario']}.csv"
        else:
            required = ["ClimateScenario", "GlobalCirculationModel", "Year", "ReturnPeriod"]
            if all(values.get(k) != "All" for k in required):
                return f"inunriver_{values['ClimateScenario']}_{values['GlobalCirculationModel']}" \
                       f"_{values['Year']}_{values['ReturnPeriod']}.csv"
        return None

    def search(self):
        if not self.latitude.get() or not self.longitude.get():
            messagebox.showerror("Input Error", "Latitude and Longitude are required fields.")
            return

        for row in self.tree.get_children():
            self.tree.delete(row)
        self.tree["columns"] = ()

        folder = COASTAL_DIR if self.search_folder.get() == "Coastal" else RIVERINE_DIR
        filters = {k: w.get() for k, w in self.dropdown_widgets.items()}
        filename = self._build_target_file(filters)
        all_files = glob.glob(os.path.join(folder, "*.csv"))

        filtered_files = []
        if filename and os.path.exists(os.path.join(folder, filename)):
            filtered_files = [os.path.join(folder, filename)]
        else:
            for f in all_files:
                basename = os.path.basename(f)
                if any(v != "All" and v not in basename for k, v in filters.items()):
                    continue
                filtered_files.append(f)

        if not filtered_files:
            filtered_files = all_files

        query = f"SELECT * FROM read_csv_auto({filtered_files}) WHERE 1=1"
        query += f" AND Latitude = {float(self.latitude.get())}"
        query += f" AND Longitude = {float(self.longitude.get())}"
        for k, v in filters.items():
            if v != "All":
                query += f" AND {k} = '{v}'"

        try:
            self.search_results = conn.execute(query).fetchdf()
            if not self.search_results.empty:
                self.tree["columns"] = list(self.search_results.columns)
                for col in self.search_results.columns:
                    self.tree.heading(col, text=col)
                    self.tree.column(col, anchor="w", width=100)
                for _, row in self.search_results.iterrows():
                    self.tree.insert("", "end", values=list(row))
            else:
                messagebox.showinfo("No Results", "No matching records found.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def export_to_csv(self):
        if self.search_results is not None and not self.search_results.empty:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"search_results_{timestamp}.csv"
            self.search_results.to_csv(filename, index=False)
            messagebox.showinfo("Export Successful", f"Results exported to {filename}")
        else:
            messagebox.showwarning("No Data", "No search results to export.")

if __name__ == "__main__":
    root = tk.Tk()
    app = SearchApp(root)
    root.mainloop()
