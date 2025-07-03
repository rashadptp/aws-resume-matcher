from flask import Flask, request, jsonify
import spacy
import subprocess
from rapidfuzz import fuzz
import os
import fitz  # PyMuPDF
from docx import Document
from werkzeug.utils import secure_filename
import io
import csv
from flask import send_file

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'docx'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    
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
def extract_text_from_pdf(file_path):
    text = ""
    with fitz.open(file_path) as doc:
        for page in doc:
            text += page.get_text()
    return text

def extract_text_from_docx(file_path):
    doc = Document(file_path)
    return "\n".join([para.text for para in doc.paragraphs])

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
import csv
from io import StringIO
from flask import render_template_string

@app.route('/upload-resume', methods=['GET', 'POST'])
def upload_resume():
    if request.method == 'POST':
        jd = request.form['job_description']
        files = request.files.getlist('resume_files')

        if not jd or not files:
            return "Please upload at least one resume and fill in JD.", 400

        jd_skills = extract_skills(jd)
        results = []

        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)

                if filename.endswith('.pdf'):
                    resume_text = extract_text_from_pdf(filepath)
                else:
                    resume_text = extract_text_from_docx(filepath)

                resume_skills = extract_skills(resume_text)
                matched = list(set(resume_skills).intersection(jd_skills))
                missing = list(set(jd_skills) - set(resume_skills))
                score = round((len(matched) / len(jd_skills)) * 100, 2) if jd_skills else 0

                results.append({
                    'filename': filename,
                    'score': score,
                    'matched_skills': ", ".join(matched),
                    'missing_skills': ", ".join(missing)
                })

        # Render results in a table
        return render_template_string("""
        <h2>Results</h2>
        <table border="1" cellpadding="5">
            <tr>
                <th>File</th>
                <th>Score</th>
                <th>Matched Skills</th>
                <th>Missing Skills</th>
            </tr>
            {% for row in results %}
            <tr>
                <td>{{ row.filename }}</td>
                <td>{{ row.score }}%</td>
                <td>{{ row.matched_skills }}</td>
                <td>{{ row.missing_skills }}</td>
            </tr>
            {% endfor %}
        </table>
        <br><a href="/">Upload More</a>
        """, results=results)

    return '''
    <!doctype html>
    <title>Upload Resumes</title>
    <h1>Upload Multiple Resumes</h1>
    <form method=post enctype=multipart/form-data>
      <label>Job Description:</label><br>
      <textarea name=job_description rows=5 cols=40></textarea><br><br>
      <input type=file name=resume_files multiple><br><br>
      <input type=submit value=Upload>
    </form>
    '''
@app.route('/download-csv')
def download_csv():
    global results
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["File Name", "Match Score", "Matched Skills", "Missing Skills"])
    writer.writeheader()
    writer.writerows(results)
    output.seek(0)

    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name='resume_results.csv'
    )
if __name__ == '__main__':
    app.run(debug=True)
