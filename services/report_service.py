"""Report service — generates Excel/CSV exports for recruiter batch analysis."""

import logging
import io
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any

logger = logging.getLogger("app.report_service")

def generate_recruiter_report(analyses: List[Dict[str, Any]], format: str = "csv") -> io.BytesIO:
    """Generate a downloadable report for a batch of CV analyses.
    
    Args:
        analyses: List of dictionaries containing candidate analysis data.
        format: "csv" or "xlsx" (requires openpyxl).
        
    Returns:
        io.BytesIO: The generated file content.
    """
    data = []
    for item in analyses:
        # Extract core metrics
        candidate_name = item.get("candidate_name") or "Unknown"
        candidate_email = item.get("candidate_email") or "N/A"
        ats_score = item.get("ats_score") or item.get("final_score") or 0
        skill_score = item.get("skill_score") or 0
        
        # Detected skills (top 10)
        skills = ", ".join(item.get("detected_skills", [])[:10])
        missing = ", ".join(item.get("missing_skills", [])[:10])
        
        # Experience summary
        ats_data = item.get("ats", {})
        exp_entries = 0
        if isinstance(ats_data, dict):
            exp_entries = ats_data.get("experience", {}).get("entry_count", 0) if isinstance(ats_data.get("experience"), dict) else 0

        # Language summary
        languages = ", ".join(item.get("languages", []))

        data.append({
            "Candidate Name": candidate_name,
            "Email": candidate_email,
            "Overall Score": round(float(ats_score), 1),
            "Skill Match %": round(float(skill_score), 1),
            "Exp. Entries": exp_entries,
            "Top Skills": skills,
            "Missing Skills": missing,
            "Languages": languages,
            "Analysis Date": datetime.now().strftime("%Y-%m-%d"),
        })

    df = pd.DataFrame(data)
    
    # Sort by score descending
    df = df.sort_values(by="Overall Score", ascending=False)

    output = io.BytesIO()
    
    if format == "xlsx":
        try:
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Candidates')
        except ImportError:
            logger.warning("openpyxl not installed, falling back to CSV")
            df.to_csv(output, index=False)
    else:
        # Default to CSV
        csv_text = df.to_csv(index=False)
        output.write(csv_text.encode('utf-8'))

    output.seek(0)
    return output

def generate_comparison_matrix(analyses: List[Dict[str, Any]]) -> io.BytesIO:
    """Generate a skill matrix showing which candidate has which required skill."""
    # Collect all required/missing skills across all candidates
    all_required = set()
    for item in analyses:
        all_required.update(item.get("detected_skills", []))
        all_required.update(item.get("missing_skills", []))
    
    sorted_skills = sorted(list(all_required))
    
    data = []
    for item in analyses:
        candidate_name = item.get("candidate_name", "Unknown")
        candidate_skills = set(item.get("detected_skills", []))
        
        row = {"Candidate": candidate_name}
        for skill in sorted_skills:
            row[skill] = "✓" if skill in candidate_skills else "✗"
        data.append(row)
        
    df = pd.DataFrame(data)
    output = io.BytesIO()
    csv_text = df.to_csv(index=False)
    output.write(csv_text.encode('utf-8'))
    output.seek(0)
    return output
