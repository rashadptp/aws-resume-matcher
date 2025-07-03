from flask import Flask, request, jsonify
import spacy

app = Flask(__name__)

# Load spaCy English model
nlp = spacy.load("en_core_web_sm")

# Simple skills list (you can expand this or extract from JD)
def extract_skills(text):
    doc = nlp(text.lower())
    # We'll keep it simple: extract nouns + proper nouns as skills
    skills = set(token.lemma_ for token in doc if token.pos_ in ["NOUN", "PROPN"])
    return skills

@app.route('/score', methods=['POST'])
def score_resume():
    data = request.get_json()
    resume_text = data.get("resume", "")
    jd_text = data.get("job_description", "")

    jd_skills = extract_skills(jd_text)
    resume_skills = extract_skills(resume_text)

    matched_skills = jd_skills.intersection(resume_skills)
    missing_skills = jd_skills - resume_skills

    match_score = round((len(matched_skills) / len(jd_skills)) * 100, 2) if jd_skills else 0

    result = {
        "match_score": match_score,
        "matched_skills": list(matched_skills),
        "missing_skills": list(missing_skills)
    }
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True)
