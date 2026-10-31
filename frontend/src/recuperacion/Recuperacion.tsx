import { useCallback, useEffect, useState } from 'react'
import { llamar, type Aviso } from '../admin/api'
import { BotonConfirmar, MostrarAviso, Tabla } from '../admin/Avisos'
import { cabeceras, avisoDeConexion, ErrorConexion, pedir } from '../respaldos/api'
import { AvisoError, AvisoExito } from '../respaldos/AvisosRespaldo'

type Respaldo = {
  directorio: string
  base: string
  tipo: string
  estado: string
  fecha: string
}

type Resultado =
  | { tipo: 'ok'; mensaje: string; log: string; advertencia: string | null; sesionCerrada?: boolean }
  | { tipo: 'error'; mensajes: string[]; log?: string; sinArchivelog?: boolean }

const CONFIRMACION_ARCHIVELOG =
  'Activar ARCHIVELOG reinicia la base de datos y corta todas las sesiones, incluida la tuya. ¿Continuar?'

// Envía la recuperación y deja el resultado (éxito o error con explicación y log) y el estado «Recuperando...».
function usarRecuperacion(token: string, respaldo: Respaldo) {
  const [recuperando, setRecuperando] = useState(false)
  const [resultado, setResultado] = useState<Resultado | null>(null)

  const recuperar = async (cuerpoPeticion: object) => {
    setResultado(null)
    setRecuperando(true)
    try {
      const { ok, status, cuerpo } = await pedir(
        `/directorios/${encodeURIComponent(respaldo.directorio)}/respaldos/${encodeURIComponent(respaldo.base)}/recuperar`,
        {
          method: 'POST',
          headers: { ...cabeceras(token), 'Content-Type': 'application/json' },
          body: JSON.stringify(cuerpoPeticion),
        },
      )
      if (ok) {
        setResultado({
          tipo: 'ok',
          mensaje: cuerpo.mensaje,
          log: cuerpo.log,
          advertencia: cuerpo.advertencia,
          sesionCerrada: cuerpo.sesion_cerrada === true,
        })
      } else {
        const mensajes: string[] =
          cuerpo.errores ?? [cuerpo.detail ?? cuerpo.mensaje, cuerpo.explicacion].filter(Boolean)
        setResultado({ tipo: 'error', mensajes, log: cuerpo.log, sinArchivelog: status === 409 })
      }
    } catch (error) {
      if (!(error instanceof ErrorConexion)) throw error
      setResultado({ tipo: 'error', mensajes: [avisoDeConexion(error)] })
    } finally {
      setRecuperando(false)
    }
  }

  return { recuperando, resultado, setResultado, recuperar }
}

function Progreso() {
  return (
    <div aria-live="polite" className="progreso">
      <p>Recuperando...</p>
      <div className="progreso-pista" aria-hidden="true">
        <div className="progreso-bloque" />
      </div>
    </div>
  )
}

function Resultados({ resultado }: { resultado: Resultado | null }) {
  return (
    <>
      <AvisoError
        mensajes={resultado?.tipo === 'error' ? resultado.mensajes : []}
        log={resultado?.tipo === 'error' ? resultado.log : undefined}
      />
      {resultado?.tipo === 'ok' && (
        <AvisoExito>
          {resultado.mensaje}
          {resultado.advertencia && <p>{resultado.advertencia}</p>}
          {resultado.sesionCerrada && <p>La sesión se cerró. Inicia sesión de nuevo</p>}
          <pre>{resultado.log}</pre>
        </AvisoExito>
      )}
    </>
  )
}

function AvisoEstado({ respaldo }: { respaldo: Respaldo }) {
  if (respaldo.estado === 'Completo') return null
  return <p className="aviso">El respaldo tiene estado «{respaldo.estado}»; se puede recuperar igual.</p>
}

function FormularioDatapump({ token, respaldo }: { token: string; respaldo: Respaldo }) {
  const [objetoModo, setObjetoModo] = useState('tablas')
  const [objetos, setObjetos] = useState('')
  const [existentes, setExistentes] = useState('SKIP')
  const { recuperando, resultado, recuperar } = usarRecuperacion(token, respaldo)

  return (
    <section aria-label={`Recuperar ${respaldo.base}`}>
      <h2>Recuperar {respaldo.base}</h2>
      <AvisoEstado respaldo={respaldo} />
      <label className="campo">
        Modo
        <select value={objetoModo} onChange={(e) => setObjetoModo(e.target.value)}>
          <option value="tablas">Tablas</option>
          <option value="schemas">Schemas</option>
        </select>
      </label>
      <label className="campo">
        Objetos
        <textarea
          value={objetos}
          onChange={(e) => setObjetos(e.target.value)}
          placeholder={objetoModo === 'tablas' ? 'OWNER.TABLA, uno por línea' : 'SCHEMA, uno por línea'}
        />
      </label>
      <label className="campo">
        Tablas existentes
        <select value={existentes} onChange={(e) => setExistentes(e.target.value)}>
          <option value="SKIP">Omitir</option>
          <option value="APPEND">Agregar</option>
          <option value="TRUNCATE">Vaciar y cargar</option>
          <option value="REPLACE">Reemplazar</option>
        </select>
      </label>
      <Resultados resultado={resultado} />
      <BotonConfirmar
        etiqueta="Ejecutar recuperación"
        pregunta={`¿Recuperar ${respaldo.base}? Vaciar y Reemplazar sobrescriben los datos de las tablas existentes.`}
        onConfirmar={() =>
          void recuperar({
            modo: 'datapump',
            objeto_modo: objetoModo,
            objetos: objetos.split(/[\s,]+/).filter(Boolean),
            existentes,
          })
        }
      />
      {recuperando && <Progreso />}
    </section>
  )
}

const PUNTOS = { ultimo: 'Lo último', instante: 'Un instante', respaldo: 'Al estado del respaldo' }

function FormularioRman({ token, respaldo }: { token: string; respaldo: Respaldo }) {
  const [punto, setPunto] = useState<keyof typeof PUNTOS>('ultimo')
  const [hasta, setHasta] = useState('')
  const { recuperando, resultado, setResultado, recuperar } = usarRecuperacion(token, respaldo)

  // Mismo endpoint que RespaldoFull; la base se reinicia, así que la sesión vuelve a pedirse en la siguiente petición.
  const activarArchivelog = async () => {
    try {
      const { ok, cuerpo } = await pedir('/respaldos/full/archivelog', {
        method: 'POST',
        headers: cabeceras(token),
      })
      if (ok) setResultado({ tipo: 'ok', mensaje: cuerpo.mensaje, log: cuerpo.log, advertencia: null })
      else {
        const mensajes: string[] = [cuerpo.detail ?? cuerpo.mensaje, cuerpo.explicacion].filter(Boolean)
        setResultado({ tipo: 'error', mensajes, log: cuerpo.log })
      }
    } catch (error) {
      if (!(error instanceof ErrorConexion)) throw error
      setResultado({ tipo: 'error', mensajes: [avisoDeConexion(error)] })
    }
  }

  return (
    <section aria-label={`Recuperar ${respaldo.base}`}>
      <h2>Recuperar {respaldo.base}</h2>
      <AvisoEstado respaldo={respaldo} />
      <label className="campo">
        Punto de recuperación
        <select value={punto} onChange={(e) => setPunto(e.target.value as keyof typeof PUNTOS)}>
          {Object.entries(PUNTOS).map(([valor, texto]) => (
            <option key={valor} value={valor}>
              {texto}
            </option>
          ))}
        </select>
      </label>
      {punto === 'instante' && (
        <label className="campo">
          UNTIL TIME
          <input value={hasta} onChange={(e) => setHasta(e.target.value)} placeholder="AAAA-MM-DD HH:MM:SS" />
        </label>
      )}
      <Resultados resultado={resultado} />
      {resultado?.tipo === 'error' && resultado.sinArchivelog && (
        <BotonConfirmar
          etiqueta="Activar ARCHIVELOG"
          pregunta={CONFIRMACION_ARCHIVELOG}
          onConfirmar={() => void activarArchivelog()}
        />
      )}
      <BotonConfirmar
        etiqueta="Ejecutar recuperación"
        pregunta={`¿Recuperar la base completa desde ${respaldo.base} (${PUNTOS[punto]})? Se apaga la base de datos y se cierra la sesión.`}
        onConfirmar={() => void recuperar({ modo: 'full', punto, ...(punto === 'instante' && { hasta }) })}
      />
      {recuperando && <Progreso />}
    </section>
  )
}

export function Recuperacion({ token }: { token: string }) {
  const [respaldos, setRespaldos] = useState<Respaldo[]>([])
  const [aviso, setAviso] = useState<Aviso | null>(null)
  const [elegido, setElegido] = useState<Respaldo | null>(null)

  const cargar = useCallback(async () => {
    const r = await llamar<{ respaldos: Respaldo[]; avisos: string[] }>(token, '/directorios/respaldos')
    if (!r.ok) return setAviso(r.aviso)
    const { respaldos = [], avisos = [] } = r.datos
    setRespaldos(respaldos)
    setAviso(avisos.length > 0 ? { tipo: 'error', textos: avisos } : null)
  }, [token])

  useEffect(() => {
    void cargar()
  }, [cargar])

  return (
    <div className="panel">
      <h1>Recuperación de respaldos</h1>
      <MostrarAviso aviso={aviso} />
      <Tabla
        titulo="Respaldos"
        columnas={[
          { titulo: 'Respaldo', valor: (r: Respaldo) => r.base },
          { titulo: 'Tipo', valor: (r: Respaldo) => r.tipo },
          { titulo: 'Estado', valor: (r: Respaldo) => r.estado },
          { titulo: 'Directorio', valor: (r: Respaldo) => r.directorio },
          { titulo: 'Fecha', valor: (r: Respaldo) => new Date(r.fecha).toLocaleString('es') },
          {
            titulo: 'Acciones',
            valor: (r: Respaldo) => (
              <button type="button" className="boton" aria-label={`Recuperar ${r.base}`} onClick={() => setElegido(r)}>
                Recuperar
              </button>
            ),
          },
        ]}
        filas={respaldos}
        clave={(r) => `${r.directorio}/${r.base}`}
        vacio="No hay respaldos para mostrar"
      />
      {elegido?.tipo === 'Data Pump' && <FormularioDatapump key={`${elegido.directorio}/${elegido.base}`} token={token} respaldo={elegido} />}
      {elegido?.tipo === 'RMAN' && <FormularioRman key={`${elegido.directorio}/${elegido.base}`} token={token} respaldo={elegido} />}
    </div>
  )
}
