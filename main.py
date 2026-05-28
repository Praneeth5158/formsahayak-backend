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
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
import cv2
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
    app_experience: str = None
    voice_guidance_helpful: str = None
    recommend_app: str = None
    additional_comments: str = None
    rating: str = None
    feedback_text: str = None

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
    import numpy as np

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

            # 1. Advanced Resize/Scaling (Target width 2000px for optimal OCR character height)
            target_width = 2000
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

    # 11. Speech Generation with Text Cleaning
    audio_filename = filename + ".mp3"
    audio_path = os.path.join(AUDIO_FOLDER, audio_filename)

    pdf_path = generate_pdf_report(
        filename,
        extracted_text,
        guidance_text,
        file_path
    )

    lang_code = "en"
    if language == "Telugu":
        lang_code = "te"
    elif language == "Hindi":
        lang_code = "hi"
    elif language == "Tamil":
        lang_code = "ta"

    try:
        # Natural Voice Generation - cleaning text before passing into TTS
        cleaned_guidance = clean_text_for_tts(guidance_text)
        print("TTS INPUT:", cleaned_guidance)
        short_text = cleaned_guidance[:1500]

        # Use edge-tts for premium neural voices
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
            logger.info(f"Edge-TTS voice successfully generated: {voice}")
        except Exception as e_edge:
            logger.warning(f"edge-tts failed: {e_edge}, falling back to gTTS")
            # Fallback to standard gTTS
            tts = gTTS(
                text=short_text,
                lang=lang_code
            )
            tts.save(audio_path)
    except Exception as e:
        logger.exception("Audio generation failed completely")
        audio_path = ""

    # 12. Dynamic Highlights & Spoken Guidance Synchronization Mapping
    guidance_steps = []
    raw_steps = [s.strip() for s in re.split(r'[\n\.]+', guidance_text) if s.strip()]
    for idx, step in enumerate(raw_steps):
        parentheses_terms = re.findall(r'\(([^)]+)\)', step)
        matched_boxes = []
        for term in parentheses_terms:
            term_clean = term.strip().lower()
            for box in ocr_boxes:
                box_text = box["text"].lower()
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

    # Save to Database
    india = timezone("Asia/Kolkata")
    current_time = datetime.now(india)

    db = SessionLocal()
    file_url = f"https://formsahayak-backend.onrender.com/uploads/{filename}"
    audio_url = f"https://formsahayak-backend.onrender.com/audio/{audio_filename}"
    pdf_url = f"https://formsahayak-backend.onrender.com/pdfs/{filename}.pdf"

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

    # Formulate urls for response
    audio_response_url = ""
    if audio_path != "":
        audio_response_url = f"https://formsahayak-backend.onrender.com/audio/{audio_filename}"

    # Print backend debug verification logs exactly as required
    logger.info(f"OCR BOXES DETECTED: {len(ocr_boxes)}")
    logger.info(f"LANGUAGE RECEIVED: {language}")
    logger.info(f"TTS LANGUAGE: {lang_code}")
    logger.info(f"OCR TEXT LENGTH: {len(extracted_text)}")
    logger.info(f"DETECTED CONTOURS COUNT: {detected_fields_count}")

    print(f"OCR BOXES DETECTED: {len(ocr_boxes)}")
    print("OCR BOXES:", len(ocr_boxes))
    print("OCR BOXES SENT:", len(ocr_boxes))
    print(f"LANGUAGE RECEIVED: {language}")
    print(f"TTS LANGUAGE: {lang_code}")
    print(f"OCR TEXT LENGTH: {len(extracted_text)}")

    return {
        "message": "Uploaded & processed successfully",
        "guidance": guidance_text,
        "guidance_text": guidance_text,
        "audio_file": audio_response_url,
        "audio_path": audio_response_url,
        "pdf_file": f"https://formsahayak-backend.onrender.com/{pdf_path.replace(chr(92), '/')}",
        "pdf_path": f"https://formsahayak-backend.onrender.com/{pdf_path.replace(chr(92), '/')}",
        "ocr_boxes": ocr_boxes,
        "extracted_text": extracted_text,
        "uploaded_image_path": file_url,
        "guidance_steps": guidance_steps
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

        server = smtplib.SMTP(
        "smtp.gmail.com",
        587,
        timeout=30
        )

        server.ehlo()

        server.starttls()


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
            detail="Document not found"
        )

    db.delete(doc)

    db.commit()

    db.close()

    return {
        "message": "History deleted successfully"
         
    }