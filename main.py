from fastapi.middleware.cors import CORSMiddleware
import logging
import shutil
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, BackgroundTasks, Depends, Security
import io
import json
import string
from sqlalchemy.orm import Session
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from gtts import gTTS
from pydantic import BaseModel, EmailStr
from typing import Optional
from PIL import Image as PILImage
from db import SessionLocal
from models import Document, User, Feedback, DeveloperDetails
import pytesseract
import os
import jwt
if os.name == 'nt':
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
import cv2
import numpy as np
import re
import time
from dotenv import load_dotenv
from groq import Groq
from datetime import datetime, timedelta
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

# Admin Dashboard Environment Configuration
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"

if not ADMIN_EMAIL or not ADMIN_PASSWORD or not JWT_SECRET:
    logger.warning("Admin Dashboard environment variables (ADMIN_EMAIL, ADMIN_PASSWORD, JWT_SECRET) are not fully configured!")

def create_admin_token(email: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=12)
    payload = {
        "sub": email,
        "role": "admin",
        "exp": expire
    }
    encoded_jwt = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt

security_scheme = HTTPBearer()

def get_current_admin(credentials: HTTPAuthorizationCredentials = Security(security_scheme)):
    if not JWT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="JWT_SECRET is not configured on the server."
        )
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        role = payload.get("role")
        if role != "admin":
            raise HTTPException(status_code=403, detail="Forbidden: Admin role required")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


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
    from db import engine, SessionLocal
    Base.metadata.create_all(bind=engine)
    
    # Self-heal missing columns in feedback table
    db = SessionLocal()
    try:
        from sqlalchemy import text
        # Try to add rating column if missing
        try:
            db.execute(text("ALTER TABLE feedback ADD COLUMN rating VARCHAR(50) NULL;"))
            db.commit()
            logger.info("Database: Added missing 'rating' column to feedback table.")
        except Exception as e_rating:
            db.rollback()
            logger.info(f"Database: 'rating' column already exists or checked. Details: {e_rating}")
            
        # Try to add feedback_text column if missing
        try:
            db.execute(text("ALTER TABLE feedback ADD COLUMN feedback_text TEXT NULL;"))
            db.commit()
            logger.info("Database: Added missing 'feedback_text' column to feedback table.")
        except Exception as e_text:
            db.rollback()
            logger.info(f"Database: 'feedback_text' column already exists or checked. Details: {e_text}")
    except Exception as e:
        logger.warning(f"Self-healing database migration failed: {e}")
    finally:
        db.close()
        
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
os.makedirs(os.path.join("static", "admin"), exist_ok=True)

app.mount("/audio", StaticFiles(directory="audio"), name="audio")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/pdfs", StaticFiles(directory="pdfs"), name="pdfs")
app.mount("/admin-static", StaticFiles(directory="static/admin"), name="admin-static")


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

        extracted_text = ""
        ocr_boxes = []
        detected_fields_count = 0

        logger.info(f"FILE UPLOADED: {file.filename}")
        logger.info(f"LANGUAGE RECEIVED: {language}")

        if file.filename.lower().endswith((".png", ".jpg", ".jpeg")):
            try:
                image = cv2.imread(file_path)
                orig_h, orig_w = image.shape[:2]

                # 1. Advanced Resize/Scaling (Target width 1000px for lightning-fast OCR & highlights)
                target_width = 1000
                scale_factor = 1.0
                if orig_w < target_width:
                    scale_factor = target_width / orig_w
                    width = int(orig_w * scale_factor)
                    height = int(orig_h * scale_factor)
                    image_resized = cv2.resize(image, (width, height), interpolation=cv2.INTER_CUBIC)
                else:
                    image_resized = image.copy()

                # 2. Grayscale Conversion
                gray = cv2.cvtColor(image_resized, cv2.COLOR_BGR2GRAY)

                # 3. Bilateral Filtering Denoising (Keep text edges sharp, clean noise)
                denoised = cv2.bilateralFilter(gray, 9, 75, 75)

                # 4. Sharpening (Filters out scan blur and heightens text contrast)
                sharpen_kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
                sharpened = cv2.filter2D(denoised, -1, sharpen_kernel)

                # 5. Gaussian Blur (Attenuates remaining high-frequency halftone/scanner noise)
                blurred = cv2.GaussianBlur(sharpened, (3, 3), 0)

                # 6. Adaptive Thresholding (Inverted for contours, standard for OCR)
                thresh_inv = cv2.adaptiveThreshold(
                    blurred,
                    255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY_INV,
                    15,
                    10
                )

                processed_ocr = cv2.adaptiveThreshold(
                    blurred,
                    255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY,
                    15,
                    10
                )

                # 7. Morphology Closing (Joins broken characters)
                kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
                processed_ocr = cv2.morphologyEx(processed_ocr, cv2.MORPH_CLOSE, kernel_close)

                # 8. Run Tesseract OCR on processed image
                # Dual PSM Engine Configurations: Merging PSM 6 (uniform block) and PSM 11 (sparse text labels)
                config_psm6 = r'--oem 3 --psm 6'
                config_psm11 = r'--oem 3 --psm 11'

                data_psm6 = pytesseract.image_to_data(
                    processed_ocr,
                    config=config_psm6,
                    output_type=pytesseract.Output.DICT
                )

                data_psm11 = pytesseract.image_to_data(
                    processed_ocr,
                    config=config_psm11,
                    output_type=pytesseract.Output.DICT
                )

                seen_boxes = []  # Keep track of x, y, w, h in original coordinates to prevent duplicates
                extracted_lines = []

                def add_ocr_box(word_text, rx, ry, rw, rh, conf):
                    word_clean = word_text.strip()
                    if not word_clean or conf < 20:  # Kept lower confidence filter to catch small/faint text
                        return

                    # Map coordinates back to original image size
                    x = int(rx / scale_factor)
                    y = int(ry / scale_factor)
                    w = int(rw / scale_factor)
                    h = int(rh / scale_factor)

                    # Overlap check
                    is_duplicate = False
                    for sx, sy, sw, sh in seen_boxes:
                        if abs(x - sx) < 15 and abs(y - sy) < 15 and abs(w - sw) < 25 and abs(h - sh) < 25:
                            is_duplicate = True
                            break

                    if not is_duplicate:
                        ocr_boxes.append({
                            "text": word_clean,
                            "x": x,
                            "y": y,
                            "w": w,
                            "h": h,
                            "confidence": float(conf)
                        })
                        seen_boxes.append((x, y, w, h))
                        extracted_lines.append(word_clean)

                # Process Primary PSM 6
                for i in range(len(data_psm6["text"])):
                    add_ocr_box(
                        data_psm6["text"][i],
                        data_psm6["left"][i],
                        data_psm6["top"][i],
                        data_psm6["width"][i],
                        data_psm6["height"][i],
                        data_psm6["conf"][i]
                    )

                # Process Secondary PSM 11 to catch sparse missing labels
                for i in range(len(data_psm11["text"])):
                    add_ocr_box(
                        data_psm11["text"][i],
                        data_psm11["left"][i],
                        data_psm11["top"][i],
                        data_psm11["width"][i],
                        data_psm11["height"][i],
                        data_psm11["conf"][i]
                    )

                # 9. Contour Detection to Identify Physical Input Boxes & Underlines
                contours, _ = cv2.findContours(thresh_inv, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                contour_boxes = []
                for cnt in contours:
                    x, y, w, h = cv2.boundingRect(cnt)
                    aspect_ratio = float(w) / h
                    if 40 < w < 900 and 15 < h < 120:
                        if aspect_ratio > 1.2:
                            contour_boxes.append({"x": x, "y": y, "w": w, "h": h})

                # Map contours to closest OCR label
                detected_fields_count = len(contour_boxes)
                for cb in contour_boxes:
                    cx, cy, cw, ch = cb["x"], cb["y"], cb["w"], cb["h"]
                    best_label = "Input Field"
                    min_dist = 999999

                    # Match against ocr_boxes
                    for box in ocr_boxes:
                        bx = box["x"] * scale_factor
                        by = box["y"] * scale_factor
                        # Text box to the left
                        if bx < cx and (cx - bx) < 180 and abs(by - cy) < 40:
                            dist = cx - bx
                            if dist < min_dist:
                                min_dist = dist
                                best_label = box["text"]
                        # Text box above
                        elif by < cy and (cy - by) < 50 and abs(bx - cx) < 100:
                            dist = cy - by
                            if dist < min_dist:
                                min_dist = dist
                                best_label = box["text"]

                    ox = int(cx / scale_factor)
                    oy = int(cy / scale_factor)
                    ow = int(cw / scale_factor)
                    oh = int(ch / scale_factor)

                    ocr_boxes.append({
                        "text": f"[Field: {best_label}]",
                        "x": ox,
                        "y": oy,
                        "w": ow,
                        "h": oh,
                        "confidence": 95.0
                    })

                extracted_text = "\n".join(extracted_lines)

            except Exception as e:
                logger.exception("OCR pipeline failed, falling back to Vision LLM")
                extracted_text = ""
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
                                        "text": "Explain this form in very simple step-by-step instructions for Indian people, rural users, and old-age users. Use simple English and short points."
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
                except Exception as e_vision:
                    logger.exception("Vision fallback also failed")
                    extracted_text = ""

        elif file.filename.lower().endswith(".pdf"):
            extracted_text = "PDF uploaded"

        # 10. Generate Multilingual AI Guidance
        if extracted_text.strip() == "":
            guidance_text = "Unable to detect text clearly."
        else:
            guidance_text = generate_guidance(extracted_text, language)

        # Predict immediate URLs for instant response
        file_url = f"https://formsahayak-backend.onrender.com/uploads/{filename}"
        audio_url = f"https://formsahayak-backend.onrender.com/audio/{filename}.mp3"
        pdf_url = f"https://formsahayak-backend.onrender.com/pdfs/{filename}.pdf"

        # 12. Dynamic Highlights & Spoken Guidance Synchronization Mapping
        guidance_steps = []
        raw_steps = [s.strip() for s in re.split(r'[\n\.]+', guidance_text) if s.strip()]
        for idx, step in enumerate(raw_steps):
            parentheses_terms = re.findall(r'\(([^)]+)\)', step)
            matched_boxes = []
            for term in parentheses_terms:
                term_clean = term.strip().lower()
                
                # 1. Primary: Exact match to specific field or exact label
                exact_matches = []
                for box in ocr_boxes:
                    box_text = box["text"].lower()
                    if box_text == f"[field: {term_clean}]" or box_text == term_clean:
                        exact_matches.append(box)
                        
                if exact_matches:
                    matched_boxes.extend(exact_matches)
                else:
                    # 2. Secondary fallback: Substring mapping but ignoring unrelated fields
                    for box in ocr_boxes:
                        box_text = box["text"].lower()
                        # If it's a field box, ensure it doesn't belong to a different specific field
                        if "[field:" in box_text and f"[field: {term_clean}]" not in box_text:
                            continue
                        if term_clean in box_text or box_text in term_clean or (term_clean == "phone" and "mobile" in box_text) or (term_clean == "dob" and "date" in box_text):
                            matched_boxes.append(box)

            # Keyword matching fallback
            if not matched_boxes:
                common_keywords = ["name", "email", "phone", "mobile", "address", "dob", "date", "signature", "account", "age"]
                step_lower = step.lower()
                for kw in common_keywords:
                    if kw in step_lower:
                        for box in ocr_boxes:
                            box_text = box["text"].lower()
                            # Avoid over-highlighting other fields (e.g. Father's Name when kw is name)
                            if "[field:" in box_text and f"[field: {kw}]" not in box_text:
                                continue
                            if kw in box_text or (kw == "phone" and "mobile" in box_text) or (kw == "dob" and "date" in box_text):
                                matched_boxes.append(box)

            # De-duplicate matched boxes
            unique_matches = []
            seen_match = set()
            for box in matched_boxes:
                box_key = (box["x"], box["y"], box["w"], box["h"])
                if box_key not in seen_match:
                    seen_match.add(box_key)
                    unique_matches.append(box)

            guidance_steps.append({
                "step_index": idx + 1,
                "step_text": step,
                "matched_fields": parentheses_terms if parentheses_terms else ["General"],
                "ocr_boxes": unique_matches
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
            guidance_text=guidance_text,
            audio_path=audio_url,
            pdf_path=pdf_url,
            created_at=current_time
        )
        db.add(new_doc)
        db.commit()
        db.close()

        # Add media compilation tasks to BackgroundTasks (completely async voice/PDF generation)
        background_tasks.add_task(
            generate_media_background,
            filename=filename,
            file_path=file_path,
            guidance_text=guidance_text,
            extracted_text=extracted_text,
            language=language if language else 'English'
        )

        # Print backend debug verification logs exactly as required
        logger.info(f"OCR BOXES DETECTED: {len(ocr_boxes)}")
        logger.info(f"LANGUAGE RECEIVED: {language}")
        logger.info(f"OCR TEXT LENGTH: {len(extracted_text)}")
        logger.info(f"DETECTED CONTOURS COUNT: {detected_fields_count}")

        print(f"OCR BOXES DETECTED: {len(ocr_boxes)}")
        print("OCR BOXES:", len(ocr_boxes))
        print(f"LANGUAGE RECEIVED: {language}")
        print(f"OCR TEXT LENGTH: {len(extracted_text)}")

        return {
            "message": "Uploaded & processed successfully",
            "guidance": guidance_text,
            "guidance_text": guidance_text,
            "audio_file": audio_url,
            "audio_path": audio_url,
            "pdf_file": pdf_url,
            "pdf_path": pdf_url,
            "ocr_boxes": ocr_boxes,
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


# ---------------- SHARED OTP MAIL HELPER ----------------

def send_otp_email_helper(email: str, otp: str):
    import os
    import requests
    
    brevo_api_key = os.getenv("BREVO_API_KEY", "").strip().strip("'\"")
    resend_api_key = os.getenv("RESEND_API_KEY", "").strip().strip("'\"")
    
    sender_email = os.getenv("SENDER_EMAIL", EMAIL_ADDRESS)
    
    if brevo_api_key:
        logger.info(f"Attempting to send OTP via Brevo. Receiver: {email}")
        logger.info(f"Brevo API key length: {len(brevo_api_key)}")
        logger.info(f"Brevo API key starts with: {brevo_api_key[:7] if len(brevo_api_key) >= 7 else brevo_api_key}...")
        
        url = "https://api.brevo.com/v3/smtp/email"
        payload = {
            "sender": {"name": "Formsahayak", "email": sender_email},
            "to": [{"email": email}],
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
        logger.info(f"Attempting to send OTP via Resend. Receiver: {email}")
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
                "to": [email],
                "subject": "Reset Password OTP",
                "html": f"<p>Your password reset OTP is <strong>{otp}</strong>. It is valid for 10 minutes.</p>"
            },
            timeout=15
        )
        
        if response.status_code != 200:
            logger.error(f"Resend API error response: {response.text}")
            raise Exception(f"Resend API failed with status {response.status_code}: {response.text}")

        logger.info("Resend API email sent successfully!")

# ---------------- FORGOT PASSWORD API ----------------

@app.post("/forgot-password")
def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(
            status_code=404, 
            detail="Email address not found. Please register first."
        )
    
    otp = str(random.randint(1000, 9999))
    otp_storage[request.email] = otp
    
    try:
        send_otp_email_helper(request.email, otp)
        return {
            "status": "success",
            "message": "OTP sent successfully"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error sending OTP: {str(e)}"
        )

# ---------------- SEND OTP API ----------------

@app.post("/send-otp")
def send_otp(data: ForgotPasswordRequest):
    db = SessionLocal()
    user = db.query(User).filter(User.email == data.email).first()
    db.close()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Email not registered"
        )

    otp = str(random.randint(1000, 9999))
    otp_storage[data.email] = otp

    try:
        send_otp_email_helper(data.email, otp)
        return {
            "message": "OTP sent successfully"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


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


# ---------------- ADMIN ENDPOINTS ----------------

class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str

@app.post("/api/admin/login")
def admin_login(data: AdminLoginRequest):
    if not ADMIN_EMAIL or not ADMIN_PASSWORD or not JWT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Admin configuration is missing on server"
        )
    if data.email != ADMIN_EMAIL or data.password != ADMIN_PASSWORD:
        raise HTTPException(
            status_code=401,
            detail="Invalid admin credentials"
        )
    
    token = create_admin_token(data.email)
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": "admin"
    }

@app.get("/api/admin/stats")
def get_admin_stats(current_admin: dict = Depends(get_current_admin)):
    db = SessionLocal()
    try:
        total_users = db.query(User).count()
        total_forms = db.query(Document).count()
        total_ocr_scans = db.query(Document).filter(
            Document.extracted_text != None,
            Document.extracted_text != ""
        ).count()
        total_feedback = db.query(Feedback).count()
        active_users = db.query(Document.user_email).distinct().count()
        
        # Get upload trends for the last 30 days
        # Group by day
        from sqlalchemy import func
        trends = db.query(
            func.date(Document.created_at).label("upload_date"),
            func.count(Document.id).label("upload_count")
        ).group_by(
            func.date(Document.created_at)
        ).order_by(
            "upload_date"
        ).limit(30).all()
        
        upload_dates = [str(t.upload_date) for t in trends]
        upload_counts = [int(t.upload_count) for t in trends]
        
        return {
            "total_users": total_users,
            "total_forms": total_forms,
            "total_ocr_scans": total_ocr_scans,
            "total_feedback": total_feedback,
            "active_users": active_users,
            "analytics": {
                "upload_dates": upload_dates,
                "upload_counts": upload_counts
            }
        }
    except Exception as e:
        logger.exception("Failed to fetch admin stats")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/api/admin/users")
def get_admin_users(
    query: Optional[str] = None,
    current_admin: dict = Depends(get_current_admin)
):
    db = SessionLocal()
    try:
        q = db.query(User)
        if query:
            q = q.filter(
                (User.name.like(f"%{query}%")) | 
                (User.email.like(f"%{query}%"))
            )
        users = q.order_by(User.id.desc()).all()
        
        result = []
        for user in users:
            profile_image_url = ""
            if user.profile_image:
                profile_image_url = f"https://formsahayak-backend.onrender.com/{user.profile_image.replace(chr(92), '/')}"
            result.append({
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "phone": user.phone,
                "language": user.language,
                "profile_image": profile_image_url
            })
        return {"users": result}
    except Exception as e:
        logger.exception("Failed to fetch admin users")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/api/admin/forms")
def get_admin_forms(current_admin: dict = Depends(get_current_admin)):
    db = SessionLocal()
    try:
        docs = db.query(Document).order_by(Document.id.desc()).all()
        result = []
        for doc in docs:
            result.append({
                "id": doc.id,
                "user_email": doc.user_email,
                "file_name": doc.file_name,
                "file_url": doc.file_path,
                "extracted_text": doc.extracted_text,
                "guidance_text": doc.guidance_text,
                "audio_path": doc.audio_path,
                "pdf_path": doc.pdf_path,
                "created_at": str(doc.created_at)
            })
        return {"forms": result}
    except Exception as e:
        logger.exception("Failed to fetch admin forms")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/api/admin/feedback")
def get_admin_feedback(current_admin: dict = Depends(get_current_admin)):
    db = SessionLocal()
    try:
        feedbacks = db.query(Feedback).order_by(Feedback.id.desc()).all()
        result = []
        for fb in feedbacks:
            result.append({
                "id": fb.id,
                "user_email": fb.user_email,
                "app_experience": fb.app_experience,
                "voice_guidance_helpful": fb.voice_guidance_helpful,
                "recommend_app": fb.recommend_app,
                "additional_comments": fb.additional_comments,
                "rating": fb.rating,
                "feedback_text": fb.feedback_text,
                "created_at": str(fb.created_at)
            })
        return {"feedback": result}
    except Exception as e:
        logger.exception("Failed to fetch admin feedback")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/admin", response_class=HTMLResponse)
def serve_admin_dashboard():
    html_path = os.path.join("static", "admin", "index.html")
    if not os.path.exists(html_path):
        raise HTTPException(status_code=404, detail="Admin Dashboard UI not found")
    return FileResponse(html_path)

@app.get("/api/developer")
def get_developer_details(db: Session = Depends(get_db)):
    details = db.query(DeveloperDetails).first()
    if not details:
        return {
            "name": "Yamanuri Praneeth",
            "father_name": "s/o Yamanuri Ramesh",
            "role": "Developer & Creator of FormSahayak",
            "description": "Computer Science Engineering student passionate about AI, Mobile Application Development, and solving real-world problems through technology.",
            "email": "praneethyamanuri@gmail.com",
            "github": "https://github.com/Praneeth5158",
            "linkedin": "https://www.linkedin.com/in/yamanuri-praneeth/",
            "portfolio": "https://praneeth5158.github.io/My-Portfolio/",
            "profile_image": ""
        }
    
    profile_image_url = ""
    if details.profile_image:
        profile_image_url = f"https://formsahayak-backend.onrender.com/{details.profile_image.replace(chr(92), '/')}"

    return {
        "name": details.name,
        "father_name": details.father_name,
        "role": details.role,
        "description": details.description,
        "email": details.email,
        "github": details.github,
        "linkedin": details.linkedin,
        "portfolio": details.portfolio,
        "profile_image": profile_image_url
    }

@app.post("/api/admin/developer")
async def update_developer_details(
    name: str = Form(...),
    father_name: str = Form(...),
    role: str = Form(...),
    description: str = Form(...),
    email: str = Form(...),
    github: str = Form(...),
    linkedin: str = Form(...),
    portfolio: str = Form(...),
    profile_image: UploadFile = File(None),
    current_admin: dict = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    details = db.query(DeveloperDetails).first()
    if not details:
        details = DeveloperDetails()
        db.add(details)

    image_path = details.profile_image

    if profile_image:
        filename = f"dev_{int(time.time())}_{profile_image.filename}"
        save_path = os.path.join(UPLOAD_FOLDER, filename)
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(profile_image.file, buffer)
        image_path = save_path

    details.name = name
    details.father_name = father_name
    details.role = role
    details.description = description
    details.email = email
    details.github = github
    details.linkedin = linkedin
    details.portfolio = portfolio
    details.profile_image = image_path

    db.commit()

    profile_image_url = ""
    if image_path:
        profile_image_url = f"https://formsahayak-backend.onrender.com/{image_path.replace(chr(92), '/')}"

    return {
        "message": "Developer details updated successfully",
        "profile_image": profile_image_url
    }