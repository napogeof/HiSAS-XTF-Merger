import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import os

from backend import sort_files_by_timestamp, merge_xtf_files, find_max_packet_size

class HiSASMergerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("HiSAS Offline XTF Line Merger")
        self.root.geometry("600x500")
        
        self.input_files = []
        self.output_file = ""
        
        # Setup Tabs
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.merge_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.merge_tab, text='Merge XTF Files')
        
        self.methodology_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.methodology_tab, text='Methodology')
        
        self.readme_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.readme_tab, text='Readme')
        
        self.setup_merge_tab()
        self.setup_methodology_tab()
        self.setup_readme_tab()

    def setup_merge_tab(self):
        # Input selection
        btn_select_files = ttk.Button(self.merge_tab, text="Select XTF Files", command=self.select_files)
        btn_select_files.grid(row=0, column=0, padx=5, pady=10, sticky='w')
        
        self.lbl_file_count = ttk.Label(self.merge_tab, text="0 files selected.")
        self.lbl_file_count.grid(row=0, column=1, padx=5, pady=10, sticky='w')
        
        # File listbox
        self.listbox = tk.Listbox(self.merge_tab, width=80, height=10)
        self.listbox.grid(row=1, column=0, columnspan=3, padx=5, pady=5)
        
        # Output selection
        btn_select_out = ttk.Button(self.merge_tab, text="Select Output File", command=self.select_output)
        btn_select_out.grid(row=2, column=0, padx=5, pady=10, sticky='w')
        
        self.lbl_output = ttk.Label(self.merge_tab, text="No output file selected.", wraplength=400)
        self.lbl_output.grid(row=2, column=1, columnspan=2, padx=5, pady=10, sticky='w')
        
        # Normalization Option
        self.var_normalize = tk.BooleanVar(value=True)
        self.chk_normalize = ttk.Checkbutton(self.merge_tab, text="Normalize Packet Sizes (Fix SonarWiz Smearing)", variable=self.var_normalize)
        self.chk_normalize.grid(row=3, column=0, columnspan=3, pady=(10, 0), sticky='w', padx=10)
        
        # Merge Button
        self.btn_merge = ttk.Button(self.merge_tab, text="MERGE FILES", command=self.start_merge)
        self.btn_merge.grid(row=4, column=0, columnspan=3, pady=20)
        
        # Progress Bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.merge_tab, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=5, column=0, columnspan=3, sticky='ew', padx=5, pady=5)
        
        self.lbl_status = ttk.Label(self.merge_tab, text="Ready.")
        self.lbl_status.grid(row=6, column=0, columnspan=3, sticky='w', padx=5)

    def setup_methodology_tab(self):
        procedure_text = """HiSAS Offline XTF Line Merger

This application combines multiple short HiSAS XTF files generated during AUV surveys into a single continuous XTF file suitable for direct import into SonarWiz.

The tool operates directly on the raw XTF data and does NOT rasterize, resample, interpolate, or otherwise alter the acoustic samples.

METHODOLOGY OVERVIEW

1. RAW XTF MERGING
HiSAS AUV surveys may generate hundreds or thousands of short XTF files, particularly when the vehicle changes heading or the acquisition system segments the data.
Instead of importing and aggregating these files individually in SonarWiz, this application combines their XTF records into a single continuous file.
The acoustic payload of each retained ping is preserved exactly as it appears in the source XTF.
No sample-size normalization or resampling is performed.
Different pings may therefore retain their original sample counts.

2. TEMPORAL OVERLAP HANDLING
Consecutive XTF files may contain overlapping acquisition periods. For example, a subsequent file may begin several seconds before the previous file ends.
When these files are subsequently aggregated in SonarWiz, overlapping coverage can result in duplicate rendering and artifacts such as smearing in the resulting mosaic.
To avoid this, the application enforces chronological continuity between files.
Files are processed in chronological order based on their internal XTF timestamps. Once the latest retained ping from the preceding file has been established, any ping in the subsequent file with a timestamp equal to or earlier than that timestamp is discarded.
This effectively removes the temporally overlapping portion at file boundaries while preserving the first occurrence of each acquisition period.

3. XTF SEQUENCE CONTINUITY
The application regenerates the relevant PingNumber and EventNumber sequences across the merged output so that they remain continuous throughout the resulting XTF.
This avoids discontinuities that may otherwise cause validation or "Time Jump" errors when the merged file is imported into SonarWiz.

4. VARIABLE PACKET SIZE NORMALIZATION
HiSAS systems often dynamically change the acoustic packet payload sizes during a survey (e.g., from 5844 bytes to 5888 bytes per ping).
When these differing files are concatenated, SonarWiz's XTF parser loses byte-synchronization and severely corrupts the mosaic (the "smearing" bug).
If the "Normalize Packet Sizes" option is enabled, the tool scans all files to find the maximum packet size, and then seamlessly zero-pads all smaller packets in the merged output. This tricks SonarWiz into seeing a uniform file without altering any real acoustic data.

5. NAVIGATION AND ACOUSTIC DATA
The application does not perform spatial interpolation, image mosaicking, pixel blending, or acoustic resampling.
For retained pings, the original acquisition information is preserved, including:
* Acoustic samples
* Sample count
* Timestamp
* Navigation
* Heading
* Attitude and other available ping metadata

The purpose of the application is to reorganize the original acquisition into a continuous XTF, not to generate a processed sonar image.
"""
        txt = tk.Text(self.methodology_tab, wrap='word', padx=10, pady=10)
        txt.insert('1.0', procedure_text)
        txt.config(state='disabled')
        txt.pack(fill='both', expand=True)

    def setup_readme_tab(self):
        readme_text = """INSTRUCTIONS

1. Select XTF files
Go to the 'Merge XTF Files' tab.
Click 'Select XTF Files' and select all XTF files belonging to a single survey line.
The application will automatically sort the files chronologically using their internal timestamps.

2. Select output
Click 'Select Output File' and specify the name and location of the merged XTF.

3. Merge
Click 'MERGE FILES'.
The application will:
1. Sort the input files chronologically.
2. Read the XTF records sequentially.
3. Preserve the original acoustic payloads.
4. Remove temporally overlapping pings at file boundaries.
5. Rebuild continuous ping/event numbering.
6. Write the resulting continuous XTF.

4. Processing report
A processing report will be generated next to the output XTF.
The report should be retained with the processed data as a record of the merge operation.

IMPORTANT

This application does NOT modify the original XTF files.
Input files remain unchanged.
The merged XTF should be considered a derived processing product and should be retained alongside the original acquisition files.

Developed by Daniel (Napo) Arráiz @nap0x
Source Code & Updates: https://github.com/napogeof/HiSAS-XTF-Merger
"""
        txt = tk.Text(self.readme_tab, wrap='word', padx=10, pady=10)
        txt.insert('1.0', readme_text)
        txt.config(state='disabled')
        txt.pack(fill='both', expand=True)

    def select_files(self):
        files = filedialog.askopenfilenames(title="Select XTF Files", filetypes=(("XTF Files", "*.xtf"), ("All Files", "*.*")))
        if files:
            self.lbl_status.config(text="Sorting files by timestamp... Please wait.")
            self.root.update_idletasks()
            
            # Sort files automatically
            try:
                self.input_files = sort_files_by_timestamp(list(files))
                self.listbox.delete(0, tk.END)
                for f in self.input_files:
                    self.listbox.insert(tk.END, os.path.basename(f))
                self.lbl_file_count.config(text=f"{len(self.input_files)} files sorted and selected.")
                self.lbl_status.config(text="Files sorted.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to parse files: {str(e)}")
                self.lbl_status.config(text="Error sorting files.")

    def select_output(self):
        f = filedialog.asksaveasfilename(defaultextension=".xtf", filetypes=(("XTF Files", "*.xtf"), ("All Files", "*.*")))
        if f:
            self.output_file = f
            self.lbl_output.config(text=self.output_file)

    def start_merge(self):
        if not self.input_files:
            messagebox.showwarning("Warning", "No input files selected.")
            return
        if not self.output_file:
            messagebox.showwarning("Warning", "No output file selected.")
            return
            
        self.btn_merge.config(state='disabled')
        self.progress_var.set(0)
        self.lbl_status.config(text="Starting merge...")
        
        # Run merge in a separate thread so GUI doesn't freeze
        thread = threading.Thread(target=self.run_merge_thread)
        thread.start()

    def update_progress(self, current_idx, total_files, current_file):
        # Schedule GUI update
        def gui_update():
            progress = (current_idx / total_files) * 100
            self.progress_var.set(progress)
            self.lbl_status.config(text=f"Processing {current_idx+1}/{total_files}: {os.path.basename(current_file)}")
        self.root.after(0, gui_update)

    def run_merge_thread(self):
        pad_to_size = None
        if self.var_normalize.get():
            self.root.after(0, lambda: self.lbl_status.config(text="Pass 1: Scanning files for maximum packet size..."))
            pad_to_size = find_max_packet_size(self.input_files, progress_callback=self.update_progress)
            
        self.root.after(0, lambda: self.lbl_status.config(text="Pass 2: Merging files..."))
        success, message = merge_xtf_files(self.input_files, self.output_file, progress_callback=self.update_progress, pad_to_size=pad_to_size)
        
        def finish():
            self.btn_merge.config(state='normal')
            if success:
                self.progress_var.set(100)
                self.lbl_status.config(text="Merge completed successfully!")
                messagebox.showinfo("Success", "Merge completed. Report generated.")
            else:
                self.lbl_status.config(text="Merge failed.")
                messagebox.showerror("Error", message)
                
        self.root.after(0, finish)

if __name__ == "__main__":
    root = tk.Tk()
    app = HiSASMergerApp(root)
    root.mainloop()
