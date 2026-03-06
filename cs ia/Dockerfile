FROM python:3.10

WORKDIR /app

# Use single quotes for paths with spaces
COPY './cs ia/app.py' /app/
COPY './cs ia/templates' /app/templates
COPY './cs ia/static' /app/static
COPY './cs ia/instance' /app/instance
COPY './cs ia/requirements.txt' /app/


RUN pip install --no-cache-dir -r requirements.txt
RUN pip install reportlab

EXPOSE 5000

CMD ["python", "app.py"]