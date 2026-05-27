from fastapi.middleware.cors import CORSMiddleware
import logging
import shutil
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from gtts import gTTS
from pydantic import BaseModel, EmailStr
from PIL import Image as PILImage
from db import SessionLocal
from models import Document, User, Feedback
import re
import os
import time
from dotenv import load_dotenv
from groq import Groq
from datetime import datetime
from pytz import timezone
import random
import smtplib
from email.mime.text import MIMEText
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Image

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

logger = logging.getLogger(__name__)

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise Exception("GROQ_API_KEY not found")

client = Groq(api_key=GROQ_API_KEY)


app = FastAPI()
app.mount("/audio", StaticFiles(directory="audio"), name="audio")

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_FOLDER = "uploads"
AUDIO_FOLDER = "audio"
PDF_FOLDER = "pdfs"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(AUDIO_FOLDER, exist_ok=True)
os.makedirs(PDF_FOLDER, exist_ok=True)

app.mount("/audio", StaticFiles(directory="audio"), name="audio")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/pdfs", StaticFiles(directory="pdfs"), name="pdfs")

# ---------------- OTP STORAGE ----------------

otp_storage = {}

EMAIL_ADDRESS = "praneethyamanuri2@gmail.com"
EMAIL_PASSWORD = "cizj vdth xkwx iisl"

# ---------------- SIGNUP ----------------

class Signup(BaseModel):
    name: str
    email: EmailStr
    password: str
    confirm_password: str


def validate_password(password: str):

    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    if not re.search(r"[A-Z]", password):
        raise HTTPException(status_code=400, detail="Must contain uppercase letter")

    if not re.search(r"[a-z]", password):
        raise HTTPException(status_code=400, detail="Must contain lowercase letter")

    if not re.search(r"[0-9]", password):
        raise HTTPException(status_code=400, detail="Must contain number")

    if not re.search(r"[!@#$%^&*]", password):
        raise HTTPException(status_code=400, detail="Must contain special character")


@app.post("/signup")
def signup(user: Signup):

    if user.password != user.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    validate_password(user.password)

    db = SessionLocal()

    existing_user = db.query(User).filter(User.email == user.email).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(
        name=user.name,
        email=user.email,
        password=user.password,
        phone="",
        language="English",
        profile_image=""
    )

    db.add(new_user)
    db.commit()
    db.close()

    return {"message": "User registered successfully"}

# ---------------- LOGIN ----------------

class Login(BaseModel):
    email: EmailStr
    password: str

# ---------------- FEEDBACK MODEL ----------------

class FeedbackRequest(BaseModel):
    user_email: str
    app_experience: str
    voice_guidance_helpful: str
    recommend_app: str
    additional_comments: str

@app.post("/login")
def login(user: Login):

    db = SessionLocal()

    existing_user = db.query(User).filter(User.email == user.email).first()

    if not existing_user:
        raise HTTPException(status_code=400, detail="Invalid email")

    if existing_user.password != user.password:
        raise HTTPException(status_code=400, detail="Invalid password")

    db.close()

    return {
        "message": "Login successful",
        "user": {
            "name": existing_user.name,
            "email": existing_user.email
        }
    }


# ---------------- CHANGE PASSWORD MODEL ----------------

class ChangePasswordRequest(BaseModel):
    email: str
    new_password: str
    confirm_password: str

# ---------------- FORGOT PASSWORD MODEL ----------------

class ForgotPasswordRequest(BaseModel):
    email: str

# ---------------- VERIFY OTP MODEL ----------------

class VerifyOtpRequest(BaseModel):
    email: str
    otp: str

# ---------------- RESET PASSWORD MODEL ----------------

class ResetPasswordRequest(BaseModel):
    email: str
    new_password: str
    confirm_password: str

# ---------------- AI FUNCTION ----------------

def generate_guidance(text: str) -> str:

    prompt = f"""
    Analyze this form text and give proper guidance for filling the form.

    Form Text:
    {text}

    Give short numbered instructions.
    """

    try:

        response = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model="llama-3.3-70b-versatile"
        )

        return response.choices[0].message.content

    except Exception as e:

        logger.exception("Groq AI failed")

        return str(e)

def generate_pdf_report(
    filename,
    extracted_text,
    guidance_text,
    image_path
):

    pdf_filename = filename + ".pdf"

    pdf_path = os.path.join(
        PDF_FOLDER,
        pdf_filename
    )

    doc = SimpleDocTemplate(pdf_path)

    styles = getSampleStyleSheet()

    elements = []

    elements.append(
        Paragraph(
            "FormSahayak AI Report",
            styles['Title']
        )
    )

    elements.append(Spacer(1, 20))

    pdf_image = Image(
        image_path,
        width=400,
        height=500
    )

    elements.append(pdf_image)

    elements.append(Spacer(1, 20))

    elements.append(
        Paragraph(
            f"<b>File Name:</b> {filename}",
            styles['BodyText']
        )
    )

    elements.append(Spacer(1, 10))

    elements.append(
        Paragraph(
            "<b>Extracted Text:</b>",
            styles['Heading2']
        )
    )

    elements.append(
        Paragraph(
            extracted_text,
            styles['BodyText']
        )
    )

    elements.append(Spacer(1, 15))

    elements.append(
        Paragraph(
            "<b>AI Guidance:</b>",
            styles['Heading2']
        )
    )

    elements.append(
        Paragraph(
            guidance_text,
            styles['BodyText']
        )
    )

    doc.build(elements)

    return pdf_path

# ---------------- DOCUMENT UPLOAD ----------------

@app.post("/upload-document")
async def upload_document(
    user_email: str = Form(...),
    language: str = Form(None),
    file: UploadFile = File(...)
):

    filename = f"{int(time.time())}_{file.filename}"

    file_path = os.path.join(UPLOAD_FOLDER, filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    extracted_text = ""

    if file.filename.lower().endswith((".png", ".jpg", ".jpeg")):

        try:

            import base64

            with open(file_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode("utf-8")

            vision_response = client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Explain this form in very simple step-by-step instructions for common Indian people, rural users, and old-age users. Use simple English and short points."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ]
            )

            extracted_text = vision_response.choices[0].message.content

        except Exception as e:

            logger.exception("OCR failed")

            extracted_text = ""

    elif file.filename.lower().endswith(".pdf"):

        extracted_text = "PDF uploaded"

    if extracted_text.strip() == "":

        guidance_text = "Unable to detect text clearly."

    else:

        guidance_text = generate_guidance(extracted_text)

   
    audio_filename = filename + ".mp3"

    audio_path = os.path.join(
        AUDIO_FOLDER,
        audio_filename
    )

    pdf_path = generate_pdf_report(
        filename,
        extracted_text,
        guidance_text,
        file_path
    )
        
    try:

        tts = gTTS(text=guidance_text, lang="en")

        tts.save(audio_path)

    except Exception as e:

        logger.exception("Audio generation failed")

        print(e)

        audio_path = ""

    india = timezone("Asia/Kolkata")
    current_time = datetime.now(india)

    db = SessionLocal()

    new_doc = Document(
        user_email=user_email,
        file_name=filename,
        file_path=file_path,
        extracted_text=extracted_text,
        guidance_text=guidance_text,
        audio_path=audio_path,
        pdf_path=pdf_path,
        created_at=current_time
    )

    db.add(new_doc)

    db.commit()

    db.close()

    audio_url = ""

    if audio_path != "":
        audio_url = f"https://formsahayak-backend.onrender.com/{audio_path.replace(chr(92), '/')}"

    return {
        "message": "Uploaded & processed successfully",
        "guidance": guidance_text,
        "audio_file": audio_url,
        "pdf_file": f"https://formsahayak-backend.onrender.com/{pdf_path.replace(chr(92), '/')}"
    }

# ---------------- PROFILE API ----------------

@app.get("/profile/{email}")
def get_profile(email: str):

    db = SessionLocal()

    user = db.query(User).filter(User.email == email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    profile_image_url = ""

    if user.profile_image:
        profile_image_url = f"https://formsahayak-backend.onrender.com/{user.profile_image.replace(chr(92), '/')}"

    return {
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "language": user.language,
        "profile_image": profile_image_url
    }

@app.post("/update-profile")
async def update_profile(
    email: str = Form(...),
    phone: str = Form(...),
    language: str = Form(...),
    profile_image: UploadFile = File(None)
):

    db = SessionLocal()

    user = db.query(User).filter(User.email == email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    image_path = user.profile_image

    if profile_image:

        filename = f"profile_{int(time.time())}_{profile_image.filename}"

        save_path = os.path.join(UPLOAD_FOLDER, filename)

        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(profile_image.file, buffer)

        image_path = save_path

    user.phone = phone
    user.language = language
    user.profile_image = image_path

    db.commit()
    db.close()

    profile_image_url = ""

    if image_path:
        profile_image_url = f"https://formsahayak-backend.onrender.com/{image_path.replace(chr(92), '/')}"

    return {
        "message": "Profile updated successfully",
        "profile_image": profile_image_url
    }

# ---------------- HISTORY API ----------------

@app.get("/history/{email}")
def get_history(email: str):

    db = SessionLocal()

    docs = db.query(Document).filter(
        Document.user_email == email
    ).order_by(Document.id.desc()).all()

    history = []

    for doc in docs:

        audio_url = ""

        if doc.audio_path:
            audio_url = f"https://formsahayak-backend.onrender.com/{doc.audio_path.replace(chr(92), '/')}"

        history.append({
        "id": doc.id,
        "file_name": doc.file_name,
        "file_url": f"https://formsahayak-backend.onrender.com/uploads/{doc.file_name}",
        "extracted_text": doc.extracted_text,
        "guidance_text": doc.guidance_text,
        "audio_path": audio_url,
        "created_at": str(doc.created_at)
    })

    db.close()

    return {
        "history": history
    }


# ---------------- FEEDBACK API ----------------

@app.post("/submit-feedback")
def submit_feedback(data: FeedbackRequest):

    india = timezone("Asia/Kolkata")
    current_time = datetime.now(india)

    db = SessionLocal()

    feedback = Feedback(
        user_email=data.user_email,
        app_experience=data.app_experience,
        voice_guidance_helpful=data.voice_guidance_helpful,
        recommend_app=data.recommend_app,
        additional_comments=data.additional_comments,
        created_at=current_time
    )

    db.add(feedback)
    db.commit()
    db.close()

    return {
        "message": "Feedback submitted successfully"
    }



# ---------------- FORM DETAILS API ----------------

@app.get("/form-details/{doc_id}")
def get_form_details(doc_id: int):

    db = SessionLocal()

    doc = db.query(Document).filter(Document.id == doc_id).first()

    if not doc:
        raise HTTPException(status_code=404, detail="Form not found")

    file_url = f"https://formsahayak-backend.onrender.com/uploads/{doc.file_name}"

    audio_url = ""

    if doc.audio_path:
        audio_url = f"https://formsahayak-backend.onrender.com/{doc.audio_path.replace(chr(92), '/')}"

    db.close()

    return {
        "id": doc.id,
        "file_name": doc.file_name,
        "file_url": file_url,
        "extracted_text": doc.extracted_text,
        "guidance_text": doc.guidance_text,
        "audio_path": audio_url,
        "created_at": str(doc.created_at)
    }


# ---------------- CHANGE PASSWORD API ----------------

@app.post("/change-password")
def change_password(data: ChangePasswordRequest):

    if data.new_password != data.confirm_password:
        raise HTTPException(
            status_code=400,
            detail="Passwords do not match"
        )

    validate_password(data.new_password)

    db = SessionLocal()

    user = db.query(User).filter(
        User.email == data.email
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    user.password = data.new_password

    db.commit()
    db.close()

    return {
        "message": "Password updated successfully"
    }


# ---------------- SEND OTP API ----------------

@app.post("/send-otp")
def send_otp(data: ForgotPasswordRequest):

    db = SessionLocal()

    user = db.query(User).filter(
        User.email == data.email
    ).first()

    db.close()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Email not registered"
        )

    otp = str(random.randint(1000, 9999))

    otp_storage[data.email] = otp

    subject = "FormSahayak OTP Verification"

    body = f"Your FormSahayak OTP is: {otp}"

    msg = MIMEText(body)

    msg["Subject"] = subject
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = data.email

    try:

        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)


        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)

        server.sendmail(
            EMAIL_ADDRESS,
            data.email,
            msg.as_string()
        )

        server.quit()

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    return {
        "message": "OTP sent successfully"
    }


# ---------------- VERIFY OTP API ----------------

@app.post("/verify-otp")
def verify_otp(data: VerifyOtpRequest):

    stored_otp = otp_storage.get(data.email)

    if not stored_otp:
        raise HTTPException(
            status_code=404,
            detail="OTP not found"
        )

    if stored_otp != data.otp:
        raise HTTPException(
            status_code=400,
            detail="Invalid OTP"
        )

    return {
        "message": "OTP verified successfully"
    }


# ---------------- RESET PASSWORD API ----------------

@app.post("/reset-password")
def reset_password(data: ResetPasswordRequest):

    if data.new_password != data.confirm_password:
        raise HTTPException(
            status_code=400,
            detail="Passwords do not match"
        )

    validate_password(data.new_password)

    db = SessionLocal()

    user = db.query(User).filter(
        User.email == data.email
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    user.password = data.new_password

    db.commit()
    db.close()

    otp_storage.pop(data.email, None)

    return {
        "message": "Password reset successful"
    }


# ---------------- DELETE HISTORY API ----------------

@app.delete("/delete-history/{doc_id}")
def delete_history(doc_id: int):

    db = SessionLocal()

    doc = db.query(Document).filter(
        Document.id == doc_id
    ).first()

    if not doc:
        raise HTTPException(
            status_code=404,
            detail="History item not found"
        )

    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    if doc.audio_path and os.path.exists(doc.audio_path):
        os.remove(doc.audio_path)

    db.delete(doc)

    db.commit()

    db.close()

    return {
        "message": "History deleted successfully"
    }

@app.get("/history/{email}")

def get_history(email: str):

    connection = get_db_connection()

    cursor = connection.cursor(pymysql.cursors.DictCursor)

    query = """
    SELECT * FROM documents
    WHERE user_email=%s
    ORDER BY id DESC
    """

    cursor.execute(query, (email,))

    documents = cursor.fetchall()

    cursor.close()

    connection.close()

    return documents