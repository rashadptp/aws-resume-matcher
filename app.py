from flask import Flask, request, jsonify, session
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
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import json
from datetime import datetime


app = Flask(__name__)
CORS(app, supports_credentials=True)  # Important for cookies/session
app.secret_key = "supersecretkey"
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'docx'}
USAGE_FILE = "usage.json"
USAGE_LIMIT = 10



def load_usage():
    if not os.path.exists(USAGE_FILE):
        return {}
    with open(USAGE_FILE, "r") as f:
        return json.load(f)

def save_usage(data):
    with open(USAGE_FILE, "w") as f:
        json.dump(data, f, indent=2)
        
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
users = {
    "test@example.com": {
        "password": generate_password_hash("password123"),
        "calls_made": 0,
        "call_limit": 10,
        "name": "Test User"
    },
    "test2@example.com": {
        "password": generate_password_hash("password123"),
        "calls_made": 0,
        "call_limit": 10,
        "name": "Test User"
    }
    
}

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
@app.route("/signup", methods=["POST"])
def signup():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    if email in users:
        return jsonify({"error": "Email already registered"}), 400

    users[email] = {
        "password": generate_password_hash(password),
        "count": 0
    }

    session["user"] = email
    return jsonify({"message": "Signup successful", "email": email})


@app.route("/login", methods=["POST"])
@app.route("/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    user = users.get(email)
    if not user or not check_password_hash(user["password"], password):
        return jsonify({"error": "Invalid credentials"}), 401

    session["user"] = email
    return jsonify({
        "email": email,
        "name": user.get("name", "User")
    })

@app.route("/logout", methods=["POST"])
def logout():
    session.pop("user", None)
    return jsonify({"message": "Logged out"})

@app.route("/me", methods=["GET"])
def get_me():
    user = session.get("user")
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    return jsonify({"email": user})



@app.route("/score", methods=["POST"])
def score_resume():
    data = request.json
    resume_text = data.get("resume", "")
    filename = data.get("filename", "Unknown")  # Add this in frontend later
    jd_text = data.get("job_description", "")
    email = data.get("email")

    if not email:
        return jsonify({"error": "Email is required"}), 400

    # Load and check usage
    usage = load_usage()
    user_data = usage.get(email, {"matches_left": 0, "history": []})


    # Handle legacy or missing data
    matches_left = (
        user_data.get("matches_left")
        if isinstance(user_data, dict)
        else max(0, 10 - user_data)  # Legacy format fallback
    )

    if matches_left <= 0:
        return jsonify({"message": "Resume limit reached. Please upgrade."}), 429

    # Decrement and save usage
    if isinstance(user_data, dict):
        usage[email]["matches_left"] = matches_left - 1
    else:
        # legacy: convert from numeric count to dict
        usage[email] = {"matches_left": 9 - user_data}
    # Skill extraction
    resume_skills = extract_skills(resume_text)
    jd_skills = extract_skills(jd_text)

    matched = list(set(resume_skills).intersection(jd_skills))
    missing = list(set(jd_skills) - set(resume_skills))
    score = round((len(matched) / len(jd_skills)) * 100, 2) if jd_skills else 0
        
    user_data["matches_left"] -= 1
    user_data.setdefault("history", []).append({
        "resume_name": filename,
        "score": score,
        "timestamp": datetime.utcnow().isoformat()
    })
    usage[email] = user_data
    save_usage(usage)



    return jsonify({
        "match_score": score,
        "matched_skills": matched,
        "missing_skills": missing
    })

@app.route("/score-text", methods=["POST"])
def score_from_text():
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
results = []
@app.route('/upload-resume', methods=['GET', 'POST'])
def upload_resume():
    global results
    results = []  # clear previous results each time

    if request.method == 'POST':
        jd = request.form['job_description']
        files = request.files.getlist('resume_files')

        if not jd or not files:
            return "Please upload at least one resume and fill in JD.", 400

        jd_skills = extract_skills(jd)

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
                    'File Name': filename,
                    'Match Score': score,
                    'Matched Skills': ", ".join(matched),
                    'Missing Skills': ", ".join(missing)
                })

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
                <td>{{ row["File Name"] }}</td>
                <td>{{ row["Match Score"] }}%</td>
                <td>{{ row["Matched Skills"] }}</td>
                <td>{{ row["Missing Skills"] }}</td>
            </tr>
            {% endfor %}
        </table>
        <br>
        <a href="/download-csv"><button>Download CSV</button></a>
        <br><br>
        <a href="/">Upload More</a>
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


@app.route("/payment-success", methods=["POST"])
def payment_success():
    data = request.json
    email = data.get("email")

    if not email:
        return jsonify({"error": "Email is required"}), 400

    usage = load_usage()
    usage[email] = {"matches_left": 500}  # Give 500 matches
    save_usage(usage)

    return jsonify({"message": "Plan upgraded. 500 matches unlocked."})

import stripe

stripe.api_key = "sk_test_51RiFrBH2vTKHOvUiqVCzKGk9p44YnovviLHKeea2DAp4ZBS1k5Cy5UFSXBLbFDcJftZjA5XdXhayTYCdQiLN99iE00pf8ZihrH"  # Use your secret key

@app.route("/create-checkout-session", methods=["POST"])
def create_checkout_session():
    data = request.json
    email = data.get("email")

    if not email:
        return jsonify({"error": "Email is required"}), 400

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="payment",
            customer_email=email,
            line_items=[
                {
                    "price_data": {
                        "currency": "inr",  # or "usd"
                        "product_data": {
                            "name": "500 Resume Matches Plan",
                        },
                        "unit_amount": 19900,  # ₹199.00 in paise
                    },
                    "quantity": 1,
                }
            ],
            metadata={"email": email},
            success_url="http://localhost:3000/payment-success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url="http://localhost:3000/payment-cancelled",
        )
        return jsonify({"url": session.url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/profile", methods=["GET"])
def profile():
    email = request.args.get("email")
    if not email:
        return jsonify({"error": "Email is required"}), 400

    usage = load_usage()
    user_data = usage.get(email, {})
    return jsonify(user_data)

if __name__ == '__main__':
    app.run(debug=True)
