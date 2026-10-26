import { useEffect, useState } from 'react'
import { avisoDeConexion, cabeceras, ErrorConexion, pedir } from './api'
import { AvisoError, AvisoExito, BarraRespaldando } from './AvisosRespaldo'
import { FormularioDestino, type Directorio } from './FormularioDestino'

type Advertencia = { explicacion: string; log: string }

type Resultado =
  | { tipo: 'ok'; mensaje: string; log: string; advertencia: Advertencia | null }
  | { tipo: 'error'; mensajes: string[]; log?: string }

const CONFIRMACION =
  'Activar ARCHIVELOG reinicia la base de datos y corta todas las sesiones, incluida la tuya. ¿Continuar?'

type Props = {
  token: string
}

type CuerpoDeError = {
  errores?: string[]
  mensaje?: string
  explicacion?: string
  detail?: string
  log?: string
}

// Los errores de la API traen `mensaje` + `explicacion` (+ `log`), `errores` (422) o `detail`.
const comoError = (cuerpo: CuerpoDeError): Resultado => ({
  tipo: 'error',
  mensajes:
    cuerpo.errores ?? [cuerpo.mensaje, cuerpo.explicacion, cuerpo.detail].filter((m): m is string => !!m),
  log: cuerpo.log,
})

export function RespaldoFull({ token }: Props) {
  const [archivelog, setArchivelog] = useState<boolean | null>(null)
  const [sinSysdba, setSinSysdba] = useState(false)
  const [directorios, setDirectorios] = useState<Directorio[]>([])
  const [directorio, setDirectorio] = useState('')
  const [nombre, setNombre] = useState('')
  const [errorCarga, setErrorCarga] = useState<string | null>(null)
  const [errorConexion, setErrorConexion] = useState<string | null>(null)
  const [resultado, setResultado] = useState<Resultado | null>(null)
  const [confirmando, setConfirmando] = useState(false)
  const [respaldando, setRespaldando] = useState(false)

  useEffect(() => {
    const headers = cabeceras(token)
    const alFallarLaConexion = (error: unknown) => {
      if (error instanceof ErrorConexion) setErrorConexion(avisoDeConexion(error))
    }

    pedir('/respaldos/full/estado', { headers })
      .then(({ ok, status, cuerpo }) => {
        if (ok) setArchivelog(cuerpo.archivelog)
        else if (status === 403) setSinSysdba(true)
      })
      .catch(alFallarLaConexion)

    pedir('/respaldos/directorios', { headers })
      .then(({ ok, cuerpo }) => {
        if (ok) setDirectorios(cuerpo.directorios)
        else setErrorCarga(cuerpo.detail)
      })
      .catch(alFallarLaConexion)
  }, [token])

  // Devuelve el cuerpo de la respuesta correcta, o null si hubo un error ya mostrado en pantalla.
  const enviar = async (url: string, cuerpo?: object) => {
    setResultado(null)
    setErrorConexion(null)
    setRespaldando(true)
    try {
      const respuesta = await pedir(url, {
        method: 'POST',
        headers: { ...cabeceras(token), 'Content-Type': 'application/json' },
        body: cuerpo && JSON.stringify(cuerpo),
      })
      if (respuesta.ok) return respuesta.cuerpo
      if (respuesta.status === 403) setSinSysdba(true)
      else if (respuesta.status !== 401) setResultado(comoError(respuesta.cuerpo))
    } catch (error) {
      if (error instanceof ErrorConexion) setErrorConexion(avisoDeConexion(error))
    } finally {
      setRespaldando(false)
    }
    return null
  }

  const respaldar = async () => {
    const cuerpo = await enviar('/respaldos/full', { directorio, nombre })
    if (cuerpo) {
      setResultado({
        tipo: 'ok',
        mensaje: 'Respaldo full creado.',
        log: cuerpo.log,
        advertencia: cuerpo.advertencia,
      })
    }
  }

  const activar = async () => {
    setConfirmando(false)
    const cuerpo = await enviar('/respaldos/full/archivelog')
    if (cuerpo) {
      setArchivelog(true)
      setResultado({ tipo: 'ok', mensaje: cuerpo.mensaje, log: cuerpo.log, advertencia: null })
    }
  }

  const avisos = [
    errorConexion,
    errorCarga,
    sinSysdba ? 'Se requiere sesión SYSDBA' : null,
  ].filter((a): a is string => a !== null)
  const mensajes = [...avisos, ...(resultado?.tipo === 'error' ? resultado.mensajes : [])]

  return (
    <section className="vista">
      <h1>Respaldar base completa (Full)</h1>
      <p className="apoyo">
        Elige el directorio de destino y el nombre del respaldo. Se hace un respaldo nivel 0 de
        toda la base con RMAN.
      </p>

      <AvisoError
        mensajes={mensajes}
        log={resultado?.tipo === 'error' ? resultado.log : undefined}
      />
      {resultado?.tipo === 'ok' && (
        <AvisoExito>
          {resultado.mensaje}
          {resultado.log && <pre>{resultado.log}</pre>}
        </AvisoExito>
      )}
      {resultado?.tipo === 'ok' && resultado.advertencia && (
        <div role="note" className="aviso">
          <p>El respaldo se creó, pero la limpieza de respaldos obsoletos falló.</p>
          <p>{resultado.advertencia.explicacion}</p>
          <pre>{resultado.advertencia.log}</pre>
        </div>
      )}

      {!sinSysdba && archivelog === true && <p className="apoyo">La base de datos está en modo ARCHIVELOG</p>}
      {!sinSysdba && archivelog === false && (
        <div className="aviso">
          <p>La base de datos está en NOARCHIVELOG: actívalo para poder respaldar</p>
          {confirmando ? (
            <>
              <p>{CONFIRMACION}</p>
              <div>
                <button type="button" className="accion" onClick={activar}>
                  Confirmar
                </button>
                <button type="button" className="volver" onClick={() => setConfirmando(false)}>
                  Cancelar
                </button>
              </div>
            </>
          ) : (
            <button type="button" className="accion" onClick={() => setConfirmando(true)}>
              Activar ARCHIVELOG
            </button>
          )}
        </div>
      )}

      <FormularioDestino
        directorios={directorios}
        directorio={directorio}
        alElegirDirectorio={setDirectorio}
        nombre={nombre}
        alCambiarNombre={setNombre}
        etiquetaNombre="Nombre del respaldo"
        ayudaNombre="Las piezas se nombran con este nombre más la base, la fecha y el número de pieza. Usa letras, números, guion y guion bajo."
      />

      {respaldando && <BarraRespaldando />}

      <button
        type="button"
        className="accion"
        onClick={respaldar}
        disabled={respaldando || sinSysdba}
      >
        Respaldar
      </button>
    </section>
  )
}
