import asyncio
import uuid
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
import PyPDF2
import docx
from openai import OpenAI
from io import BytesIO
import os
from dotenv import load_dotenv
from supabase import create_client, Client
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict
from datetime import datetime

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

# Configure Supabase client
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# Configure OpenAI client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


@app.get("/health/{name}")
async def healthCheck(name: str):
    try:
        return JSONResponse(content={"detail": name})
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/summarize")
async def summarize(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        text = extract_text(contents, file.filename)

        # Truncate text if it's too long (approximate token limit)
        MAX_CHARS = 12000
        if len(text) > MAX_CHARS:
            text = text[:MAX_CHARS] + "... (text truncated due to length)"

        summary = generate_summary(text)
        return JSONResponse(content={"summary": summary})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/start_chat")
async def start_chat(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        file_path = f"documents/{uuid.uuid4()}_{file.filename}"

        # Upload file to Supabase storage
        supabase.storage.from_("documents").upload(file_path, contents)

        session_id = str(uuid.uuid4())

        # Insert new session into the database
        supabase.table("chat_sessions").insert(
            {"id": session_id, "file_path": file_path, "messages": []}
        ).execute()

        return JSONResponse(content={"session_id": session_id})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/{session_id}")
async def chat(session_id: str, message: str = Form(...)):
    try:
        # Fetch the session from the database
        result = (
            supabase.table("chat_sessions").select("*").eq("id", session_id).execute()
        )
        if not result.data:
            raise HTTPException(status_code=400, detail="Invalid session ID")

        session = result.data[0]

        # Download file from Supabase
        file_data = supabase.storage.from_("documents").download(session["file_path"])
        text = extract_text(file_data, session["file_path"])

        messages = session["messages"]
        messages.append({"role": "user", "content": message})

        response = generate_chat_response(text, messages)
        messages.append({"role": "assistant", "content": response})

        # Update the session in the database
        supabase.table("chat_sessions").update(
            {"messages": messages, "updated_at": datetime.utcnow().isoformat()}
        ).eq("id", session_id).execute()

        return JSONResponse(content={"response": response})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/end_chat/{session_id}")
async def end_chat(session_id: str):
    try:
        result = (
            supabase.table("chat_sessions").select("*").eq("id", session_id).execute()
        )
        if not result.data:
            raise HTTPException(status_code=400, detail="Invalid session ID")

        session = result.data[0]

        # Delete file from Supabase storage
        try:
            supabase.storage.from_("documents").remove([session["file_path"]])
        except Exception as e:
            print(f"Error deleting file: {str(e)}")

        # Delete session from the database
        supabase.table("chat_sessions").delete().eq("id", session_id).execute()

        return JSONResponse(
            content={"message": "Chat session ended and file deleted successfully"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
    response = openai_client.chat.completions.create(
        model="gpt-4",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant that summarizes text. Provide a concise summary of the main points.",
            },
            {"role": "user", "content": f"Summarize the following text:\n\n{text}"},
        ],
        max_tokens=500,
    )

    return response.choices[0].message.content


def generate_chat_response(context: str, messages: List[Dict[str, str]]) -> str:
    system_message = {
        "role": "system",
        "content": "You are a helpful assistant that can answer questions about the given document.",
    }
    context_message = {"role": "system", "content": f"Context:\n\n{context}"}

    all_messages = [system_message, context_message] + messages

    response = openai_client.chat.completions.create(
        model="gpt-4", messages=all_messages, max_tokens=500
    )

    return response.choices[0].message.content


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
