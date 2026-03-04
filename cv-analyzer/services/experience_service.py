import re
from datetime import datetime


def extract_years(text: str) -> int:
    text = text.lower()

    # 1️⃣ Direct experience patterns (5+ years, 3 yrs etc.)
    direct_patterns = [
        r"(\d+)\+?\s*years",
        r"(\d+)\+?\s*year",
        r"(\d+)\+?\s*yrs",
        r"(\d+)\+?\s*yr",
        r"(\d+)\+?\s*yıl"
    ]

    found_years = []

    for pattern in direct_patterns:
        matches = re.findall(pattern, text)
        for m in matches:
            found_years.append(int(m))

    if found_years:
        # En yüksek değeri al (genelde toplam experience yazılır)
        return max(found_years)

    # 2️⃣ Date range detection (2018 - 2022, 2020 – present)
    year_ranges = re.findall(r"(20\d{2})\s*[-–]\s*(20\d{2}|present)", text)

    total_years = 0
    current_year = datetime.now().year

    for start, end in year_ranges:
        start = int(start)

        if end == "present":
            end = current_year
        else:
            end = int(end)

        if end > start:
            total_years += (end - start)

    # Eğer mantıklı bir aralık çıktıysa kullan
    if total_years > 0:
        return total_years

    return 0


def experience_score(cv_text: str, job_text: str) -> float:
    cv_years = extract_years(cv_text)
    job_years = extract_years(job_text)

    # Job experience belirtilmemişse cezalandırma yapma
    if job_years == 0:
        return 100.0

    # CV experience fazlaysa full score
    if cv_years >= job_years:
        return 100.0

    # Gap hesapla
    gap = job_years - cv_years

    # Yumuşak ceza sistemi
    # Küçük gap hafif cezalandırılır, büyük gap sert düşer
    penalty = min(40, gap * 15)

    score = 100 - penalty

    return round(max(0, score), 2)