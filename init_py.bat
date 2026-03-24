
if not exist ".venv" (
    python -m venv .venv
)
 echo * > .venv/.gitignore


.venv\Scripts\pip install -r requirements.txt 
:: -i "https://mirrors.aliyun.com/pypi/simple/"

if not "%VIRTUAL_ENV%" == "" (
    if not "%VIRTUAL_ENV%" == "%cd%\.venv" (
        .venv\Scripts\activate.bat
    )
) else (
    .venv\Scripts\activate.bat
)
