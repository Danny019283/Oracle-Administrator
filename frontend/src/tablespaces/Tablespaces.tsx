import { useCallback, useEffect, useState } from 'react'
import '../admin/admin.css'
import { llamar, type Aviso, type Credenciales } from '../admin/api'
import { BotonConfirmar, MostrarAviso, Tabla } from '../admin/Avisos'

type Tablespace = {
  nombre: string
  tipo: string
  estado: string
  bigfile: boolean
  tamano_mb: number
  usado_mb: number
  libre_mb: number
  maximo_mb: number
  porcentaje_uso: number
  archivos: number
}

type Datafile = {
  id: number
  archivo: string
  tamano_mb: number
  autoextensible: boolean
  maximo_mb: number
  estado: string
}

type Detalle = Tablespace & { datafiles: Datafile[] }

type Mensaje = { mensaje: string }

type Vista = { tipo: 'lista' } | { tipo: 'crear' } | { tipo: 'detalle'; tablespace: string }

const TIPOS: Record<string, string> = {
  PERMANENT: 'Permanente',
  TEMPORARY: 'Temporal',
  UNDO: 'Undo',
}

// A partir de este porcentaje el uso se marca como alto.
const USO_ALTO = 85

// Solo se cambia el estado de tablespaces permanentes que no sean del sistema.
const estadoEditable = (ts: Tablespace) => ts.tipo === 'PERMANENT' && !['SYSTEM', 'SYSAUX'].includes(ts.nombre)

const carpetaDe = (ruta: string) => ruta.slice(0, ruta.lastIndexOf('/') + 1)

function Uso({ porcentaje }: { porcentaje: number }) {
  return (
    <span className={`uso ${porcentaje >= USO_ALTO ? 'alto' : ''}`}>
      <span className="pista-uso" aria-hidden="true">
        <span className="relleno" style={{ width: `${Math.min(porcentaje, 100)}%` }} />
      </span>
      {porcentaje} %
    </span>
  )
}

function EstadoTablespace({ estado }: { estado: string }) {
  return <span className={`estado ${estado === 'ONLINE' ? 'bien' : estado === 'OFFLINE' ? 'mal' : ''}`}>{estado}</span>
}

type Props = { credenciales: Credenciales }

export function Tablespaces({ credenciales }: Props) {
  const [vista, setVista] = useState<Vista>({ tipo: 'lista' })
  const [aviso, setAviso] = useState<Aviso | null>(null)

  const ir = (siguiente: Vista, mensaje: Aviso | null = null) => {
    setAviso(mensaje)
    setVista(siguiente)
  }

  return (
    <section className="vista">
      {vista.tipo !== 'lista' && (
        <button type="button" className="volver" onClick={() => ir({ tipo: 'lista' })}>
          ← Lista de tablespaces
        </button>
      )}
      {vista.tipo === 'lista' && (
        <ListaTablespaces credenciales={credenciales} aviso={aviso} setAviso={setAviso} ir={ir} />
      )}
      {vista.tipo === 'crear' && (
        <CrearTablespace credenciales={credenciales} aviso={aviso} setAviso={setAviso} ir={ir} />
      )}
      {vista.tipo === 'detalle' && (
        <DetalleTablespace
          credenciales={credenciales}
          tablespace={vista.tablespace}
          aviso={aviso}
          setAviso={setAviso}
        />
      )}
    </section>
  )
}

type PropsVista = Props & {
  aviso: Aviso | null
  setAviso: (aviso: Aviso | null) => void
  ir: (vista: Vista, mensaje?: Aviso | null) => void
}

function ListaTablespaces({ credenciales, aviso, setAviso, ir }: PropsVista) {
  const [tablespaces, setTablespaces] = useState<Tablespace[]>([])

  useEffect(() => {
    void llamar<{ tablespaces: Tablespace[] }>(credenciales, '/tablespaces').then((r) => {
      if (r.ok) setTablespaces(r.datos.tablespaces)
      else setAviso(r.aviso)
    })
  }, [credenciales, setAviso])

  return (
    <>
      <div className="encabezado-modulo">
        <div>
          <h1>Administración de tablespaces</h1>
          <p className="apoyo">
            Revisa cuánto espacio usa cada tablespace, crea nuevos y administra sus archivos de datos.
          </p>
        </div>
        <button type="button" className="boton principal" onClick={() => ir({ tipo: 'crear' })}>
          Crear tablespace
        </button>
      </div>

      <MostrarAviso aviso={aviso} />

      <div className="panel">
        <h2>Tablespaces</h2>
        <Tabla
          titulo="Tablespaces"
          columnas={[
            { titulo: 'Nombre', valor: (t: Tablespace) => t.nombre },
            { titulo: 'Tipo', valor: (t: Tablespace) => TIPOS[t.tipo] ?? t.tipo },
            { titulo: 'Estado', valor: (t: Tablespace) => <EstadoTablespace estado={t.estado} /> },
            { titulo: 'Tamaño (MB)', valor: (t: Tablespace) => t.tamano_mb },
            { titulo: 'Usado (MB)', valor: (t: Tablespace) => t.usado_mb },
            { titulo: 'Libre (MB)', valor: (t: Tablespace) => t.libre_mb },
            { titulo: 'Uso', valor: (t: Tablespace) => <Uso porcentaje={t.porcentaje_uso} /> },
            { titulo: 'Máximo (MB)', valor: (t: Tablespace) => t.maximo_mb },
            {
              titulo: 'Detalle',
              valor: (t: Tablespace) => (
                <button
                  type="button"
                  className="boton"
                  aria-label={`Administrar ${t.nombre}`}
                  onClick={() => ir({ tipo: 'detalle', tablespace: t.nombre })}
                >
                  Administrar
                </button>
              ),
            },
          ]}
          filas={tablespaces}
          clave={(t) => t.nombre}
          vacio="No hay tablespaces para mostrar"
        />
        <p className="ayuda">
          El máximo es hasta dónde puede crecer el tablespace si sus archivos tienen AUTOEXTEND activado.
        </p>
      </div>
    </>
  )
}

type Archivo = {
  archivo: string
  tamano: string
  autoextend: boolean
  siguiente: string
  maximo: string
}

const ARCHIVO_INICIAL: Archivo = {
  archivo: '',
  tamano: '100M',
  autoextend: true,
  siguiente: '10M',
  maximo: 'UNLIMITED',
}

function CamposArchivo({
  valor,
  onCambiar,
  carpeta,
}: {
  valor: Archivo
  onCambiar: (valor: Archivo) => void
  carpeta: string
}) {
  const cambiar = (campo: Partial<Archivo>) => onCambiar({ ...valor, ...campo })
  return (
    <>
      <label className="campo">
        Nombre del archivo
        <input value={valor.archivo} onChange={(e) => cambiar({ archivo: e.target.value })} />
      </label>
      <p className="ayuda">
        Por ejemplo ventas01.dbf. {carpeta && <>Se crea en {carpeta}</>}
      </p>
      <div className="fila-formulario" style={{ marginTop: '1.25rem' }}>
        <label className="campo">
          Tamaño inicial
          <input value={valor.tamano} onChange={(e) => cambiar({ tamano: e.target.value })} />
        </label>
      </div>
      <label className="opcion" style={{ marginTop: '0.75rem' }}>
        <input
          type="checkbox"
          checked={valor.autoextend}
          onChange={() => cambiar({ autoextend: !valor.autoextend })}
        />
        Crecer automáticamente cuando se llene (AUTOEXTEND)
      </label>
      {valor.autoextend && (
        <div className="fila-formulario">
          <label className="campo">
            Crecer de a
            <input value={valor.siguiente} onChange={(e) => cambiar({ siguiente: e.target.value })} />
          </label>
          <label className="campo">
            Tamaño máximo
            <input value={valor.maximo} onChange={(e) => cambiar({ maximo: e.target.value })} />
          </label>
        </div>
      )}
      <p className="ayuda">Los tamaños se escriben como 500K, 100M o 1G. El máximo también puede ser UNLIMITED.</p>
    </>
  )
}

function CrearTablespace({ credenciales, aviso, setAviso, ir }: PropsVista) {
  const [carpeta, setCarpeta] = useState('')
  const [nombre, setNombre] = useState('')
  const [tipo, setTipo] = useState('PERMANENT')
  const [archivo, setArchivo] = useState<Archivo>(ARCHIVO_INICIAL)

  useEffect(() => {
    void llamar<{ carpeta: string }>(credenciales, '/tablespaces').then((r) => {
      if (r.ok) setCarpeta(r.datos.carpeta)
      else setAviso(r.aviso)
    })
  }, [credenciales, setAviso])

  const crear = async () => {
    const r = await llamar<Mensaje>(credenciales, '/tablespaces', { nombre, tipo, ...archivo })
    if (r.ok) ir({ tipo: 'lista' }, { tipo: 'ok', textos: [r.datos.mensaje] })
    else setAviso(r.aviso)
  }

  return (
    <>
      <h1>Crear tablespace</h1>
      <p className="apoyo">El nombre se guarda en mayúsculas. Solo eliges el nombre del archivo, no su ruta.</p>

      <MostrarAviso aviso={aviso} />

      <div className="panel">
        <label className="campo">
          Nombre del tablespace
          <input value={nombre} onChange={(e) => setNombre(e.target.value)} />
        </label>
        <label className="campo">
          Tipo
          <select value={tipo} onChange={(e) => setTipo(e.target.value)}>
            <option value="PERMANENT">Permanente (tablas e índices)</option>
            <option value="TEMPORARY">Temporal (ordenamientos y consultas grandes)</option>
          </select>
        </label>
      </div>

      <div className="panel">
        <h2>Primer archivo de datos</h2>
        <CamposArchivo valor={archivo} onCambiar={setArchivo} carpeta={carpeta} />
      </div>

      <button type="button" className="accion" onClick={() => void crear()}>
        Crear tablespace
      </button>
    </>
  )
}

function DetalleTablespace({
  credenciales,
  tablespace,
  aviso,
  setAviso,
}: Omit<PropsVista, 'ir'> & { tablespace: string }) {
  const [detalle, setDetalle] = useState<Detalle | null>(null)
  const [nuevo, setNuevo] = useState<Archivo>({ ...ARCHIVO_INICIAL, tamano: '50M' })
  const [redimensionar, setRedimensionar] = useState({ id: '', tamano: '' })

  const base = `/tablespaces/${encodeURIComponent(tablespace)}`

  const cargar = useCallback(
    () =>
      llamar<Detalle>(credenciales, base).then((r) => {
        if (r.ok) setDetalle(r.datos)
        else setAviso(r.aviso)
      }),
    [credenciales, base, setAviso],
  )

  useEffect(() => {
    void cargar()
  }, [cargar])

  const operar = async (ruta: string, cuerpo: unknown) => {
    const r = await llamar<Mensaje>(credenciales, `${base}/${ruta}`, cuerpo)
    if (!r.ok) {
      setAviso(r.aviso)
      return false
    }
    await cargar()
    setAviso({ tipo: 'ok', textos: [r.datos.mensaje] })
    return true
  }

  const cambiarEstado = (estado: string) => void operar('estado', { estado, confirmar: true })

  return (
    <>
      <h1>Tablespace {tablespace}</h1>
      {detalle && (
        <p className="apoyo">
          {TIPOS[detalle.tipo] ?? detalle.tipo} · <EstadoTablespace estado={detalle.estado} /> · {detalle.usado_mb}{' '}
          de {detalle.tamano_mb} MB usados ({detalle.porcentaje_uso} %)
        </p>
      )}

      <MostrarAviso aviso={aviso} />

      {detalle && (
        <>
          <div className="panel">
            <h2>Estado</h2>
            {estadoEditable(detalle) ? (
              <div className="botones">
                {detalle.estado === 'OFFLINE' ? (
                  <button type="button" className="boton" onClick={() => cambiarEstado('ONLINE')}>
                    Poner ONLINE
                  </button>
                ) : (
                  <BotonConfirmar
                    etiqueta="Poner OFFLINE"
                    pregunta={`¿Poner ${tablespace} OFFLINE? Sus datos dejarán de estar disponibles.`}
                    onConfirmar={() => cambiarEstado('OFFLINE')}
                  />
                )}
                {detalle.estado === 'ONLINE' && (
                  <button type="button" className="boton" onClick={() => cambiarEstado('READ ONLY')}>
                    Solo lectura (READ ONLY)
                  </button>
                )}
                {detalle.estado === 'READ ONLY' && (
                  <button type="button" className="boton" onClick={() => cambiarEstado('READ WRITE')}>
                    Lectura y escritura (READ WRITE)
                  </button>
                )}
              </div>
            ) : (
              <p className="ayuda">
                El estado de los tablespaces SYSTEM, SYSAUX, temporales y de UNDO no se cambia desde aquí.
              </p>
            )}
          </div>

          <div className="panel">
            <h2>Archivos de datos</h2>
            <Tabla
              titulo="Archivos de datos"
              columnas={[
                { titulo: 'ID', valor: (d: Datafile) => d.id },
                { titulo: 'Archivo', valor: (d: Datafile) => <code className="sentencia">{d.archivo}</code> },
                { titulo: 'Tamaño (MB)', valor: (d: Datafile) => d.tamano_mb },
                {
                  titulo: 'AUTOEXTEND',
                  valor: (d: Datafile) => (d.autoextensible ? `Sí, hasta ${d.maximo_mb} MB` : 'No'),
                },
                { titulo: 'Estado', valor: (d: Datafile) => d.estado },
                {
                  titulo: 'Crecimiento',
                  valor: (d: Datafile) => (
                    <button
                      type="button"
                      className="boton"
                      aria-label={`${d.autoextensible ? 'Desactivar' : 'Activar'} AUTOEXTEND del archivo ${d.id}`}
                      onClick={() => void operar(`archivos/${d.id}/autoextend`, { autoextend: !d.autoextensible })}
                    >
                      {d.autoextensible ? 'Desactivar AUTOEXTEND' : 'Activar AUTOEXTEND'}
                    </button>
                  ),
                },
              ]}
              filas={detalle.datafiles}
              clave={(d) => String(d.id)}
              vacio="El tablespace no tiene archivos"
            />
            <p className="ayuda">Al activar AUTOEXTEND el archivo crece de a 10M sin límite.</p>

            <div className="fila-formulario" style={{ marginTop: '1.25rem' }}>
              <label className="campo">
                Archivo a redimensionar
                <select
                  value={redimensionar.id}
                  onChange={(e) => setRedimensionar({ ...redimensionar, id: e.target.value })}
                >
                  <option value="">Selecciona un archivo</option>
                  {detalle.datafiles.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.id} · {d.archivo.slice(d.archivo.lastIndexOf('/') + 1)} ({d.tamano_mb} MB)
                    </option>
                  ))}
                </select>
              </label>
              <label className="campo">
                Nuevo tamaño
                <input
                  value={redimensionar.tamano}
                  onChange={(e) => setRedimensionar({ ...redimensionar, tamano: e.target.value })}
                />
              </label>
              <button
                type="button"
                className="boton principal"
                disabled={!redimensionar.id}
                onClick={async () => {
                  const listo = await operar(`archivos/${redimensionar.id}/redimensionar`, {
                    tamano: redimensionar.tamano,
                  })
                  if (listo) setRedimensionar({ id: '', tamano: '' })
                }}
              >
                Redimensionar
              </button>
            </div>
          </div>

          {!detalle.bigfile && (
            <div className="panel">
              <h2>Agregar archivo</h2>
              <CamposArchivo
                valor={nuevo}
                onCambiar={setNuevo}
                carpeta={detalle.datafiles[0] ? carpetaDe(detalle.datafiles[0].archivo) : ''}
              />
              <div className="botones" style={{ marginTop: '1.25rem' }}>
                <button
                  type="button"
                  className="boton principal"
                  onClick={async () => {
                    if (await operar('archivos', nuevo)) setNuevo({ ...ARCHIVO_INICIAL, tamano: '50M' })
                  }}
                >
                  Agregar archivo
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </>
  )
}
