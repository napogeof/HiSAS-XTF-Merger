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

def get_first_timestamp(filepath):
    """Scan file to find the first valid SONAR packet timestamp for sorting."""
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
                if dt:
                    return dt
            
            f.seek(header['pos'] + header['numbytes'])
    return datetime.datetime.max

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

def merge_xtf_files(infiles, base_outfile, progress_callback=None, pad_to_size=None, max_gap_seconds=5.0):
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
    
    def get_out_path(idx):
        return f"{base}_{idx}{ext}"
        
    def close_current_file():
        nonlocal out_f
        if out_f:
            out_f.close()
            generated_files.append({
                'path': get_out_path(file_index),
                'pings': global_ping_count,
                'padded': global_padded_packets,
                'first': first_time,
                'last': last_time,
                'infiles': current_infiles.copy()
            })
            out_f = None

    try:
        current_out_path = get_out_path(file_index)
        out_f = open(current_out_path, 'wb')
        
        for i, infile in enumerate(infiles):
            if progress_callback:
                progress_callback(i, total_files, infile)
                
            with open(infile, 'rb') as in_f:
                file_header = in_f.read(1024)
                
                # Check for time gap
                current_first_time = get_first_timestamp(infile)
                
                if i > 0 and last_time is not None and current_first_time != datetime.datetime.max:
                    gap = (current_first_time - last_time).total_seconds()
                    if gap > max_gap_seconds:
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
                        
                        current_out_path = get_out_path(file_index)
                        out_f = open(current_out_path, 'wb')
                
                # Write file header if this is the first file in the CURRENT output file
                if len(current_infiles) == 0:
                    out_f.write(file_header)
                    
                current_infiles.append(os.path.basename(infile))
                
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
                                
                        record_payload = bytearray(record_payload)
                        struct.pack_into('<II', record_payload, 10, global_event_count, global_ping_count)
                        global_ping_count += 1
                        global_event_count += 1
                    
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
        
        # Generate master report
        report_path = f"{base}_report.txt"
        with open(report_path, 'w') as f:
            f.write("HiSAS Offline XTF Merger - Processing Report\n")
            f.write("="*50 + "\n\n")
            f.write(f"Total input files processed: {total_files}\n")
            f.write(f"Total merged files generated: {len(generated_files)}\n\n")
            
            for gen in generated_files:
                f.write(f"Output File: {os.path.basename(gen['path'])}\n")
                f.write(f"  Total output sonar pings: {gen['pings']}\n")
                if pad_to_size:
                    f.write(f"  Packets zero-padded to uniform size ({pad_to_size} bytes): {gen['padded']}\n")
                else:
                    f.write("  Packets zero-padded: 0 (Normalization disabled)\n")
                f.write(f"  First ping timestamp: {gen['first']}\n")
                f.write(f"  Last ping timestamp: {gen['last']}\n")
                f.write("  Input files included:\n")
                for src in gen['infiles']:
                    f.write(f"    - {src}\n")
                f.write("\n")
        
        return True, f"Success! Generated {len(generated_files)} files."
    except Exception as e:
        if out_f:
            out_f.close()
        return False, str(e)
