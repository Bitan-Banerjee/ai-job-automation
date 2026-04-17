import os
from docx import Document

# Path setup
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCX_PATH = os.path.join(BASE_DIR, 'Resume.docx')
TXT_OUTPUT = os.path.join(BASE_DIR, 'data', 'base_resume.txt')

def extract_resume_text():
    if not os.path.exists(DOCX_PATH):
        print(f"❌ Resume.docx not found at {DOCX_PATH}")
        return

    print(f"📄 Reading {DOCX_PATH}...")
    doc = Document(DOCX_PATH)
    full_text = []
    
    for para in doc.paragraphs:
        if para.text.strip():
            full_text.append(para.text.strip())
            
    # Join with newlines to preserve structure
    resume_content = "\n".join(full_text)
    
    # Create data directory if it doesn't exist
    os.makedirs(os.path.dirname(TXT_OUTPUT), exist_ok=True)
    
    with open(TXT_OUTPUT, "w") as f:
        f.write(resume_content)
        
    print(f"✅ Successfully converted resume to {TXT_OUTPUT}")
    print("-" * 30)
    print(f"Preview (First 200 chars):\n{resume_content[:200]}...")

if __name__ == "__main__":
    extract_resume_text()
