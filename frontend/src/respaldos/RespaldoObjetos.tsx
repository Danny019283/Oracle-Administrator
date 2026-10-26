import { useEffect, useRef, useState } from 'react'
import { avisoDeConexion, cabeceras, ErrorConexion, pedir } from './api'
import { AvisoError, AvisoExito, BarraRespaldando } from './AvisosRespaldo'
import { FormularioDestino, type Directorio } from './FormularioDestino'

type Resultado =
  | { tipo: 'ok'; dmp: string; log: string }
  | { tipo: 'error'; mensajes: string[]; log?: string }

// Lo único que cambia entre respaldar tablas y respaldar schemas.
export type TipoObjeto = {
  recurso: string
  titulo: string
  encabezadoLista: string
  descripcion: string
  seleccionarTodos: string
}

type Props = {
  token: string
  tipo: TipoObjeto
}

export function RespaldoObjetos({ token, tipo }: Props) {
  const { recurso } = tipo
  const [objetos, setObjetos] = useState<string[]>([])
  const [directorios, setDirectorios] = useState<Directorio[]>([])
  const [seleccionados, setSeleccionados] = useState<string[]>([])
  const [directorio, setDirectorio] = useState('')
  const [nombre, setNombre] = useState('')
  const [errorObjetos, setErrorObjetos] = useState<string | null>(null)
  const [errorDirectorios, setErrorDirectorios] = useState<string | null>(null)
  const [resultado, setResultado] = useState<Resultado | null>(null)
  const [errorConexion, setErrorConexion] = useState<string | null>(null)
  const [respaldando, setRespaldando] = useState(false)
  const encabezado = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    const headers = cabeceras(token)
    const alFallarLaConexion = (error: unknown) => {
      if (error instanceof ErrorConexion) setErrorConexion(avisoDeConexion(error))
    }

    pedir(`/respaldos/${recurso}`, { headers })
      .then(({ ok, cuerpo }) => {
        if (ok) setObjetos(cuerpo[recurso])
        else setErrorObjetos(cuerpo.detail)
      })
      .catch(alFallarLaConexion)

    pedir('/respaldos/directorios', { headers })
      .then(({ ok, cuerpo }) => {
        if (ok) setDirectorios(cuerpo.directorios)
        else setErrorDirectorios(cuerpo.detail)
      })
      .catch(alFallarLaConexion)
  }, [token, recurso])

  const todosMarcados = objetos.length > 0 && seleccionados.length === objetos.length

  const alternar = (objeto: string) =>
    setSeleccionados((actuales) =>
      actuales.includes(objeto) ? actuales.filter((o) => o !== objeto) : [...actuales, objeto],
    )

  const respaldar = async () => {
    setResultado(null)
    setErrorConexion(null)
    setRespaldando(true)
    try {
      const { ok, status, cuerpo } = await pedir(`/respaldos/${recurso}`, {
        method: 'POST',
        headers: { ...cabeceras(token), 'Content-Type': 'application/json' },
        body: JSON.stringify({ [recurso]: seleccionados, directorio, nombre }),
      })
      if (ok && cuerpo.dmp) setResultado({ tipo: 'ok', dmp: cuerpo.dmp, log: cuerpo.log })
      else if (status === 422) setResultado({ tipo: 'error', mensajes: cuerpo.errores })
      else if (!ok) {
        const mensajes = [cuerpo.mensaje, cuerpo.explicacion].filter(Boolean)
        setResultado({ tipo: 'error', mensajes, log: cuerpo.log })
      }
    } catch (error) {
      if (error instanceof ErrorConexion) setErrorConexion(avisoDeConexion(error))
    } finally {
      setRespaldando(false)
    }
  }

  const avisos = [errorConexion, errorObjetos, errorDirectorios].filter(
    (a): a is string => a !== null,
  )
  const mensajes = [...avisos, ...(resultado?.tipo === 'error' ? resultado.mensajes : [])]

  // El botón queda al final de la página y los avisos arriba: se llevan a la vista.
  useEffect(() => {
    if (resultado) encabezado.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
  }, [resultado])

  return (
    <section className="vista">
      <h1 ref={encabezado}>{tipo.titulo}</h1>
      <p className="apoyo">{tipo.descripcion}</p>

      <AvisoError
        mensajes={mensajes}
        log={resultado?.tipo === 'error' ? resultado.log : undefined}
      />
      {resultado?.tipo === 'ok' && (
        <AvisoExito>
          Respaldo creado: {resultado.dmp} (log: {resultado.log})
        </AvisoExito>
      )}

      <div className="panel">
        <h2>{tipo.encabezadoLista}</h2>
        <label className="opcion todas">
          <input
            type="checkbox"
            checked={todosMarcados}
            onChange={() => setSeleccionados(todosMarcados ? [] : objetos)}
          />
          {tipo.seleccionarTodos}
        </label>
        <ul className="opciones">
          {objetos.map((objeto) => (
            <li key={objeto}>
              <label className="opcion">
                <input
                  type="checkbox"
                  checked={seleccionados.includes(objeto)}
                  onChange={() => alternar(objeto)}
                />
                {objeto}
              </label>
            </li>
          ))}
        </ul>
      </div>

      <FormularioDestino
        directorios={directorios}
        directorio={directorio}
        alElegirDirectorio={setDirectorio}
        nombre={nombre}
        alCambiarNombre={setNombre}
        etiquetaNombre="Nombre del dumpfile"
        ayudaNombre="Se agrega la fecha y la hora al nombre. Usa letras, números, guion y guion bajo."
      />

      {respaldando && <BarraRespaldando />}

      <button type="button" className="accion" onClick={respaldar} disabled={respaldando}>
        Respaldar
      </button>
    </section>
  )
}
