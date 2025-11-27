from fastapi import UploadFile, HTTPException
import os
from loguru import logger

# Configuration
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = ['.pdf', '.docx']

async def validate_resume_file(file: UploadFile) -> bytes:
    """
    Validates resume file size and type.
    
    Args:
        file: Uploaded file from FastAPI
        
    Returns:
        bytes: File content if validation passes
        
    Raises:
        HTTPException: If validation fails
    """
    # Read file content
    content = await file.read()
    file_size = len(content)
    
    # Validate size
    if file_size == 0:
        logger.warning(f"Empty file uploaded: {file.filename}")
        raise HTTPException(
            status_code=400, 
            detail="File is empty. Please upload a valid resume."
        )
    
    if file_size > MAX_FILE_SIZE:
        logger.warning(f"File too large: {file.filename} ({file_size / 1024 / 1024:.2f} MB)")
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE / 1024 / 1024:.0f} MB. Your file is {file_size / 1024 / 1024:.2f} MB."
        )
    
    # Validate file type by extension
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        logger.warning(f"Invalid file type: {file.filename} ({file_ext})")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '{file_ext}'. Allowed formats: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    logger.info(f"✅ File validated: {file.filename} ({file_size / 1024:.2f} KB)")
    return content