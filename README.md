# Change Order Generator API

This API service generates detailed construction change orders from job descriptions or PDF files. It uses OpenAI's GPT-4 to analyze the input and create comprehensive cost breakdowns, which are then formatted into Excel files and stored in Firebase Storage.

## Features

- Generate change orders from text descriptions
- Generate change orders from PDF files
- Automatic storage of generated files in Firebase Storage
- Detailed cost breakdowns including:
  - Materials
  - Equipment
  - Labor
  - Subcontractors
  - General Requirements

## Prerequisites

- Python 3.8+
- Firebase project with Storage enabled
- OpenAI API key
- Firebase service account credentials

## Environment Variables

Create a `.env` file in the root directory with the following variables:

```env
OPENAI_API_KEY=your_openai_api_key
FIREBASE_CREDENTIALS_PATH=/path/to/your/firebase-credentials.json
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_STORAGE_BUCKET=your-storage-bucket.appspot.com
FIREBASE_API_KEY=your-firebase-api-key
FIREBASE_APP_ID=your-firebase-app-id
FIREBASE_MESSAGING_SENDER_ID=your-messaging-sender-id
FIREBASE_MEASUREMENT_ID=your-measurement-id
```

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up your environment variables in `.env`
4. Run the API:
   ```bash
   uvicorn api:app --reload
   ```

## API Endpoints

### Generate from PDF
```http
POST /generate-from-pdf
Content-Type: multipart/form-data

file: [PDF File]
```

### Generate from Text
```http
POST /generate-from-text
Content-Type: application/x-www-form-urlencoded

description: [Job Description Text]
```

### Health Check
```http
GET /health
```

## Response Format

Successful responses will have the following format:
```json
{
    "status": "success",
    "message": "Change order generated successfully",
    "download_url": "https://storage.googleapis.com/...",
    "filename": "20231120_123456_abcd1234.xlsx"
}
```

## Error Handling

The API returns appropriate HTTP status codes and error messages:

- 400: Bad Request (invalid input)
- 500: Internal Server Error (processing failed)

## Example Usage

Using curl:

```bash
# Generate from PDF
curl -X POST http://localhost:8000/generate-from-pdf \
  -F "file=@/path/to/your/document.pdf"

# Generate from text
curl -X POST http://localhost:8000/generate-from-text \
  -d "description=Install new electrical outlets in conference room"
```

## Notes

- The API uses temporary files for processing, which are automatically cleaned up
- Generated Excel files are stored in the `change_orders/` directory in Firebase Storage
- Files are given unique names using timestamps and UUIDs
- All generated files are publicly accessible via their download URLs 