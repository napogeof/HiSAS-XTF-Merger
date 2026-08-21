import os
import struct
import datetime

def read_packet_header(f):
    pos = f.tell()
    data = f.read(14)
    if len(data) < 14:
        return None
    try:
        magic, htype, subchan, numchans, res1, res2, numbytes = struct.unpack('<HBBHHHI', data)
        return {
            'magic': magic,
            'type': htype,
            'subchan': subchan,
            'numchans': numchans,
            'numbytes': numbytes,
            'pos': pos
        }
    except struct.error:
        return None

def extract_packet_timestamp(record_payload):
    try:
        year, month, day, hour, minute, second, hsec = struct.unpack_from('<HBBBBBB', record_payload, 0)
        return datetime.datetime(year, month, day, hour, minute, second, hsec * 10000)
    except Exception:
        return None

def extract_packet_heading(record_payload):
    try:
        # Kongsberg hides the locked SAS heading in the 'Yaw' field!
        # XTF 'Yaw' is a float at offset 108 in the ping header (offset 94 in payload)
        heading = struct.unpack_from('<f', record_payload, 94)[0]
        return heading
    except Exception:
        return None

def get_file_metadata(filepath):
    """Scan file to find the first valid SONAR packet timestamp and heading."""
    first_dt = datetime.datetime.max
    first_heading = None
    with open(filepath, 'rb') as f:
        f.seek(1024)  # skip file header
        while True:
            header = read_packet_header(f)
            if not header or header['magic'] != 0xFACE:
                break
            
            f.seek(header['pos'] + 14)
            payload = f.read(header['numbytes'] - 14)
            if header['type'] == 0 and len(payload) >= 256 - 14:
                dt = extract_packet_timestamp(payload)
                if dt and first_dt == datetime.datetime.max:
                    first_dt = dt
                
                heading = extract_packet_heading(payload)
                if heading is not None and first_heading is None:
                    first_heading = heading
                    
                if first_dt != datetime.datetime.max and first_heading is not None:
                    break
            
            f.seek(header['pos'] + header['numbytes'])
    return first_dt, first_heading

def get_first_timestamp(filepath):
    dt, _ = get_file_metadata(filepath)
    return dt

def find_max_packet_size(file_paths, progress_callback=None):
    """Scan files to find the maximum packet size (numbytes) across all pings."""
    max_size = 0
    total_files = len(file_paths)
    for i, filepath in enumerate(file_paths):
        if progress_callback:
            progress_callback(i, total_files, filepath)
        try:
            with open(filepath, 'rb') as f:
                f.seek(1024)
                while True:
                    header = read_packet_header(f)
                    if not header or header['magic'] != 0xFACE:
                        break
                    if header['numbytes'] > max_size:
                        max_size = header['numbytes']
                    f.seek(header['pos'] + header['numbytes'])
        except Exception:
            pass
    return max_size

def sort_files_by_timestamp(file_paths):
    return sorted(file_paths, key=get_first_timestamp)

def merge_xtf_files(infiles, base_outfile, progress_callback=None, pad_to_size=None, max_gap_seconds=5.0, max_heading_gap=0.1, survey_range=200.0, dry_run=False):
    if not infiles:
        return False, "No files provided."
        
    total_files = len(infiles)
    base, ext = os.path.splitext(base_outfile)
    
    file_index = 1
    out_f = None
    
    # State for current output file
    global_ping_count = 0
    global_event_count = 0
    global_max_time = datetime.datetime.min
    global_padded_packets = 0
    first_time = None
    last_time = None
    current_infiles = []
    
    generated_files = []
    current_split_reason = None
    
    def get_out_path(idx):
        return f"{base}_{idx}{ext}"
        
    def close_current_file():
        nonlocal out_f
        headings = [f['heading'] for f in current_infiles if f['heading'] is not None]
        avg_h = sum(headings) / len(headings) if headings else None
        min_h = min(headings) if headings else None
        max_h = max(headings) if headings else None
        
        if out_f:
            out_f.close()
            
        generated_files.append({
            'path': get_out_path(file_index),
            'pings': global_ping_count,
            'padded': global_padded_packets,
            'first': first_time,
            'last': last_time,
            'infiles': current_infiles.copy(),
            'split_reason': current_split_reason,
            'avg_heading': avg_h,
            'min_heading': min_h,
            'max_heading': max_h
        })
        out_f = None

    try:
        current_out_path = get_out_path(file_index)
        if not dry_run:
            out_f = open(current_out_path, 'wb')
        
        previous_heading = None
        
        for i, infile in enumerate(infiles):
            if progress_callback:
                progress_callback(i, total_files, infile)
                
            with open(infile, 'rb') as in_f:
                file_header = in_f.read(1024)
                
                # Check for time gap and heading gap
                current_first_time, current_heading = get_file_metadata(infile)
                
                split_reason_text = None
                
                if i > 0:
                    if last_time is not None and current_first_time != datetime.datetime.max:
                        gap_sec = (current_first_time - last_time).total_seconds()
                        if gap_sec > max_gap_seconds:
                            split_reason_text = f"Time Gap: {gap_sec:.1f}s"
                            
                    if split_reason_text is None and previous_heading is not None and current_heading is not None:
                        # Shortest angular difference between two headings
                        heading_diff = abs((current_heading - previous_heading + 180) % 360 - 180)
                        if heading_diff > max_heading_gap:
                            import math
                            error_m = survey_range * math.sin(math.radians(heading_diff))
                            split_reason_text = f"Heading Change: {heading_diff:.2f}° (Prevented ~{error_m:.1f}m of geometric target displacement at {survey_range}m range)"

                if split_reason_text:
                    # Gap detected! Close current file and start a new one.
                    close_current_file()
                    file_index += 1
                    
                    global_ping_count = 0
                    global_event_count = 0
                    global_max_time = datetime.datetime.min
                    global_padded_packets = 0
                    first_time = None
                    last_time = None
                    current_infiles = []
                    current_split_reason = split_reason_text
                    
                    current_out_path = get_out_path(file_index)
                    if not dry_run:
                        out_f = open(current_out_path, 'wb')
                
                if current_heading is not None:
                    previous_heading = current_heading

                # Write file header if this is the first file in the CURRENT output file
                if len(current_infiles) == 0 and out_f:
                    out_f.write(file_header)
                    
                current_infiles.append({'name': os.path.basename(infile), 'heading': current_heading})
                
                in_f.seek(1024)
                while True:
                    header = read_packet_header(in_f)
                    if not header:
                        break
                    
                    if header['magic'] != 0xFACE:
                        break
                    
                    in_f.seek(header['pos'] + 14)
                    record_payload = in_f.read(header['numbytes'] - 14)
                    
                    if header['type'] == 0 and len(record_payload) >= 256 - 14:
                        dt = extract_packet_timestamp(record_payload)
                        if dt:
                            if dt > global_max_time:
                                global_max_time = dt
                            if first_time is None:
                                first_time = dt
                            last_time = dt
                                
                        if not dry_run:
                            record_payload = bytearray(record_payload)
                            struct.pack_into('<II', record_payload, 10, global_event_count, global_ping_count)
                        
                        global_ping_count += 1
                        global_event_count += 1
                    
                    if not dry_run:
                        out_f.seek(0, os.SEEK_END)
                        if pad_to_size and header['numbytes'] < pad_to_size:
                            padding_len = pad_to_size - header['numbytes']
                            in_f.seek(header['pos'])
                            orig_header = bytearray(in_f.read(14))
                            struct.pack_into('<I', orig_header, 10, pad_to_size)
                            out_f.write(orig_header)
                            out_f.write(record_payload)
                            out_f.write(b'\x00' * padding_len)
                            global_padded_packets += 1
                        else:
                            in_f.seek(header['pos'])
                            out_f.write(in_f.read(14))
                            out_f.write(record_payload)
                    
                    in_f.seek(header['pos'] + header['numbytes'])
        
        close_current_file()
        
        # Calculate global heading stats across all input files
        all_headings = []
        for gen in generated_files:
            for f in gen['infiles']:
                if f['heading'] is not None:
                    all_headings.append(f['heading'])
                    
        global_avg = sum(all_headings) / len(all_headings) if all_headings else None
        global_min = min(all_headings) if all_headings else None
        global_max = max(all_headings) if all_headings else None
        
        # Generate master report
        report_path = f"{base}_report.txt"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("HiSAS Offline XTF Merger - Processing Report\n")
            f.write("="*50 + "\n\n")
            if dry_run:
                f.write("*** DRY RUN MODE: No XTF files were generated ***\n\n")
            f.write(f"Total input files processed: {total_files}\n")
            f.write(f"Total merged files generated: {len(generated_files)}\n\n")
            
            if global_avg is not None:
                f.write(f"Global Heading Stats (Across All Files):\n")
                f.write(f"  Avg: {global_avg:.2f}° | Min: {global_min:.2f}° | Max: {global_max:.2f}°\n")
                f.write(f"  Maximum Angular Variance: {(global_max - global_min):.2f}°\n\n")
            f.write("="*50 + "\n\n")
            
            for gen in generated_files:
                if gen['split_reason']:
                    f.write(f"--- Split triggered by: {gen['split_reason']} ---\n\n")
                
                f.write(f"Output File: {os.path.basename(gen['path'])}\n")
                
                if gen['avg_heading'] is not None:
                    f.write(f"  Heading Stats - Avg: {gen['avg_heading']:.2f}° | Min: {gen['min_heading']:.2f}° | Max: {gen['max_heading']:.2f}°\n")
                
                f.write(f"  Total output sonar pings: {gen['pings']}\n")
                
                if dry_run:
                    f.write(f"  Packets zero-padded: Skipped (Dry Run)\n")
                elif pad_to_size:
                    f.write(f"  Packets zero-padded to uniform size ({pad_to_size} bytes): {gen['padded']}\n")
                else:
                    f.write("  Packets zero-padded: 0 (Normalization disabled)\n")
                    
                f.write(f"  First ping timestamp: {gen['first']}\n")
                f.write(f"  Last ping timestamp: {gen['last']}\n")
                f.write("  Input files included:\n")
                for src in gen['infiles']:
                    h_str = f"{src['heading']:.2f}°" if src['heading'] is not None else "Unknown"
                    f.write(f"    - {src['name']} (Heading: {h_str})\n")
                f.write("\n")
        
        if dry_run:
            return True, f"Dry Run completed! Analyzed {len(generated_files)} file splits."
        return True, f"Success! Generated {len(generated_files)} files."
    except Exception as e:
        if out_f:
            out_f.close()
        return False, str(e)
