# Create a virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate

# Install required packages
pip install django djangorestframework django-cors-headers openai markdown python-dotenv requests pillow

# Create Django project (correctly structured)
django-admin startproject LFG .
python manage.py startapp chat