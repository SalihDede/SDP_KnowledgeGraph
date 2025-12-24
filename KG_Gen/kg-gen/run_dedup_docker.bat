@echo off
REM Script to run the dedup_graph.py script in Docker
REM Usage: run_dedup_docker.bat <graph path> [additional_args...]

setlocal enabledelayedexpansion

REM Default script to run
set SCRIPT=examples/dedup_graph.py

REM Build the Docker image
echo 🐳 Building Docker container for kg-gen scripts...
docker build -f Dockerfile -t kg-gen-dedup-graph .
if errorlevel 1 (
    echo ❌ Error: Docker build failed
    exit /b 1
)
echo ✅ Docker image built successfully!

REM Check if the script exists
if not exist "%SCRIPT%" (
    echo ❌ Error: %SCRIPT% not found in current directory
    echo    Available Python scripts:
    dir /b *.py 2>nul
    if errorlevel 1 echo    No Python scripts found
    exit /b 1
)

REM Create output and logs directories if they don't exist
if not exist "output" mkdir output
if not exist "logs" mkdir logs

REM Run the container with volume mounts
echo 🚀 Running %SCRIPT% in Docker container with arguments: %*
docker run --rm ^
    -v "%cd%:/workspace" ^
    -v "%cd%/output:/workspace/output" ^
    -v "%cd%/logs:/workspace/logs" ^
    --env-file .env ^
    kg-gen-dedup-graph python "%SCRIPT%" %*

if errorlevel 1 (
    echo ❌ Error: Script execution failed
    exit /b 1
)

echo ✅ Script execution completed! Check the output/ directory for results.

endlocal