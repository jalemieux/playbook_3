FROM python:3.14-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV CHANNEL=cli
CMD ["sh", "-c", "python main.py --channel $CHANNEL"]
