import { useCallback, useEffect, useState } from 'react'
import '../admin/admin.css'
import { llamar, type Aviso } from '../admin/api'
import { BotonConfirmar, MostrarAviso, Tabla } from '../admin/Avisos'

type Memoria = { nombre: string; mb: number }

type Resumen = {
  instancia: {
    nombre: string
    host: string
    version: string
    estado: string
    inicio: string
    base_datos: string
    modo_log: string
    modo_apertura: string
  }
  memoria: { sga: Memoria[]; sga_total_mb: number; pga: Memoria[] }
  indicadores: {
    buffer_cache_hit: number | null
    library_cache_hit: number | null
    sesiones_total: number
    sesiones_activas: number
  }
}

type Sesion = {
  sid: number
  serial: number
  usuario: string | null
  estado: string
  usuario_so: string | null
  maquina: string | null
  programa: string | null
  conexion: string
  sql_id: string | null
}

type ConsultaSql = {
  sql_id: string
  schema: string
  ejecuciones: number
  tiempo_total_s: number
  cpu_s: number
  lecturas_logicas: number
  lecturas_disco: number
  texto: string
}

type Espera = { evento: string; clase: string; esperas: number; tiempo_s: number }

const porcentaje = (valor: number | null) => (valor === null ? 'Sin datos' : `${valor} %`)

export function Performance({ token }: { token: string }) {
  const [resumen, setResumen] = useState<Resumen | null>(null)
  const [sesiones, setSesiones] = useState<Sesion[]>([])
  const [consultas, setConsultas] = useState<ConsultaSql[]>([])
  const [esperas, setEsperas] = useState<Espera[]>([])
  const [aviso, setAviso] = useState<Aviso | null>(null)
  const [cargando, setCargando] = useState(true)

  const cargar = useCallback(
    () =>
      Promise.all([
        llamar<Resumen>(token, '/performance/resumen'),
        llamar<{ sesiones: Sesion[] }>(token, '/performance/sesiones'),
        llamar<{ consultas: ConsultaSql[] }>(token, '/performance/consultas?limite=10'),
        llamar<{ esperas: Espera[] }>(token, '/performance/esperas'),
      ]).then(([r, s, c, e]) => {
        if (r.ok) setResumen(r.datos)
        if (s.ok) setSesiones(s.datos.sesiones)
        if (c.ok) setConsultas(c.datos.consultas)
        if (e.ok) setEsperas(e.datos.esperas)
        const fallo = [r, s, c, e].find((x) => !x.ok)
        setAviso(fallo && !fallo.ok ? fallo.aviso : null)
        setCargando(false)
      }),
    [token],
  )

  useEffect(() => {
    // Carga inicial de los datos al abrir la pantalla.
    void cargar()
  }, [cargar])

  const terminar = async (sesion: Sesion) => {
    const r = await llamar<{ mensaje: string }>(token, '/performance/sesiones/terminar', {
      sid: sesion.sid,
      serial: sesion.serial,
      confirmar: true,
    })
    if (!r.ok) {
      setAviso(r.aviso)
      return
    }
    await cargar()
    setAviso({ tipo: 'ok', textos: [r.datos.mensaje] })
  }

  return (
    <section className="vista">
      <div className="encabezado-modulo">
        <div>
          <h1>Performance de la base de datos</h1>
          <p className="apoyo">
            Estado de la instancia, uso de memoria, sesiones y las consultas que más recursos consumen.
          </p>
        </div>
        <button
          type="button"
          className="boton principal"
          onClick={() => {
            setCargando(true)
            void cargar()
          }}
          disabled={cargando}
        >
          {cargando ? 'Actualizando…' : 'Actualizar'}
        </button>
      </div>

      <MostrarAviso aviso={aviso} />

      {resumen && (
        <>
          <div className="panel">
            <h2>Instancia</h2>
            <dl className="indicadores">
              <div className="indicador">
                <dt>Estado</dt>
                <dd>{resumen.instancia.estado}</dd>
              </div>
              <div className="indicador">
                <dt>Base de datos</dt>
                <dd>
                  {resumen.instancia.base_datos} ({resumen.instancia.nombre})
                </dd>
              </div>
              <div className="indicador">
                <dt>Versión</dt>
                <dd>{resumen.instancia.version}</dd>
              </div>
              <div className="indicador">
                <dt>Iniciada</dt>
                <dd>{resumen.instancia.inicio}</dd>
              </div>
              <div className="indicador">
                <dt>Modo de log</dt>
                <dd>{resumen.instancia.modo_log}</dd>
              </div>
              <div className="indicador">
                <dt>Apertura</dt>
                <dd>{resumen.instancia.modo_apertura}</dd>
              </div>
            </dl>
          </div>

          <div className="panel">
            <h2>Indicadores</h2>
            <dl className="indicadores">
              <div className="indicador">
                <dt>Buffer cache hit ratio</dt>
                <dd>{porcentaje(resumen.indicadores.buffer_cache_hit)}</dd>
              </div>
              <div className="indicador">
                <dt>Library cache hit ratio</dt>
                <dd>{porcentaje(resumen.indicadores.library_cache_hit)}</dd>
              </div>
              <div className="indicador">
                <dt>Sesiones de usuario</dt>
                <dd>{resumen.indicadores.sesiones_total}</dd>
              </div>
              <div className="indicador">
                <dt>Sesiones activas</dt>
                <dd>{resumen.indicadores.sesiones_activas}</dd>
              </div>
            </dl>
            <p className="ayuda">
              Un hit ratio cercano a 100 % indica que la mayoría de las lecturas se resuelven en memoria.
            </p>
          </div>

          <div className="panel">
            <h2>Memoria</h2>
            <div className="columnas">
              <Tabla
                titulo="SGA"
                columnas={[
                  { titulo: 'SGA', valor: (m: Memoria) => m.nombre },
                  { titulo: 'MB', valor: (m: Memoria) => m.mb },
                ]}
                filas={[...resumen.memoria.sga, { nombre: 'Total SGA', mb: resumen.memoria.sga_total_mb }]}
                clave={(m) => m.nombre}
                vacio="Sin datos de la SGA"
              />
              <Tabla
                titulo="PGA"
                columnas={[
                  { titulo: 'PGA', valor: (m: Memoria) => m.nombre },
                  { titulo: 'MB', valor: (m: Memoria) => m.mb },
                ]}
                filas={resumen.memoria.pga}
                clave={(m) => m.nombre}
                vacio="Sin datos de la PGA"
              />
            </div>
          </div>
        </>
      )}

      <div className="panel">
        <h2>Sesiones de usuario</h2>
        <Tabla
          titulo="Sesiones de usuario"
          columnas={[
            { titulo: 'SID,SERIAL#', valor: (s: Sesion) => `${s.sid},${s.serial}` },
            { titulo: 'Usuario', valor: (s: Sesion) => s.usuario ?? '—' },
            {
              titulo: 'Estado',
              valor: (s: Sesion) => (
                <span className={`estado ${s.estado === 'ACTIVE' ? 'bien' : ''}`}>{s.estado}</span>
              ),
            },
            { titulo: 'Máquina', valor: (s: Sesion) => s.maquina ?? '—' },
            { titulo: 'Programa', valor: (s: Sesion) => s.programa ?? '—' },
            { titulo: 'Conexión', valor: (s: Sesion) => s.conexion },
            {
              titulo: 'Acción',
              valor: (s: Sesion) => (
                <BotonConfirmar
                  etiqueta="Terminar"
                  pregunta={`¿Terminar la sesión ${s.sid},${s.serial}?`}
                  onConfirmar={() => void terminar(s)}
                />
              ),
            },
          ]}
          filas={sesiones}
          clave={(s) => `${s.sid}-${s.serial}`}
          vacio="No hay sesiones de usuario"
        />
      </div>

      <div className="panel">
        <h2>Consultas más costosas</h2>
        <Tabla
          titulo="Consultas más costosas"
          columnas={[
            { titulo: 'SQL_ID', valor: (c: ConsultaSql) => <code className="id">{c.sql_id}</code> },
            { titulo: 'Schema', valor: (c: ConsultaSql) => c.schema },
            { titulo: 'Ejecuciones', valor: (c: ConsultaSql) => c.ejecuciones },
            { titulo: 'Tiempo total (s)', valor: (c: ConsultaSql) => c.tiempo_total_s },
            { titulo: 'CPU (s)', valor: (c: ConsultaSql) => c.cpu_s },
            { titulo: 'Lecturas disco', valor: (c: ConsultaSql) => c.lecturas_disco },
            { titulo: 'Sentencia', valor: (c: ConsultaSql) => <code className="sentencia">{c.texto}</code> },
          ]}
          filas={consultas}
          clave={(c, i) => `${c.sql_id}-${i}`}
          vacio="No hay consultas registradas"
        />
      </div>

      <div className="panel">
        <h2>Principales esperas</h2>
        <Tabla
          titulo="Principales esperas"
          columnas={[
            { titulo: 'Evento', valor: (e: Espera) => e.evento },
            { titulo: 'Clase', valor: (e: Espera) => e.clase },
            { titulo: 'Esperas', valor: (e: Espera) => e.esperas },
            { titulo: 'Tiempo (s)', valor: (e: Espera) => e.tiempo_s },
          ]}
          filas={esperas}
          clave={(e) => e.evento}
          vacio="No hay esperas registradas"
        />
      </div>
    </section>
  )
}
