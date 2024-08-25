import asyncio
import uuid
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
import PyPDF2
import docx
from openai import OpenAI
from io import BytesIO
import os
from dotenv import load_dotenv
from supabase import create_client, Client
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables
load_dotenv()

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure OpenAI API key

supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))


@app.get("/health/{name}")
async def healthCheck(name: str):
    try:
        return JSONResponse(content={"detail": name})
    except Exception as e:
        print(e)


@app.post("/api/summarize")
async def summarize(file: UploadFile = File(...)):
    try:
        contents = await file.read()

        buckets = supabase.storage.list_buckets()
        print(f"Available buckets: {[bucket.name for bucket in buckets]}")

        file_id = str(uuid.uuid4())
        file_path = f"{file_id}_{file.filename}"
        print(f"Generated file path: {file_path}")

        try:
            result = supabase.storage.from_("documents").upload(file_path, contents)
            print(f"File upload result: {result}")
            print(f"Uploaded file path: {file_path}")
        except Exception as e:
            print(f"Error uploading file: {str(e)}")
            return JSONResponse(
                content={"error": f"Error uploading file: {str(e)}"}, status_code=500
            )

        await asyncio.sleep(2)  # Wait for 2 seconds

        try:
            public_url = supabase.storage.from_("documents").get_public_url(file_path)
            print(f"Public URL: {public_url}")

            signed_url = supabase.storage.from_("documents").create_signed_url(
                file_path, 60
            )
            print(f"Signed URL: {signed_url}")

            file_info = supabase.storage.from_("documents").get_public_url(file_path)
            print(f"File info: {file_info}")

            files = supabase.storage.from_("documents").list()
            print(f"Files in documents bucket: {[file['name'] for file in files]}")
        except Exception as e:
            print(f"Error accessing file info: {str(e)}")

        # Use the original contents instead of trying to download
        text = extract_text(contents, file.filename)

        # Truncate text if it's too long (approximate token limit)
        MAX_CHARS = 12000
        if len(text) > MAX_CHARS:
            text = text[:MAX_CHARS] + "... (text truncated due to length)"

        summary = generate_summary(text)
        return JSONResponse(content={"summary": summary})
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


def extract_text(contents: bytes, filename: str) -> str:
    if filename.lower().endswith(".pdf"):
        return extract_text_from_pdf(contents)
    elif filename.lower().endswith(".docx"):
        return extract_text_from_docx(contents)
    else:
        raise ValueError("Unsupported file type")


def extract_text_from_pdf(contents: bytes) -> str:
    pdf_reader = PyPDF2.PdfReader(BytesIO(contents))
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text


def extract_text_from_docx(contents: bytes) -> str:
    doc = docx.Document(BytesIO(contents))
    text = ""
    for para in doc.paragraphs:
        text += para.text + "\n"
    return text


def generate_summary(text: str) -> str:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that summarizes text. Provide a concise summary of the main points."},
            {"role": "user", "content": f"Summarize the following text:\n\n{text}"}
        ],
        max_tokens=500
    )
    
    return response.choices[0].message.content


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
