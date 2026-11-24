import React from 'react';
import { MOCK_HOGAR_ID } from '../api/devMocks';
import { ConfigurarTarifaScreen } from '../screens/ConfigurarTarifaScreen';

export default function Page() {
  // TODO(pendiente: hogarId): vendrá del estado de sesión/hogar; MOCK_HOGAR_ID es null fuera del modo de ejemplo.
  return <ConfigurarTarifaScreen hogarId={MOCK_HOGAR_ID} />;
}
