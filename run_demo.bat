@echo off
SET BASE_DIR=C:\Users\kevin\Desktop\PeerToPeerFileSharing
SET CLIENT1_DIR=%BASE_DIR%\client1
SET CLIENT2_DIR=%BASE_DIR%\client2
SET CLIENT3_DIR=%BASE_DIR%\client3
SET PYTHON=python
SET SERVER=server.py
SET CLIENT=client.py

:: Launch the server in its own window
echo Starting the server...
start "Server" cmd /k "%PYTHON% %SERVER%"
timeout /t 2 > nul

:: Launch client1 in its own window and ensure it runs in client1's directory
echo Starting client1...
start "Client1" cmd /k "cd /d %CLIENT1_DIR% && %PYTHON% %CLIENT%"
timeout /t 2 > nul

:: Launch client2 in its own window and ensure it runs in client2's directory
echo Starting client2...
start "Client2" cmd /k "cd /d %CLIENT2_DIR% && %PYTHON% %CLIENT%"
timeout /t 2 > nul

:: Launch client3 in its own window and ensure it runs in client3's directory
echo Starting client3...
start "Client3" cmd /k "cd /d %CLIENT3_DIR% && %PYTHON% %CLIENT%"
