import os

file_path = r'c:\Users\ozkan\Desktop\cv-analyzer\frontend\src\api.js'

with open(file_path, 'rb') as f:
    lines = f.readlines()

new_lines = []
skip_mode = False

# Tek tek satirlari kontrol edip 831 civarindaki eski recruiter kismini silelim
# Ama cok spesifik olmali
for line in lines:
    if b'export function recruiterListJobs' in line:
        # Sadece eski (async olmayan) tanimi yakalayalim
        if b'async' not in line:
             print("Eski recruiterListJobs (831) siliniyor...")
             continue # Satiri atla
    
    # Diger kopyalari da temizleyelim (garanti olsun)
    if b'export const recruiterListJobs = async' in line:
        print("Alternatif kopyalar temizleniyor...")
        continue

    new_lines.append(line)

with open(file_path, 'wb') as f:
    f.writelines(new_lines)

print("api.js duplikasyonlardan arindirildi.")
