# HiSAS Offline XTF Line Merger

**Merge hundreds of short HiSAS XTF files into continuous survey lines — without resampling or rasterizing the raw acoustic data.**

Developed by **Daniel (Napo) Arráiz @nap0x**, AI-assisted development

---

## The problem

AUV-based HiSAS surveys can produce a very large number of short XTF files. During acquisition, relatively small changes in AUV heading can cause the system to segment the recording. A single survey line may therefore consist of hundreds or even thousands of files, sometimes only ~70 m long.

Processing these files individually in downstream software like SonarWiz can become cumbersome. When consecutive files contain overlapping acquisition periods or differing locked headings, the resulting mosaic can contain duplicate coverage and severe geometric artifacts such as stretching, smearing, or target duplication.

This application addresses the problem **before processing**, directly at the raw XTF level.

---

## Key Features

### 1. Intelligent Heading Splitting (SAS Geometry Preservation)
Unlike traditional Side Scan Sonar (SSS), Synthetic Aperture Sonar (SAS) imagery is deeply processed into orthorectified rectangular image blocks. To preserve the geometric integrity of these pre-rendered blocks, the Kongsberg SAS processor establishes a single mean reference heading for the entire segment, storing it in the XTF `Yaw` field. 
If you merge two files with different locked headings, downstream software sees a sudden step-change in heading and violently twists the rectangles together, duplicating targets. 
**Solution:** The Merger monitors the internal heading of each file. If the heading change exceeds your specified threshold, it intelligently splits the output file to mathematically prevent target displacement. 
**Interactive Calculator:** The GUI includes a live error calculator based on your Survey Swath Max Range to calculate exactly how much displacement error you are avoiding!

### 2. Variable Packet Size Normalization
HiSAS systems often dynamically change acoustic packet payload sizes during a survey (e.g., jumping from 5844 to 5888 bytes per ping). 
When these differing files are concatenated, downstream XTF parsers lose byte-synchronization, causing catastrophic file corruption and smearing.
**Solution:** The Merger safely zero-pads smaller acoustic packets to match the largest packet size in the merge group, ensuring uniform structure without altering acoustic data.

### 3. Time Gap Splitting
The tool reads XTF ping timestamps. If it detects a chronological gap exceeding your specified limit (e.g., AUV surface time or missing data), it will automatically split the file rather than forcing downstream software to stretch the mosaic over the void.

### 4. 100% Lossless Pings
The application preserves the raw acoustic payloads precisely as they were acquired, including overlapping pings during AUV turns. No decimation or spatial interpolation is performed.

### 5. Advanced Processing Reports
Automatically generates a comprehensive `_report.txt` that tracks output files, ping counts, time boundaries, and specific split triggers. It explicitly logs the mathematical target displacement prevented during heading splits!

---

## How to Run

Download the latest executable from the [Releases](https://github.com/napogeof/HiSAS-XTF-Merger/releases) page.
`HiSAS_Merger_v10.exe` is a standalone Windows application and requires no installation.

## Developer Compilation

If you want to modify the source code and recompile:

```powershell
pip install pyinstaller
pyinstaller --noconsole --onefile --name HiSAS_Merger_v10 gui.py
```

---

## License

MIT License
