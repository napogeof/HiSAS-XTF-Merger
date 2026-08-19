# HiSAS Offline XTF Line Merger

**Merge hundreds of short HiSAS XTF files into continuous survey lines — without resampling or rasterizing the raw acoustic data.**

Developed by **Daniel (Napo) Arráiz @nap0x**, AI-assisted development

---

## The problem

AUV-based HiSAS surveys can produce a very large number of short XTF files.

During acquisition, relatively small changes in AUV heading can cause the system to segment the recording. A single survey line may therefore consist of hundreds or even thousands of files, sometimes only ~70 m long.

For example:

```text
LINE_001
├── 001.xtf
├── 002.xtf
├── 003.xtf
├── 004.xtf
├── ...
└── 847.xtf
```

Processing these files individually in SonarWiz can become cumbersome.

SonarWiz provides aggregation tools for combining the resulting products, but when consecutive files contain overlapping acquisition periods, the resulting mosaic can contain duplicate coverage and artifacts such as stretching or smearing.

This application addresses the problem **before SonarWiz processing**, directly at the raw XTF level.

---

# What it does

The HiSAS Offline XTF Line Merger combines multiple segmented XTF files belonging to the same survey line into a single continuous XTF file.

```text
847 short XTF files
        │
        ▼
┌───────────────────────┐
│  HiSAS XTF Line Merger│
└───────────────────────┘
        │
        ▼
1 continuous XTF file
        │
        ▼
      SonarWiz
```

The application operates directly on the XTF records.

It does **not** create an image mosaic.

It does **not** rasterize the sonar data.

It does **not** resample the acoustic signal.

---

# Key features

### Lossless acoustic payload preservation

The application preserves the original acoustic payload of every retained ping.

It does not force all pings to have the same number of samples.

For example, if the source data contains:

```text
Ping 001 → 1392 samples
Ping 002 → 1387 samples
Ping 003 → 1401 samples
Ping 004 → 1384 samples
```

the merged XTF retains those original sample counts.

No automatic normalization to a fixed sample count is performed.

This is intentional: the goal is to preserve the original acquisition rather than reproduce undocumented processing performed by downstream software.

---

### Temporal overlap handling

Segmented AUV files may overlap in time.

For example:

```text
File A
10:00:00 ───────────────── 10:05:00
### 2. Time Ordering and File Merging
The merger identifies the earliest timestamp in each XTF file and processes them in strict chronological order. It extracts the raw packets from each file and concatenates them. 

Because Kongsberg AUVs often start a new file slightly before the previous file finishes (to prevent data loss during turns), the files may temporally overlap by a few seconds. The merger **preserves all pings** without deleting any overlapping data. This ensures that no geographic coverage is lost, especially during turns where the swath geometry intersects.

While this may cause SonarWiz to report a harmless "Time Reversal" warning during import, it allows SonarWiz to naturally blend the overlapping swaths together on the mosaic.

---

The original source files are never modified.

---

### 3. Ping Sequence Reconstruction
The ping number and event number sequences in the original files will inevitably reset or contain gaps. To prevent "Missing Ping" errors during import, the merger completely regenerates the `PingNumber` and `EventNumber` sequence across the final file (starting from 0 and incrementing by 1 for every single ping) to ensure strict continuity.

---

### Variable Packet Size Normalization (Fixes SonarWiz Smearing)

Kongsberg HiSAS systems dynamically adjust acoustic packet payload sizes during a survey (e.g., jumping from 5844 bytes to 5888 bytes). When multiple files with differing packet sizes are concatenated, SonarWiz's XTF parser often loses byte-synchronization and severely corrupts the mosaic (resulting in the "smearing" bug).
By default, the merger scans the input files, identifies the maximum packet size, and **zero-pads** all smaller packets to match that maximum size. This tricks SonarWiz into reading a perfectly uniform file without altering or distorting any real acoustic data.

---

### Navigation preservation

The application does not perform navigation correction or interpolation.

For retained pings, the original available navigation and acquisition metadata are preserved, including information such as:

* Timestamp
* Position
* Heading
* Attitude
* Altitude/depth
* Channel information
* Acoustic samples
* Sample count

The purpose of the application is to reorganize the acquisition into a continuous XTF, **not to reinterpret the survey**.

---

# What this software does NOT do

This is a file-level XTF utility, not a sonar processing or mosaicking application.

It does not perform:

* Acoustic image mosaicking
* Pixel blending
* Image averaging
* Spatial interpolation
* Acoustic resampling
* Slant-range correction
* Navigation correction
* Radiometric normalization
* Sonar image enhancement
* Bottom tracking
* Georeferencing of raster products

The output remains an XTF intended for subsequent processing in software such as SonarWiz.

---

# Sample count and SonarWiz

A common workflow with these HiSAS datasets is to configure SonarWiz to use a fixed sample count during import.
```

For example, raw files may contain approximately:

```text
1380–1400 samples/ping
```

while the SonarWiz import may be configured for:

```text
1290 samples/ping
```

The exact operation performed internally by SonarWiz when applying this setting is not assumed by this application.

It may involve truncation, resampling, modification of sample interval, range calculations, or another internal operation.

Therefore, **the XTF merger does not reproduce this behavior**.

Instead, it preserves the original sample count and acoustic payload contained in each source ping.

If a future workflow demonstrates that a fixed sample count is required for a specific SonarWiz configuration, sample normalization may be implemented as a separate, explicitly controlled processing option.

---

# Workflow

## 1. Select XTF files

Open the **Merge XTF Files** tab.

Click:

**Select XTF Files**

and select all XTF files belonging to a single survey line.

The application automatically sorts the selected files chronologically using their internal XTF timestamps.

---

## 2. Select output file

Click:

**Select Output File**

and specify the location and name of the merged XTF.

For example:

```text
LINE_001_MERGED.XTF
```

---

## 3. Merge

Click:

**MERGE FILES**

The application will:

1. Sort the input files chronologically.
2. Read the XTF records sequentially.
3. Preserve the original acoustic payloads.
4. Intelligently split output files if large time gaps are detected.
5. Regenerate continuous ping/event numbering per output file.
6. Write the resulting continuous XTF(s).

---

## 4. Processing report

A processing report is generated next to the output XTF.

The report provides a record of the merge operation and should be retained with the processed dataset.

Typical information includes:

* Number of merged files generated
* Input files included per output
* Number of retained pings
* Number of zero-padded packets (if normalization enabled)
* First and last timestamps for each file

---

# Example

### Before

A single AUV survey line:

```text
LINE_034_001.XTF
LINE_034_002.XTF
LINE_034_003.XTF
...
LINE_034_624.XTF
```

Some files overlap temporally because of acquisition segmentation.

### After

```text
LINE_034_MERGED.XTF
```

The resulting file contains the retained ping records as one continuous XTF stream.

It can then be imported directly into SonarWiz.

---

# Data integrity

The application does not modify the original input files.

The merger is designed to preserve 100% of the acoustic payloads and pings from the source data. Overlapping pings are intentionally preserved to ensure no geometric "connective tissue" is lost during sharp AUV turns.

Therefore, the application should be understood as:

> **Completely lossless with respect to XTF records, with zero acoustic data dropped or deduplicated.**

The original acquisition files should always be retained as the authoritative source dataset.

---

# Recommended workflow

```text
             RAW ACQUISITION
                    │
                    ▼
        Hundreds of short XTF files
                    │
                    ▼
        ┌──────────────────────┐
        │ HiSAS XTF Line Merger│
        └──────────────────────┘
                    │
                    ▼
        Continuous XTF per line
                    │
                    ▼
                SonarWiz
                    │
                    ▼
          Normal processing
          / interpretation
```

The merger is intended to reduce the number of input files **before** sonar processing while keeping the raw acoustic acquisition intact.

---

# Requirements

* Windows
* HiSAS XTF files
* No internet connection required
* No cloud processing required

The application is designed to operate completely offline.

---

# Development

This project was developed to address a practical processing problem encountered with AUV-based HiSAS surveys.

The development approach prioritizes:

1. Preservation of the original acoustic acquisition.
2. Avoidance of unnecessary resampling.
3. Preservation of navigation and metadata.
4. Intelligent splitting of disjoint survey lines.
5. Direct compatibility with downstream XTF processing workflows.

The software was developed with AI-assisted programming using Google DeepMind Antigravity.

---

# Feedback and contributions

If you encounter a HiSAS/XTF dataset that behaves differently from the datasets used during development, please open an issue and provide as much information as possible about:

* HiSAS system/configuration
* XTF characteristics
* Number of files
* Sample counts
* SonarWiz version
* Error messages
* Processing behavior
* Whether the source files can be shared

Do **not** upload proprietary survey data unless you have permission to distribute it.

---

# License

MIT License

See `LICENSE` for details.
