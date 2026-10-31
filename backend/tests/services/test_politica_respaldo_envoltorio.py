from pathlib import PurePosixPath, PureWindowsPath

import pytest

from src.services.politica_respaldo import envoltorio, extension_envoltorio

RMAN_POSIX = PurePosixPath("/u01/backup/scripts_programados/diario.rman")
DEST_POSIX = PurePosixPath("/u01/backup")
RMAN_WIN = PureWindowsPath("D:/BACKUP/scripts_programados/diario.rman")
DEST_WIN = PureWindowsPath("D:/BACKUP")

SH = """#!/bin/sh
export ORACLE_SID=ORCLCDB
export ORACLE_HOME=/opt/oracle/product/21c/dbhome_1
export PATH="$ORACLE_HOME/bin:$PATH"
BASE="diario-1_$(date +%Y%m%d_%H%M%S)"
rman target / cmdfile=/u01/backup/scripts_programados/diario.rman log=/u01/backup/$BASE.log using "$BASE"
exit $?
"""

BAT = "\r\n".join(
    [
        "@echo off",
        "set ORACLE_SID=ORCLCDB",
        r"set ORACLE_HOME=C:\app\oracle\product\21c\dbhome_1",
        r"set PATH=%ORACLE_HOME%\bin;%PATH%",
        """for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set TS=%%i""",
        "set BASE=diario-1_%TS%",
        r'rman target / cmdfile="D:\BACKUP\scripts_programados\diario.rman" log="D:\BACKUP\%BASE%.log" using %BASE%',
        "exit /b %errorlevel%",
        "",
    ]
)


def sh(**cambios):
    args = dict(
        nombre="diario-1",
        sid="ORCLCDB",
        oracle_home="/opt/oracle/product/21c/dbhome_1",
        ruta_rman=RMAN_POSIX,
        ruta_destino=DEST_POSIX,
    )
    return envoltorio(**{**args, **cambios})


def bat(**cambios):
    return sh(
        oracle_home=r"C:\app\oracle\product\21c\dbhome_1",
        ruta_rman=RMAN_WIN,
        ruta_destino=DEST_WIN,
        **cambios,
    )


def test_extension_segun_tipo_de_ruta():
    assert extension_envoltorio(RMAN_POSIX) == ".sh"
    assert extension_envoltorio(RMAN_WIN) == ".bat"


def test_envoltorio_sh_texto_exacto():
    assert sh() == SH


def test_envoltorio_bat_texto_exacto_con_crlf():
    assert bat() == BAT
    assert "\r\n" in bat() and bat().count("\n") == bat().count("\r\n")


def test_sh_sin_crlf():
    assert "\r" not in sh()


@pytest.mark.parametrize("texto", [sh(), bat()])
def test_sin_contrasenas_y_rman_termina_con_la_base(texto):
    assert "password" not in texto.lower() and "identified" not in texto.lower()
    linea = next(l for l in texto.splitlines() if l.startswith("rman "))
    assert "target /" in linea
    assert linea.endswith(('using "$BASE"', "using %BASE%"))


def test_oracle_home_con_espacio_se_entrecomilla_en_sh():
    assert "export ORACLE_HOME='/opt/mi oracle'\n" in sh(oracle_home="/opt/mi oracle")


@pytest.mark.parametrize("nombre", ["con espacio", "a;b", "$(reboot)", "", "ñandú", "a\nb"])
def test_nombre_invalido(nombre):
    with pytest.raises(ValueError):
        sh(nombre=nombre)


@pytest.mark.parametrize("sid", ["A;B", "", "A B", "A-B", "$(x)"])
def test_sid_invalido(sid):
    with pytest.raises(ValueError):
        sh(sid=sid)


@pytest.mark.parametrize(
    "home",
    ["/opt/o'x", '/opt/o"x', "/opt/a\nb", "/opt/a\rb", "/opt/$HOME", "/opt/`id`", "/opt/%X%",
     "/opt/a&b", "/opt/a|b", "/opt/a<b", "/opt/a>b", "/opt/a^b", "/opt/a!b", "/opt/a;b",
     "relativa/ruta", ""],
)
def test_oracle_home_invalido(home):
    with pytest.raises(ValueError):
        sh(oracle_home=home)


def test_oracle_home_windows_con_unidad_vale():
    assert "set ORACLE_HOME=C:\\x\n".replace("\n", "\r\n") in sh(
        oracle_home="C:\\x", ruta_rman=RMAN_WIN, ruta_destino=DEST_WIN
    )
