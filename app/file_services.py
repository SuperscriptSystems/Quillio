import os
import PyPDF2
from werkzeug.utils import secure_filename
from flask_login import current_user
from app.ai_clients import ask_ai
from models.prompt_builders import CoursePromptBuilder
from models.json_extractor import JsonExtractor
from app.models import db, Course, Lesson


def _update_token_count(tokens_to_add):
    """Helper function to add tokens to the current user's total."""
    if tokens_to_add > 0:
        current_user.tokens_used += tokens_to_add
        db.session.commit()


def extract_text_from_pdf(file_path):
    """Extract text content from a PDF file."""
    try:
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        print(f"Error extracting text from PDF: {str(e)}")
        return None


def process_uploaded_file(file):
    """Process uploaded file and extract text content."""
    if not file or file.filename == '':
        return None, "No file selected"
    
    # Check file extension
    filename = secure_filename(file.filename)
    if not filename.lower().endswith('.pdf'):
        return None, "Only PDF files are supported"
    
    # Create uploads directory if it doesn't exist
    upload_dir = os.path.join(os.path.dirname(__file__), '..', 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    
    # Save file temporarily
    file_path = os.path.join(upload_dir, filename)
    file.save(file_path)
    
    try:
        # Extract text from PDF
        extracted_text = extract_text_from_pdf(file_path)
        if not extracted_text:
            return None, "Could not extract text from PDF"
        
        return extracted_text, None
    finally:
        # Clean up temporary file
        if os.path.exists(file_path):
            os.remove(file_path)


def create_course_from_file_service(file, user):
    """Create a course from uploaded file content."""
    # Extract text from file
    extracted_text, error = process_uploaded_file(file)
    if error:
        return None, error
    
    # Generate course title from content
    title_prompt = f"Based on this content, generate a concise course title (max 8 words):\n\n{extracted_text[:1000]}..."
    course_title, tokens = ask_ai(title_prompt, model="gpt-4o")
    _update_token_count(tokens)
    
    if "Error:" in course_title:
        course_title = "Course from Uploaded Document"
    
    # Generate course structure from extracted text
    prompt = CoursePromptBuilder.build_course_structure_from_content_prompt(
        extracted_text, user.language, user
    )
    
    raw_output, tokens = ask_ai(prompt, model="gpt-4o", json_mode=True)
    _update_token_count(tokens)
    
    if not raw_output or "Error:" in raw_output:
        return None, f"AI failed to generate course structure. Response: {raw_output}"
    
    try:
        course_json = JsonExtractor.extract_json(raw_output)
        
        # Override title with generated one
        course_json['course_title'] = course_title.strip('"')
        
        # Create course in database
        new_course = Course(
            user_id=user.id,
            course_title=course_json['course_title'],
            course_data=course_json
        )
        db.session.add(new_course)
        db.session.commit()
        
        # Create lesson entries
        for unit in course_json.get('units', []):
            for lesson_data in unit.get('lessons', []):
                new_lesson = Lesson(
                    course_id=new_course.id,
                    unit_title=unit['unit_title'],
                    lesson_title=lesson_data['lesson_title']
                )
                db.session.add(new_lesson)
        
        db.session.commit()
        return new_course, None
        
    except Exception as e:
        db.session.rollback()
        return None, f"Error creating course: {str(e)}"
