FROM python:3.13-slim
WORKDIR /app
COPY project_ten /app/project_ten
ENV PYTHONUNBUFFERED=1 PROJECT_TEN_ROOT=/ledger
VOLUME ["/ledger"]
EXPOSE 8080
CMD ["python", "-m", "project_ten.continuous", "--confirm-sole-runner", "--interval", "60"]
