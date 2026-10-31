from pathlib import PurePosixPath, PureWindowsPath

import pytest

from src.services.politica_respaldo import script_rman

POSIX = PurePosixPath("/u01/backup/politica")
WINDOWS = PureWindowsPath("D:/BACKUP/POLITICA")

FULL = """RUN {{
  ALLOCATE CHANNEL ch1 DEVICE TYPE DISK;
  BACKUP INCREMENTAL LEVEL 0
  DATABASE
  TAG 'PROG_FULL_L0'
  FORMAT '{f}';
  CROSSCHECK BACKUP;
  CROSSCHECK ARCHIVELOG ALL;
  DELETE NOPROMPT OBSOLETE;
  RELEASE CHANNEL ch1;
}}
"""
INCREMENTAL = """RUN {{
  ALLOCATE CHANNEL ch1 DEVICE TYPE DISK;
  BACKUP INCREMENTAL LEVEL 1
  DATABASE
  TAG 'PROG_INCREMENTAL_L1'
  FORMAT '{f}';
  BACKUP ARCHIVELOG ALL
  FORMAT '{f}'
  DELETE INPUT;
  RELEASE CHANNEL ch1;
}}
"""
TRANSACCIONAL = """RUN {{
  ALLOCATE CHANNEL ch1 DEVICE TYPE DISK;
  SQL 'ALTER SYSTEM SWITCH LOGFILE';
  BACKUP ARCHIVELOG ALL
  TAG 'PROG_TRANSACCIONAL'
  FORMAT '{f}'
  DELETE INPUT;
  RELEASE CHANNEL ch1;
}}
"""
PLANTILLAS = {"FULL": FULL, "INCREMENTAL": INCREMENTAL, "TRANSACCIONAL": TRANSACCIONAL}
FORMATOS = {
    POSIX: "/u01/backup/politica/&1_%d_%s_%p.dbf",
    WINDOWS: "D:\\BACKUP\\POLITICA\\&1_%d_%s_%p.dbf",
}


@pytest.mark.parametrize("politica", PLANTILLAS)
@pytest.mark.parametrize("ruta", FORMATOS)
def test_texto_exacto(politica, ruta):
    assert script_rman(politica, ruta) == PLANTILLAS[politica].format(f=FORMATOS[ruta])


@pytest.mark.parametrize("politica", PLANTILLAS)
def test_sin_redundancy_y_con_variable_de_rman(politica):
    script = script_rman(politica, POSIX)
    assert "REDUNDANCY" not in script
    assert "FORMAT '/u01/backup/politica/&1_%d_%s_%p.dbf'" in script


def test_politica_desconocida():
    with pytest.raises(ValueError):
        script_rman("OTRA", POSIX)
