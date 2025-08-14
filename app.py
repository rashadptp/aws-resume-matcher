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
from models import db, User, MatchHistory 
from flask_mail import Message,Mail # <-- Add this import



app = Flask(__name__)
CORS(app, supports_credentials=True,origins=["http://localhost:3000" ,"https://resume-matcher-ai4.vercel.app"])  # Important for cookies/session
app.secret_key = "supersecretkey"
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'docx'}
USAGE_FILE = "usage.json"
USAGE_LIMIT = 10

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'ptprashad@gmail.com'  # replace
app.config['MAIL_PASSWORD'] = 'kayz xpyn vbzj gieo'     # replace with app password
app.config['MAIL_DEFAULT_SENDER'] = 'ptprashad@gmail.com'  # same as MAIL_USERNAME
mail = Mail(app)
# Database setup
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///site.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

# Create tables
with app.app_context():
    db.create_all()


# def load_usage():
#     if not os.path.exists(USAGE_FILE):
#         return {}
#     with open(USAGE_FILE, "r") as f:
#         return json.load(f)

# def save_usage(data):
#     with open(USAGE_FILE, "w") as f:
#         json.dump(data, f, indent=2)
        
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# users = {
#     "test@example.com": {
#         "password": generate_password_hash("password123"),
#         "calls_made": 0,
#         "call_limit": 10,
#         "name": "Test User"
#     },
#     "test2@example.com": {
#         "password": generate_password_hash("password123"),
#         "calls_made": 0,
#         "call_limit": 10,
#         "name": "Test User"
#     }
    


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
# @app.route("/signup", methods=["POST"])
# def signup():
#     data = request.json
#     email = data.get("email")
#     password = data.get("password")

#     if not email or not password:
#         return jsonify({"error": "Missing email or password"}), 400

#     existing_user = User.query.filter_by(email=email).first()
#     if existing_user:
#         return jsonify({"error": "Email already registered"}), 400

#     hashed_password = generate_password_hash(password)
#     user = User(email=email, password_hash=hashed_password)
#     db.session.add(user)
#     db.session.commit()

#     session["user"] = email
#     return jsonify({"message": "Signup successful", "email": email})


# @app.route("/login", methods=["POST"])
# def login():
#     data = request.json
#     email = data.get("email")
#     password = data.get("password")

#     user = User.query.filter_by(email=email).first()
#     if not user or not user.check_password(password):
#         return jsonify({"error": "Invalid credentials"}), 401

#     session["user"] = email
#     return jsonify({
#         "email": user.email,
#         "name": "User"
#     })
    


@app.route("/score", methods=["POST"])
def score_resume():
    data = request.json
    resume_text = data.get("resume", "")
    filename = data.get("filename", "Unknown")
    jd_text = data.get("job_description", "")
    email = data.get("email")

    if not email:
        return jsonify({"error": "Email is required"}), 400

    # 🔍 Fetch user from DB
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    if user.matches_left <= 0:
        return jsonify({"message": "Resume limit reached. Please upgrade."}), 429

    # ✅ Extract skills and compute score
    resume_skills = extract_skills(resume_text)
    jd_skills = extract_skills(jd_text)

    matched = list(set(resume_skills).intersection(jd_skills))
    missing = list(set(jd_skills) - set(resume_skills))
    score = round((len(matched) / len(jd_skills)) * 100, 2) if jd_skills else 0

    # 📉 Decrement match count
    user.matches_left -= 1

    # 📝 Save history
    print(f"User: {user.email}, Resume Name: {filename}, Score: {score}")
    history_entry = MatchHistory(
        user_id=user.id,
        resume_name=filename,
        score=score,
        timestamp=datetime.utcnow()
    )
    db.session.add(history_entry)
    db.session.commit()

    return jsonify({
        "match_score": score,
        "matched_skills": matched,
        "missing_skills": missing
    })

# @app.route("/score", methods=["POST"])
# def score_resume():
#     data = request.json
#     resume_text = data.get("resume", "")
#     filename = data.get("filename", "Unknown")  # Add this in frontend later
#     jd_text = data.get("job_description", "")
#     email = data.get("email")

#     if not email:
#         return jsonify({"error": "Email is required"}), 400

#     # Load and check usage
#     usage = load_usage()
#     user_data = usage.get(email, {"matches_left": 0, "history": []})


#     # Handle legacy or missing data
#     matches_left = (
#         user_data.get("matches_left")
#         if isinstance(user_data, dict)
#         else max(0, 10 - user_data)  # Legacy format fallback
#     )

#     if matches_left <= 0:
#         return jsonify({"message": "Resume limit reached. Please upgrade."}), 429

#     # Decrement and save usage
#     if isinstance(user_data, dict):
#         usage[email]["matches_left"] = matches_left - 1
#     else:
#         # legacy: convert from numeric count to dict
#         usage[email] = {"matches_left": 9 - user_data}
#     # Skill extraction
#     resume_skills = extract_skills(resume_text)
#     jd_skills = extract_skills(jd_text)

#     matched = list(set(resume_skills).intersection(jd_skills))
#     missing = list(set(jd_skills) - set(resume_skills))
#     score = round((len(matched) / len(jd_skills)) * 100, 2) if jd_skills else 0
        
#     user_data["matches_left"] -= 1
#     user_data.setdefault("history", []).append({
#         "resume_name": filename,
#         "score": score,
#         "timestamp": datetime.utcnow().isoformat()
#     })
#     usage[email] = user_data
#     save_usage(usage)



#     return jsonify({
#         "match_score": score,
#         "matched_skills": matched,
#         "missing_skills": missing
#     })

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
                    'File Name': filename,
                    'Match Score': score,
                    'Matched Skills': ", ".join(matched),
                    'Missing Skills': ", ".join(missing)
                })

        # 🧠 Store results in session or re-render as HTML with download option
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=["File Name", "Match Score", "Matched Skills", "Missing Skills"])
        writer.writeheader()
        writer.writerows(results)
        csv_data = output.getvalue()

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
        <form method="post" action="/download-csv">
            <input type="hidden" name="csv" value="{{ csv }}">
            <button type="submit">Download CSV</button>
        </form>
        <br><br>
        <a href="/">Upload More</a>
        """, results=results, csv=csv_data)

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
@app.route('/download-csv', methods=['POST'])
def download_csv():
    csv_data = request.form.get("csv")
    if not csv_data:
        return "No CSV data provided", 400

    return send_file(
        io.BytesIO(csv_data.encode()),
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

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    user.matches_left = user.matches_left + 500  # Upgrade plan
    db.session.commit()

    return jsonify({"message": "Plan upgraded. 500 matches unlocked."})

import stripe

stripe.api_key = "sk_test_51RiFrBH2vTKHOvUiqVCzKGk9p44YnovviLHKeea2DAp4ZBS1k5Cy5UFSXBLbFDcJftZjA5XdXhayTYCdQiLN99iE00pf8ZihrH"  # Use your secret key

@app.route("/create-checkout-session", methods=["POST"])
def create_checkout_session():
    data = request.json
    email = data.get("email")
    plan = data.get("plan")

    if not email or not plan:
        return jsonify({"error": "Email and plan are required"}), 400

    # 🎯 Define pricing for each plan
    plan_options = {
        "100": {"amount": 9900, "name": "100 Resume Matches Plan", "matches": 100},
        "500": {"amount": 19900, "name": "500 Resume Matches Plan", "matches": 500},
        "unlimited": {"amount": 49900, "name": "Unlimited Resume Matches Plan", "matches": 1000},
    }

    if plan not in plan_options:
        return jsonify({"error": "Invalid plan selected"}), 400

    plan_data = plan_options[plan]

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="payment",
            customer_email=email,
            line_items=[
                {
                    "price_data": {
                        "currency": "inr",
                        "product_data": {"name": plan_data["name"]},
                        "unit_amount": plan_data["amount"],
                    },
                    "quantity": 1,
                }
            ],
            metadata={
                "email": email,
                "matches": plan_data["matches"],
                "plan_id": plan,
            },
            success_url="https://resume-matcher-ai4.vercel.app/payment-success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url="https://resume-matcher-ai4.vercel.app/payment-cancelled",
        )
        return jsonify({"url": session.url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/profile", methods=["GET"])
def profile():
    email = request.args.get("email")
    if not email:
        return jsonify({"error": "Email is required"}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Fetch match history
    history = [
        {
            "resume_name": h.resume_name,
            "score": h.score,
            "timestamp": h.timestamp.isoformat() if h.timestamp else None,
        }
        for h in user.match_history
    ]

    return jsonify({
        "email": user.email,
        "remaining": user.matches_left,
        "used": len(history),
        "history": history
    })

@app.route("/google-login", methods=["POST"])
def google_login():
    try:
        data = request.json
        email = data.get("email")
        name = data.get("name", "User")

        if not email:
            return jsonify({"error": "Email is required"}), 400

        user = User.query.filter_by(email=email).first()

        if not user:
            # Create user without password for Google auth
            user = User(
                email=email, 
                matches_left=10,
                auth_provider='google'
            )
            db.session.add(user)
            db.session.commit()

        # Return user data
        return jsonify({
            "email": user.email,
            "name": name,
            "remaining": user.matches_left,
            "history": [h.to_dict() for h in user.match_history] if hasattr(user, 'match_history') else [],
        })

    except Exception as e:
        print(f"Error in google_login: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

from flask import jsonify, request, session
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from flask_cors import CORS
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import uuid

@app.route("/signup", methods=["POST"])
def signup():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Missing email or password"}), 400

    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({"error": "Email already registered"}), 400

    # Generate verification token with expiration (24 hours)
    verification_token = str(uuid.uuid4())
    token_expiration = datetime.utcnow() + timedelta(hours=24)

    hashed_password = generate_password_hash(password)
    user = User(
        email=email,
        password_hash=hashed_password,
        is_verified=False,
        verification_token=verification_token,
        token_expiration=token_expiration
    )
    
    db.session.add(user)
    db.session.commit()

    # Send verification email
    verification_url = f"https://resume-matcher-ai4.vercel.app/verify-email?token={verification_token}"
    msg = Message(
        subject="Verify Your Email",
        recipients=[email],
        html=f"""
        <h2>Please verify your email</h2>
        <p>Click the link below to verify your email address:</p>
        <a href="{verification_url}">{verification_url}</a>
        <p>This link will expire in 24 hours.</p>
        """
    )
    mail.send(msg)

    return jsonify({
        "message": "Signup successful. Please check your email to verify your account.",
        "email": email
    })


@app.route("/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Invalid credentials"}), 401

    if not user.is_verified:
        return jsonify({
            "error": "Email not verified",
            "message": "Please check your email for the verification link",
            "resend_verification": True
        }), 403

    session["user"] = email
    return jsonify({
        "email": user.email,
        "name": "User"
    })


@app.route("/verify-email", methods=["POST"])
def verify_email():
    token = request.json.get("token")
    if not token:
        return jsonify({"error": "Token is required"}), 400

    user = User.query.filter_by(verification_token=token).first()
    
    # Check if token exists and isn't expired
    if not user or user.token_expiration < datetime.utcnow():
        return jsonify({"error": "Invalid or expired token"}), 400

    user.is_verified = True
    user.verification_token = None
    user.token_expiration = None
    db.session.commit()

    return jsonify({"message": "Email verified successfully"})


@app.route("/resend-verification", methods=["POST"])
def resend_verification():
    email = request.json.get("email")
    if not email:
        return jsonify({"error": "Email is required"}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    if user.is_verified:
        return jsonify({"error": "Email is already verified"}), 400

    # Generate new token and expiration
    new_token = str(uuid.uuid4())
    new_expiration = datetime.utcnow() + timedelta(hours=24)

    user.verification_token = new_token
    user.token_expiration = new_expiration
    db.session.commit()

    # Send new verification email
    verification_url = f"http://your-frontend-domain.com/verify-email?token={new_token}"
    msg = Message(
        subject="Verify Your Email",
        recipients=[email],
        html=f"""
        <h2>Please verify your email</h2>
        <p>Click the link below to verify your email address:</p>
        <a href="{verification_url}">{verification_url}</a>
        <p>This link will expire in 24 hours.</p>
        """
    )
    mail.send(msg)

    return jsonify({"message": "Verification email resent successfully"})
        
if __name__ == '__main__':
    app.run(debug=True)




