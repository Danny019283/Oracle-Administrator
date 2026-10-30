import { useCallback, useEffect, useState } from 'react'
import '../admin/admin.css'
import { llamar, type Aviso } from '../admin/api'
import { BotonConfirmar, MostrarAviso, Tabla } from '../admin/Avisos'
import { ArchivosRespaldo } from './ArchivosRespaldo'

type Directorio = { nombre: string; ruta: string }

type Usuario = { usuario: string }

type Mensaje = { mensaje: string }

export function Directorios({ token }: { token: string }) {
  const [directorios, setDirectorios] = useState<Directorio[]>([])
  const [ejemplos, setEjemplos] = useState<string[]>([])
  const [aviso, setAviso] = useState<Aviso | null>(null)
  const [creando, setCreando] = useState(false)
  const [editando, setEditando] = useState(false)
  const [nombre, setNombre] = useState('')
  const [ruta, setRuta] = useState('')
  const [schema, setSchema] = useState('')
  const [usuarios, setUsuarios] = useState<Usuario[]>([])

  const cargar = useCallback(
    () =>
      llamar<{ directorios: Directorio[]; ejemplos_ruta: string[] }>(token, '/directorios').then((r) => {
        if (r.ok) {
          setDirectorios(r.datos.directorios)
          setEjemplos(r.datos.ejemplos_ruta)
        } else setAviso(r.aviso)
      }),
    [token],
  )

  useEffect(() => {
    void cargar()
  }, [cargar])

  const abrirCrear = () => {
    setAviso(null)
    setNombre('')
    setRuta('')
    setSchema('')
    setUsuarios([])
    setCreando(true)
    void llamar<{ usuarios: Usuario[] }>(token, '/seguridad/usuarios').then((r) => {
      if (r.ok) setUsuarios(r.datos.usuarios)
      else setAviso(r.aviso)
    })
  }

  const abrirEditar = (d: Directorio) => {
    setAviso(null)
    setNombre(d.nombre)
    setRuta(d.ruta)
    setEditando(true)
  }

  // Crear y editar comparten formulario: editar solo envía la ruta y el nombre queda de solo lectura.
  // El schema solo se envía al crear y únicamente si se eligió un usuario (la opción vacía es «Sin schema»).
  const enviar = async () => {
    const r = editando
      ? await llamar<Mensaje>(token, `/directorios/${encodeURIComponent(nombre)}`, { ruta }, 'PUT')
      : await llamar<Mensaje>(token, '/directorios', { nombre, ruta, ...(schema && { schema }) })
    if (!r.ok) return setAviso(r.aviso)
    await cargar()
    setCreando(false)
    setEditando(false)
    setAviso({ tipo: 'ok', textos: [r.datos.mensaje] })
  }

  const eliminar = async (d: Directorio) => {
    const r = await llamar<Mensaje>(token, `/directorios/${encodeURIComponent(d.nombre)}`, undefined, 'DELETE')
    if (!r.ok) return setAviso(r.aviso)
    await cargar()
    setAviso({ tipo: 'ok', textos: [r.datos.mensaje] })
  }

  if (creando || editando) {
    return (
      <section className="vista">
        <button
          type="button"
          className="volver"
          onClick={() => {
            setAviso(null)
            setCreando(false)
            setEditando(false)
          }}
        >
          ← Lista de directorios
        </button>
        <h1>{editando ? 'Editar directorio' : 'Crear directorio'}</h1>
        <p className="apoyo">El nombre se guarda en mayúsculas. La carpeta debe existir y Oracle debe poder escribir en ella.</p>

        <MostrarAviso aviso={aviso} />

        <div className="panel">
          <label className="campo">
            Nombre del directorio
            <input value={nombre} readOnly={editando} onChange={(e) => setNombre(e.target.value)} />
          </label>
          <label className="campo">
            Ruta de la carpeta
            <input value={ruta} onChange={(e) => setRuta(e.target.value)} />
          </label>
          <p className="ayuda">Por ejemplo {ejemplos.join(' o ')}</p>
          {!editando && (
            <label className="campo">
              Schema (opcional)
              <select value={schema} onChange={(e) => setSchema(e.target.value)}>
                <option value="">Sin schema</option>
                {usuarios.map((u) => (
                  <option key={u.usuario} value={u.usuario}>
                    {u.usuario}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>

        <button type="button" className="accion" onClick={() => void enviar()}>
          {editando ? 'Guardar' : 'Crear'}
        </button>
      </section>
    )
  }

  return (
    <section className="vista">
      <div className="encabezado-modulo">
        <div>
          <h1>Administración de archivos de respaldos y directorios</h1>
          <p className="apoyo">Consulta los directorios de Oracle donde se guardan los respaldos.</p>
        </div>
        <button type="button" className="boton principal" onClick={abrirCrear}>
          Crear directorio
        </button>
      </div>

      <MostrarAviso aviso={aviso} />

      <div className="panel">
        <h2>Directorios</h2>
        <Tabla
          titulo="Directorios"
          columnas={[
            { titulo: 'Nombre', valor: (d: Directorio) => d.nombre },
            { titulo: 'Ruta', valor: (d: Directorio) => d.ruta },
            {
              titulo: 'Acciones',
              valor: (d: Directorio) => (
                <>
                  <button type="button" className="boton" aria-label={`Editar ${d.nombre}`} onClick={() => abrirEditar(d)}>
                    Editar
                  </button>
                  <BotonConfirmar
                    etiqueta={`Eliminar ${d.nombre}`}
                    pregunta={`¿Eliminar el directorio ${d.nombre}? Los archivos de la carpeta no se borran.`}
                    onConfirmar={() => void eliminar(d)}
                  />
                </>
              ),
            },
          ]}
          filas={directorios}
          clave={(d) => d.nombre}
          vacio="No hay directorios para mostrar"
        />
      </div>

      <ArchivosRespaldo token={token} />
    </section>
  )
}
