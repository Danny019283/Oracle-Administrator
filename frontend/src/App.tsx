import { useState } from 'react'
import { Menu, type TipoRespaldo } from './menu/Menu'
import { RespaldoTablas, type Credenciales } from './respaldos/RespaldoTablas'

// Provisional hasta que exista la pantalla de ingreso a Oracle.
const CREDENCIALES: Credenciales = {
  usuario: import.meta.env.VITE_ORACLE_USER ?? '',
  password: import.meta.env.VITE_ORACLE_PASSWORD ?? '',
  servicio: import.meta.env.VITE_ORACLE_SERVICE ?? '',
}

function App() {
  const [respaldo, setRespaldo] = useState<TipoRespaldo | null>(null)

  return (
    <>
      <Menu onElegirRespaldo={setRespaldo} />
      {respaldo === 'tablas' && <RespaldoTablas credenciales={CREDENCIALES} />}
    </>
  )
}

export default App
