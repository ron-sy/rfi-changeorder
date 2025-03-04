from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import tempfile
import os
import uuid
import requests
import logging
from datetime import datetime
from dotenv import load_dotenv
from change_order_generator import extract_text_from_pdf, parse_job_description, create_excel_file
import firebase_admin
from firebase_admin import credentials, storage
import json

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Initialize Firebase Admin SDK
if not firebase_admin._apps:
    try:
        cred_dict = {
            "type": "service_account",
            "project_id": "dashboard-55056",
            "private_key_id": "6b33618a2530f557c7e7a9d6a6d6d6a6d6d6a6",
            "private_key": os.environ.get("FIREBASE_PRIVATE_KEY", "").replace("\\n", "\n"),
            "client_email": os.environ.get("FIREBASE_CLIENT_EMAIL"),
            "client_id": os.environ.get("FIREBASE_CLIENT_ID"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": os.environ.get("FIREBASE_CLIENT_CERT_URL")
        }
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred, {
            'storageBucket': os.environ.get('FIREBASE_STORAGE_BUCKET')
        })
    except Exception as e:
        logging.error(f"Failed to initialize Firebase: {str(e)}")

app = FastAPI(
    title="Change Order Generator API",
    description="API for generating construction change orders from PDF files or text descriptions",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add trusted host middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests."""
    logger.info(f"Request: {request.method} {request.url}")
    logger.info(f"Headers: {request.headers}")
    response = await call_next(request)
    logger.info(f"Response status: {response.status_code}")
    return response

@app.get("/")
async def root(request: Request):
    """Root endpoint showing API status and available endpoints."""
    logger.info(f"Root endpoint accessed from {request.client.host}")
    return {
        "status": "online",
        "message": "RFI Quote API is running",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "generate_from_pdf": "/generate-from-pdf",
            "generate_from_text": "/generate-from-text",
            "documentation": "/docs"
        }
    }

def upload_to_firebase(file_path: str, destination_blob_name: str) -> str:
    """Upload a file to Firebase Storage and return its public URL."""
    try:
        bucket = storage.bucket()
        blob = bucket.blob(destination_blob_name)
        
        # Upload the file
        blob.upload_from_filename(file_path)
        logger.info(f"File uploaded successfully to {destination_blob_name}")
        
        # Get the public URL (no need to make public since we're using Uniform Bucket-Level Access)
        return f"https://storage.googleapis.com/{bucket.name}/{destination_blob_name}"
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error uploading to Firebase: {error_msg}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload file to Firebase: {error_msg}"
        )

def generate_unique_filename(original_filename: str) -> str:
    """Generate a unique filename with timestamp and UUID."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    extension = os.path.splitext(original_filename)[1]
    return f"{timestamp}_{unique_id}{extension}"

@app.post("/generate-from-pdf")
async def generate_from_pdf(file: UploadFile = File(...)):
    """Generate a change order from a PDF file."""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        # Create temporary files for processing
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as pdf_temp:
            pdf_content = await file.read()
            pdf_temp.write(pdf_content)
            pdf_temp.flush()
            
            # Extract text from PDF
            job_description = extract_text_from_pdf(pdf_temp.name)
            if not job_description:
                raise HTTPException(status_code=400, detail="Could not extract text from PDF")
            
            # Parse job description
            parsed_data = parse_job_description(job_description)
            if not parsed_data:
                raise HTTPException(status_code=400, detail="Failed to parse job description")
            
            # Generate Excel file
            excel_filename = generate_unique_filename('change_order.xlsx')
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as excel_temp:
                excel_path = create_excel_file(parsed_data, excel_temp.name)
                
                # Upload to Firebase Storage
                firebase_path = f"change_orders/{excel_filename}"
                download_url = upload_to_firebase(excel_path, firebase_path)
                
                # Clean up temporary files
                os.unlink(pdf_temp.name)
                os.unlink(excel_temp.name)
                
                return JSONResponse({
                    "status": "success",
                    "message": "Change order generated successfully",
                    "download_url": download_url,
                    "filename": excel_filename
                })
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate-from-text")
async def generate_from_text(
    description: str = Form(...),
    request: Request = None
):
    """Generate a change order from text description."""
    try:
        logger.info(f"Generating change order from text for client: {request.client.host}")
        
        if not description or description.isspace():
            raise HTTPException(status_code=400, detail="Description cannot be empty")
        
        # Parse the job description
        parsed_data = parse_job_description(description)
        if not parsed_data:
            raise HTTPException(status_code=400, detail="Failed to parse job description")
        
        # Create Excel file
        excel_path = create_excel_file(parsed_data)
        if not excel_path:
            raise HTTPException(status_code=500, detail="Failed to create Excel file")
            
        logger.info(f"Excel file created at: {excel_path}")
        
        try:
            # Upload to Firebase
            destination_blob_name = f"change_orders/{generate_unique_filename('change_order.xlsx')}"
            file_url = upload_to_firebase(excel_path, destination_blob_name)
            
            # Clean up the temporary file
            os.remove(excel_path)
            
            return {
                "status": "success",
                "message": "Change order generated successfully",
                "file_url": file_url,
                "data": parsed_data
            }
            
        except Exception as e:
            # Clean up the temporary file even if upload fails
            if os.path.exists(excel_path):
                os.remove(excel_path)
            raise
            
    except HTTPException as he:
        raise he
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error processing text: {error_msg}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process text: {error_msg}"
        )

@app.get("/health")
async def health_check(request: Request):
    """Health check endpoint."""
    logger.info(f"Health check accessed from {request.client.host}")
    return {
        "status": "healthy",
        "environment": {
            "firebase_configured": firebase_configured
        },
        "request": {
            "client": request.client.host,
            "headers": dict(request.headers)
        }
    } 