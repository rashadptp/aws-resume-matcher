from flask import Flask, request, jsonify
import spacy
import subprocess
from rapidfuzz import fuzz

app = Flask(__name__)

# Load spaCy English model
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")

skill_db = [
    "python", "django", "flask", "react", "nodejs", "docker", "kubernetes", 
    "apis", "rest", "sql", "mongodb", "leadership", "aws", "azure", "gcp",
    "data analysis", "machine learning", "pandas", "numpy", "excel"
]

def extract_skills(text):
    found_skills = set()
    for skill in skill_db:
        # Fuzzy match threshold (adjust as needed)
        if fuzz.partial_ratio(skill.lower(), text.lower()) >= 80:
            found_skills.add(skill.lower())
    return list(found_skills)

@app.route("/score", methods=["POST"])
def score_resume():
    data = request.json
    resume_text = data.get("resume", "")
    jd_text = data.get("job_description", "")

    resume_skills = extract_skills(resume_text)
    jd_skills = extract_skills(jd_text)

    matched = list(set(resume_skills).intersection(jd_skills))
    missing = list(set(jd_skills) - set(resume_skills))

    if jd_skills:
        score = round((len(matched) / len(jd_skills)) * 100, 2)
    else:
        score = 0

    return jsonify({
        "match_score": score,
        "matched_skills": matched,
        "missing_skills": missing
    })

if __name__ == '__main__':
    app.run(debug=True)
