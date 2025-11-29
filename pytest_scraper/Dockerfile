FROM mcr.microsoft.com/azure-functions/python:4-python3.10

WORKDIR /home/site/wwwroot
ENV PYTHONPATH=/home/site/wwwroot

# Copy app folder
COPY app ./app

# Copy tests folder
COPY tests ./tests

# Install requirements
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
