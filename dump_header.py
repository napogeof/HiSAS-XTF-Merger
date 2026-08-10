import struct
filepath = 'c:/Users/napog/Documents/P.A.R.A/1-Projects/HiSAS/sale10/sasi-upper-20260803-172621-sale10.xtf'
with open(filepath, 'rb') as f:
    f.seek(1024 + 14)
    ping_header = f.read(256)
    print('Ping header uint32s:')
    for i in range(0, 256, 4):
        print(f'{i:3}: {struct.unpack_from("<I", ping_header, i)[0]}')
