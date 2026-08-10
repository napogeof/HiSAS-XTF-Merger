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

def merge_xtf_files(infiles, outfile, progress_callback=None, pad_to_size=None, drop_overlap=True):
    if not infiles:
        return False, "No files provided."
        
    global_ping_count = 0
    global_event_count = 0
    global_max_time = datetime.datetime.min
    global_dropped_pings = 0
    global_padded_packets = 0
    total_files = len(infiles)
    
    first_time = None
    last_time = None

    try:
        with open(outfile, 'wb') as out_f:
            for i, infile in enumerate(infiles):
                if progress_callback:
                    progress_callback(i, total_files, infile)
                
                with open(infile, 'rb') as in_f:
                    if i == 0:
                        out_f.write(in_f.read(1024))
                    else:
                        in_f.seek(1024)
                    
                    while True:
                        header = read_packet_header(in_f)
                        if not header:
                            break
                        
                        if header['magic'] != 0xFACE:
                            break
                        
                        in_f.seek(header['pos'] + 14)
                        record_payload = in_f.read(header['numbytes'] - 14)
                        
                        write_packet = True
                        if header['type'] == 0 and len(record_payload) >= 256 - 14:
                            dt = extract_packet_timestamp(record_payload)
                            if dt:
                                if drop_overlap and dt <= global_max_time:
                                    write_packet = False
                                    global_dropped_pings += 1
                                else:
                                    if dt > global_max_time:
                                        global_max_time = dt
                                    if first_time is None:
                                        first_time = dt
                                    last_time = dt
                                    
                            if write_packet:
                                record_payload = bytearray(record_payload)
                                struct.pack_into('<II', record_payload, 10, global_event_count, global_ping_count)
                                global_ping_count += 1
                                global_event_count += 1
                        
                        if write_packet:
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
        
        # Generate report
        report_path = os.path.splitext(outfile)[0] + "_report.txt"
        with open(report_path, 'w') as f:
            f.write("HiSAS Offline XTF Merger - Processing Report\n")
            f.write("="*50 + "\n\n")
            f.write(f"Merged output: {outfile}\n")
            f.write(f"Total input files: {total_files}\n")
            f.write(f"Total output sonar pings: {global_ping_count}\n")
            f.write(f"Overlapping pings dropped: {global_dropped_pings}\n")
            if pad_to_size:
                f.write(f"Packets zero-padded to uniform size ({pad_to_size} bytes): {global_padded_packets}\n")
            f.write(f"First ping timestamp: {first_time}\n")
            f.write(f"Last ping timestamp: {last_time}\n\n")
            f.write("Files processed in order:\n")
            for fp in infiles:
                f.write(f"  - {os.path.basename(fp)}\n")
        
        return True, "Merge completed successfully."
    except Exception as e:
        return False, str(e)
