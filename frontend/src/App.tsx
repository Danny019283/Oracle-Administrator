import { useState } from 'react'
import { Menu, type TipoRespaldo } from './menu/Menu'

function App() {
  const [respaldo, setRespaldo] = useState<TipoRespaldo | null>(null)

  return (
    <>
      <Menu onElegirRespaldo={setRespaldo} />
      {respaldo === 'tablas' && <h1>Respaldar tablas</h1>}
    </>
  )
}

export default App
