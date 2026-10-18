import { useState } from 'react'
import { MenuPrincipal, MenuRespaldos } from './menu/Menu'
import { RespaldoTablas, type Credenciales } from './respaldos/RespaldoTablas'

// Provisional hasta que exista la pantalla de ingreso a Oracle.
const CREDENCIALES: Credenciales = {
  usuario: import.meta.env.VITE_ORACLE_USER ?? '',
  password: import.meta.env.VITE_ORACLE_PASSWORD ?? '',
  servicio: import.meta.env.VITE_ORACLE_SERVICE ?? '',
}

type Vista = 'principal' | 'respaldos' | 'tablas'

function App() {
  const [vista, setVista] = useState<Vista>('principal')

  if (vista === 'tablas') {
    return (
      <>
        <button type="button" onClick={() => setVista('respaldos')}>
          Volver
        </button>
        <RespaldoTablas credenciales={CREDENCIALES} />
      </>
    )
  }

  if (vista === 'respaldos') {
    return (
      <MenuRespaldos
        onElegirRespaldo={(tipo) => tipo === 'tablas' && setVista('tablas')}
        onVolver={() => setVista('principal')}
      />
    )
  }

  return <MenuPrincipal onAbrirRespaldos={() => setVista('respaldos')} />
}

export default App
