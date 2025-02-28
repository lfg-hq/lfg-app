# Use an official Python runtime as a parent image.
FROM python:3.10-slim

# Prevent Python from writing pyc files to disk & enable unbuffered output.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory inside the container.
WORKDIR /app

# Install dependencies.
# It's a good idea to copy only the requirements first for caching.
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the project files into the container.
COPY . /app/

# Create the staticfiles directory
RUN mkdir -p /app/staticfiles

# Collect static files (if your project uses Django's staticfiles app).
RUN python manage.py collectstatic --noinput

# Expose port 8000 for the Django app.
EXPOSE 8000

# Command to run the Django development server.
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
