@echo off
title AgentCompany — FalkorDB Setup
color 0B
echo.
echo  ============================================================
echo   AgentCompany — FalkorDB Local Graph Database Setup
echo  ============================================================
echo.

cd /d "%~dp0"

:: Check Docker
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Docker is not installed or not running.
    echo.
    echo  Please install Docker Desktop from https://www.docker.com/products/docker-desktop/
    echo  Then run this script again.
    echo.
    pause
    exit /b 1
)

echo  [OK] Docker found.
echo.

:: Pull latest FalkorDB image
echo  Pulling FalkorDB image (first time may take a few minutes)...
docker pull falkordb/falkordb:latest

:: Stop existing container if running
docker stop agentcompany-falkordb >nul 2>&1
docker rm agentcompany-falkordb >nul 2>&1

:: Start FalkorDB
echo.
echo  Starting FalkorDB...
docker-compose up -d

echo.
echo  ============================================================
echo   FalkorDB is running!
echo.
echo   Redis/Graph port : localhost:6379
echo   Browser UI       : http://localhost:3000
echo.
echo   To stop:  docker-compose down
echo   To view:  docker-compose logs -f falkordb
echo  ============================================================
echo.
pause
