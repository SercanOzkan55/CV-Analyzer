import re
from datetime import datetime


def extract_years(text: str) -> int:
    text_lower = text.lower()

    # 1) Direct experience patterns: "5+ years", "3 yrs", "10 yıl"
    direct_patterns = [
        r"(\d+)\+?\s*years?",
        r"(\d+)\+?\s*yrs?",
        r"(\d+)\+?\s*yıl",
    ]

    found_years = []
    for pattern in direct_patterns:
        for m in re.findall(pattern, text_lower):
            found_years.append(int(m))

    if found_years:
        return max(found_years)

    # 2) Date range detection: "2018 - 2022", "2020 – present", "Jan 2018 - Mar 2022"
    current_year = datetime.now().year

    # Match year ranges like (1995-2020), (2018 - present), (2020 – current), "2018 to 2023"
    year_ranges = re.findall(
        r"((?:19|20)\d{2})\s*(?:[-–—]|to)\s*((?:19|20)\d{2}|present|current|now|günümüz|halen|devam)",
        text_lower,
    )

    if not year_ranges:
        return 0

    # Merge overlapping ranges to avoid double-counting concurrent positions
    intervals = []
    for start_str, end_str in year_ranges:
        start = int(start_str)
        if end_str.isdigit():
            end = int(end_str)
        else:
            end = current_year

        if end >= start and start >= 1970 and end <= current_year + 1:
            intervals.append((start, end))

    if not intervals:
        return 0

    # Sort and merge overlapping intervals
    intervals.sort()
    merged = [intervals[0]]
    for s, e in intervals[1:]:
        prev_s, prev_e = merged[-1]
        if s <= prev_e:
            merged[-1] = (prev_s, max(prev_e, e))
        else:
            merged.append((s, e))

    total = sum(e - s for s, e in merged)
    return max(0, total)


def experience_score(cv_text: str, job_text: str) -> float:
    cv_years = extract_years(cv_text)
    job_years = extract_years(job_text)

    # Job experience not specified — give benefit of doubt
    if job_years == 0:
        # Still reward having experience mentioned
        if cv_years >= 5:
            return 100.0
        elif cv_years >= 2:
            return 80.0
        elif cv_years >= 1:
            return 60.0
        return 50.0  # neutral — no info available

    # CV has equal or more experience
    if cv_years >= job_years:
        return 100.0

    # Gap penalty: proportional to how far short the candidate is
    ratio = cv_years / job_years
    # Smooth penalty curve: 80% of required → 80 score, 50% → 50, 0% → 20
    score = max(20.0, ratio * 100)

    return round(score, 2)
