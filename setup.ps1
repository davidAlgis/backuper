# Setup.ps1

# Set the script directory to ensure relative paths are correctly resolved
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -Path $scriptDir

# Check if the virtual environment already exists
if (-Not (Test-Path -Path ".\env")) {
    Write-Host "Creating virtual environment 'env'..."
    python -m venv env
}

# Activate the virtual environment
Write-Host "Activating the virtual environment..."
. .\env\Scripts\Activate.ps1

# Install dependencies from requirements.txt (if it exists)
if (Test-Path -Path ".\requirements.txt") {
    Write-Host "Installing dependencies from requirements.txt..."
    pip install -r .\requirements.txt
}

# Execute the pyinstaller command to create the executable
Write-Host "Running PyInstaller..."
pyinstaller --onefile --name backuper --clean --windowed --icon=backuper-icon.ico --distpath . --workpath . main.py

Write-Host "Build process complete. Check the 'dist' directory for the 'backuper.exe' file."
