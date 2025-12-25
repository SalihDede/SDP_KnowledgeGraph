@echo off
REM Script to run the kg-gen FastAPI server in Docker
REM Usage: run_server.bat

setlocal

REM Build the Docker image
echo 🐳 Building Docker container for kg-gen scripts...
docker build -f Dockerfile -t kg-gen-dedup-demo .
if errorlevel 1 (
    echo ❌ Error: Docker build failed
    exit /b 1
)
echo ✅ Docker image built successfully!

REM Create output and logs directories if they don't exist
if not exist "output" mkdir output
if not exist "logs" mkdir logs

REM Run the container with volume mounts
echo 🚀 Running kg-gen FastAPI server in Docker container
docker run --rm ^
    -v "%cd%:/workspace" ^
    -v "%cd%/output:/workspace/output" ^
    -v "%cd%/logs:/workspace/logs" ^
    -p 8000:8000 ^
    --add-host=host.docker.internal:host-gateway ^
    --env-file .env ^
    kg-gen-dedup-demo uvicorn app.server:app --reload --host 0.0.0.0 --port 8000

if errorlevel 1 (
    echo ❌ Error: Server failed to start
    exit /b 1
)

endlocal