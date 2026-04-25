@echo off
cd /d C:\Users\IKA\zendaya\zendaya_backend
call poetry shell
poetry run uvicorn main:app --host 127.0.0.1 --port 8000 --reload
