FROM python:3.11-slim

# Устанавливаем часовой пояс
ENV TZ=Europe/Moscow
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем requirements.txt и обновляем pip
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY . .

# Настраиваем права для пользователя 1000:1000
RUN chown -R 1000:1000 /app

# Указываем пользователя
USER 1000:1000

# Открываем порт
EXPOSE 8000

# Команда по умолчанию (переопределяется в docker-compose.yml)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]