docker build -t slack-coach:latest .
docker compose up -d coach-server coach-socket coach-cron
