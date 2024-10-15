@echo off
SET BASE_DIR=C:\Users\kevin\Desktop\PeerToPeerFileSharing
SET CLIENT2_DIR=%BASE_DIR%\client2
SET CLIENT3_DIR=%BASE_DIR%\client3
SET FILES_DIR=files

:: Clear client2's files folder
echo Clearing client2's files folder...
del /q "%CLIENT2_DIR%\%FILES_DIR%\*.*"
echo client2's files folder cleared.

:: Clear client3's files folder
echo Clearing client3's files folder...
del /q "%CLIENT3_DIR%\%FILES_DIR%\*.*"
echo client3's files folder cleared.

echo Cleanup complete.
