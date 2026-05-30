from fastapi.middleware.cors import CORSMiddleware
import logging
import shutil
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, BackgroundTasks, Depends
import google.generativeai as genai
import io
import json
import string
from sqlalchemy.orm import Session
from fastapi.staticfiles import StaticFiles
from gtts import gTTS
from pydantic import BaseModel, EmailStr
from typing import Optional
from PIL import Image as PILImage
from db import SessionLocal
from models import Document, User, Feedback
import pytesseract
import os
if os.name == 'nt':
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
import cv2
import re
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

# Configure Gemini SDK
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY.strip().strip("'\""))
    logger.info("Gemini SDK successfully configured.")
else:
    logger.warning("GEMINI_API_KEY not found in environment variables. Gemini calls might fail.")

# Database Session Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI()

@app.on_event("startup")
def on_startup():
    from models import Base
    from db import engine
    Base.metadata.create_all(bind=engine)
    logger.info("MySQL tables verified/created on startup.")
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
    user_email: Optional[str] = None
    app_experience: Optional[str] = "Excellent"
    voice_guidance_helpful: Optional[str] = "Yes"
    recommend_app: Optional[str] = "Yes"
    additional_comments: Optional[str] = None
    rating: Optional[str] = None
    feedback_text: Optional[str] = None

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

# ---------------- TTS TEXT CLEANING HELPER ----------------
def clean_text_for_tts(text: str) -> str:
    if not text:
        return ""
    
    # 1. Split text into lines
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Remove markdown bold/italic/headers
        line = re.sub(r'[*_#`~]', '', line)
        
        # Remove leading bullets (- , * , + , •) and leading whitespace
        line = re.sub(r'^[\-\*\+\•\s]+', '', line)
        
        # Remove numbering prefixes at the start of the line like: "1.", "2)", "1. ", "2) ", "1 - "
        line = re.sub(r'^\d+[\.\)\-\:\s]+', '', line)
        
        line = line.strip()
        if not line:
            continue
            
        # Ensure the line ends with a period for punctuation and natural flow pause
        if not line.endswith(('.', '!', '?', '।')):
            line += '.'
            
        cleaned_lines.append(line)
        
    # Join with space to preserve sentence flow and pauses
    cleaned_text = " ".join(cleaned_lines)
    
    # Normalize spaces
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
    return cleaned_text

# ---------------- AI FUNCTION ----------------
def generate_guidance(text: str, language: str) -> str:

    prompt = f"""
    Analyze this form text and give proper, clear guidance for filling the form.

    Form Text:
    {text}

    IMPORTANT:
    Respond completely in the {language} language.
    You MUST write the response entirely in the native script of {language} (Devanagari for Hindi, Telugu script for Telugu, Tamil script for Tamil, English for English).
    Do NOT use English script/alphabet for regional languages, except for field labels as instructed below.

    Requirements:
    1. Provide short, simple, step-by-step numbered instructions.
    2. Use simple, natural, and polite spoken words suitable for rural and old-age users.
    3. Crucial for Highlight Synchronization: Whenever you mention or refer to a specific form field or box that the user needs to fill out, you MUST explicitly mention the field's printed English name in parentheses next to it.
       Example in Telugu: "మొదటి పెట్టెలో మీ పేరు (Name) ని నమోదు చేయండి."
       Example in Hindi: "कृपया अपना मोबाइल नंबर (Phone) या (Mobile) यहाँ दर्ज करें।"
       Example in Tamil: "உங்கள் மின்னஞ்சல் முகவரியை (Email) பெட்டியில் எழுதவும்."
    4. Focus on guiding the user step-by-step through the main fields like Name, Email, Phone, Address, Date of Birth (DOB), Signature, Account Number, etc.
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

# ---------------- BACKGROUND MEDIA GENERATION ----------------
async def generate_media_background(
    filename: str,
    file_path: str,
    guidance_text: str,
    extracted_text: str,
    language: str
):
    try:
        audio_filename = filename + ".mp3"
        audio_path = os.path.join(AUDIO_FOLDER, audio_filename)
        
        lang_code = "en"
        if language == "Telugu":
            lang_code = "te"
        elif language == "Hindi":
            lang_code = "hi"
        elif language == "Tamil":
            lang_code = "ta"
            
        cleaned_guidance = clean_text_for_tts(guidance_text)
        short_text = cleaned_guidance[:1500]
        
        # Edge-TTS voice generation
        try:
            import edge_tts
            voice_map = {
                "Telugu": "te-IN-MohanNeural",
                "Tamil": "ta-IN-ValluvarNeural",
                "Hindi": "hi-IN-MadhurNeural",
                "English": "en-US-AvaNeural"
            }
            voice = voice_map.get(language, "en-US-AvaNeural")
            communicate = edge_tts.Communicate(short_text, voice)
            await communicate.save(audio_path)
            logger.info(f"Edge-TTS voice successfully generated in background: {voice}")
        except Exception as e_edge:
            logger.warning(f"edge-tts failed in background: {e_edge}, falling back to gTTS")
            from gtts import gTTS
            tts = gTTS(text=short_text, lang=lang_code)
            tts.save(audio_path)
            
        # PDF generation
        generate_pdf_report(
            filename,
            extracted_text,
            guidance_text,
            file_path
        )
        logger.info(f"Background media generation completed for {filename}")
        
    except Exception as e:
        logger.exception(f"Background media generation failed for {filename}: {e}")


# ---------------- DOCUMENT UPLOAD ----------------

@app.post("/upload-document")
async def upload_document(
    background_tasks: BackgroundTasks,
    user_email: str = Form(...),
    language: str = Form(None),
    file: UploadFile = File(...)
):
    try:
        filename = f"{int(time.time())}_{file.filename}"
        file_path = os.path.join(UPLOAD_FOLDER, filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        logger.info(f"FILE UPLOADED: {file.filename}")
        logger.info(f"LANGUAGE RECEIVED: {language}")

        extracted_text = ""
        guidance = "Unable to process document."

        # Handle image processing via Gemini 1.5 Flash
        if file.filename.lower().endswith((".png", ".jpg", ".jpeg")):
            try:
                # Open image using Pillow
                image = PILImage.open(file_path)
                
                model = genai.GenerativeModel("gemini-1.5-flash")
                prompt = f"""
                You are FormSahayak, a multilingual AI designed to help old-age people fill out official forms.
                Analyze this form image:
                1. Perform high-precision OCR to extract visible fields.
                2. Translate key fields into {language if language else 'English'}.
                3. Write friendly, simplified, step-by-step guidelines separated by newlines.
                
                Return JSON format with keys "guidance" and "extracted_text".
                """
                response = model.generate_content([image, prompt])
                response_text = response.text
                
                # Clean JSON markdown blocks if present
                if "```json" in response_text:
                    response_text = response_text.split("```json")[1].split("```")[0].strip()
                elif "```" in response_text:
                    response_text = response_text.split("```")[1].split("```")[0].strip()
                
                try:
                    data = json.loads(response_text)
                    guidance = data.get("guidance", "Form uploaded successfully.")
                    extracted_text = data.get("extracted_text", "")
                except Exception as e_json:
                    logger.warning(f"Failed to parse JSON directly from Gemini: {e_json}. Using raw text as guidance.")
                    guidance = response_text
                    extracted_text = "OCR Text processed via Multimodal Gemini."

            except Exception as e_gemini:
                logger.exception("Gemini API call failed")
                raise Exception(f"Gemini AI processing failed: {str(e_gemini)}")

        elif file.filename.lower().endswith(".pdf"):
            extracted_text = "PDF uploaded"
            guidance = "PDF forms processing not fully supported via Gemini multimodal currently. Please upload images."

        # Predict immediate URLs for instant response
        file_url = f"https://formsahayak-backend.onrender.com/uploads/{filename}"
        audio_url = f"https://formsahayak-backend.onrender.com/audio/{filename}.mp3"
        pdf_url = f"https://formsahayak-backend.onrender.com/pdfs/{filename}.pdf"

        # Construct safe guidance steps for UI mapping compatibilities
        guidance_steps = []
        raw_steps = [s.strip() for s in re.split(r'[\n\.]+', guidance) if s.strip()]
        for idx, step in enumerate(raw_steps):
            guidance_steps.append({
                "step_index": idx + 1,
                "step_text": step,
                "matched_fields": ["General"],
                "ocr_boxes": []
            })

        # Save record to database
        india = timezone("Asia/Kolkata")
        current_time = datetime.now(india)

        db = SessionLocal()
        new_doc = Document(
            user_email=user_email,
            file_name=filename,
            file_path=file_url,
            extracted_text=extracted_text,
            guidance_text=guidance,
            audio_path=audio_url,
            pdf_path=pdf_url,
            created_at=current_time
        )
        db.add(new_doc)
        db.commit()
        db.close()

        # Add media compilation tasks to BackgroundTasks
        background_tasks.add_task(
            generate_media_background,
            filename=filename,
            file_path=file_path,
            guidance_text=guidance,
            extracted_text=extracted_text,
            language=language if language else 'English'
        )

        return {
            "message": "Uploaded & processed successfully",
            "guidance": guidance,
            "guidance_text": guidance,
            "audio_file": audio_url,
            "audio_path": audio_url,
            "pdf_file": pdf_url,
            "pdf_path": pdf_url,
            "ocr_boxes": [],
            "extracted_text": extracted_text,
            "uploaded_image_path": file_url,
            "guidance_steps": guidance_steps
        }

    except Exception as e:
        logger.exception("Upload processing failed")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


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

        history.append({
            "id": doc.id,
            "file_name": doc.file_name,
            "file_url": doc.file_path,
            "extracted_text": doc.extracted_text,
            "guidance_text": doc.guidance_text,
            "audio_path": doc.audio_path,
            "pdf_path": doc.pdf_path,
            "created_at": str(doc.created_at)
        })

    db.close()

    return {
        "history": history
    }

# ---------------- FEEDBACK API ----------------

def process_feedback_submission(data: FeedbackRequest):
    print("FEEDBACK RECEIVED")
    india = timezone("Asia/Kolkata")
    current_time = datetime.now(india)

    db = SessionLocal()

    # Combine text details for additional_comments as a robust fallback
    combined_comments = data.additional_comments or ""
    if data.feedback_text:
        combined_comments = f"Feedback: {data.feedback_text}. {combined_comments}".strip()
    if data.rating:
        combined_comments = f"Rating: {data.rating}. {combined_comments}".strip()

    feedback = Feedback(
        user_email=data.user_email,
        app_experience=data.app_experience or "",
        voice_guidance_helpful=data.voice_guidance_helpful or "",
        recommend_app=data.recommend_app or "",
        additional_comments=combined_comments,
        rating=data.rating or "",
        feedback_text=data.feedback_text or "",
        created_at=current_time
    )

    db.add(feedback)
    db.commit()
    db.close()

    return {
        "message": "Feedback submitted successfully"
    }

@app.post("/submit-feedback")
def submit_feedback(data: FeedbackRequest):
    return process_feedback_submission(data)

@app.post("/submit-feedback/")
def submit_feedback_slash(data: FeedbackRequest):
    return process_feedback_submission(data)

@app.post("/feedback")
def submit_feedback_alias(data: FeedbackRequest):
    return process_feedback_submission(data)

@app.post("/feedback/")
def submit_feedback_alias_slash(data: FeedbackRequest):
    return process_feedback_submission(data)



# ---------------- FORM DETAILS API ----------------
@app.get("/form-details/{doc_id}")
def get_form_details(doc_id: int):

    db = SessionLocal()

    doc = db.query(Document).filter(
        Document.id == doc_id
    ).first()

    if not doc:
        raise HTTPException(
            status_code=404,
            detail="Form not found"
        )

    db.close()

    return {
        "id": doc.id,
        "file_name": doc.file_name,
        "file_url": doc.file_path,
        "extracted_text": doc.extracted_text,
        "guidance_text": doc.guidance_text,
        "audio_path": doc.audio_path,
        "pdf_path": doc.pdf_path,
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


# ---------------- FORGOT PASSWORD API ----------------

@app.post("/forgot-password")
def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(
            status_code=404, 
            detail="Email address not found. Please register first."
        )
    
    try:
        temp_pass = "".join(random.choices(string.ascii_letters + string.digits, k=8))
        user.password = temp_pass # Plain text to align with the database's existing login and signup schema
        db.commit()
        return {
            "status": "success",
            "message": f"A temporary password has been successfully generated for {request.email}. (Demo Password: {temp_pass})"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error resetting password: {str(e)}")


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

    try:
        import os
        import requests
        
        brevo_api_key = os.getenv("BREVO_API_KEY", "").strip().strip("'\"")
        resend_api_key = os.getenv("RESEND_API_KEY", "").strip().strip("'\"")
        
        sender_email = os.getenv("SENDER_EMAIL", EMAIL_ADDRESS)
        
        if brevo_api_key:
            logger.info(f"Attempting to send OTP via Brevo. Receiver: {data.email}")
            logger.info(f"Brevo API key length: {len(brevo_api_key)}")
            logger.info(f"Brevo API key starts with: {brevo_api_key[:7] if len(brevo_api_key) >= 7 else brevo_api_key}...")
            
            url = "https://api.brevo.com/v3/smtp/email"
            payload = {
                "sender": {"name": "Formsahayak", "email": sender_email},
                "to": [{"email": data.email}],
                "subject": "Reset Password OTP",
                "htmlContent": f"<p>Your password reset OTP is <strong>{otp}</strong>. It is valid for 10 minutes.</p>"
            }
            headers = {
                "api-key": brevo_api_key,
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            response = requests.post(url, headers=headers, json=payload, timeout=15)
            
            if response.status_code not in (200, 201):
                logger.error(f"Brevo API error response: {response.text}")
                raise Exception(f"Brevo API failed with status {response.status_code}: {response.text}")
                
            logger.info("Brevo API email sent successfully!")
            
        else:
            api_key_to_use = resend_api_key if resend_api_key else "re_your_api_key_here"
            logger.info(f"Attempting to send OTP via Resend. Receiver: {data.email}")
            logger.info(f"Resend API key length: {len(api_key_to_use)}")
            logger.info(f"Resend API key starts with: {api_key_to_use[:7] if len(api_key_to_use) >= 7 else api_key_to_use}...")
            
            response = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {api_key_to_use}",
                    "Content-Type": "application/json"
                },
                json={
                    "from": "Formsahayak <onboarding@resend.dev>",
                    "to": [data.email],
                    "subject": "Reset Password OTP",
                    "html": f"<p>Your password reset OTP is <strong>{otp}</strong>. It is valid for 10 minutes.</p>"
                },
                timeout=15
            )
            
            if response.status_code != 200:
                logger.error(f"Resend API error response: {response.text}")
                raise Exception(f"Resend API failed with status {response.status_code}: {response.text}")

            logger.info("Resend API email sent successfully!")

    except Exception as e:
        logger.exception("Send OTP execution failed")
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
            detail="Document not found"
        )

    db.delete(doc)

    db.commit()

    db.close()

    return {
        "message": "History deleted successfully"
         
    }