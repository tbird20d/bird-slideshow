@ECHO OFF
SET DEBUG=%1
CHDIR C:\Users\natha\Programming\Personal\GitHubProjects\nbird11_bird-slideshow\tagger
IF NOT EXIST %LOCALAPPDATA%\tagger\dist\tagger\tagger.exe (
    ECHO Did not find `tagger.exe`.
    ECHO Building executable...
    CALL .\build-executable.bat
) ELSE (
    ECHO Found `tagger.exe`.
)
@ECHO ON
tagger remove-database %DEBUG%
tagger init %DEBUG%
@CHDIR .\sample-pics
tagger tag sample -- dessert-swans.JPG ropes-zipline-course.JPG Tori-gate-japan.jpg skyscraper.jpg %DEBUG%
tagger tag outside -- ropes-zipline-course.JPG Tori-gate-japan.jpg skyscraper.jpg %DEBUG%
tagger tag tree -- ropes-zipline-course.JPG Tori-gate-japan.jpg %DEBUG%
tagger tag building -- skyscraper.jpg %DEBUG%
tagger tag japan -- Tori-gate-japan.jpg %DEBUG%
tagger tag food -- dessert-swans.JPG %DEBUG%

sqlite3 %LOCALAPPDATA%\tagger\tagger.db .dump