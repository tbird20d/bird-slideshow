@ECHO OFF
CHDIR %LOCALAPPDATA%\tagger
SET RESETARG=%1
IF "%RESETARG%"=="-r" (
    ECHO Building from scratch...
    RMDIR /S /Q .\build
    RMDIR /S /Q .\dist
) ELSE (
    ECHO Using existing build files...
)
CHDIR C:\Users\natha\Programming\Personal\GitHubProjects\nbird11_bird-slideshow\tagger
pyinstaller tagger.py --onedir --noconfirm --distpath %LOCALAPPDATA%\tagger\dist --workpath %LOCALAPPDATA%\tagger\build --specpath %LOCALAPPDATA%\tagger
