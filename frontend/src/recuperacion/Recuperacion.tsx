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
  | { tipo: 'ok'; mensaje: string; log: string; advertencia: string | null }
  | { tipo: 'error'; mensajes: string[]; log?: string }

function FormularioDatapump({ token, respaldo }: { token: string; respaldo: Respaldo }) {
  const [objetoModo, setObjetoModo] = useState('tablas')
  const [objetos, setObjetos] = useState('')
  const [existentes, setExistentes] = useState('SKIP')
  const [recuperando, setRecuperando] = useState(false)
  const [resultado, setResultado] = useState<Resultado | null>(null)

  const recuperar = async () => {
    setResultado(null)
    setRecuperando(true)
    try {
      const { ok, cuerpo } = await pedir(
        `/directorios/${encodeURIComponent(respaldo.directorio)}/respaldos/${encodeURIComponent(respaldo.base)}/recuperar`,
        {
          method: 'POST',
          headers: { ...cabeceras(token), 'Content-Type': 'application/json' },
          body: JSON.stringify({
            modo: 'datapump',
            objeto_modo: objetoModo,
            objetos: objetos.split(/[\s,]+/).filter(Boolean),
            existentes,
          }),
        },
      )
      if (ok) setResultado({ tipo: 'ok', mensaje: cuerpo.mensaje, log: cuerpo.log, advertencia: cuerpo.advertencia })
      else {
        const mensajes: string[] = cuerpo.errores ?? [cuerpo.detail ?? cuerpo.mensaje, cuerpo.explicacion].filter(Boolean)
        setResultado({ tipo: 'error', mensajes, log: cuerpo.log })
      }
    } catch (error) {
      if (!(error instanceof ErrorConexion)) throw error
      setResultado({ tipo: 'error', mensajes: [avisoDeConexion(error)] })
    } finally {
      setRecuperando(false)
    }
  }

  return (
    <section aria-label={`Recuperar ${respaldo.base}`}>
      <h2>Recuperar {respaldo.base}</h2>
      {respaldo.estado !== 'Completo' && (
        <p className="aviso">El respaldo tiene estado «{respaldo.estado}»; se puede recuperar igual.</p>
      )}
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
      <AvisoError
        mensajes={resultado?.tipo === 'error' ? resultado.mensajes : []}
        log={resultado?.tipo === 'error' ? resultado.log : undefined}
      />
      {resultado?.tipo === 'ok' && (
        <AvisoExito>
          {resultado.mensaje}
          {resultado.advertencia && <p>{resultado.advertencia}</p>}
          <pre>{resultado.log}</pre>
        </AvisoExito>
      )}
      <BotonConfirmar
        etiqueta="Ejecutar recuperación"
        pregunta={`¿Recuperar ${respaldo.base}? Vaciar y Reemplazar sobrescriben los datos de las tablas existentes.`}
        onConfirmar={() => void recuperar()}
      />
      {recuperando && (
        <div aria-live="polite" className="progreso">
          <p>Recuperando...</p>
          <div className="progreso-pista" aria-hidden="true">
            <div className="progreso-bloque" />
          </div>
        </div>
      )}
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
    </div>
  )
}
