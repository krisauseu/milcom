FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# The aircraft DB (aircraft.csv.gz) is downloaded automatically
# on first startup by app.py and refreshed every 12 hours.

EXPOSE 5050

CMD ["python", "app.py"]
