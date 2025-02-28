# Run migrations to create database tables
python manage.py makemigrations
python manage.py migrate

# Create a superuser for admin access
python manage.py createsuperuser

# Run the development server on port 9000
python manage.py runserver 9000 