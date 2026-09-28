import cloudinary
import cloudinary.uploader
import os

def init_cloudinary():
    # Only configure if environment variables exist
    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME')
    api_key = os.environ.get('CLOUDINARY_API_KEY')
    api_secret = os.environ.get('CLOUDINARY_API_SECRET')
    
    if cloud_name and api_key and api_secret:
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret
        )

def upload_image_to_cloudinary(file, folder="curatera_uploads"):
    """
    Uploads a file object to Cloudinary and returns the secure URL.
    Returns None if upload fails.
    """
    init_cloudinary()
    try:
        result = cloudinary.uploader.upload(file, folder=folder)
        return result.get('secure_url')
    except Exception as e:
        print(f"Cloudinary Upload Error: {e}")
        return None
