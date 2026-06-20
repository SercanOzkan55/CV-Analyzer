import os

ROOT = r"c:\Users\ASUS\Desktop\cv-analyzer"

EXCLUDE_DIRS = {
    'node_modules', '.git', '__pycache__', '.venv', 'venv', 'dist', 'build',
    '.pytest_cache', '.mypy_cache', '.gemini_scratch', '.next',
    '.ruff_cache', '.npm-cache', 'CV-Analyzer-DEMO-export', '_dev_scratch',
    'dev_logs', '.runtime-logs', 'test_tmp', '.codex',
}

EXCLUDE_FILES = {'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml'}
BINARY_EXTS = {'.png', '.jpg', '.jpeg', '.ico', '.woff', '.woff2', '.ttf', '.eot', 
               '.gif', '.bmp', '.webp', '.mp4', '.mp3', '.pdf', '.zip', '.pkl', 
               '.db', '.sqlite3', '.pyc', '.pyo', '.exe', '.dll', '.so', '.map'}

LANG_MAP = {
    '.py': 'Python', '.js': 'JavaScript', '.jsx': 'React JSX',
    '.ts': 'TypeScript', '.tsx': 'React TSX', '.css': 'CSS',
    '.html': 'HTML', '.json': 'JSON', '.md': 'Markdown',
    '.yml': 'YAML', '.yaml': 'YAML', '.toml': 'TOML',
    '.txt': 'Text', '.sh': 'Shell/Bash', '.bat': 'Batch',
    '.ps1': 'PowerShell', '.sql': 'SQL', '.env': 'Environment',
    '.cfg': 'Config', '.ini': 'Config', '.conf': 'Config (Nginx)',
    '.svg': 'SVG', '.http': 'HTTP Request', '.jsonl': 'JSON Lines',
    '.log': 'Log', '.lock': 'Lock File',
}

results = {}
file_details = []

for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
    
    for fname in filenames:
        if fname in EXCLUDE_FILES:
            continue
        
        fpath = os.path.join(dirpath, fname)
        _, ext = os.path.splitext(fname)
        
        if not ext:
            if fname == 'Dockerfile':
                ext = 'Dockerfile'
            elif fname == 'Makefile':
                ext = 'Makefile'
            elif fname.startswith('.'):
                ext = fname
            else:
                ext = fname
        
        ext_lower = ext.lower()
        
        # Skip large binary files
        if ext_lower in BINARY_EXTS:
            continue
        # Skip .pytest_test_*.db files
        if fname.startswith('.pytest_test_') and fname.endswith('.db'):
            continue
            
        lang = LANG_MAP.get(ext_lower, ext_lower if ext_lower else 'Other')
        
        if lang not in results:
            results[lang] = {'files': 0, 'lines': 0, 'bytes': 0}
        
        try:
            size = os.path.getsize(fpath)
        except:
            size = 0
        
        results[lang]['files'] += 1
        results[lang]['bytes'] += size
        
        try:
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                line_count = sum(1 for _ in f)
            results[lang]['lines'] += line_count
        except:
            pass

sorted_results = sorted(results.items(), key=lambda x: x[1]['lines'], reverse=True)

print("| Dil / Dosya Türü | Dosya Sayısı | Satır Sayısı | Boyut (KB) |")
print("|---|---|---|---|")

total_files = 0
total_lines = 0
total_bytes = 0

for lang, data in sorted_results:
    size_kb = round(data['bytes'] / 1024, 1)
    print(f"| {lang} | {data['files']} | {data['lines']:,} | {size_kb:,} |")
    total_files += data['files']
    total_lines += data['lines']
    total_bytes += data['bytes']

total_kb = round(total_bytes / 1024, 1)
total_mb = round(total_bytes / (1024*1024), 1)
print(f"| **TOPLAM** | **{total_files}** | **{total_lines:,}** | **{total_kb:,} ({total_mb} MB)** |")
