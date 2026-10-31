import shlex
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence

from src.services.entorno_oracle import OperacionEntornoFallida, Salida
from src.services.politica_respaldo import FRECUENCIAS, POLITICAS, Programacion
from src.services.procesos import ejecutar_proceso

_DIAS = ("SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT")
_SC = {"DIARIO": "DAILY", "SEMANAL": "WEEKLY", "MENSUAL": "MONTHLY", "HORAS": "HOURLY"}


def _id_valido(id_programacion) -> int:
    if type(id_programacion) is not int or id_programacion < 1:
        raise ValueError("El id de la programación debe ser un entero mayor o igual que 1")
    return id_programacion


def _comprobar(prog: Programacion) -> None:
    if prog.politica not in POLITICAS:
        raise ValueError(f"Política desconocida: {prog.politica!r}")
    if prog.frecuencia not in FRECUENCIAS:
        raise ValueError(f"Frecuencia desconocida: {prog.frecuencia!r}")


def nombre_tarea(id_programacion: int) -> str:
    return f"OracleAdmin_{_id_valido(id_programacion)}"


def marca_cron(id_programacion: int) -> str:
    return f"# oracle-admin:{_id_valido(id_programacion)}"


def _hora_minuto(prog: Programacion) -> tuple[int, int]:
    hora, minuto = prog.hora.split(":")
    return int(hora), int(minuto)


def expresion_cron(prog: Programacion) -> str:
    _comprobar(prog)
    if prog.frecuencia == "HORAS":
        return f"0 */{prog.intervalo_horas} * * *"
    h, m = _hora_minuto(prog)
    if prog.frecuencia == "DIARIO":
        return f"{m} {h} * * *"
    if prog.frecuencia == "SEMANAL":
        return f"{m} {h} * * {prog.dia_efectivo}"
    return f"{m} {h} {prog.dia_efectivo} * *"


def argumentos_schtasks(prog: Programacion, id_programacion: int, ruta_script: str) -> list[str]:
    _comprobar(prog)
    args = ["/Create", "/TN", nombre_tarea(id_programacion), "/TR", f'"{ruta_script}"']
    args += ["/SC", _SC[prog.frecuencia], "/ST", "00:00" if prog.frecuencia == "HORAS" else prog.hora]
    if prog.frecuencia == "SEMANAL":
        args += ["/D", _DIAS[prog.dia_efectivo]]
    elif prog.frecuencia == "MENSUAL":
        args += ["/D", str(prog.dia_efectivo)]
    elif prog.frecuencia == "HORAS":
        args += ["/MO", str(prog.intervalo_horas)]
    return args + ["/RU", "SYSTEM", "/F"]


class ProgramadorTareas(ABC):
    @abstractmethod
    def instalar(self, id_programacion: int, prog: Programacion, ruta_script: str) -> None: ...

    @abstractmethod
    def eliminar(self, id_programacion: int) -> None: ...


class ProgramadorCron(ProgramadorTareas):
    def __init__(
        self,
        ejecutar: Callable[..., Salida] = ejecutar_proceso,
        comando: Sequence[str] = ("crontab",),
        comando_escritura: Sequence[str] | None = None,
    ):
        self._ejecutar = ejecutar
        self._comando = list(comando)
        self._comando_escritura = list(comando_escritura or comando)

    def _leer(self) -> list[str]:
        salida = self._ejecutar([*self._comando, "-l"], variables={"LC_ALL": "C"})
        if salida.codigo != 0:
            if salida.texto and "no crontab" not in salida.texto.lower():
                raise OperacionEntornoFallida(salida.texto)
            return []
        return salida.texto.splitlines()

    def _escribir(self, lineas: list[str]) -> None:
        salida = self._ejecutar([*self._comando_escritura, "-"], entrada="\n".join(lineas) + "\n")
        if salida.codigo != 0:
            raise OperacionEntornoFallida(salida.texto)

    @staticmethod
    def _sin(lineas: list[str], marca: str) -> list[str]:
        resto, saltar = [], False
        for linea in lineas:
            if saltar and linea.strip() and not linea.lstrip().startswith("#"):
                saltar = False  # la línea de trabajo que acompaña a la marca propia
            elif linea.rstrip() == marca:
                saltar = True
            else:
                saltar = False
                resto.append(linea)
        return resto

    def instalar(self, id_programacion: int, prog: Programacion, ruta_script: str) -> None:
        marca = marca_cron(id_programacion)
        trabajo = f"{expresion_cron(prog)} {shlex.quote(ruta_script)}"
        self._escribir([*self._sin(self._leer(), marca), marca, trabajo])

    def eliminar(self, id_programacion: int) -> None:
        actual = self._leer()
        resto = self._sin(actual, marca_cron(id_programacion))
        if resto != actual:
            self._escribir(resto)


class ProgramadorCronContenedor(ProgramadorCron):
    """Cron del usuario Oracle dentro de un contenedor; `-i` solo en la escritura (en la lectura colgaría el stdin)."""

    def __init__(self, contenedor: str, ejecutar: Callable[..., Salida], cli: str, usuario: str = "oracle"):
        base = [cli, "exec"]
        destino = ["-u", "root", contenedor]
        super().__init__(
            ejecutar,
            [*base, *destino, "crontab", "-u", usuario],
            [*base, "-i", *destino, "crontab", "-u", usuario],
        )
        self._asegurar = [*base, *destino, "sh", "-c", "pgrep -x crond >/dev/null 2>&1 || crond"]

    def _asegurar_crond(self) -> None:
        salida = self._ejecutar(self._asegurar)
        if salida.codigo != 0:
            raise OperacionEntornoFallida(salida.texto)

    def instalar(self, id_programacion: int, prog: Programacion, ruta_script: str) -> None:
        self._asegurar_crond()
        super().instalar(id_programacion, prog, ruta_script)

    def eliminar(self, id_programacion: int) -> None:
        self._asegurar_crond()
        super().eliminar(id_programacion)
