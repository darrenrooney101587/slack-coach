docker build -t slack-coach:latest .
docker compose up -d coach-socket coach-cron
