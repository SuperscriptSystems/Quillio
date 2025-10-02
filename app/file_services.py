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
        print(f"Attempting to read PDF from: {file_path}")
        print(f"File exists: {os.path.exists(file_path)}")
        print(f"File size: {os.path.getsize(file_path) if os.path.exists(file_path) else 0} bytes")
        
        # Read file in binary mode first
        with open(file_path, 'rb') as file:
            file_content = file.read()
            
        # Create file-like object from bytes
        from io import BytesIO
        pdf_file = BytesIO(file_content)
        
        # Extract text using PyPDF2
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            try:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            except Exception as page_error:
                print(f"Warning: Error processing page: {str(page_error)}")
                continue
                
        print(f"Extracted {len(text)} characters of text from PDF")
        return text.strip() if text.strip() else None
        
    except Exception as e:
        import traceback
        error_msg = f"Error extracting text from PDF: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return None


def process_uploaded_file(file):
    """Process uploaded file and extract text content."""
    import tempfile
    import shutil
    
    if not file or file.filename == '':
        return None, "No file selected"
    
    temp_dir = None
    try:
        # Check file extension
        filename = secure_filename(file.filename)
        if not filename.lower().endswith('.pdf'):
            return None, "Only PDF files are supported"
        
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp()
        temp_filepath = os.path.join(temp_dir, 'temp_upload.pdf')
        print(f"Temporary file path: {temp_filepath}")
        
        # Save the file directly to the temporary location
        try:
            file.save(temp_filepath)
            print(f"File saved to temporary location: {temp_filepath}")
            print(f"Temporary file size: {os.path.getsize(temp_filepath)} bytes")
            
            # Verify the file was saved correctly
            if not os.path.exists(temp_filepath):
                return None, "Failed to save temporary file"
                
            # Extract text from PDF
            print("Attempting to extract text from PDF...")
            extracted_text = extract_text_from_pdf(temp_filepath)
            if not extracted_text:
                return None, "Could not extract text from PDF"
            
            print(f"Successfully extracted {len(extracted_text)} characters from PDF")
            return extracted_text, None
            
        except Exception as e:
            import traceback
            error_msg = f"Error processing file: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            return None, f"Error processing file: {str(e)}"
            
    except Exception as e:
        import traceback
        error_msg = f"Unexpected error: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return None, f"Unexpected error: {str(e)}"
        
    finally:
        # Clean up temporary directory
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                print(f"Cleaned up temporary directory: {temp_dir}")
            except Exception as e:
                print(f"Warning: Could not remove temporary directory {temp_dir}: {str(e)}")


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
