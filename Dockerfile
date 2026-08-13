# استخدام نسخة بايثون رسمية وخفيفة
FROM python:3.10-slim

# تحديد مجلد العمل داخل السيرفر
WORKDIR /app

# نسخ ملف المكتبات أولاً لتسريع البناء
COPY requirements.txt .

# تثبيت المكتبات المستخدمة في المشروع
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات المشروع إلى السيرفر
COPY . .

# المنفذ الذي سيعمل عليه التطبيق
EXPOSE 5000

# أمر تشغيل تطبيق Flask
CMD ["python", "app.py"]
