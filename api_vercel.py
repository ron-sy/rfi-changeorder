from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import tempfile
import os
import json
import numpy as np
from datetime import datetime
import logging
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, storage

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK
if not firebase_admin._apps:
    try:
        cred_dict = {
            "type": "service_account",
            "project_id": "dashboard-55056",
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
        logger.error(f"Failed to initialize Firebase: {str(e)}")

app = FastAPI(
    title="Change Order Generator API",
    description="API for generating construction change orders",
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

@app.get("/")
async def root():
    """Root endpoint showing API status."""
    return {
        "status": "online",
        "message": "Change Order Generator API is running",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "environment": {
            "firebase_initialized": len(firebase_admin._apps) > 0
        }
    }

# Import the business logic functions after initializing Firebase
from change_order_generator import extract_text_from_pdf, parse_job_description, create_excel_file

@app.post("/generate-from-pdf")
async def generate_from_pdf(file: UploadFile = File(...)):
    """Generate a change order from a PDF file."""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as pdf_temp:
            content = await file.read()
            pdf_temp.write(content)
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
            excel_filename = f"change_order_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as excel_temp:
                excel_path = create_excel_file(parsed_data, excel_temp.name)
                
                # Upload to Firebase Storage
                bucket = storage.bucket()
                blob = bucket.blob(f"change_orders/{excel_filename}")
                blob.upload_from_filename(excel_path)
                
                # Clean up temporary files
                os.unlink(pdf_temp.name)
                os.unlink(excel_temp.name)
                
                return JSONResponse({
                    "status": "success",
                    "message": "Change order generated successfully",
                    "download_url": f"https://storage.googleapis.com/{bucket.name}/change_orders/{excel_filename}",
                    "filename": excel_filename
                })
                
    except Exception as e:
        logger.error(f"Error processing PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate-from-text")
async def generate_from_text(description: str = Form(...)):
    """Generate a change order from text description."""
    try:
        if not description or description.isspace():
            raise HTTPException(status_code=400, detail="Description cannot be empty")
        
        # Parse the job description
        parsed_data = parse_job_description(description)
        if not parsed_data:
            raise HTTPException(status_code=400, detail="Failed to parse job description")
        
        # Generate Excel file
        excel_filename = f"change_order_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as excel_temp:
            excel_path = create_excel_file(parsed_data, excel_temp.name)
            
            # Upload to Firebase Storage
            bucket = storage.bucket()
            blob = bucket.blob(f"change_orders/{excel_filename}")
            blob.upload_from_filename(excel_path)
            
            # Clean up temporary file
            os.unlink(excel_temp.name)
            
            return JSONResponse({
                "status": "success",
                "message": "Change order generated successfully",
                "download_url": f"https://storage.googleapis.com/{bucket.name}/change_orders/{excel_filename}",
                "filename": excel_filename,
                "data": parsed_data
            })
            
    except Exception as e:
        logger.error(f"Error processing text: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 