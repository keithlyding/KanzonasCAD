@echo off
rem Starts KanzonasCAD from this folder (no Command Prompt window stays open).
cd /d "%~dp0"
start "" pyw -m kanzonascad %*
